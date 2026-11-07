"""Walls, doors, windows and quantity summary derived from room rectangles.

Rooms are the single source of truth: change a room and walls, openings and the estimate follow.
Units: feet. Room coordinates are relative to the building origin (front-left corner of the building).
"""
from __future__ import annotations

STEP = 0.25  # sampling resolution (ft)
FT_M = 0.3048

OPEN_PAIRS = {frozenset(p) for p in [("hall", "dining"), ("dining", "passage"), ("lounge", "passage"),
                                      ("passage", "stair"), ("parking", "parking"), ("hall", "passage"),
                                      ("lounge", "stair"), ("parking", "stair"),
                                      ("passage", "passage")]}
OPEN_OUTSIDE = {"parking"}  # no external wall on open parking sides
OPEN_TYPES = {"terrace", "balcony", "sitout"}  # open to sky / partly open – parapet instead of wall
HABITABLE = {"bedroom", "hall", "lounge", "kitchen", "dining"}
DOOR_W = {"main_door": 3.5, "door": 3.0, "toilet_door": 2.5, "opening": 3.0, "pooja_door": 2.5}
WIN = {"bedroom": 5, "hall": 6, "lounge": 5, "kitchen": 4, "dining": 4, "pooja": 2, "stair": 3, "toilet": 2}
WIN_H = {"toilet": 1.5}


def room_at(rooms: list[dict], x: float, y: float) -> dict | None:
    for r in rooms:
        if r["x"] - 1e-6 <= x <= r["x"] + r["w"] + 1e-6 and r["y"] - 1e-6 <= y <= r["y"] + r["d"] + 1e-6:
            return r
    return None


def wall_kind(a: dict | None, b: dict | None) -> str | None:
    """Classify the boundary between room a and room b (None = outside)."""
    if a is None and b is None:
        return None
    if a is None or b is None:
        r = a or b
        if r["type"] in OPEN_TYPES:
            return "parapet"
        return None if r["type"] in OPEN_OUTSIDE else "ext"
    if a is b:
        return None
    ta, tb = a["type"], b["type"]
    if a.get("unit") != b.get("unit"):
        return "int230"  # 1.19: a 9" wall always separates two houses (and a house from the common lobby / stair)
    if ta in OPEN_TYPES and tb in OPEN_TYPES:
        return None
    if ta in OPEN_TYPES or tb in OPEN_TYPES:
        return "ext"  # the room's outer wall faces the open terrace
    if frozenset((ta, tb)) in OPEN_PAIRS:
        return None
    # dress area is part of its bedroom – no wall between them
    if (ta == "dress" and a.get("parent") == b["id"]) or (tb == "dress" and b.get("parent") == a["id"]):
        return None
    if "toilet" in (ta, tb) or "common_toilet" in (ta, tb):
        t, o = (a, b) if ta in ("toilet", "common_toilet") else (b, a)
        if t.get("parent") and (o["id"] == t["parent"] or o.get("parent") == t["parent"]):
            return "int115"
    return "int230"


def walls(rooms: list[dict]) -> list[dict]:
    """Return merged wall segments: {kind, x1, y1, x2, y2, a, b} (a/b = room ids on each side)."""
    if not rooms:
        return []
    xs = sorted({round(v, 3) for r in rooms for v in (r["x"], r["x"] + r["w"])})
    ys = sorted({round(v, 3) for r in rooms for v in (r["y"], r["y"] + r["d"])})
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    eps = 0.01
    segs = []

    def scan(horizontal: bool, c: float, lo: float, hi: float):
        cur = None
        t = lo
        while t < hi - 1e-9:
            m = t + STEP / 2
            if horizontal:
                a, b = room_at(rooms, m, c - eps), room_at(rooms, m, c + eps)
            else:
                a, b = room_at(rooms, c - eps, m), room_at(rooms, c + eps, m)
            k = wall_kind(a, b)
            key = (k, a["id"] if a else None, b["id"] if b else None) if k else None
            if cur and key == cur["key"]:
                cur["end"] = t + STEP
            else:
                if cur:
                    segs.append(cur)
                cur = {"key": key, "start": t, "end": t + STEP} if key else None
            t += STEP
        if cur:
            segs.append(cur)
        for s in [s for s in segs if "h" not in s]:
            s["h"] = horizontal
            s["c"] = c

    for y in ys:
        scan(True, y, x0, x1)
    for x in xs:
        scan(False, x, y0, y1)
    out = []
    for s in segs:
        k, a, b = s["key"]
        if s["h"]:
            out.append({"kind": k, "x1": s["start"], "y1": s["c"], "x2": s["end"], "y2": s["c"], "a": a, "b": b})
        else:
            out.append({"kind": k, "x1": s["c"], "y1": s["start"], "x2": s["c"], "y2": s["end"], "a": a, "b": b})
    return out


def seg_len(s: dict) -> float:
    return abs(s["x2"] - s["x1"]) + abs(s["y2"] - s["y1"])


def shared(walls_: list[dict], rid: str, other_types: list[str], rooms_by_id: dict, open_too: bool = False,
           rooms: list[dict] | None = None) -> tuple[dict | None, str | None]:
    """Longest wall (or open boundary) between room rid and a neighbour of the given types (priority order)."""
    for t in other_types:
        best = None
        for w in walls_:
            if rid not in (w["a"], w["b"]):
                continue
            other = w["b"] if w["a"] == rid else w["a"]
            if other and rooms_by_id[other]["type"] == t and seg_len(w) >= 2.5:
                if not best or seg_len(w) > seg_len(best):
                    best = w
        if best:
            return best, t
    return None, None


def _on_line(o: dict, w: dict) -> bool:
    if w["y1"] == w["y2"]:
        return abs(o["y1"] - o["y2"]) < 1e-6 and abs(o["y1"] - w["y1"]) < 0.01
    return abs(o["x1"] - o["x2"]) < 1e-6 and abs(o["x1"] - w["x1"]) < 0.01


def place_free(w: dict, width: float, ops: list[dict], gap: float = 1.0, prefer_end: bool = False) -> dict | None:
    """1.15: like place(), but never on top of a door / window already on that wall (keeps `gap` ft between).
    Picks the free stretch nearest the middle of the wall; None when it does not fit."""
    horiz = w["y1"] == w["y2"]
    a0 = min(w["x1"], w["x2"]) if horiz else min(w["y1"], w["y2"])
    a1 = max(w["x1"], w["x2"]) if horiz else max(w["y1"], w["y2"])
    busy = sorted(((min(o["x1"], o["x2"]) if horiz else min(o["y1"], o["y2"])) - gap,
                   (max(o["x1"], o["x2"]) if horiz else max(o["y1"], o["y2"])) + gap) for o in ops if _on_line(o, w))
    if not busy:
        if seg_len(w) + 1e-6 < width + 1.0:
            return None
        return place(w, width, prefer_end)
    free, cur = [], a0 + 0.5
    for b0, b1 in busy:
        if b0 > cur:
            free.append((cur, b0))
        cur = max(cur, b1)
    if a1 - 0.5 > cur:
        free.append((cur, a1 - 0.5))
    mid = (a1 - 0.75 - width / 2) if prefer_end else (a0 + a1) / 2
    best = None
    for f0, f1 in free:
        if f1 - f0 + 1e-6 < width:
            continue
        c = min(max(mid, f0 + width / 2), f1 - width / 2)  # as near the middle as the free stretch allows
        if best is None or abs(c - mid) < abs(best - mid):
            best = c
    if best is None:
        return None
    s0 = best - width / 2
    if horiz:
        return {"x1": round(s0, 2), "y1": w["y1"], "x2": round(s0 + width, 2), "y2": w["y1"], "w": round(width, 2)}
    return {"x1": w["x1"], "y1": round(s0, 2), "x2": w["x1"], "y2": round(s0 + width, 2), "w": round(width, 2)}


def place(w: dict, width: float, prefer_end: bool = False) -> dict:
    L = seg_len(w)
    width = min(width, max(1.5, L - 1.0))
    if prefer_end and L > width + 1.5:
        start = L - width - 0.75
    else:
        start = (L - width) / 2
    if w["y1"] == w["y2"]:
        x = min(w["x1"], w["x2"]) + start
        return {"x1": round(x, 2), "y1": w["y1"], "x2": round(x + width, 2), "y2": w["y1"], "w": round(width, 2)}
    y = min(w["y1"], w["y2"]) + start
    return {"x1": w["x1"], "y1": round(y, 2), "x2": w["x1"], "y2": round(y + width, 2), "w": round(width, 2)}


# 1.17: who may open into whom (priority order). A bedroom NEVER opens into another bedroom.
COMMON = ["passage", "lounge", "hall", "dining", "stair"]
ACCESS = {
    "bedroom": COMMON + ["kitchen"],
    "toilet": COMMON,  # attached toilets first try their own bedroom / dress (below)
    "common_toilet": ["passage", "dining", "hall", "lounge", "stair", "utility", "kitchen"],
    "kitchen": ["dining", "hall", "lounge", "passage", "stair", "utility"],
    "dining": ["hall", "lounge", "passage", "kitchen", "stair"],
    "hall": ["dining", "lounge", "passage", "stair"],
    "lounge": ["passage", "stair", "hall", "dining"],
    "passage": ["stair", "hall", "lounge", "dining", "kitchen", "utility"],  # wash area behind the kitchen is normal
    "stair": ["passage", "hall", "lounge", "dining", "parking", "sitout"],
    "utility": ["kitchen", "dining", "passage", "hall", "lounge", "stair"],
    "store": ["kitchen", "dining", "passage", "hall", "lounge", "stair", "utility"],
    "pooja": ["hall", "dining", "lounge", "passage", "stair", "kitchen"],
    "terrace": ["stair", "lounge", "passage", "hall", "dining", "bedroom"],
    "balcony": ["bedroom", "lounge", "hall", "dining", "passage"],
    "sitout": ["hall", "lounge", "dining", "bedroom", "passage"],
    "study": COMMON, "office": COMMON, "guest": COMMON,
}
KIND = {"bedroom": ("door", 3.0), "toilet": ("toilet_door", 2.5), "common_toilet": ("toilet_door", 2.5),
        "kitchen": ("opening", 3.0), "dining": ("opening", 3.0), "hall": ("opening", 3.0), "lounge": ("opening", 3.0),
        "passage": ("opening", 3.0), "stair": ("opening", 3.0), "utility": ("door", 2.5), "store": ("door", 2.5),
        "pooja": ("pooja_door", 2.5), "terrace": ("door", 3.0), "balcony": ("door", 3.0), "sitout": ("door", 3.0)}
NO_ACCESS_NEEDED = {"dress", "parking"}
# rooms are opened up in this order: circulation first, then bedrooms, … attached toilets last
ORDER = {"hall": 0, "lounge": 0, "dining": 0, "passage": 0, "stair": 0, "kitchen": 1, "bedroom": 2, "utility": 3,
         "store": 3, "pooja": 3, "common_toilet": 4, "terrace": 4, "balcony": 4, "sitout": 4, "toilet": 5}


def _wall_between(ws: list[dict], a: str, b: str) -> list[dict]:
    return [w for w in ws if {w["a"], w["b"]} == {a, b}]


def _shared_open(a: dict, b: dict) -> float:
    """Length of the boundary between two rooms (used when there is no wall between them)."""
    if abs(a["x"] + a["w"] - b["x"]) < 0.02 or abs(b["x"] + b["w"] - a["x"]) < 0.02:
        return min(a["y"] + a["d"], b["y"] + b["d"]) - max(a["y"], b["y"])
    if abs(a["y"] + a["d"] - b["y"]) < 0.02 or abs(b["y"] + b["d"] - a["y"]) < 0.02:
        return min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    return 0.0


def _door_on(o: dict, w: dict) -> bool:
    if not _on_line(o, w):
        return False
    if w["y1"] == w["y2"]:
        return min(max(o["x1"], o["x2"]), max(w["x1"], w["x2"])) - max(min(o["x1"], o["x2"]), min(w["x1"], w["x2"])) > 0.5
    return min(max(o["y1"], o["y2"]), max(w["y1"], w["y2"])) - max(min(o["y1"], o["y2"]), min(w["y1"], w["y2"])) > 0.5


def reachable(lv: dict, ops: list[dict], ws: list[dict] | None = None, level_index: int = 0) -> tuple[set, set]:
    """1.17: rooms you can walk into (from the main door on the ground floor, from the staircase above).
    Returns (reached ids, ids that need access but cannot be reached)."""
    rooms = lv["rooms"]
    ws = ws if ws is not None else walls(rooms)
    by = {r["id"]: r for r in rooms}
    doors = [o for o in ops if o["type"] not in ("window", "vent")]
    adj: dict[str, set] = {r["id"]: set() for r in rooms}
    for i, a in enumerate(rooms):
        for b in rooms[i + 1:]:
            if wall_kind(a, b) is None and _shared_open(a, b) >= 2.5:
                adj[a["id"]].add(b["id"]); adj[b["id"]].add(a["id"])
    for w in ws:
        if w["a"] and w["b"] and any(_door_on(o, w) for o in doors):
            adj[w["a"]].add(w["b"]); adj[w["b"]].add(w["a"])
    roots = {o["room"] for o in doors if o["type"] == "main_door"}
    roots |= {r["id"] for r in rooms if r["type"] == "parking"}
    if level_index > 0 or lv.get("stilt") or not roots:
        roots |= {r["id"] for r in rooms if r["type"] == "stair"}
    if level_index == 0 and not lv.get("stilt"):
        roots |= {r["id"] for r in rooms if r["type"] == "sitout"}  # ground sit-out is outside
    seen, todo = set(roots), list(roots)
    while todo:
        x = todo.pop()
        for y in adj.get(x, ()):
            if y not in seen:
                seen.add(y); todo.append(y)
    need = {r["id"] for r in rooms if r["type"] not in NO_ACCESS_NEEDED}
    return seen, need - seen


def level_openings(lv: dict, level_index: int, building_d: float) -> tuple[list[dict], list[str]]:
    rooms = lv["rooms"]
    by_id = {r["id"]: r for r in rooms}
    ws = walls(rooms)
    ops, warnings = [], []
    n = 0

    def add(rid, kind, h, seg):
        nonlocal n
        n += 1
        ops.append({"id": f"op{n}", "room": rid, "type": kind, "h": h, **seg})

    def door_on_wall(rid, kind, width, h, cands, prefer_end=False) -> bool:
        """1.17: put the door on a FREE part of one of these walls (longest first) – never dropped silently."""
        for w in sorted(cands, key=seg_len, reverse=True):
            for wd in (width, 2.5 if width > 2.5 else width):
                spot = place_free(w, wd, ops, gap=0.5, prefer_end=prefer_end)
                if spot:
                    add(rid, kind, h, spot)
                    return True
        return False

    # 1.19: several houses on this floor → each gets its own main door from the stair / common lobby
    unit_labels = sorted({r["unit"] for r in rooms if r.get("unit")})
    for lab in unit_labels:
        hall = next((r for r in rooms if r.get("unit") == lab and r["type"] in ("hall", "lounge")), None)
        if not hall:
            continue
        common = [w for w in ws if hall["id"] in (w["a"], w["b"]) and seg_len(w) >= 3.5 and
                  by_id.get(w["b"] if w["a"] == hall["id"] else w["a"], {}).get("type") in ("stair", "passage")
                  and not by_id.get(w["b"] if w["a"] == hall["id"] else w["a"], {}).get("unit")]
        lobby = [w for w in common if by_id.get(w["b"] if w["a"] == hall["id"] else w["a"], {}).get("type") == "passage"]
        if lobby and door_on_wall(hall["id"], "main_door", 3.5, 7, lobby):  # lobby first, the stair flight only if no lobby
            continue
        if level_index == 0 and not common:
            common = [w for w in ws if w["kind"] == "ext" and hall["id"] in (w["a"], w["b"]) and w["y1"] == w["y2"]
                      and abs(w["y1"] - min(rr["y"] for rr in rooms)) < 0.01]
        if not door_on_wall(hall["id"], "main_door", 3.5, 7, common):
            warnings.append(f"{lv['name']}: {hall.get('unit_name') or 'house ' + lab} has no wall on the common lobby for its main door.")
    # main door on the front (road side) wall
    if level_index == 0 and not lv.get("stilt") and not unit_labels:
        for r in rooms:
            if r["type"] not in ("hall", "lounge"):
                continue
            rid = r["id"]
            front = [w for w in ws if w["kind"] == "ext" and rid in (w["a"], w["b"]) and w["y1"] == w["y2"]
                     and abs(w["y1"] - min(rr["y"] for rr in rooms)) < 0.01]
            if not front:  # hall behind parking / sit-out: main door between them and the hall
                front = [w for w in ws if rid in (w["a"], w["b"]) and w["y1"] == w["y2"] and
                         ({by_id.get(w["a"], {}).get("type"), by_id.get(w["b"], {}).get("type")} & {"parking", "sitout"})]
            if front and door_on_wall(rid, "main_door", 3.5, 7, [max(front, key=seg_len)]):
                break
    # attached toilets → their own bedroom (or its dress area)
    for r in rooms:
        if r["type"] == "toilet" and r.get("parent"):
            target = r["parent"]
            mine = {target} | {x["id"] for x in rooms if x.get("parent") == target and x["type"] == "dress"}
            cand = [w for w in ws if r["id"] in (w["a"], w["b"]) and seg_len(w) >= 3.0 and
                    ((w["b"] if w["a"] == r["id"] else w["a"]) in mine)]
            dress = [w for w in cand if by_id.get(w["b"] if w["a"] == r["id"] else w["a"], {}).get("type") == "dress"]
            door_on_wall(r["id"], "toilet_door", 2.5, 7, dress or cand)
    # every other room: open it into the best room you can already reach (repeat until nothing changes)
    for _ in range(len(rooms) + 2):
        seen, missing = reachable(lv, ops, ws, level_index)
        if not missing:
            break
        progress = False
        for r in sorted((by_id[i] for i in missing), key=lambda q: (ORDER.get(q["type"], 3), q["id"])):
            allowed = ACCESS.get(r["type"], COMMON)
            for t in allowed:
                cands = [w for x in rooms if x["id"] in seen and x["type"] == t and x.get("unit") == r.get("unit")
                         for w in _wall_between(ws, r["id"], x["id"])
                         if w["kind"] and w["kind"] != "parapet" and seg_len(w) >= 3.0]
                kind, width = KIND.get(r["type"], ("door", 3.0))
                if r["type"] in ("terrace", "balcony", "sitout") and t in ("bedroom", "lounge", "hall", "dining", "passage", "stair"):
                    kind = "door"
                if cands and door_on_wall(r["id"], kind, width, 6 if kind == "pooja_door" else 7, cands, prefer_end=r["type"] == "bedroom"):
                    progress = True
                    break
            if progress:
                break  # re-check what is reachable now
        if not progress:
            break
    seen, missing = reachable(lv, ops, ws, level_index)
    for rid in sorted(missing):
        r = by_id[rid]
        if r["type"] == "bedroom":
            warnings.append(f"{lv['name']}: {r['name']} has no access from the hall / passage – a bedroom never opens "
                            f"into another bedroom; move it next to the hall, dining or passage.")
        else:
            warnings.append(f"{lv['name']}: {r['name']} cannot be reached – move it next to a common area.")

    for r in rooms:
        t = r["type"]
        rid = r["id"]
        # windows on the longest external wall
        if t in WIN:
            ext = [w for w in ws if w["kind"] == "ext" and rid in (w["a"], w["b"]) and seg_len(w) >= WIN[t] + 1]
            spot = None
            y_front = min(q["y"] for q in rooms)  # 1.20: a living room / bedroom on the road side gets its window on the front
            on_front = lambda w: (t in HABITABLE and w["y1"] == w["y2"] and abs(w["y1"] - y_front) < 0.01)  # noqa: E731
            for w in sorted(ext, key=lambda w: (on_front(w), seg_len(w)), reverse=True):  # 1.15: never on top of the main door / another opening
                spot = place_free(w, WIN[t], ops)
                if spot:
                    break
            if spot:
                add(rid, "vent" if t == "toilet" or t == "common_toilet" else "window", WIN_H.get(t, 4), spot)
            elif ext and t in HABITABLE:
                warnings.append(f"{lv['name']}: {r['name']} – no free outside wall length for a window next to the door.")
            elif t in HABITABLE:
                warnings.append(f"{lv['name']}: {r['name']} has no outside wall for a window – add a light well / "
                                f"duct or rearrange.")
        if t == "common_toilet":
            ext = [w for w in ws if w["kind"] == "ext" and rid in (w["a"], w["b"]) and seg_len(w) >= 3]
            for w in sorted(ext, key=seg_len, reverse=True):
                spot = place_free(w, 2, ops)
                if spot:
                    add(rid, "vent", 1.5, spot)
                    break
    if level_index > 0 or lv.get("stilt"):
        pass  # upper floors are entered from the staircase (open)
    return ops, warnings


def check_rooms(lv: dict, bw: float, bd: float) -> list[str]:
    warns = []
    rooms = lv["rooms"]
    for r in rooms:
        if r["w"] <= 0 or r["d"] <= 0:
            warns.append(f"{lv['name']}: {r['name']} has zero size.")
        if r["x"] < -0.01 or r["y"] < -0.01 or r["x"] + r["w"] > bw + 0.01 or r["y"] + r["d"] > bd + 0.01:
            warns.append(f"{lv['name']}: {r['name']} goes outside the buildable area (setback violation).")
    for i, a in enumerate(rooms):
        for b in rooms[i + 1:]:
            ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            oy = min(a["y"] + a["d"], b["y"] + b["d"]) - max(a["y"], b["y"])
            if ox > 0.05 and oy > 0.05:
                warns.append(f"{lv['name']}: {a['name']} overlaps {b['name']}.")
    return warns


def add_openings(plan: dict) -> dict:
    """(Re)derive openings, walls and the quantity summary for every level. Mutates and returns plan."""
    bw, bd = plan["building"]["w"], plan["building"]["d"]
    all_warn = []
    per = []
    for i, lv in enumerate(plan["levels"]):
        warns = check_rooms(lv, bw, bd)
        ops, w2 = level_openings(lv, i, bd)
        lv["openings"] = ops
        per.append(warns + w2)
    from .sheets import apply_specs  # 1.10: door/window sizes edited in the schedule
    spec_warn = apply_specs(plan)
    for lv in plan["levels"]:  # 1.15: bigger sizes from the schedule must not push a window into a door
        spec_warn += separate_openings(lv)
    for i, lv in enumerate(plan["levels"]):
        lv["walls"] = walls(lv["rooms"])
        lv["summary"] = summarize_level(lv)
        lv["warnings"] = per[i] + [w for w in spec_warn if w.startswith(lv["name"] + ":")]
        all_warn += lv["warnings"]
    plan["warnings"] = all_warn
    plan["summary"] = summarize_plan(plan)
    return plan


def separate_openings(lv: dict) -> list[str]:
    """Move a window / vent that touches a door or another window on the same wall to a free part of that wall."""
    warns = []
    ws = walls(lv["rooms"])
    ops = lv.get("openings", [])
    rank = {"main_door": 0, "door": 1, "pooja_door": 1, "toilet_door": 1, "opening": 1, "window": 2, "vent": 3}
    for o in sorted(ops, key=lambda x: rank.get(x["type"], 2)):
        if o["type"] not in ("window", "vent"):
            continue
        others = [x for x in ops if x is not o]
        horiz = abs(o["y1"] - o["y2"]) < 1e-6
        s0, s1 = (sorted((o["x1"], o["x2"])) if horiz else sorted((o["y1"], o["y2"])))
        clash = False
        for x in others:
            if horiz != (abs(x["y1"] - x["y2"]) < 1e-6):
                continue
            if horiz and abs(x["y1"] - o["y1"]) > 0.01 or (not horiz and abs(x["x1"] - o["x1"]) > 0.01):
                continue
            t0, t1 = (sorted((x["x1"], x["x2"])) if horiz else sorted((x["y1"], x["y2"])))
            if min(s1, t1) - max(s0, t0) > -0.75:
                clash = True
                break
        if not clash:
            continue
        mid = (s0 + s1) / 2
        wall = next((w for w in ws if _on_line(o, w) and
                     (min(w["x1"], w["x2"]) if horiz else min(w["y1"], w["y2"])) - 0.01 <= mid <=
                     (max(w["x1"], w["x2"]) if horiz else max(w["y1"], w["y2"])) + 0.01), None)
        spot = place_free(wall, s1 - s0, others, gap=0.75) if wall else None
        if spot:
            o.update({k: spot[k] for k in ("x1", "y1", "x2", "y2")})
        else:
            warns.append(f"{lv['name']}: a {o['type']} is too close to a door – make the wall longer or the window smaller.")
    return warns


def summarize_level(lv: dict) -> dict:
    ws = lv.get("walls") or walls(lv["rooms"])
    rooms = lv["rooms"]
    lens = {"ext": 0.0, "int230": 0.0, "int115": 0.0, "parapet": 0.0}
    for w in ws:
        lens[w["kind"]] += seg_len(w)
    xs = [r["x"] for r in rooms] + [r["x"] + r["w"] for r in rooms]
    ys = [r["y"] for r in rooms] + [r["y"] + r["d"] for r in rooms]
    bw = (max(xs) - min(xs)) if rooms else 0
    bd = (max(ys) - min(ys)) if rooms else 0
    terrace = sum(r["w"] * r["d"] for r in rooms if r["type"] == "terrace")

    ops = lv.get("openings", [])
    cnt = lambda t: sum(1 for r in rooms if r["type"] == t)
    win = [o for o in ops if o["type"] in ("window", "vent")]
    return {
        "width_ft": round(bw, 2), "depth_ft": round(bd, 2),
        "builtup_sqft": round(bw * bd - terrace, 1), "terrace_sqft": round(terrace, 1),
        "carpet_sqft": round(sum(r["w"] * r["d"] for r in rooms if r["type"] not in ("parking", "terrace")), 1),
        "balcony_sqft": round(sum(r["w"] * r["d"] for r in rooms if r["type"] in ("balcony", "sitout")), 1),
        "parapet_ft": round(lens["parapet"], 2),
        "ext_wall_ft": round(lens["ext"], 2), "int230_wall_ft": round(lens["int230"], 2),
        "int115_wall_ft": round(lens["int115"], 2),
        "bedrooms": cnt("bedroom"), "toilets": cnt("toilet") + cnt("common_toilet"), "kitchens": cnt("kitchen"),
        "halls": cnt("hall") + cnt("lounge"), "dining": cnt("dining"), "stair": cnt("stair") > 0,
        "main_doors": sum(1 for o in ops if o["type"] == "main_door"),
        "doors": sum(1 for o in ops if o["type"] in ("door", "pooja_door")),
        "toilet_doors": sum(1 for o in ops if o["type"] == "toilet_door"),
        "windows": len(win),
        "window_area_sqft": round(sum(o["w"] * o["h"] for o in win), 1),
        "rooms": [{"id": r["id"], "name": r["name"], "type": r["type"], "size": f"{r['w']:g}' × {r['d']:g}'",
                   "area_sqft": round(r["w"] * r["d"], 1)} for r in rooms],
    }


def summarize_plan(plan: dict) -> dict:
    lv = [l["summary"] for l in plan["levels"]]
    return {
        "levels": len(lv), "builtup_sqft": round(sum(s["builtup_sqft"] for s in lv), 1),
        "carpet_sqft": round(sum(s["carpet_sqft"] for s in lv), 1),
        "bedrooms": sum(s["bedrooms"] for s in lv), "toilets": sum(s["toilets"] for s in lv),
        "kitchens": sum(s["kitchens"] for s in lv),
    }


def estimate_geometry(plan: dict) -> list[dict]:
    """Per-level geometry in the form the estimate engine expects (metres)."""
    out = []
    for lv in plan["levels"]:
        s = lv["summary"]
        out.append({
            "width_m": s["width_ft"] * FT_M, "depth_m": s["depth_ft"] * FT_M,
            "ext_m": s["ext_wall_ft"] * FT_M, "int230_m": s["int230_wall_ft"] * FT_M,
            "part_m": s["int115_wall_ft"] * FT_M,
            "parapet_m": s.get("parapet_ft", 0) * FT_M, "terrace_m2": s.get("terrace_sqft", 0) * FT_M * FT_M,
            "main_doors": s["main_doors"], "int_doors": s["doors"], "toilet_doors": s["toilet_doors"],
            "win_area_m2": s["window_area_sqft"] * FT_M * FT_M, "n_win": s["windows"],
            "bed": s["bedrooms"], "toi": s["toilets"], "kit": s["kitchens"], "hall": s["halls"],
            "stilt": bool(lv.get("stilt")),
        })
    return out


def estimate_inputs(plan: dict, base: dict | None = None) -> dict:
    """Estimate inputs built from a design (geometry mode)."""
    lv = plan["levels"]
    inp = dict(base or {})
    inp.update({
        "floor_areas_sqft": [l["summary"]["builtup_sqft"] for l in lv],
        "stilt": bool(lv and lv[0].get("stilt")),
        "floor_height_ft": plan.get("floor_height_ft", 10),
        "bedrooms": plan["summary"]["bedrooms"], "toilets": plan["summary"]["toilets"],
        "kitchens": plan["summary"]["kitchens"], "halls": sum(l["summary"]["halls"] for l in lv),
        "plot_width_ft": plan["plot"]["w"], "plot_length_ft": plan["plot"]["d"],
        "staircase": any(l["summary"]["stair"] for l in lv) or len(lv) > 1,
        "geometry": estimate_geometry(plan),
    })
    if plan.get("roof_sheets"):  # 1.17
        from .roof import estimate_rows
        inp["roof_sheets"] = estimate_rows(plan)
    if plan["plot"].get("poly"):  # 1.18 irregular plot: compound wall along the real boundary (minus a 3.6 m gate)
        from .plot import info as poly_info
        per = poly_info([tuple(p) for p in plan["plot"]["poly"]])["perimeter_ft"]
        inp["compound_wall_length_m"] = round(per * 0.3048 - 3.6, 2)
    if len(lv) > 1:  # 1.18 designed staircase
        try:
            from .stair import estimate_row
            row = estimate_row(plan)
            if row:
                inp["stair"] = row
        except Exception:
            pass
    return inp
