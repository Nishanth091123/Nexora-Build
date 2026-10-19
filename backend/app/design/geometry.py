"""Walls, doors, windows and quantity summary derived from room rectangles.

Rooms are the single source of truth: change a room and walls, openings and the estimate follow.
Units: feet. Room coordinates are relative to the building origin (front-left corner of the building).
"""
from __future__ import annotations

STEP = 0.25  # sampling resolution (ft)
FT_M = 0.3048

OPEN_PAIRS = {frozenset(p) for p in [("hall", "dining"), ("dining", "passage"), ("lounge", "passage"),
                                      ("passage", "stair"), ("parking", "parking"), ("hall", "passage"),
                                      ("lounge", "stair"), ("parking", "stair")]}
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


def level_openings(lv: dict, level_index: int, building_d: float) -> tuple[list[dict], list[str]]:
    rooms = lv["rooms"]
    by_id = {r["id"]: r for r in rooms}
    ws = walls(rooms)
    ops, warnings = [], []
    n = 0

    def add(rid, kind, w, h, seg):
        nonlocal n
        n += 1
        ops.append({"id": f"op{n}", "room": rid, "type": kind, "h": h, **seg})

    circulation = ["hall", "lounge", "dining", "passage", "stair", "kitchen"]
    main_done = False
    for r in rooms:
        t = r["type"]
        rid = r["id"]
        if t in ("dress", "parking", "passage") or t in OPEN_TYPES:
            continue
        # main door on the front (road side) wall
        if not main_done and level_index == 0 and not lv.get("stilt") and t in ("hall", "lounge"):
            front = [w for w in ws if w["kind"] == "ext" and rid in (w["a"], w["b"]) and w["y1"] == w["y2"]
                     and abs(w["y1"] - min(rr["y"] for rr in rooms)) < 0.01]
            if not front:  # hall behind parking: main door between parking and hall
                front = [w for w in ws if rid in (w["a"], w["b"]) and w["y1"] == w["y2"] and
                         {by_id.get(w["a"], {}).get("type"), by_id.get(w["b"], {}).get("type")} >= {"parking"}]
            if front:
                add(rid, "main_door", 3.5, 7, place(max(front, key=seg_len), 3.5))
                main_done = True
        if t == "bedroom":
            w, _ = shared(ws, rid, circulation + ["bedroom"], by_id)
            if w:
                add(rid, "door", 3.0, 7, place(w, 3.0, prefer_end=True))
            else:
                warnings.append(f"{lv['name']}: {r['name']} has no access – move it next to the hall/dining.")
        elif t == "toilet":
            target = r.get("parent")
            cand = [w for w in ws if rid in (w["a"], w["b"]) and seg_len(w) >= 2.5 and
                    ((w["b"] if w["a"] == rid else w["a"]) in [target] + [x["id"] for x in rooms if x.get("parent") == target and x["type"] == "dress"])]
            if cand:
                dress = [w for w in cand if by_id.get(w["b"] if w["a"] == rid else w["a"], {}).get("type") == "dress"]
                add(rid, "toilet_door", 2.5, 7, place(max(dress or cand, key=seg_len), 2.5))
            else:
                w, _ = shared(ws, rid, circulation + ["bedroom"], by_id)
                if w:
                    add(rid, "toilet_door", 2.5, 7, place(w, 2.5))
        elif t == "common_toilet":
            w, _ = shared(ws, rid, ["dining", "hall", "lounge", "passage", "kitchen", "stair"], by_id)
            if w:
                add(rid, "toilet_door", 2.5, 7, place(w, 2.5))
            else:
                warnings.append(f"{lv['name']}: Common toilet has no access from a common area.")
        elif t == "kitchen":
            w, _ = shared(ws, rid, ["dining", "hall", "lounge", "passage"], by_id)
            if w:
                add(rid, "opening", 3.0, 7, place(w, 3.0))
        elif t in ("utility", "store"):
            w, _ = shared(ws, rid, ["kitchen", "dining", "hall", "lounge", "passage"], by_id)
            if w:
                add(rid, "door", 2.5, 7, place(w, 2.5))
        elif t == "pooja":
            w, _ = shared(ws, rid, ["hall", "dining", "lounge", "passage"], by_id)
            if w:
                add(rid, "pooja_door", 2.5, 6, place(w, 2.5))
        # windows on the longest external wall
        if t in WIN:
            ext = [w for w in ws if w["kind"] == "ext" and rid in (w["a"], w["b"]) and seg_len(w) >= WIN[t] + 1]
            if ext:
                w = max(ext, key=seg_len)
                add(rid, "vent" if t == "toilet" or t == "common_toilet" else "window", WIN[t], WIN_H.get(t, 4),
                    place(w, WIN[t]))
            elif t in HABITABLE:
                warnings.append(f"{lv['name']}: {r['name']} has no outside wall for a window – add a light well / "
                                f"duct or rearrange.")
        if t == "common_toilet":
            ext = [w for w in ws if w["kind"] == "ext" and rid in (w["a"], w["b"]) and seg_len(w) >= 3]
            if ext:
                add(rid, "vent", 2, 1.5, place(max(ext, key=seg_len), 2))
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
    for i, lv in enumerate(plan["levels"]):
        warns = check_rooms(lv, bw, bd)
        ops, w2 = level_openings(lv, i, bd)
        lv["openings"] = ops
        lv["walls"] = walls(lv["rooms"])
        lv["summary"] = summarize_level(lv)
        lv["warnings"] = warns + w2
        all_warn += lv["warnings"]
    plan["warnings"] = all_warn
    plan["summary"] = summarize_plan(plan)
    return plan


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
    return inp
