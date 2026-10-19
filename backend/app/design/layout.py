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
              stilt: bool = False, relax: bool = False, upper: bool = False) -> list[list[Cell]]:
    """Greedy row packing from the road side.

    Multi-floor plans keep the staircase in the FRONT row at an edge, so it stacks on every floor and
    upper floors only need the same front-row depth. Only front items (parking, hall/lounge) and bedrooms
    may sit in the front row; kitchen, dining, pooja and toilets start from the second row.
    tol = how far the desired widths of a row may exceed the building width (minimum widths must always fit).
    A stilt floor keeps one row of vehicles; whatever does not fit is left out (open parking behind).
    """
    rows: list[list[Cell]] = [[stair] if stair else []]

    def fits(row, c):
        dw = sum(x.fixed_w or x.dw for x in row) + (c.fixed_w or c.dw)
        mw = sum(x.fixed_w or x.mw for x in row) + (c.fixed_w or c.mw)
        return mw <= bw and dw <= bw * tol

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
    best, best_s = row, -1e9
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
        if s > best_s + 1e-9:
            best, best_s = list(p), s
    return best


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
            r = pack_rows(front, rest, stair, bw, tol, stilt, relax, upper=not lv.get("hall"))
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
    rooms: list[dict] = []
    y = 0.0
    info = {"front_d": depths[0], "mid_d": depths[1] if len(depths) > 1 else 0, "stair_w": stair_w, "stair_side": None}
    pinned = template["stair_side"] if template else ("edge" if multi else None)
    counters: dict[str, int] = {}
    for ri, (row, d) in enumerate(zip(rows, depths)):
        row = order_row(row, y, d, bw, bd, comp, pinned)
        widths = [r2(w) for w in size_row(row, bw)]
        widths[-1] = r2(bw - sum(widths[:-1]))
        x = 0.0
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
            add_cell(rooms, c, x, y, w, d, counters)
            x += w
        y += d
    return rooms, info


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
    sb = tn_setbacks(float(req["plot_w_ft"]), float(req["plot_d_ft"]), float(req["road_width_m"]), n,
                     float(req.get("floor_height_ft") or 10), req.get("area_type", "other"), bool(req.get("corner")),
                     req.get("side_road_width_m"), req.get("one_side", "left"))
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
        "plot": {"w": float(req["plot_w_ft"]), "d": float(req["plot_d_ft"])},
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
