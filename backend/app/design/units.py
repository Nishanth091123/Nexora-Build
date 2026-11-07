"""1.19 Several houses on one floor (owner + rental units).

Layout (stair on one side, say left):
    ┌─────────────── back ───────────────┐
    │            LAST HOUSE              │   full width; its hall touches the lobby
    ├──────┬─────────────────────────────┤
    │LOBBY │        HOUSE A …            │   each earlier house: the strip beside the lobby,
    │      │                             │   its hall on the lobby side
    ├──────┤                             │
    │STAIR │                             │
    └──────┴──────── road side ──────────┘
Every house is laid out by the normal room packer inside its own rectangle, so every room is reachable inside the
house; its MAIN DOOR opens from the stair / common lobby. Rooms of different houses never get a door between them.
"""
from __future__ import annotations

from .layout import SIZES, Cell, LayoutError, build_level, level_items, r2

LETTERS = "ABCDEF"


def _need(u: dict) -> float:
    """Floor area a house asks for (desired room sizes + 15 % walls / passage)."""
    front, rest, _ = level_items({**u, "lounge": False}, False)
    a = sum(c.dw * c.dd for c in front + rest)
    return a * 1.15


def _touches_x(rooms: list[dict], kind: tuple, x: float) -> bool:
    return any(r["type"] in kind and (abs(r["x"] - x) < 0.05 or abs(r["x"] + r["w"] - x) < 0.05) for r in rooms)


def _mirror(rooms: list[dict], w: float) -> list[dict]:
    return [{**r, "x": r2(w - r["x"] - r["w"])} for r in rooms]


LIT = ("bedroom", "master", "kitchen", "hall")


def _flip_y(rooms: list[dict], d: float) -> list[dict]:
    return [{**r, "y": r2(d - r["y"] - r["d"])} for r in rooms]


def _lit(rooms: list[dict], zw: float, zd: float, ext: tuple) -> int:
    """How many living rooms touch an outside edge of the house (window possible)."""
    n = 0
    for r in rooms:
        if r["type"] not in LIT:
            continue
        if (("front" in ext and r["y"] < 0.05) or ("back" in ext and abs(r["y"] + r["d"] - zd) < 0.05) or
                ("left" in ext and r["x"] < 0.05) or ("right" in ext and abs(r["x"] + r["w"] - zw) < 0.05)):
            n += 1
    return n


def _house(u: dict, zw: float, zd: float, comp: dict, lobby_side: str, name: str, door_at: tuple | None = None,
           ext: tuple = ("front", "back", "left", "right"), lobby_from: float = 0.0) -> list[dict]:
    """Rooms of one house in its own rectangle (0,0)-(zw,zd).
    The hall touches the lobby side (x edge), or with door_at = (x0, x1) the FRONT edge between x0 and x1.
    Among the layouts that work, the one with the most living rooms on an outside wall (ext edges) wins."""
    lv = {"name": name, "stilt": False, "bedrooms": u["bedrooms"], "attached_toilets": u["attached_toilets"],
          "common_toilets": u["common_toilets"], "kitchen": True, "hall": True, "dining": u.get("dining", False),
          "pooja": u.get("pooja", False), "parking_car": False, "parking_bike": False, "lounge": False}
    edge = 0.0 if lobby_side == "left" else zw
    from .layout import _build_level  # 1.17 spine logic
    tries = []
    for fn in (lambda: build_level(lv, zw, zd, comp, False, None), lambda: _build_level(lv, zw, zd, comp, False, None, "left"),
               lambda: _build_level(lv, zw, zd, comp, False, None, "right")):
        try:
            tries.append(fn()[0])
        except LayoutError:
            pass
    best, score = None, -1
    for rooms in tries:
        for c0 in (rooms, _flip_y(rooms, zd)):
            for cand in (c0, _mirror(c0, zw)):
                if door_at:
                    ok = any(r["type"] == "hall" and r["y"] < 0.05 and
                             min(r["x"] + r["w"], door_at[1]) - max(r["x"], door_at[0]) >= 3.5 for r in cand)
                else:  # hall on the lobby side, facing the lobby (not the stair flight) for at least 3.5 ft
                    ok = any(r["type"] == "hall" and (abs(r["x"] - edge) < 0.05 or abs(r["x"] + r["w"] - edge) < 0.05)
                             and r["y"] + r["d"] - max(r["y"], lobby_from) >= 3.5 for r in cand)
                if ok:
                    sc = _lit(cand, zw, zd, ext)
                    if sc > score:
                        best, score = cand, sc
    if best:
        return best
    if not tries:
        need = _need(u)
        raise LayoutError([f"{name}: a {u['bhk']} BHK needs about {need:.0f} sq ft but only {zw * zd:.0f} sq ft "
                           f"({zw:.1f} × {zd:.1f} ft) is left for it on this floor."])
    raise LayoutError([f"{name}: the hall cannot be placed next to the common lobby on this plot."])


def build_units_level(lv: dict, bw: float, bd: float, comp: dict, template: dict | None, level_index: int) -> tuple[list[dict], dict]:
    units = lv.get("units") or []
    if level_index == 0 and lv.get("parking_car"):
        raise LayoutError([f"{lv['name']}: car parking with several houses on the ground floor – put the parking on a stilt "
                           f"floor, or keep one house on the ground floor."])
    sw = r2(template["stair_w"] if template and template.get("stair_w") else SIZES["stair"][0])
    fd = r2(template["front_d"] if template and template.get("front_d") else SIZES["stair"][1])
    side = template.get("stair_side") if template and template.get("stair_side") in ("left", "right") else "left"
    zw = r2(bw - sw)
    if zw < 12:
        raise LayoutError([f"{lv['name']}: the building is too narrow ({bw:.1f} ft) for houses beside a staircase."])
    if len(units) == 1:
        u = units[0]
        rooms = _house(u, zw, bd, comp, side, f"{lv['name']} – House {u['label']}")
        x0 = sw if side == "left" else 0.0
        out = [{**r, "x": r2(r["x"] + x0)} for r in rooms]
        stair = {"id": "stair_1", "type": "stair", "name": "Staircase", "x": 0.0 if side == "left" else zw, "y": 0.0, "w": sw, "d": fd}
        lobby = {"id": "passage_lobby", "type": "passage", "name": "Common Lobby", "x": stair["x"], "y": fd, "w": sw, "d": r2(bd - fd)}
        out = _tag(out, u) + [stair] + ([lobby] if bd - fd > 0.5 else [])
        return out, {"front_d": fd, "mid_d": 0, "stair_w": sw, "stair_side": side}
    x_lobby = 0.0 if side == "left" else zw
    x_zone = sw if side == "left" else 0.0
    k = len(units)
    errors: list[str] = []
    # try: given order, then the bigger houses at the back; full dining first, then dining inside the hall
    orders = [list(units)]
    alt = sorted(units, key=lambda u: (u["bhk"], u.get("use") == "owner"))
    if alt != orders[0]:
        orders.append(alt)
    for merge_dining in (False, True):
        for order in orders:
            us = [{**u, "dining": u.get("dining") and not merge_dining} for u in order]
            got = _stack(us, bw, bd, zw, sw, fd, side, x_lobby, x_zone, comp, lv["name"], errors)
            if got:
                out, y = got
                out.append({"id": "stair_1", "type": "stair", "name": "Staircase", "x": x_lobby, "y": 0.0, "w": sw, "d": fd})
                if y - fd > 0.5:
                    out.append({"id": "passage_lobby", "type": "passage", "name": "Common Lobby", "x": x_lobby, "y": fd,
                                "w": sw, "d": r2(y - fd)})
                notes = []
                if merge_dining and any(u.get("dining") for u in units):
                    notes.append(f"{lv['name']}: dining is part of the hall in each house (no room for a separate dining).")
                return out, {"front_d": fd, "mid_d": 0, "stair_w": sw, "stair_side": side, "notes": notes}
    total = sum(_need(u) for u in units) / 1.25
    avail = bw * bd - sw * fd
    raise LayoutError([f"{lv['name']}: {k} houses ({', '.join(str(u['bhk']) + ' BHK' for u in units)}) need at least about "
                       f"{total:.0f} sq ft; this floor has {avail:.0f} sq ft after the staircase ({bw:.1f} × {bd:.1f} ft). "
                       f"Options: (1) fewer houses on this floor, (2) smaller houses (e.g. 1 BHK instead of 2 BHK), "
                       f"(3) move one house to another floor, (4) reduce setbacks if the rules allow."])


def _stack(us: list[dict], bw, bd, zw, sw, fd, side, x_lobby, x_zone, comp, lname, errors, tight: bool = False):
    """Houses one behind the other: all but the last beside the lobby strip, the last one full width behind it.
    Each house first gets the smallest depth it packs in; the spare depth is then shared in proportion to need."""
    k = len(us)
    far = "right" if side == "left" else "left"
    door = (x_lobby, x_lobby + sw)

    def ext_of(i):
        if i == k - 1:
            return ("back", "left", "right")
        return ("front", far) if i == 0 else (far,)

    def make(i, d, y0):
        u = us[i]
        nm = f"{lname} – House {u['label']}"
        if i == k - 1:
            return _house(u, bw, d, comp, side, nm, door_at=door, ext=ext_of(i))
        return _house(u, zw, d, comp, side, nm, ext=ext_of(i), lobby_from=max(0.0, fd - y0))

    mins = []
    for i in range(k):
        d, got = (fd + 3.5 if i == 0 and k > 1 else 10.0), None
        y0 = sum(mins)
        while d <= bd:
            try:
                got = make(i, d, y0)
                break
            except LayoutError as e:
                errors.append(e.questions[0])
                d = r2(d + 0.5)
        if got is None:
            return None
        mins.append(d)
    front = sum(mins[:-1])
    if front < fd + 0.5:  # the lobby strip must at least pass the staircase
        mins[k - 2] = r2(mins[k - 2] + fd + 0.5 - front)
    spare = bd - sum(mins)
    if spare < 0:
        return None
    needs = [_need(u) / (bw if i == k - 1 else zw) for i, u in enumerate(us)]
    depths = [r2(m + int(spare * n / sum(needs) * 2) / 2) for m, n in zip(mins, needs)]
    depths[-1] = r2(bd - sum(depths[:-1]))
    out: list[dict] = []
    y = 0.0
    for i, u in enumerate(us):
        try:
            rooms = make(i, depths[i], y)
        except LayoutError:
            try:
                rooms = make(i, mins[i], y) if i < k - 1 else None
            except LayoutError:
                rooms = None
            if rooms is None:
                return None
            depths[-1] = r2(depths[-1] + depths[i] - mins[i])
            depths[i] = mins[i]
        dx = x_zone if i < k - 1 else 0.0
        out += _tag([{**r, "x": r2(r["x"] + dx), "y": r2(r["y"] + y)} for r in rooms], u)
        y = r2(y + depths[i]) if i < k - 1 else y
    return out, y


def _tag(rooms: list[dict], u: dict) -> list[dict]:
    lab = u["label"]
    use = {"rental": "Rental", "owner": "Owner"}.get(u.get("use") or "", "")
    out = []
    for r in rooms:
        q = dict(r)
        q["id"] = f"u{lab}_{r['id']}"
        if r.get("parent"):
            q["parent"] = f"u{lab}_{r['parent']}"
        q["unit"] = lab
        q["unit_name"] = f"House {lab} – {u['bhk']} BHK" + (f" ({use})" if use else "")
        q["name"] = f"{r['name']} ({lab})"
        out.append(q)
    return out
