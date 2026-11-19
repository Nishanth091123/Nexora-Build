"""1.24.2 – "spine" floor generator.

Every room is reached from a PASS room (hall / dining / lounge / passage / stair) BY CONSTRUCTION, so the plan can
never contain a room without a door, a split passage or a filler "passage" cell:

      ┌────────┬───────────────┐   left column  : car parking, kitchen, bedrooms, toilets …
      │  car   │     hall      │ (bike)
      ├────────┼───────────────┤   centre strip : hall → dining (one open space)
      │kitchen │    dining     │
      ├────────┼──┬────────────┤   ONE passage (3.5 ft) runs down from the dining
      │ bed    │  │  staircase │   right column : staircase, then rooms that open into the passage
      │        │P ├────────────┤
      │        │  │   bed      │
      └────────┴──┴────────────┘

Rooms get the size they need (area / width) – nothing is stretched into a bedroom-sized toilet, and a floor that
needs less than the plot gives simply leaves a bigger rear yard. Upper floors repeat the same skeleton
(same staircase, same passage). A floor that cannot be built this way raises LayoutError (the caller then asks).
"""
from __future__ import annotations

import itertools

from .layout import LayoutError, NAMES, r2

PW = 3.5          # passage width
STAIR_D = 11.0
CAR_D, CAR_MIN_W = 16.0, 8.6
BIKE_W = 6.0
TOIL_D, TOIL_W = 6.0, 5.5   # attached toilet strip at the back of a bedroom
AREA = {"master": 140.0, "bedroom": 120.0, "kitchen": 80.0, "common_toilet": 36.0, "pooja": 30.0, "lounge": 110.0,
        "dining": 90.0}
MINW = {"master": 10.0, "bedroom": 9.0, "kitchen": 7.0, "common_toilet": 4.0, "pooja": 3.5, "lounge": 8.0, "dining": 7.0}
MIND = {"master": 10.0, "bedroom": 9.0, "kitchen": 8.0, "common_toilet": 4.5, "pooja": 4.0, "lounge": 9.0, "dining": 8.0}
STRETCH = 1.45


def _depth(kind: str, w: float, attached: bool) -> float:
    d = max(MIND[kind], AREA[kind] / w)
    if kind == "common_toilet":
        d = max(4.5, min(d, 6.5))
    elif kind == "pooja":
        d = max(4.0, min(d, 6.0))
    return r2(d + (TOIL_D if attached else 0.0))


def _items(lv: dict, upper: bool, front_in_left: bool) -> list[tuple[str, bool]]:
    """Rooms that go into the free columns (in priority order): (kind, attached)."""
    out: list[tuple[str, bool]] = []
    att = int(lv.get("attached_toilets") or 0)
    beds = int(lv.get("bedrooms") or 0)
    for i in range(beds):
        out.append(("master" if i == 0 else "bedroom", i < att))
    for _ in range(int(lv.get("common_toilets") or 0)):
        out.append(("common_toilet", False))
    if lv.get("pooja"):
        out.append(("pooja", False))
    if upper:  # on an upper floor the kitchen / dining (if asked) are ordinary rooms off the passage
        if lv.get("kitchen"):
            out.append(("kitchen", False))
        if lv.get("dining"):
            out.append(("dining", False))
    if front_in_left:
        out.insert(0, ("lounge", False))
    return out


def _split(items, n_slots):
    """All ways to put the items into n_slots ordered lists (keeps the item order inside each slot)."""
    for assign in itertools.product(range(n_slots), repeat=len(items)):
        slots = [[] for _ in range(n_slots)]
        for it, a in zip(items, assign):
            slots[a].append(it)
        yield slots


def _need(slot, w) -> float | None:
    t = 0.0
    for kind, att in slot:
        if w + 1e-6 < MINW[kind]:
            return None
        t += _depth(kind, w, att)
    return t


def candidates(lv: dict, bw: float, bd: float, multi: bool, template: dict | None, min_frac: float = 0.0):
    """Skeleton variants, best first."""
    upper = template is not None
    car = bool(lv.get("parking_car")) and not upper
    bike = bool(lv.get("parking_bike")) and not upper
    front_kind = "hall" if lv.get("hall") else ("lounge" if lv.get("lounge") else None)
    has_dining = bool(lv.get("dining")) and not upper and bool(lv.get("dining"))
    kit = bool(lv.get("kitchen")) and not upper
    front_in_left = bool(upper and front_kind and template["hd"] <= 0)
    items = _items(lv, upper, front_in_left)
    if upper and front_in_left:
        front_kind = None
    out = []
    lws = [template["lw"]] if upper else [9.5, 10.5, 11.5, 12.5, 13.5]
    rws = [template["rw"]] if upper else [9.0, 10.0, 11.0, 12.0]
    for lw in lws:
        if car and lw < CAR_MIN_W:
            continue
        for rw in rws:
            Wf = template["Wf"] if upper else r2(lw + PW + rw)
            if Wf > bw + 1e-6:
                continue
            bike_w = BIKE_W if (bike and front_kind == "hall") else 0.0
            if front_kind and Wf - lw - bike_w < 9.5:
                continue
            kd = r2(max(8.0, _depth("kitchen", lw, False)))
            if not upper:
                hd = (CAR_D if car else 13.0) if front_kind else 0.0
                dd = (max(9.0, kd) if kit else 9.5) if has_dining else 0.0
                y_rear = hd + dd
                sy = y_rear if multi else None
                p_top = y_rear
                segs_def = [(sy + STAIR_D, None)] if multi else [(y_rear, None)]
                lounge_d = hd
            else:
                hd, dd, y_rear, sy = template["hd"], template["dd"], template["y_rear"], template["sy"]
                if front_kind and hd > 0:
                    lounge_d = hd if (sy - hd) >= 8 else sy
                    p_top = lounge_d
                    segs_def = ([(lounge_d, sy)] if sy - lounge_d >= 8 else [])
                else:
                    lounge_d = 0.0
                    p_top = 0.0
                    segs_def = [(0.0, sy)] if sy >= 8 else []
                segs_def.append((sy + STAIR_D, None))
            left_fixed = []
            if car:
                left_fixed.append(("car", CAR_D))
            if kit:
                left_fixed.append(("kitchen", kd))
            left_y0 = sum(d for _, d in left_fixed)
            n_slots = 1 + len(segs_def)
            for slots in _split(items, n_slots):
                need_l = _need(slots[0], lw)
                if need_l is None:
                    continue
                ends, ok = [left_y0 + need_l], True
                for (y0, y1), sl in zip(segs_def, slots[1:]):
                    nr = _need(sl, rw)
                    if nr is None or (y1 is not None and y0 + nr > y1 + 1e-6):
                        ok = False
                        break
                    ends.append(y0 + nr)
                if not ok:
                    continue
                if upper:
                    Du = template["Du"]
                    if any(e > Du + 1e-6 for e in ends):
                        continue
                else:
                    Du = r2(max(ends + [y_rear + 6.0, (sy + STAIR_D) if sy is not None else 0.0, min_frac * bd]))
                if Du > bd + 1e-6:
                    continue
                mism = abs(max(ends) - min(ends))
                rear = bd - Du
                cost = mism * 2.0 + Du * 0.15 + abs(Wf - min(bw, 25.0)) * 0.3 + abs(rw - 10.0) * 0.2 \
                    + (max(0.0, 3.3 - rear) * 1.5 if not upper else 0.0)
                out.append({"lw": lw, "rw": rw, "Wf": Wf, "Du": Du, "hd": hd, "dd": dd, "y_rear": y_rear, "sy": sy,
                            "p_top": p_top, "lounge_d": lounge_d, "left": slots[0], "segs": slots[1:],
                            "segs_def": segs_def, "left_fixed": left_fixed, "cost": cost, "front_kind": front_kind,
                            "has_dining": has_dining, "bike_w": bike_w})
    out.sort(key=lambda c: c["cost"])
    return out


def _mk(rooms, counters, kind, name, x, y, w, d, parent=None):
    t = {"master": "bedroom", "car": "parking", "bike": "parking"}.get(kind, kind)
    counters[t] = counters.get(t, 0) + 1
    r = {"id": f"{t}_{counters[t]}", "type": t, "name": name, "x": r2(x), "y": r2(y), "w": r2(w), "d": r2(d)}
    if parent:
        r["parent"] = parent
    rooms.append(r)
    return r


FLEX = {"master", "bedroom", "kitchen", "dining", "lounge"}


def _col(rooms, counters, slot, x, w, y0, y1, level0=False):
    """Stack the rooms of one column / segment between y0 and y1. Only bedrooms / lounge / kitchen / dining stretch
    (≤ STRETCH); toilets and pooja keep their size; what is left becomes open terrace (never a filler passage)."""
    span = y1 - y0
    if not slot:
        if span >= 4.0:
            _mk(rooms, counters, "terrace", "Open Yard" if level0 else NAMES["terrace"], x, y0, w, span)
        return
    need = [_depth(k, w, a) for k, a in slot]
    flex = [i for i, (k, a) in enumerate(slot) if k in FLEX]
    extra = span - sum(need)
    depth = list(need)
    if flex and extra > 0:
        base = sum(need[i] for i in flex)
        f = min(STRETCH, (base + extra) / base)
        for i in flex:
            depth[i] = r2(need[i] * f)
    leftover = span - sum(depth)
    if leftover < 3.0 and leftover > 0:  # a sliver: give it to the last flexible room (or the last room)
        depth[(flex[-1] if flex else len(slot) - 1)] += leftover
        leftover = 0.0
    y = y0
    for (kind, att), d in zip(slot, depth):
        d = r2(d)
        if kind in ("master", "bedroom") and att:
            bd_ = r2(d - TOIL_D)
            b = _mk(rooms, counters, kind, NAMES[kind], x, y, w, bd_)
            tw = min(TOIL_W, w)
            _mk(rooms, counters, "toilet", "Attached Toilet", x, y + bd_, tw, TOIL_D, parent=b["id"])
            if w - tw >= 3.0:
                _mk(rooms, counters, "dress", NAMES["dress"], x + tw, y + bd_, w - tw, TOIL_D, parent=b["id"])
            elif w - tw > 0.1:
                rooms[-1]["w"] = r2(w)
        else:
            _mk(rooms, counters, kind, NAMES.get(kind, kind.title()), x, y, w, d)
        y += d
    if y1 - y >= 3.0:
        _mk(rooms, counters, "terrace", "Open Yard" if level0 else NAMES["terrace"], x, y, w, y1 - y)


def build(lv: dict, bw: float, bd: float, multi: bool, template: dict | None, k: int, min_frac: float = 0.0) -> tuple[list[dict], dict]:
    """Return (rooms, info). k = which skeleton variant (0 = best). Coordinates are inside the building."""
    cands = candidates(lv, bw, bd, multi, template, min_frac)
    nm = lv.get("name", "Floor")
    if not cands:
        raise LayoutError([f"{nm}: these rooms do not fit this plot in a connected layout "
                           f"(buildable {bw:.1f} × {bd:.1f} ft)."])
    if k >= len(cands):
        raise LayoutError([f"{nm}: no further layout variant."])
    c = cands[k]
    lw, rw, Wf, Du = c["lw"], c["rw"], c["Wf"], c["Du"]
    upper = template is not None
    rooms: list[dict] = []
    cn: dict = {}
    fk, hd, dd = c["front_kind"], c["hd"], c["dd"]
    hall_w = Wf - lw - c["bike_w"]
    # ---- strip (PASS rooms) ----
    if fk:
        _mk(rooms, cn, fk, NAMES[fk], lw, 0, hall_w, c["lounge_d"] if upper else hd)
        if c["bike_w"]:
            _mk(rooms, cn, "bike", NAMES["parking_bike"], lw + hall_w, 0, c["bike_w"], hd)
        if c["has_dining"]:
            _mk(rooms, cn, "dining", NAMES["dining"], lw, hd, Wf - lw, dd)
    elif c["has_dining"]:
        _mk(rooms, cn, "dining", NAMES["dining"], lw, 0, Wf - lw, dd)
    _mk(rooms, cn, "passage", "Passage", lw, c["p_top"], PW, Du - c["p_top"])
    # ---- left column ----
    y = 0.0
    for kind, d in c["left_fixed"]:
        _mk(rooms, cn, kind, NAMES["parking_car"] if kind == "car" else NAMES["kitchen"], 0, y, lw, d)
        y += d
    _col(rooms, cn, c["left"], 0, lw, y, Du, not upper)
    # ---- right column ----
    rx, sy = lw + PW, c["sy"]
    if sy is not None:
        _mk(rooms, cn, "stair", NAMES["stair"], rx, sy, rw, STAIR_D)
    for (y0, y1), sl in zip(c["segs_def"], c["segs"]):
        _col(rooms, cn, sl, rx, rw, y0, Du if y1 is None else y1, not upper)
    info = {"spine": True, "lw": lw, "rw": rw, "Wf": Wf, "Du": Du, "hd": hd, "dd": dd, "y_rear": c["y_rear"],
            "sy": sy, "stair_side": None, "k": k}
    return rooms, info
