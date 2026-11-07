"""Concept floor-plan generator (row-zoning solver).

Builds a buildable rectangle from Tamil Nadu setbacks, then fills it in rows from the road:
  front row  : parking + hall (or family lounge on upper floors)
  middle row : dining, kitchen, pooja, common toilet, staircase (staircase pinned on every floor)
  rear rows  : bedrooms with attached toilets
Rooms are ordered inside each row to follow common Vastu preferences where the facing allows
(kitchen SE, master bedroom SW, pooja NE, staircase S/W). Sizes respect minimum room sizes;
if rooms cannot fit, the generator raises LayoutError with a clear question for the user.
All dimensions in feet. Coordinates: origin = plot front-left corner, x along the road, y away from it.
"""
from __future__ import annotations

import itertools
import math

from .setbacks import tn_setbacks

# desired w, desired d, min w, min d  (ft)
SIZES = {
    "hall": (12, 13, 9, 10), "lounge": (11, 11, 8, 9), "kitchen": (8, 10, 6.5, 7.5), "dining": (9, 10, 7, 8),
    "bedroom": (11, 11, 9, 8.5), "master": (12, 12, 10, 9.5), "toilet": (5, 8, 4, 6),
    "common_toilet": (5, 7, 4, 6), "pooja": (4.5, 5, 3.5, 4), "stair": (7.5, 11, 7, 10.5),
    "parking_car": (9.5, 16, 8.5, 15), "parking_bike": (6, 8, 5, 6.5), "passage": (4, 6, 3, 3),
    "terrace": (5, 5, 4, 4), "stilt_open": (4, 6, 3, 3),
}
NAMES = {"hall": "Living / Hall", "lounge": "Family Lounge", "kitchen": "Kitchen", "dining": "Dining",
         "bedroom": "Bedroom", "master": "Master Bedroom", "toilet": "Toilet", "common_toilet": "Common Toilet",
         "pooja": "Pooja", "stair": "Staircase", "parking_car": "Car Parking", "parking_bike": "Bike Parking",
         "passage": "Passage / Open", "dress": "Dress", "parking": "Parking", "terrace": "Open Terrace", "stilt_open": "Open Stilt Area"}
# Vastu-style direction preferences as (east, north) vectors
PREF = {"kitchen": (1, -1), "pooja": (1, 1), "master": (-1, -1), "stair": (-0.6, -0.6),
        "common_toilet": (-0.4, 0.4), "hall": (0.3, 0.3), "parking_car": (0.2, 0.2)}

FACING_UP = {  # direction (E, N) pointing AWAY from the road
    "east": (-1, 0), "west": (1, 0), "north": (0, -1), "south": (0, 1),
    "north-east": (-0.7071, -0.7071), "north-west": (0.7071, -0.7071),
    "south-east": (-0.7071, 0.7071), "south-west": (0.7071, 0.7071),
}


class LayoutError(ValueError):
    def __init__(self, questions: list[str], suggestions: list[dict] | None = None):
        super().__init__("; ".join(questions))
        self.questions = questions
        self.suggestions = suggestions or []


def compass(facing: str) -> dict:
    up = FACING_UP.get(facing or "east", FACING_UP["east"])
    right = (up[1], -up[0])  # rotate clockwise
    return {"up": up, "right": right}


def r2(v: float) -> float:
    return round(v * 4) / 4  # snap to 3 inches


class Cell:
    def __init__(self, kind: str, fixed_w: float | None = None, attached: bool = False):
        self.kind = kind
        self.attached = attached
        dw, dd, mw, md = SIZES[kind]
        if attached:
            tw = SIZES["toilet"]
            dw, mw = dw + tw[0], mw + tw[2]
        self.dw, self.dd, self.mw, self.md = dw, dd, mw, md
        self.fixed_w = fixed_w
        self.x = self.w = 0.0


def level_items(lv: dict, multi: bool) -> tuple[list[Cell], list[Cell], Cell | None]:
    """Front items, other items (in priority order) and the staircase cell."""
    stair = Cell("stair") if multi else None
    if lv.get("stilt"):
        return [Cell("parking_car"), Cell("parking_car"), Cell("parking_bike")], [], stair
    front, rest = [], []
    if lv.get("parking_car"):
        front.append(Cell("parking_car"))
    if lv.get("parking_bike"):
        front.append(Cell("parking_bike"))
    if lv.get("hall"):
        h = Cell("hall")
        if lv.get("_dining_in_hall"):
            h.dw += 3
        front.append(h)
    elif lv.get("lounge"):
        front.append(Cell("lounge"))
    if lv.get("kitchen"):
        rest.append(Cell("kitchen"))
    if lv.get("dining") and not lv.get("_dining_in_hall"):
        rest.append(Cell("dining"))
    if lv.get("pooja"):
        rest.append(Cell("pooja"))
    for _ in range(int(lv.get("common_toilets") or 0)):
        rest.append(Cell("common_toilet"))
    beds = int(lv.get("bedrooms") or 0)
    att = int(lv.get("attached_toilets") or 0)
    for i in range(beds):
        rest.append(Cell("master" if i == 0 else "bedroom", attached=i < att))
    if not front and rest:
        k = next((j for j, c in enumerate(rest) if c.kind in ("master", "bedroom")), 0)
        front.append(rest.pop(k))
    return front, rest, stair


def pack_rows(front: list[Cell], rest: list[Cell], stair: Cell | None, bw: float, tol: float = 1.08,
              stilt: bool = False, relax: bool = False, upper: bool = False, spine_w: float = 0.0) -> list[list[Cell]]:
    """Greedy row packing from the road side.

    Multi-floor plans keep the staircase in the FRONT row at an edge, so it stacks on every floor and
    upper floors only need the same front-row depth. Only front items (parking, hall/lounge) and bedrooms
    may sit in the front row; kitchen, dining, pooja and toilets start from the second row.
    tol = how far the desired widths of a row may exceed the building width (minimum widths must always fit).
    A stilt floor keeps one row of vehicles; whatever does not fit is left out (open parking behind).
    """
    rows: list[list[Cell]] = [[stair] if stair else []]

    def fits(row, c):
        cap = bw if row is rows[0] else bw - spine_w  # 1.17: back rows leave room for the access passage
        dw = sum(x.fixed_w or x.dw for x in row) + (c.fixed_w or c.dw)
        mw = sum(x.fixed_w or x.mw for x in row) + (c.fixed_w or c.mw)
        return mw <= cap and dw <= cap * tol

    ptr = 0
    for c in front:
        if stilt:
            if fits(rows[0], c):
                rows[0].append(c)
            continue
        while ptr < len(rows) and rows[ptr] and not fits(rows[ptr], c):
            ptr += 1
        if ptr >= len(rows):
            rows.append([])
        rows[ptr].append(c)
    for c in rest:
        p = ptr
        if c.kind not in ("bedroom", "master") and not (relax and (c.kind != "common_toilet" or upper)):
            p = max(p, 1)
        while p < len(rows) and not fits(rows[p], c):
            p += 1
        while p >= len(rows):
            rows.append([])
        rows[p].append(c)
    rows = [r for r in rows if r]
    # a row with only fixed-width cells (e.g. staircase) gets a passage / lobby to fill it
    for row in rows:
        if all(c.fixed_w for c in row) and sum(c.fixed_w for c in row) < bw - 0.1:
            row.append(Cell("passage"))
    return rows


def _orderings(rest: list[Cell]) -> list[list[Cell]]:
    """A few sensible item orders to try – the packer is greedy, so order changes the result."""
    beds = [c for c in rest if c.kind in ("bedroom", "master")]
    other = [c for c in rest if c.kind not in ("bedroom", "master")]
    small = sorted(other, key=lambda c: c.mw)
    out = [rest, beds + other, other[:1] + beds + other[1:], small + beds, beds[:1] + small + beds[1:]]
    seen, uniq = set(), []
    for o in out:
        key = tuple(id(c) for c in o)
        if key not in seen:
            seen.add(key)
            uniq.append(o)
    return uniq


def order_row(row: list[Cell], y0: float, d: float, bw: float, bd: float, comp: dict, pinned_stair: str | None):
    """Try permutations; keep the one with the best direction score. Returns ordered list."""
    c = order_candidates(row, y0, d, bw, bd, comp, pinned_stair, 1)
    return c[0] if c else row


def order_candidates(row: list[Cell], y0: float, d: float, bw: float, bd: float, comp: dict, pinned_stair: str | None,
                     keep: int = 40) -> list[list[Cell]]:
    """1.17: the best `keep` orders by direction score (the layout then picks the one that keeps rooms reachable)."""
    scored = []
    perms = itertools.permutations(row) if len(row) <= 6 else [row]
    for p in perms:
        if pinned_stair and any(c.kind == "stair" for c in p):
            idx = [i for i, c in enumerate(p) if c.kind == "stair"][0]
            last = len(p) - 1
            if ((pinned_stair == "left" and idx != 0) or (pinned_stair == "right" and idx != last)
                    or (pinned_stair == "edge" and idx not in (0, last))):
                continue
        widths = size_row(list(p), bw)
        x, s = 0.0, 0.0
        for c, w in zip(p, widths):
            cx, cy = x + w / 2, y0 + d / 2
            xn, yn = (cx - bw / 2) / (bw / 2), (cy - bd / 2) / (bd / 2)
            e = xn * comp["right"][0] + yn * comp["up"][0]
            n = xn * comp["right"][1] + yn * comp["up"][1]
            pv = PREF.get(c.kind)
            if pv:
                s += pv[0] * e + pv[1] * n
            if c.kind in ("bedroom", "master", "kitchen"):
                s += 1.2 * abs(xn)  # rooms that need windows prefer the outer walls
            if c.kind == "parking_car":
                s += 0.8 * abs(xn)
            x += w
        scored.append((s, list(p)))
    scored.sort(key=lambda t: -t[0])
    out, seen = [], set()
    for sc, p in scored:
        key = tuple((c.kind, c.attached) for c in p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= keep:
            break
    return out


def size_row(row: list[Cell], bw: float) -> list[float]:
    """Widths: fixed cells keep theirs; others get their minimum first, then a share of the rest."""
    fixed = sum(c.fixed_w for c in row if c.fixed_w)
    flex = [c for c in row if not c.fixed_w]
    if not flex:
        return [c.fixed_w for c in row]
    avail = bw - fixed
    total_dw = sum(c.dw for c in flex)
    total_mw = sum(c.mw for c in flex)
    if avail >= total_dw:
        w = {id(c): avail * c.dw / total_dw for c in flex}
    elif avail <= total_mw:
        w = {id(c): avail * c.mw / total_mw for c in flex}
    else:
        span = total_dw - total_mw
        k = (avail - total_mw) / span if span else 0
        w = {id(c): c.mw + (c.dw - c.mw) * k for c in flex}
    return [c.fixed_w if c.fixed_w else w[id(c)] for c in row]


def _depths(rows, bd, template, cap_front=False):
    """Depth for each row, or (None, need) when the minimum depths do not fit."""
    des = [max(c.dd for c in r) for r in rows]
    mins = [max(c.md for c in r) for r in rows]
    fixed_idx = {0: template["front_d"]} if template and len(rows) > 1 else {}
    depths = [0.0] * len(rows)
    remaining, free = bd, []
    for i in range(len(rows)):
        if i in fixed_idx:
            depths[i] = fixed_idx[i]
            remaining -= fixed_idx[i]
        else:
            free.append(i)
    need = sum(mins[i] for i in free) + sum(fixed_idx.values())
    if free:
        dsum = sum(des[i] for i in free)
        msum = sum(mins[i] for i in free)
        if remaining < msum - 0.01:
            return None, need
        if remaining >= dsum:
            extra = remaining - dsum
            grow = [i for i in free if not (cap_front and i == 0 and len(free) > 1)]
            gsum = sum(des[i] for i in grow)
            for i in free:
                depths[i] = des[i] + (extra * des[i] / gsum if i in grow else 0)
        else:  # shrink towards minimums proportionally
            span = dsum - msum
            k = (dsum - remaining) / span if span else 0
            for i in free:
                depths[i] = des[i] - (des[i] - mins[i]) * k
    elif abs(remaining) > 0.5:
        rows.append([Cell("passage")])
        depths.append(remaining)
    return depths, need


def build_level(lv: dict, bw: float, bd: float, comp: dict, multi: bool, template: dict | None) -> tuple[list[dict], dict]:
    """1.17: lay the floor out; if a room cannot be reached without passing through another room, try again with
    an access passage (spine) along one side. The first layout where every room is reachable wins."""
    first = _build_level(lv, bw, bd, comp, multi, template)
    if lv.get("stilt"):
        return first
    best, best_cost = first, _unreached_count(first[0], lv)
    if best_cost == 0:
        return first
    carved = _carve_passage(first[0], lv, bw, bd)
    if carved:
        c = _unreached_count(carved, lv)
        if c < best_cost:
            best, best_cost = (carved, first[1]), c
    sides = ([template["stair_side"]] if template and template.get("stair_side") in ("left", "right") else []) + ["left", "right"]
    global SPINE
    for sw in (3.5, 3.0):
        if best_cost == 0:
            break
        SPINE = sw
        try:
            for side in dict.fromkeys(sides):
                try:
                    cand = _build_level(lv, bw, bd, comp, multi, template, side)
                except LayoutError:
                    continue
                c = _unreached_count(cand[0], lv)
                if c < best_cost:
                    best, best_cost = cand, c
                    if template:
                        best[1]["stair_side"] = template.get("stair_side")
                if best_cost == 0:
                    break
        finally:
            SPINE = 3.5
    if best_cost >= 10:  # 1.17: never hand out a plan with a room you cannot walk into
        from .geometry import level_openings, reachable
        tmp = {"name": lv.get("name", ""), "rooms": best[0], "stilt": False}
        li = 0 if lv.get("hall") else 1
        miss = reachable(tmp, level_openings(tmp, li, 0)[0], None, li)[1]
        names = sorted({r["name"] for r in best[0] if r["id"] in miss})
        raise LayoutError([f"{lv['name']}: {', '.join(names)} cannot be reached without walking through another room "
                           f"on this plot."])
    return best


def _build_level(lv: dict, bw: float, bd: float, comp: dict, multi: bool, template: dict | None,
                 spine: str | None = None) -> tuple[list[dict], dict]:
    stair_w = r2(SIZES["stair"][0])
    best_need, rows, depths = 1e9, None, None
    stilt = bool(lv.get("stilt"))
    for tol, relax in ((1.08, False), (1.2, False), (1.4, False), (1.4, True)):
        front0, rest0, _s = level_items(lv, multi)
        for order in _orderings(rest0):
            front, rest, stair = level_items(lv, multi)  # fresh cells per attempt
            idx = {id(c): k for k, c in enumerate(rest0)}
            rest = [rest[idx[id(c)]] for c in order]
            if stair:
                stair.fixed_w = template["stair_w"] if template else stair_w
            r = pack_rows(front, rest, stair, bw, tol, stilt, relax, upper=not lv.get("hall"), spine_w=SPINE if spine else 0.0)
            if stilt:  # vehicles in one row; the rest of the stilt floor stays open
                dd = max(c.dd for c in r[0])
                if bd - dd > 0.5:
                    r.append([Cell("passage")])
                d, need = ([dd, bd - dd] if bd - dd > 0.5 else [bd]), dd
            else:
                d, need = _depths(r, bd, template, cap_front=multi and not template)
            if d is not None:
                rows, depths = r, d
                break
            best_need = min(best_need, need)
        if rows:
            break
    if rows is None:
        raise LayoutError([f"{lv['name']}: these rooms need about {best_need:.0f} ft depth but only {bd:.1f} ft is "
                           f"available after setbacks."])
    if stilt:
        front_all, _, _ = level_items(lv, multi)
        placed = sum(1 for c in rows[0] if c.kind.startswith("parking"))
        if placed < len(front_all):
            lv["_stilt_note"] = f"{lv['name']}: {placed} parking bay(s) under the building; the rest is open stilt area."
    if template and not stilt:
        # upper floors with few rooms: keep rooms near their desired size, the rest becomes open terrace
        extra = 0.0
        for i in range(1, len(rows)):
            des_i = max(c.dd for c in rows[i]) * 1.15
            if depths[i] > des_i:
                extra += depths[i] - des_i
                depths[i] = des_i
        if extra >= 4:
            rows.append([Cell("terrace")])
            depths.append(extra)
        elif extra > 0:
            depths[-1] += extra
        for i in range(1, len(rows)):
            row = rows[i]
            if any(c.kind == "terrace" for c in row):
                continue
            dws = sum(c.fixed_w or c.dw for c in row)
            spare = bw - dws * 1.15
            if spare >= 4.5:
                t = Cell("terrace")
                t.fixed_w = r2(spare)
                row.append(t)
    depths = [r2(x) for x in depths]
    depths[-1] = r2(bd - sum(depths[:-1]))

    if stilt:
        for row in rows:
            for c in row:
                if c.kind == "passage":
                    c.kind = "stilt_open"
    def place(spine: str | None):
        """Lay the rows out. spine = 'left' / 'right': a 3.5 ft passage runs from the front row to the back along
        that side (1.17), so every back room opens into a common passage instead of through another room."""
        rooms: list[dict] = []
        y = 0.0
        info = {"front_d": depths[0], "mid_d": depths[1] if len(depths) > 1 else 0, "stair_w": stair_w, "stair_side": None}
        pinned = template["stair_side"] if template else ("edge" if multi else None)
        counters: dict[str, int] = {}
        for ri, (row, d) in enumerate(zip(rows, depths)):
            use = spine and ri >= 1 and not all(c.kind in ("terrace",) for c in row)
            avail = bw - SPINE if use else bw
            x0 = SPINE if use and spine == "left" else 0.0
            if ri == 0 and spine:
                row = _pin_edge(order_row(row, y, d, bw, bd, comp, pinned), spine)
            elif ri == 0 or stilt:
                row = order_row(row, y, d, avail, bd, comp, pinned)
            else:  # 1.17: among the good orders, take the one that leaves the fewest rooms without access
                cands = order_candidates(row, y, d, avail, bd, comp, pinned)
                best_row, best_bad = cands[0] if cands else row, None
                for cand in cands:
                    trial = list(rooms)
                    ws_ = [r2(w) for w in size_row(cand, avail)]
                    ws_[-1] = r2(avail - sum(ws_[:-1]))
                    xx, cnt = x0, dict(counters)
                    if use:
                        trial.append({"id": f"passage_s{ri}", "type": "passage", "name": "Passage",
                                      "x": 0.0 if spine == "left" else r2(bw - SPINE), "y": r2(y), "w": SPINE, "d": r2(d)})
                    for c, w in zip(cand, ws_):
                        add_cell(trial, c, r2(xx), y, w, d, cnt)
                        xx += w
                    bad = _unreached_count(trial, lv)
                    if best_bad is None or bad < best_bad:
                        best_row, best_bad = cand, bad
                    if bad == 0:
                        break
                row = best_row
            widths = [r2(w) for w in size_row(row, avail)]
            widths[-1] = r2(avail - sum(widths[:-1]))
            x = x0
            if use:
                rooms.append({"id": f"passage_s{ri}", "type": "passage", "name": "Passage",
                              "x": 0.0 if spine == "left" else r2(bw - SPINE), "y": r2(y), "w": SPINE, "d": r2(d)})
            for c, w in zip(row, widths):
                if c.mw - w > 0.6:
                    raise LayoutError([f"{lv['name']}: {NAMES[c.kind]} would be only {w:.1f} ft wide (minimum "
                                       f"{c.mw:g} ft)."])
                if c.kind in ("bedroom", "master"):
                    net_w = w - (SIZES["toilet"][0] if c.attached else 0)
                    if net_w * d < (100 if c.kind == "master" else 80) - 0.5:
                        raise LayoutError([f"{lv['name']}: {NAMES[c.kind]} would be only {net_w * d:.0f} sq ft "
                                           f"(minimum {100 if c.kind == 'master' else 80} sq ft)."])
                if c.kind == "stair":
                    info["stair_side"] = "left" if x < 0.1 else ("right" if abs(x + w - bw) < 0.1 else "middle")
                add_cell(rooms, c, r2(x), y, w, d, counters)
                x += w
            y += d
        return rooms, info

    return place(spine)


SPINE = 3.5  # ft – width of the access passage (1.17)
ENTRY = ("hall", "lounge", "stair", "passage", "dining")
MIN_W = {"bedroom": 8.5, "kitchen": 6.5, "dining": 7.0, "toilet": 4.0, "common_toilet": 4.0, "pooja": 3.5,
         "dress": 3.0, "passage": 3.0, "lounge": 8.0, "hall": 9.0, "utility": 4.0, "store": 4.0, "terrace": 3.0}


MIN_D = {"bedroom": 8.0, "kitchen": 7.0, "dining": 7.0, "toilet": 5.0, "common_toilet": 5.0, "pooja": 3.5,
         "dress": 3.0, "passage": 3.0, "lounge": 8.0, "hall": 9.0, "utility": 4.0, "store": 4.0, "terrace": 3.0}


def _cut(rooms: list[dict], x0: float, y0: float, x1: float, y1: float) -> list[dict] | None:
    """Cut the rectangle out of the rooms it touches – only from a room's side (never splitting a room in two) and
    never below a room's minimum size. Returns the new rooms incl. the passage, or None."""
    new = []
    for r in rooms:
        rx1, ry1 = r["x"] + r["w"], r["y"] + r["d"]
        ox, oy = min(x1, rx1) - max(x0, r["x"]), min(y1, ry1) - max(y0, r["y"])
        if ox <= 0.01 or oy <= 0.01:
            new.append(dict(r)); continue
        if r["type"] in ("hall", "lounge", "stair", "parking", "terrace") or r["id"].startswith("passage_c"):
            return None  # never cut into the entry rooms / an earlier passage
        q = dict(r)
        full_x, full_y = ox >= r["w"] - 0.01, oy >= r["d"] - 0.01
        if full_x and full_y:
            if r["type"] == "passage":
                continue  # an old small passage simply becomes part of the new one
            return None
        if full_y:  # vertical strip through the room
            if x0 <= r["x"] + 0.01:
                q["x"], q["w"] = round(x1, 2), round(rx1 - x1, 2)
            elif x1 >= rx1 - 0.01:
                q["w"] = round(x0 - r["x"], 2)
            else:
                return None
        elif full_x:  # horizontal strip through the room
            if y0 <= r["y"] + 0.01:
                q["y"], q["d"] = round(y1, 2), round(ry1 - y1, 2)
            elif y1 >= ry1 - 0.01:
                q["d"] = round(y0 - r["y"], 2)
            else:
                return None
        else:
            return None  # a corner bite – not allowed
        if q["w"] < MIN_W.get(q["type"], 3.0) - 0.01 or q["d"] < MIN_D.get(q["type"], 3.0) - 0.01 \
                or (q["type"] == "bedroom" and q["w"] * q["d"] < 80 - 0.5):
            return None
        new.append(q)
    return new


def _carve_passage(rooms: list[dict], lv: dict, bw: float, bd: float) -> list[dict] | None:
    """1.17: when a room can only be reached through another room, cut a 3½ ft (or 3 ft) passage out of the side of
    the back rooms – vertical along the rooms, or across a row – starting from a room you can already reach.
    Up to three passages, each one only if it really gives access. Returns the new room list, or None."""
    from .geometry import level_openings, reachable
    cur, cost, k = rooms, _unreached_count(rooms, lv), 0
    while cost > 0 and k < 3:
        tmp = {"name": lv.get("name", ""), "rooms": cur, "stilt": False}
        li = 0 if lv.get("hall") else 1
        seen = reachable(tmp, level_openings(tmp, li, 0)[0], None, li)[0]
        entries = [r for r in cur if r["id"] in seen and r["type"] in ("hall", "lounge", "stair", "dining", "passage")]
        xs = sorted({round(v, 2) for r in cur for v in (r["x"], r["x"] + r["w"])})
        ys = sorted({round(v, 2) for r in cur for v in (r["y"], r["y"] + r["d"])})
        cands = []
        for width in (SPINE, 3.0):
            for e in entries:  # vertical: from the bottom of a reachable room to the back
                yb = e["y"] + e["d"]
                if yb > bd - 4:
                    continue
                for x0 in {v for x in xs for v in (x, x - width)}:
                    if x0 < -0.01 or x0 + width > bw + 0.01:
                        continue
                    if min(x0 + width, e["x"] + e["w"]) - max(x0, e["x"]) < width - 0.01:
                        continue
                    for yend in [y for y in ys if y > yb + 4] or [bd]:
                        cands.append((x0, yb, x0 + width, yend))
            for y in ys:  # across: along the top of a row, full width or from a reachable passage to one side
                if y < 0.01 or y + width > bd - 3:
                    continue
                for xa, xb in [(0.0, bw)] + [(e["x"], bw) for e in entries] + [(0.0, e["x"] + e["w"]) for e in entries]:
                    if xb - xa >= 6:
                        cands.append((xa, y, xb, y + width))
        best = None
        for x0, y0, x1, y1 in set(cands):
            new = _cut(cur, x0, y0, x1, y1)
            if new is None:
                continue
            k_id = f"passage_c{k + 1}"
            new.append({"id": k_id, "type": "passage", "name": "Passage", "x": round(x0, 2), "y": round(y0, 2),
                        "w": round(x1 - x0, 2), "d": round(y1 - y0, 2)})
            c = _unreached_count(new, lv)
            area = (x1 - x0) * (y1 - y0)
            if c < cost and (best is None or (c, area) < (best[0], best[2])):
                best = (c, new, area)
        if not best:
            break
        cost, cur, _ = best
        k += 1
    return cur if cur is not rooms else None


def _pin_edge(row: list, side: str) -> list:
    """Front row: put the hall / stair (where the passage starts) at the spine side."""
    k = next((i for i, c in enumerate(row) if c.kind == "stair"), None)
    if k is None:
        k = next((i for i, c in enumerate(row) if c.kind in ENTRY), None)
    if k is None:
        return row
    row = list(row)
    c = row.pop(k)
    return [c] + row if side == "left" else row + [c]


def _unreached_count(rooms: list[dict], lv: dict) -> int:
    """Layout access cost: a room you cannot reach = 10, a bedroom / pooja that opens only into the kitchen = 3."""
    from .geometry import level_openings, reachable
    tmp = {"name": lv.get("name", ""), "rooms": rooms, "stilt": bool(lv.get("stilt"))}
    li = 0 if lv.get("hall") else 1
    ops, _ = level_openings(tmp, li, 0)
    by = {r["id"]: r for r in rooms}
    cost = 10 * len(reachable(tmp, ops, None, li)[1])
    for o in ops:
        if o["type"] in ("door", "pooja_door") and by.get(o["room"], {}).get("type") in ("bedroom", "pooja"):
            r = by[o["room"]]
            horiz = o["y1"] == o["y2"]
            for q in rooms:
                if q["type"] != "kitchen":
                    continue
                if horiz and (abs(q["y"] - o["y1"]) < 0.02 or abs(q["y"] + q["d"] - o["y1"]) < 0.02) and q["x"] <= o["x1"] + 0.01 and o["x2"] <= q["x"] + q["w"] + 0.01:
                    cost += 3
                if not horiz and (abs(q["x"] - o["x1"]) < 0.02 or abs(q["x"] + q["w"] - o["x1"]) < 0.02) and q["y"] <= o["y1"] + 0.01 and o["y2"] <= q["y"] + q["d"] + 0.01:
                    cost += 3
    return cost


def _all_reached(rooms: list[dict], lv: dict) -> bool:
    from .geometry import level_openings, reachable
    tmp = {"name": lv.get("name", ""), "rooms": rooms, "stilt": bool(lv.get("stilt"))}
    li = 0 if lv.get("hall") else 1
    ops, _ = level_openings(tmp, li, 0)
    return not reachable(tmp, ops, None, li)[1]


def add_cell(rooms: list[dict], c: Cell, x: float, y: float, w: float, d: float, counters: dict):
    def nid(kind):
        counters[kind] = counters.get(kind, 0) + 1
        return f"{kind}_{counters[kind]}"

    kind = c.kind
    if kind in ("bedroom", "master") and c.attached:
        tw, td = SIZES["toilet"][0], min(SIZES["toilet"][1], max(SIZES["toilet"][3], d * 0.62))
        tw, td = r2(tw), r2(td)
        bid = nid("bedroom")
        rooms.append({"id": bid, "type": "bedroom", "name": NAMES[kind], "x": x, "y": y, "w": r2(w - tw), "d": d})
        rooms.append({"id": nid("toilet"), "type": "toilet", "name": "Attached Toilet", "x": r2(x + w - tw),
                      "y": r2(y + d - td), "w": tw, "d": td, "parent": bid})
        if d - td > 0.5:
            rooms.append({"id": nid("dress"), "type": "dress", "name": "Dress", "x": r2(x + w - tw), "y": y,
                          "w": tw, "d": r2(d - td), "parent": bid})
        return
    if kind in ("common_toilet", "pooja") and d > SIZES[kind][1] * 1.5 and d - SIZES[kind][1] >= 3:
        td = r2(SIZES[kind][1] + 1)
        rooms.append({"id": nid("passage"), "type": "passage", "name": "Passage / Wash", "x": r2(x), "y": r2(y),
                      "w": r2(w), "d": r2(d - td)})
        rooms.append({"id": nid(kind), "type": kind, "name": NAMES[kind], "x": r2(x), "y": r2(y + d - td),
                      "w": r2(w), "d": td})
        return
    t = {"master": "bedroom", "parking_car": "parking", "parking_bike": "parking", "stilt_open": "parking"}.get(kind, kind)
    name = NAMES[kind]
    rooms.append({"id": nid(t), "type": t, "name": name, "x": r2(x), "y": r2(y), "w": r2(w), "d": r2(d)})


def fallback(levels: list[dict], i: int, notes: list[str]) -> bool:
    """Make room on level i when its rooms do not fit. Returns True if something was changed.

    Order (least change first): dining into hall → pooja shelf → drop upper-floor lounge →
    move a bedroom up (only when the floor above stays lighter) → attached toilet to common toilet.
    """
    lv = levels[i]
    beds = int(lv.get("bedrooms") or 0)
    if lv.get("dining") and not lv.get("_dining_in_hall") and lv.get("hall"):
        lv["_dining_in_hall"] = True
        lv["dining"] = False
        notes.append(f"{lv['name']}: dining combined with the hall to fit the plot.")
        return True
    if lv.get("pooja") and beds > 0:
        lv["pooja"] = False
        notes.append(f"{lv['name']}: pooja room removed to fit (add a pooja shelf in the hall/kitchen) – change if needed.")
        return True
    if lv.get("lounge") and beds > 0:
        lv["lounge"] = False
        notes.append(f"{lv['name']}: family lounge removed to fit – rooms open from the staircase lobby.")
        return True
    if int(lv.get("attached_toilets") or 0) >= 1 and int(lv.get("common_toilets") or 0) == 0 and beds >= 1:
        lv["attached_toilets"] = int(lv["attached_toilets"]) - 1
        lv["common_toilets"] = 1
        notes.append(f"{lv['name']}: one attached toilet changed to a common toilet to fit.")
        return True
    if beds > 0 and i + 1 < len(levels):
        up = levels[i + 1]
        up_beds = int(up.get("bedrooms") or 0)
        if up_beds <= beds - 1 or (not up.get("kitchen") and up_beds <= beds and not lv.get("_moved_once")):
            lv["bedrooms"] = beds - 1
            lv["_moved_once"] = True
            moved_att = 1 if int(lv.get("attached_toilets") or 0) >= beds else 0
            if moved_att:
                lv["attached_toilets"] = int(lv["attached_toilets"]) - 1
            up["bedrooms"] = up_beds + 1
            up["attached_toilets"] = int(up.get("attached_toilets") or 0) + moved_att
            if (moved_att and (lv.get("hall") or lv.get("kitchen"))
                    and int(lv.get("attached_toilets") or 0) + int(lv.get("common_toilets") or 0) == 0):
                lv["common_toilets"] = 1
                notes.append(f"{lv['name']}: a common toilet kept for the living area.")
            if not moved_att and int(up.get("common_toilets") or 0) == 0:
                up["common_toilets"] = 1
                notes.append(f"{up['name']}: a common toilet added for the moved bedroom.")
            notes.append(f"Moved 1 bedroom{' with toilet' if moved_att else ''} from {lv['name']} to {up['name']} to fit.")
            return True
    att = int(lv.get("attached_toilets") or 0)
    common = int(lv.get("common_toilets") or 0)
    if att >= 1:
        lv["attached_toilets"] = att - 1
        if common == 0:
            lv["common_toilets"] = 1
            notes.append(f"{lv['name']}: one attached toilet changed to a common toilet to fit.")
        else:
            notes.append(f"{lv['name']}: one attached toilet removed – the common toilet serves this bedroom.")
        return True
    if common > 1:
        lv["common_toilets"] = common - 1
        notes.append(f"{lv['name']}: one common toilet removed to fit.")
        return True
    return False


def generate(req: dict, _probe: bool = False) -> dict:
    """req = parser.build_requirements(...) output (possibly edited by the user)."""
    q = []
    for k, label in [("plot_w_ft", "plot frontage"), ("plot_d_ft", "plot depth"), ("facing", "facing"),
                     ("road_width_m", "road width")]:
        if not req.get(k):
            q.append(f"Please confirm the {label}.")
    levels = req.get("levels") or []
    if not levels:
        q.append("Please confirm the rooms on each floor.")
    if q:
        raise LayoutError(q)
    n = len(levels)
    shape = req.get("plot_shape") if isinstance(req.get("plot_shape"), dict) else None
    poly = pinfo = None
    if shape:  # 1.18 irregular plot: frontage = the road side, depth = the deepest point
        from .plot import PlotError, buildable as poly_buildable, info as poly_info, polygon
        try:
            poly = polygon(shape)
        except PlotError as e:
            raise LayoutError(e.questions)
        pinfo = poly_info(poly)
        req = {**req, "plot_w_ft": pinfo["sides_ft"][0], "plot_d_ft": pinfo["d"]}
    sb = tn_setbacks(float(req["plot_w_ft"]), float(req["plot_d_ft"]), float(req["road_width_m"]), n,
                     float(req.get("floor_height_ft") or 10), req.get("area_type", "other"), bool(req.get("corner")),
                     req.get("side_road_width_m"), req.get("one_side", "left"))
    man = {k: float(v) for k, v in (req.get("setback_override") or {}).items()
           if k in ("front", "rear", "left", "right") and v not in (None, "") and float(v) >= 0}
    if man:  # 1.18 Auto + Manual: the user's own setbacks win; the rule values stay for the compliance check
        eff = {**sb["ft"], **man}
        pw, pd = float(req["plot_w_ft"]), float(req["plot_d_ft"])
        bw0, bd0 = round(pw - eff["left"] - eff["right"], 2), round(pd - eff["front"] - eff["rear"], 2)
        if bw0 < 10 or bd0 < 15:
            raise LayoutError([f"With your setbacks only {bw0:.1f} × {bd0:.1f} ft remains – too small for a house."])
        below = [k for k, v in man.items() if v + 1e-6 < sb["ft"][k]]
        sb = {**sb, "ft_rule": sb["ft"], "ft": eff, "manual": sorted(man),
              "buildable": {"x": eff["left"], "y": eff["front"], "w": bw0, "d": bd0}}
        sb["notes"] = list(sb.get("notes") or []) + [f"Manual setbacks used for: {', '.join(sorted(man))}" +
                                                       (f" – {', '.join(below)} below the TNCDBR value (check with the local body)." if below else ".")]
    if poly:
        try:
            bb = poly_buildable(poly, sb["ft"], shape.get("road_sides"))
        except PlotError as e:
            raise LayoutError(e.questions)
        if bb["w"] < 10 or bb["d"] < 15:
            raise LayoutError([f"After the setbacks only {bb['w']:.1f} × {bb['d']:.1f} ft fits as a rectangle on this plot – too small for a house."])
        sb = {**sb, "buildable": {k: bb[k] for k in ("x", "y", "w", "d")}, "edge_kinds": bb["edge_kinds"],
              "edge_setbacks_ft": bb["edge_setbacks_ft"],
              "coverage_pct": round(100 * bb["w"] * bb["d"] / max(pinfo["area_sqft"], 1), 1)}
        sb["notes"] = list(sb.get("notes") or []) + [
            f"Irregular plot ({len(poly)} sides, {pinfo['area_sqft']:g} sq ft): setbacks kept from every side; the house is the "
            f"largest rectangle that fits ({bb['w']:g}' × {bb['d']:g}'). Left-over corners → garden / parking / sump."]
    b = sb["buildable"]
    bw, bd = math.floor(b["w"] * 4) / 4, math.floor(b["d"] * 4) / 4  # snap to 3" grid, never into setbacks
    comp = compass(req["facing"])
    multi = n > 1 and req.get("staircase", True)
    levels = [dict(lv, name=lv.get("name") or f"Level {i}") for i, lv in enumerate(levels)]
    notes: list[str] = list(req.get("assumptions") or [])
    out_levels, template = [], None
    i = 0
    while i < len(levels):
        lv = levels[i]
        try:
            rooms, info = build_level(lv, bw, bd, comp, multi, template)
        except LayoutError as e:
            fix = fallback(levels, i, notes)
            if fix:
                continue  # retry this level with the adjusted rooms
            err = LayoutError(e.questions + [
                "Options: reduce bedrooms/toilets, remove car parking, combine dining with hall, "
                "or add a floor (G+1)." if n == 1 else
                "Options: reduce bedrooms/toilets or remove car parking on this floor."])
            if not _probe:
                err.suggestions = suggest_alternatives(req)
            raise err
        if i == 0 and multi:
            template = info
        out_levels.append({"name": lv["name"], "stilt": bool(lv.get("stilt")), "rooms": rooms})
        i += 1
    plan = {
        "version": 1, "units": "ft",
        "plot": ({"w": pinfo["w"], "d": pinfo["d"], "poly": [list(p) for p in poly], "info": pinfo, "edges": sb["edge_kinds"]}
                 if poly else {"w": float(req["plot_w_ft"]), "d": float(req["plot_d_ft"])}),
        "facing": req["facing"], "compass": comp, "setbacks": sb,
        "building": {"x": b["x"], "y": b["y"], "w": bw, "d": bd},
        "floor_height_ft": float(req.get("floor_height_ft") or 10),
        "levels": out_levels, "notes": notes,
        "requirements": {**req, "levels": levels},
    }
    from .geometry import add_openings
    return add_openings(plan)


def _clean_levels(levels: list[dict]) -> list[dict]:
    return [{k: v for k, v in lv.items() if not k.startswith("_")} for lv in levels]


def suggest_alternatives(req: dict) -> list[dict]:
    """When the requested rooms do not fit, try a few honest variants and return those that work.
    The user picks one (nothing is changed silently)."""
    import copy
    base = copy.deepcopy(req)
    base["levels"] = _clean_levels(base.get("levels") or [])
    cands: list[tuple[str, dict]] = []
    total_beds = sum(int(lv.get("bedrooms") or 0) for lv in base["levels"])
    # 1. one bedroom less (taken from the most loaded floor)
    if total_beds > 1:
        r = copy.deepcopy(base)
        lv = max(r["levels"], key=lambda l: int(l.get("bedrooms") or 0))
        lv["bedrooms"] = int(lv["bedrooms"]) - 1
        lv["attached_toilets"] = min(int(lv.get("attached_toilets") or 0), lv["bedrooms"])
        if int(lv.get("attached_toilets") or 0) + int(lv.get("common_toilets") or 0) == 0:
            lv["common_toilets"] = 1
        cands.append((f"{total_beds - 1} bedrooms instead of {total_beds}", r))
    # 2. no car parking
    if any(lv.get("parking_car") and not lv.get("stilt") for lv in base["levels"]):
        r = copy.deepcopy(base)
        for lv in r["levels"]:
            if not lv.get("stilt"):
                lv["parking_car"] = False
        cands.append(("Without car parking (two-wheeler only)", r))
    # 3. one more floor: bedrooms upstairs
    stilt = any(lv.get("stilt") for lv in base["levels"])
    if len(base["levels"]) < (4 if stilt else 3):
        r = copy.deepcopy(base)
        main = next((lv for lv in r["levels"] if lv.get("kitchen")), r["levels"][-1])
        move = max(1, int(main.get("bedrooms") or 0) // 2 + (1 if int(main.get("bedrooms") or 0) % 2 else 0))
        move = min(move, int(main.get("bedrooms") or 0))
        if move:
            att = min(int(main.get("attached_toilets") or 0), move)
            main["bedrooms"] = int(main["bedrooms"]) - move
            main["attached_toilets"] = int(main.get("attached_toilets") or 0) - att
            if int(main.get("common_toilets") or 0) == 0:
                main["common_toilets"] = 1
            names = ["Ground Floor", "First Floor", "Second Floor", "Third Floor"]
            r["levels"].append({"name": names[min(len(r["levels"]) - (1 if stilt else 0), 3)], "stilt": False,
                                "bedrooms": move, "attached_toilets": att, "common_toilets": 0 if att else 1,
                                "kitchen": False, "hall": False, "dining": False, "pooja": False,
                                "parking_car": False, "parking_bike": False, "lounge": True})
            r["staircase"] = True
            n = len(r["levels"])
            cands.append((f"Add a floor ({'Stilt' if stilt else 'G'}+{n - (2 if stilt else 1)}) with {move} bedroom(s) upstairs", r))
    # 4. dining in hall + no pooja everywhere (compact)
    out = []
    for label, r in cands:
        try:
            plan = generate(r, _probe=True)
        except (LayoutError, ValueError):
            continue
        out.append({"label": label, "requirements": r, "notes": plan.get("notes", [])})
    return out
