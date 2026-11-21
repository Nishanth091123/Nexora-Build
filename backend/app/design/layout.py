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


SPINE_FRAC = 0.0  # ground floor made at least this share of the buildable depth (upper floors reuse it)
COMPACT_K = None  # 1.27.1: compact (no-passage) generator variant for small single-floor plots
SPINE_K = None  # 1.24.2: None = row-zoning generator, 0..n = spine generator variant
TIGHT = False  # 1.24: compact attached toilet (4 ft) + slightly smaller bedroom minimum, used before dropping a toilet


def _tw() -> float:
    return 4.0 if TIGHT else SIZES["toilet"][0]


def _min_area(kind: str) -> float:
    if TIGHT:
        return 90.0 if kind == "master" else 75.0
    return 100.0 if kind == "master" else 80.0


class Cell:
    def __init__(self, kind: str, fixed_w: float | None = None, attached: bool = False):
        self.kind = kind
        self.attached = attached
        dw, dd, mw, md = SIZES[kind]
        if attached:
            tw = SIZES["toilet"]
            dw, mw = dw + _tw(), mw + min(tw[2], _tw())
        self.dw, self.dd, self.mw, self.md = dw, dd, mw, md
        self.fixed_w = fixed_w
        self.x = self.w = 0.0


def level_items(lv: dict, multi: bool) -> tuple[list[Cell], list[Cell], Cell | None]:
    """1.22: sizes the user wrote (room_sizes) replace the default desired size of that room."""
    front, rest, stair = _level_items(lv, multi)
    sizes = lv.get("_sizes") or {}
    if sizes:
        tw = _tw()
        for c in front + rest + ([stair] if stair else []):
            s = sizes.get(c.kind)
            if s and len(s) == 2 and s[0] > 0 and s[1] > 0:
                c.dw, c.dd = float(s[0]) + (tw if c.attached else 0), float(s[1])
                c.mw, c.md = min(c.mw, c.dw), min(c.md, c.dd)
                c.wanted = True
    return front, rest, stair


def _level_items(lv: dict, multi: bool) -> tuple[list[Cell], list[Cell], Cell | None]:
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


def merge_passages(rooms: list[dict]) -> list[dict]:
    """1.24: passage cells of the same width that touch end-to-end are ONE continuous passage (never split cells)."""
    rooms = [dict(r) for r in rooms]
    changed = True
    while changed:
        changed = False
        ps = [r for r in rooms if r["type"] == "passage"]
        for a in ps:
            for b in ps:
                if a is b or a not in rooms or b not in rooms:
                    continue
                vert = abs(a["x"] - b["x"]) < 0.06 and abs(a["w"] - b["w"]) < 0.06 and abs(a["y"] + a["d"] - b["y"]) < 0.06
                horiz = abs(a["y"] - b["y"]) < 0.06 and abs(a["d"] - b["d"]) < 0.06 and abs(a["x"] + a["w"] - b["x"]) < 0.06
                if vert:
                    a["d"] = r2(a["d"] + b["d"])
                elif horiz:
                    a["w"] = r2(a["w"] + b["w"])
                else:
                    continue
                rooms.remove(b)
                changed = True
    return rooms


def build_level(lv: dict, bw: float, bd: float, comp: dict, multi: bool, template: dict | None) -> tuple[list[dict], dict]:
    global TIGHT
    TIGHT = bool(lv.get("_tight_att"))
    try:
        r_ = _build_level_best(lv, bw, bd, comp, multi, template)
    finally:
        TIGHT = False
    return merge_passages(r_[0]), r_[1]


def _build_level_best(lv: dict, bw: float, bd: float, comp: dict, multi: bool, template: dict | None) -> tuple[list[dict], dict]:
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
    sides = ([template["stair_side"]] if template and template.get("stair_side") in ("left", "right") else []) + ["left", "right", "mid", "mid1", "mid2", "mid3"]
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


def _row_ok(cand: list, ws: list[float], d: float) -> bool:
    """Every room in this row is wide enough (and every bedroom big enough) – same limits the layout enforces."""
    for c, w in zip(cand, ws):
        if c.mw - w > 0.6:
            return False
        if c.kind in ("bedroom", "master"):
            net_w = w - (_tw() if c.attached else 0)
            if net_w * d < _min_area(c.kind) - 0.5:
                return False
    return True


def _mid_widths(cand: list, kk: int, px: float | None, bw: float, avail: float) -> list[float]:
    """Widths of a row split by the middle passage: first row free; later rows keep the passage at the same x."""
    if px is None:
        ws = [r2(w) for w in size_row(cand, avail)]
        ws[-1] = r2(avail - sum(ws[:-1]))
        return ws
    left = [r2(w) for w in size_row(cand[:kk], px)]
    left[-1] = r2(px - sum(left[:-1]))
    right = [r2(w) for w in size_row(cand[kk:], bw - px - SPINE)]
    right[-1] = r2(bw - px - SPINE - sum(right[:-1]))
    return left + right


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
        mid_px = None  # 1.23: x of the middle passage – the same in every row so the passages join up
        for ri, (row, d) in enumerate(zip(rows, depths)):
            use = spine and ri >= 1 and not all(c.kind in ("terrace",) for c in row)
            avail = bw - SPINE if use else bw
            x0 = SPINE if use and spine == "left" else 0.0
            mid_k, mid_ws = None, None  # 1.23: 'mid' spine – the passage sits between two groups of rooms, so rooms on BOTH sides open into it
            if ri == 0 and spine in ("left", "right"):
                row = _pin_edge(order_row(row, y, d, bw, bd, comp, pinned), spine)
            elif use and spine.startswith("mid"):
                forced = int(spine[3:]) if len(spine) > 3 else None
                cands = order_candidates(row, y, d, avail, bd, comp, pinned, 14)
                best_row, best_bad, mid_k, mid_ws = cands[0] if cands else row, None, 1, None
                for cand in cands:
                    ks = [forced] if (mid_px is None and forced and 0 < forced < len(cand)) else list(range(1, len(cand)))
                    for kk in ks:
                        ws_ = _mid_widths(cand, kk, mid_px, bw, avail)
                        if not _row_ok(cand, ws_, d):
                            continue
                        trial = list(rooms)
                        xx, cnt = 0.0, dict(counters)
                        for i_, (c, w) in enumerate(zip(cand, ws_)):
                            if i_ == kk:
                                trial.append({"id": f"passage_s{ri}", "type": "passage", "name": "Passage",
                                              "x": r2(xx), "y": r2(y), "w": SPINE, "d": r2(d)})
                                xx += SPINE
                            add_cell(trial, c, r2(xx), y, w, d, cnt)
                            xx += w
                        bad = _unreached_count(trial, lv)
                        if best_bad is None or bad < best_bad:
                            best_row, best_bad, mid_k, mid_ws = cand, bad, kk, ws_
                        if bad == 0:
                            break
                    if best_bad == 0:
                        break
                row = best_row
                if best_bad is None:
                    mid_k, mid_ws = None, None
                elif mid_px is None:
                    mid_px = r2(sum(mid_ws[:mid_k]))
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
            if mid_k is not None and mid_ws:
                widths = list(mid_ws)
            x = x0
            if use and mid_k is None:
                rooms.append({"id": f"passage_s{ri}", "type": "passage", "name": "Passage",
                              "x": 0.0 if spine == "left" else r2(bw - SPINE), "y": r2(y), "w": SPINE, "d": r2(d)})
            for ci, (c, w) in enumerate(zip(row, widths)):
                if mid_k is not None and ci == mid_k:
                    rooms.append({"id": f"passage_s{ri}", "type": "passage", "name": "Passage",
                                  "x": r2(x), "y": r2(y), "w": SPINE, "d": r2(d)})
                    x += SPINE
                if c.mw - w > 0.6:
                    raise LayoutError([f"{lv['name']}: {NAMES[c.kind]} would be only {w:.1f} ft wide (minimum "
                                       f"{c.mw:g} ft)."])
                if c.kind in ("bedroom", "master"):
                    net_w = w - (_tw() if c.attached else 0)
                    if net_w * d < _min_area(c.kind) - 0.5:
                        raise LayoutError([f"{lv['name']}: {NAMES[c.kind]} would be only {net_w * d:.0f} sq ft "
                                           f"(minimum {_min_area(c.kind):g} sq ft)."])
                if c.kind == "stair":
                    info["stair_side"] = "left" if x < 0.1 else ("right" if abs(x + w - bw) < 0.1 else "middle")
                add_cell(rooms, c, r2(x), y, w, d, counters)
                x += w
            y += d
        return rooms, info

    return place(spine)


BENIGN_ONLY = False  # 1.23: fallback() may only merge dining / drop pooja / drop lounge
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
        tw, td = _tw(), min(SIZES["toilet"][1], max(SIZES["toilet"][3], d * 0.62))
        tw, td = r2(tw), r2(td)
        bid = nid("bedroom")
        rooms.append({"id": bid, "type": "bedroom", "name": NAMES[kind], "x": x, "y": y, "w": r2(w - tw), "d": d})
        rooms.append({"id": nid("toilet"), "type": "toilet", "name": "Attached Toilet", "x": r2(x + w - tw),
                      "y": r2(y + d - td), "w": tw, "d": td, "parent": bid})
        if d - td > 0.5:
            rooms.append({"id": nid("dress"), "type": "dress", "name": "Dress", "x": r2(x + w - tw), "y": y,
                          "w": tw, "d": r2(d - td), "parent": bid})
        return
    big_toilet = kind == "common_toilet" and w * d > 48 and d >= 8.5  # 1.24: a common toilet is never bedroom-sized
    if big_toilet or (kind in ("common_toilet", "pooja") and d > SIZES[kind][1] * 1.5 and d - SIZES[kind][1] >= 3):
        td = r2(max(5.0, min(7.0, 40.0 / max(w, 1))) if big_toilet else SIZES[kind][1] + 1)
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
    if int(lv.get("attached_toilets") or 0) >= 1 and not lv.get("_tight_att"):
        lv["_tight_att"] = True
        notes.append(f"{lv['name']}: attached toilet made compact (4 ft wide) so it stays inside the bedroom.")
        return True
    if BENIGN_ONLY:  # 1.23: first try to keep every room the user asked for (toilets, bedrooms)
        return False
    if int(lv.get("attached_toilets") or 0) >= 1 and int(lv.get("common_toilets") or 0) == 0 and beds >= 1:
        lv["attached_toilets"] = int(lv["attached_toilets"]) - 1
        lv["common_toilets"] = 1
        notes.append(f"⚠ {lv['name']}: one attached toilet changed to a common toilet to fit.")
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
                notes.append(f"⚠ {lv['name']}: a common toilet kept for the living area.")
            if not moved_att and int(up.get("common_toilets") or 0) == 0:
                up["common_toilets"] = 1
                notes.append(f"{up['name']}: a common toilet added for the moved bedroom.")
            notes.append(f"⚠ Moved 1 bedroom{' with toilet' if moved_att else ''} from {lv['name']} to {up['name']} to fit.")
            return True
    att = int(lv.get("attached_toilets") or 0)
    common = int(lv.get("common_toilets") or 0)
    if att >= 1:
        lv["attached_toilets"] = att - 1
        notes[:] = [n for n in notes if not (lv["name"] in n and "made compact" in n)]
        if common == 0:
            lv["common_toilets"] = 1
            notes.append(f"⚠ {lv['name']}: one attached toilet changed to a common toilet to fit.")
        else:
            notes.append(f"⚠ {lv['name']}: one attached toilet removed – the plot is too tight to connect every room with it. To keep it: widen the plot, drop the car parking, or make it G+1.")
        return True
    if common > 1:
        lv["common_toilets"] = common - 1
        notes.append(f"{lv['name']}: one common toilet removed to fit.")
        return True
    return False


def _rebalance(req: dict):
    """Variants that keep the TOTAL bedrooms / toilets but move a bedroom (with its attached toilet) to another floor."""
    import copy
    lv0 = [lv for lv in (req.get("levels") or [])]
    idx = [i for i, lv in enumerate(lv0) if not lv.get("stilt") and not lv.get("units")]
    if len(idx) < 2:
        return
    seen = set()
    frontier = [(copy.deepcopy(req), "")]
    for _ in range(2):
        nxt = []
        for r, desc in frontier:
            for i in idx:
                for j in idx:
                    if i == j or int(r["levels"][i].get("bedrooms") or 0) <= 0:
                        continue
                    v = copy.deepcopy(r)
                    a, b = v["levels"][i], v["levels"][j]
                    a["bedrooms"] = int(a["bedrooms"]) - 1
                    b["bedrooms"] = int(b.get("bedrooms") or 0) + 1
                    if int(a.get("attached_toilets") or 0) > a["bedrooms"] or (int(a.get("attached_toilets") or 0) > 0 and int(b.get("attached_toilets") or 0) < b["bedrooms"] - 0):
                        if int(a.get("attached_toilets") or 0) > 0:
                            a["attached_toilets"] = int(a["attached_toilets"]) - 1
                            b["attached_toilets"] = int(b.get("attached_toilets") or 0) + 1
                    key = tuple((int(l.get("bedrooms") or 0), int(l.get("attached_toilets") or 0)) for l in v["levels"])
                    if key in seen:
                        continue
                    seen.add(key)
                    d2 = (desc + "; " if desc else "") + f"1 bedroom from {a.get('name')} to {b.get('name')}"
                    nxt.append((v, d2))
                    yield v, d2
        frontier = nxt[:4]


def _pipeline(req: dict, orig: dict, adjust: bool):
    """Try every layout engine in order. Returns (plan | None, best_dev, best_bad, first_err).
    A plan is accepted only if it passes the automatic check AND keeps exactly what the user chose
    (unless the user allowed adjusting)."""
    global BENIGN_ONLY, SPINE_K, SPINE_FRAC, COMPACT_K
    from . import geometry
    from .validate import check, compliance
    first_err, best_bad, best_dev = None, None, None

    def _void_over_parking(out):
        """A floor has one passage. The void above the car porch is an open terrace, not a second passage."""
        lvs = out.get("levels") or []
        if len(lvs) < 2:
            return
        park = [r for r in lvs[0]["rooms"] if r["type"] == "parking"]
        for lv in lvs[1:]:
            ps = [r for r in lv["rooms"] if r["type"] == "passage"]
            if len(ps) < 2:
                continue
            for r in ps:
                area = r["w"] * r["d"]
                over = sum(max(0.0, min(r["x"] + r["w"], q["x"] + q["w"]) - max(r["x"], q["x"]))
                           * max(0.0, min(r["y"] + r["d"], q["y"] + q["d"]) - max(r["y"], q["y"])) for q in park)
                if area and over >= 0.6 * area and sum(1 for x in lv["rooms"] if x["type"] == "passage") > 1:
                    r["type"], r["name"] = "terrace", "Open Terrace (above car park)"
            # any other second passage cell on the outer wall is a balcony, not a passage (the biggest cell stays the passage)
            from .geometry import add_openings as _ao

            def _chk(o):  # doors / walls must be re-derived after every trial change
                _ao(o)
                return check(o)

            ps = sorted((r for r in lv["rooms"] if r["type"] == "passage"), key=lambda r: -r["w"] * r["d"])
            if len(ps) > 1:
                mx = max(r["x"] + r["w"] for r in lv["rooms"])
                my = max(r["y"] + r["d"] for r in lv["rooms"])
                import copy as _cp
                for r in ps[1:]:
                    if not (min(r["x"], r["y"], mx - r["x"] - r["w"], my - r["y"] - r["d"]) <= 0.3 and r["w"] * r["d"] >= 12):
                        continue
                    base_bad = len(_chk(out)["hard"])
                    snap = _cp.deepcopy(lv["rooms"])
                    r["type"], r["name"] = "terrace", "Balcony"
                    if len(_chk(out)["hard"]) <= base_bad - 1 or not _chk(out)["hard"]:
                        continue
                    # a toilet above / below the cell needs the cell for its door: swap them (toilet next to the lounge / passage)
                    lv["rooms"][:] = snap
                    r = next(q for q in lv["rooms"] if q["id"] == r["id"])
                    for t in [q for q in lv["rooms"] if q["type"] in ("toilet", "common_toilet", "dress")
                              and abs(q["x"] - r["x"]) < 0.05 and abs(q["w"] - r["w"]) < 0.05]:
                        if abs(t["y"] - (r["y"] + r["d"])) < 0.05:      # toilet above the cell
                            y0 = r["y"]
                            t["y"], r["y"] = y0, y0 + t["d"]
                        elif abs(t["y"] + t["d"] - r["y"]) < 0.05:      # toilet below the cell
                            t["y"], r["y"] = r["y"] + r["d"] - t["d"], t["y"]
                        else:
                            continue
                        r["type"], r["name"] = "terrace", "Balcony"
                        if not _chk(out)["hard"]:
                            break
                        lv["rooms"][:] = _cp.deepcopy(snap)
                        r = next(q for q in lv["rooms"] if q["id"] == r["id"])
                    else:
                        lv["rooms"][:] = snap

    def judge(out, relax=False):
        nonlocal best_bad, best_dev
        _void_over_parking(out)
        res = check(out)
        if res["hard"]:
            if best_bad is None or len(res["hard"]) < len(best_bad[1]):
                best_bad = (out, res["hard"])
            return None
        cp = compliance(orig, out)
        dev = cp["hard"]
        if dev and not adjust:
            if best_dev is None or len(dev) < len(best_dev[1]):
                best_dev = (out, dev)
            return None
        if dev:
            out["notes"] = list(out.get("notes") or []) + ["⚠ Adjusted as you allowed: " + "; ".join(dev)]
        if cp["soft"]:
            out["notes"] = list(out.get("notes") or []) + ["⚠ Changed to fit this plot: " + " ".join(cp["soft"][:6])]
        if isinstance(out.get("requirements"), dict):
            out["requirements"].pop("allow_adjust", None)
        if relax:
            out["notes"] = list(out.get("notes") or []) + [
                "⚠ This plot is too tight to give every bedroom its own door from the hall / passage – one room opens "
                "through the kitchen. To avoid it: widen the plot, drop the car parking, make it G+1, or ask for fewer rooms."]
        out["notes"] = list(out.get("notes") or []) + ["⚠ " + x for x in res["soft"]]
        out["checks"] = {"passed": True, "soft": res["soft"]}
        return out

    # 0. compact engine (1.27.1): single floor, no passage at all – rooms open from the hall / dining
    if len(req.get("levels") or []) == 1 and not any(lv.get("stilt") or lv.get("units") for lv in req["levels"]):
        for k in range(4):
            COMPACT_K = k
            try:
                out = _generate(req, True)
            except LayoutError as e:
                if any("not used" in q for q in e.questions):
                    break
                continue
            finally:
                COMPACT_K = None
            got = judge(out)
            if got:
                got["notes"] = list(got.get("notes") or []) + ["Compact layout: no passage – bedrooms open from the dining, toilets from the hall / dining."]
                return got, best_dev, best_bad, first_err
    # 1. spine engine: every room opens from a hall / dining / passage by construction
    if not any(lv.get("stilt") or lv.get("units") for lv in (req.get("levels") or [])):
        gname = ((req.get("levels") or [{}])[0].get("name") or "Ground Floor")
        for k in range(6):
            out, stop = None, False
            for frac in (0.0, 0.6, 0.8, 0.95):
                SPINE_K, SPINE_FRAC = k, frac
                try:
                    out = _generate(req, True)
                    break
                except LayoutError as e:
                    first_err = first_err or e
                    if any("no further layout variant" in q for q in e.questions):
                        stop = True
                        break
                    if e.questions and str(e.questions[0]).startswith(gname):
                        break   # a ground-floor problem – a deeper ground floor does not help
                    # an upper floor needs more depth than the ground floor gave → try a deeper ground floor
                finally:
                    SPINE_K, SPINE_FRAC = None, 0.0
            if stop:
                break
            if out is None:
                continue
            got = judge(out)
            if got:
                return got, best_dev, best_bad, first_err
    # 2. row-zoning engine
    for relax, benign in ((False, True), (False, False), (True, True), (True, False)):
        geometry.RELAX_KITCHEN, BENIGN_ONLY = relax, benign
        try:
            out = _generate(req, True)  # probe mode: suggestions are worked out once, at the end
        except LayoutError as e:
            first_err = first_err or e
            continue
        finally:
            geometry.RELAX_KITCHEN, BENIGN_ONLY = False, False
        got = judge(out, relax)
        if got:
            return got, best_dev, best_bad, first_err
    return None, best_dev, best_bad, first_err


def generate(req: dict, _probe: bool = False) -> dict:
    """1.24.2: the plan keeps EXACTLY the rooms the user chose and passes the automatic check (every room has a door
    from a hall / dining / passage, one passage, small common toilet …). If that is impossible on this plot, nothing is
    changed silently – the user is asked and gets options (one of them: "adjust automatically", which lists every change)."""
    import copy
    if _probe or any(lv.get("units") for lv in (req.get("levels") or [])):
        return _generate(req, _probe)  # probes / several houses on a floor: one plain pass (fast, no suggestion loop)
    orig = copy.deepcopy(req)
    adjust = bool(req.get("allow_adjust"))
    out, best_dev, best_bad, first_err = _pipeline(req, orig, adjust)
    if out is not None:
        return out
    if (best_dev is not None or best_bad is not None or first_err is not None) and not orig.get("strict") and not adjust:
        # the user gave totals (e.g. 2 bedrooms), not a floor split → try other splits before asking
        for var, what in _rebalance(orig):
            out2 = _pipeline(copy.deepcopy(var), orig, False)[0]
            if out2 is not None:
                out2["notes"] = list(out2.get("notes") or []) + [f"Floor split changed to fit the plot: {what}."]
                return out2
    if best_dev is not None:  # only plans that change what the user chose → ask first
        try:
            sug = suggest_alternatives(orig)
        except Exception:
            sug = []
        sug.append({"label": "Adjust automatically (I will list exactly what changed)",
                    "requirements": {**orig, "allow_adjust": True}, "notes": best_dev[1]})
        raise LayoutError(["These rooms do not fit this plot exactly as you chose: " + " ".join(best_dev[1][:6]),
                           "Nothing was changed. Pick an option below, or change the plot / rooms and generate again."], sug)
    if best_bad is not None:  # every layout failed the check → ask the user instead of handing out a bad plan
        try:
            sug = suggest_alternatives(orig)
        except Exception:
            sug = []
        raise LayoutError(["I could not make a clean plan for this input: " + "; ".join(best_bad[1][:4]),
                           "Options: widen the plot, drop the car parking, make it one floor more, or ask for fewer rooms / toilets – "
                           "tell me which one to try."], sug)
    try:
        return _generate(req, False)  # nothing fits: raises the error WITH the options / suggestions
    except LayoutError as e:
        if not e.suggestions:
            try:
                e.suggestions = suggest_alternatives(orig)
            except Exception:
                pass
        raise


def _generate(req: dict, _probe: bool = False) -> dict:
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
    for lv_ in levels:
        lv_["_sizes"] = req.get("room_sizes") or {}
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
    multi = (n > 1 and req.get("staircase", True)) or bool(req.get("staircase_asked"))
    levels = [dict(lv, name=lv.get("name") or f"Level {i}") for i, lv in enumerate(levels)]
    notes: list[str] = list(req.get("assumptions") or [])
    out_levels, template = [], None
    i = 0
    while i < len(levels):
        lv = levels[i]
        try:
            if lv.get("units"):  # 1.19 several houses on this floor
                from .units import build_units_level
                rooms, info = build_units_level(lv, bw, bd, comp, template, i)
            elif COMPACT_K is not None and n == 1 and not lv.get("stilt"):
                from . import compact
                rooms, info = compact.build(lv, bw, bd, multi, COMPACT_K)
            elif SPINE_K is not None and not lv.get("stilt"):
                from . import spine
                rooms, info = spine.build(lv, bw, bd, multi or n > 1, template if i > 0 else None, SPINE_K, SPINE_FRAC)
                if i == 0:
                    template = info
            else:
                rooms, info = build_level(lv, bw, bd, comp, multi, template)
        except LayoutError as e:
            if SPINE_K is not None or COMPACT_K is not None:  # spine layouts never change what the user chose – the caller asks instead
                raise
            if lv.get("units"):
                err = LayoutError(e.questions)
                if not _probe:
                    err.suggestions = suggest_alternatives(req)
                raise err
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
        out_levels.append({"name": lv["name"], "stilt": bool(lv.get("stilt")), "rooms": rooms,
                           **({"units": [{"label": u["label"], "bhk": u["bhk"], "use": u.get("use", "")} for u in lv["units"]]}
                              if lv.get("units") else {})})
        i += 1
    plan = {
        "version": 1, "units": "ft",
        "plot": ({"w": pinfo["w"], "d": pinfo["d"], "poly": [list(p) for p in poly], "info": pinfo, "edges": sb["edge_kinds"]}
                 if poly else {"w": float(req["plot_w_ft"]), "d": float(req["plot_d_ft"])}),
        "facing": req["facing"], "compass": comp, "setbacks": sb,
        "building": ({"x": r2(b["x"] + (bw - template["Wf"]) / 2), "y": b["y"], "w": template["Wf"], "d": template["Du"]}
                     if SPINE_K is not None and template and template.get("spine") else
                     {"x": b["x"], "y": b["y"], "w": bw, "d": bd}),
        "floor_height_ft": float(req.get("floor_height_ft") or 10),
        "levels": out_levels, "notes": notes,
        "requirements": {**req, "levels": levels},
    }
    if req.get("ugd"):   # 1.27.7 sewer connection instead of a septic tank on the site plan
        plan["site"] = {"ugd": True, "sump": True, "rwh": True, "gate": True}
    if req.get("external_stair") and n == 1:   # 1.27.4: staircase outside the building (to the terrace)
        ft = sb.get("ft") or {}
        side = "right" if ft.get("right", 0) >= ft.get("left", 0) else "left"
        w_ = 3.0
        rise = float(req.get("floor_height_ft") or 10) + 0.7
        risers = round(rise / 0.54)
        plan["ext_stair"] = {"on": True, "side": side, "w": w_, "floors": 1, "risers": risers, "len": round((risers - 1) * 0.83 + 3.0, 1)}
        gap = ft.get(side, 0)
        plan["notes"] = list(plan.get("notes") or []) + [
            f"External staircase on the {side} side: {w_:g} ft wide, ≈ {plan['ext_stair']['len']:g} ft long, {risers} risers to the terrace. "
            + ("It sits inside the side setback – an open stair there needs the local body's permission."
               if gap and gap < 6 else "Check its position against the setbacks with the local body.")]
    from .geometry import add_openings
    out = add_openings(plan)
    out["notes"] = list(out.get("notes") or []) + size_report(req, out_levels)
    return out


TYPE_OF = {"master": ("Master Bedroom",), "bedroom": ("Bedroom",), "hall": ("Living / Hall",), "lounge": ("Family Lounge",),
           "kitchen": ("Kitchen",), "dining": ("Dining",), "common_toilet": ("Common Toilet",), "pooja": ("Pooja",),
           "stair": ("Staircase",), "parking_car": ("Car Parking",), "parking_bike": ("Bike Parking",)}


def size_report(req: dict, out_levels: list[dict]) -> list[str]:
    """1.22: sizes the user asked for against what the generator could give. Nothing is silent."""
    wanted = req.get("room_sizes") or {}
    msgs = []
    for kind, (w, d) in ((k, v) for k, v in wanted.items() if isinstance(v, (list, tuple)) and len(v) == 2):
        names = TYPE_OF.get(kind, ())
        got = [r for lv in out_levels[:1] for r in lv["rooms"] if r.get("name") in names]
        if not got:
            continue
        r = got[0]
        if abs(r["w"] - w) + abs(r["d"] - d) <= 0.6 or abs(r["w"] - d) + abs(r["d"] - w) <= 0.6:
            msgs.append(f"{names[0]} {w:g}' × {d:g}' – kept as asked.")
        else:
            msgs.append(f"{names[0]}: you asked {w:g}' × {d:g}', the generated plan has {r['w']:g}' × {r['d']:g}' "
                        "(the rooms had to share the plot width). Edit it in the 2D editor, or upload your drawing to keep exact sizes.")
    return msgs


def _clean_levels(levels: list[dict]) -> list[dict]:
    return [{k: v for k, v in lv.items() if not k.startswith("_")} for lv in levels]


def suggest_alternatives(req: dict) -> list[dict]:
    """When the requested rooms do not fit, try a few honest variants and return those that work.
    The user picks one (nothing is changed silently)."""
    import copy
    import time as _time
    _t_end = _time.monotonic() + 15.0   # never keep the user waiting: options found within 15 s are offered
    base = copy.deepcopy(req)
    if any(lv.get("units") for lv in (base.get("levels") or [])):
        return []   # several houses on a floor: the message lists the options (a probe per option would take minutes)
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
    # 4. single-room changes (each one is only offered if the result is a clean, exact plan)
    def flag_off(label, key, cond=None):
        if any(lv.get(key) and not lv.get("stilt") for lv in base["levels"]):
            r = copy.deepcopy(base)
            for lv in r["levels"]:
                if not lv.get("stilt"):
                    lv[key] = False
            cands.append((label, r))
    flag_off("Without the pooja room", "pooja")
    flag_off("Without two-wheeler parking", "parking_bike")
    flag_off("Dining joined with the hall (no separate dining)", "dining")
    flag_off("Without the family lounge", "lounge")
    if any(int(lv.get("attached_toilets") or 0) > 0 for lv in base["levels"]):
        r = copy.deepcopy(base)
        lv = max(r["levels"], key=lambda l: int(l.get("attached_toilets") or 0))
        lv["attached_toilets"] = int(lv["attached_toilets"]) - 1
        lv["common_toilets"] = int(lv.get("common_toilets") or 0) + 1
        cands.append(("One attached toilet as a common toilet", r))
    # 4. dining in hall + no pooja everywhere (compact)
    out = []
    for label, r in cands:
        if len(out) >= 4 or _time.monotonic() > _t_end:
            break
        try:
            import copy as _c
            plan = _pipeline(_c.deepcopy(r), _c.deepcopy(r), False)[0]
        except (LayoutError, ValueError):
            continue
        if plan is None:  # an option that again fails / drops something is not offered as "works"
            continue
        out.append({"label": label, "requirements": r, "notes": plan.get("notes", [])})
    if not out:  # no single change is enough → several together (each step listed, tried in the order that costs the user least)
        import copy as _c
        cur = _c.deepcopy(base)
        done: list[str] = []

        def _drop(key: str, text: str):
            if any(lv.get(key) and not lv.get("stilt") for lv in cur["levels"]):
                for lv in cur["levels"]:
                    if not lv.get("stilt"):
                        lv[key] = False
                done.append(text)
                return True
            return False

        def _less_bed():
            lv = max(reversed(cur["levels"]), key=lambda l: int(l.get("bedrooms") or 0))
            if sum(int(l.get("bedrooms") or 0) for l in cur["levels"]) <= 1 or int(lv.get("bedrooms") or 0) < 1:
                return False
            lv["bedrooms"] = int(lv["bedrooms"]) - 1
            lv["attached_toilets"] = min(int(lv.get("attached_toilets") or 0), lv["bedrooms"])
            if int(lv.get("attached_toilets") or 0) + int(lv.get("common_toilets") or 0) == 0:
                lv["common_toilets"] = 1
            done.append("1 bedroom less")
            return True

        def _att_to_common():
            lv = max(cur["levels"], key=lambda l: int(l.get("attached_toilets") or 0))
            if int(lv.get("attached_toilets") or 0) < 1:
                return False
            lv["attached_toilets"] = int(lv["attached_toilets"]) - 1
            lv["common_toilets"] = max(1, int(lv.get("common_toilets") or 0))
            done.append("one attached toilet made common")
            return True
        def _min_toilets():
            ch = False
            for l in cur["levels"]:
                a, c = int(l.get("attached_toilets") or 0), int(l.get("common_toilets") or 0)
                want = 0 if a >= 1 else 1
                if c > want:
                    l["common_toilets"] = want
                    ch = True
            if ch:
                done.append("no extra common toilet")
            return ch
        steps = [lambda: _drop("pooja", "no pooja room"), lambda: _drop("parking_bike", "no two-wheeler parking"),
                 lambda: _drop("lounge", "no family lounge"), lambda: _drop("dining", "dining joined with the hall"),
                 _att_to_common, lambda: _drop("parking_car", "no car parking"), _min_toilets] + [_att_to_common, _min_toilets, _less_bed, _min_toilets] * 4
        for st in steps:
            if _time.monotonic() > _t_end:
                break
            if not st():
                continue
            try:
                plan = _pipeline(_c.deepcopy(cur), _c.deepcopy(cur), False)[0]
            except (LayoutError, ValueError):
                plan = None
            if plan is not None:
                out.append({"label": "Several changes together: " + ", ".join(done), "requirements": _c.deepcopy(cur),
                            "notes": plan.get("notes", [])})
                break
    return out
