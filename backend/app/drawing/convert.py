"""Turn reader output (DXF / PDF / AI vision) into confirmed-ready rooms (feet) and a design plan."""
from __future__ import annotations

import math

from ..design.geometry import add_openings
from ..design.layout import NAMES
from ..design.setbacks import FT, SetbackError, tn_setbacks
from .regions import parse_size, room_type, tidy, to_ft

TYPE_NAMES = {**NAMES, "bedroom": "Bedroom", "utility": "Utility", "store": "Store", "sitout": "Sit-out",
              "balcony": "Balcony", "terrace": "Open Terrace", "parking": "Parking", "toilet": "Toilet"}


def _r(v: float) -> float:
    return round(v * 4) / 4


def rooms_from_raw(ext: dict, units: str | None = None, scale: float | None = None) -> dict:
    """DXF / vector-PDF reader output → rooms in feet.
    units overrides the detected DXF units; scale (feet per drawing unit) overrides everything."""
    k = ext["to_ft"] if not units else {"in": 1 / 12, "ft": 1.0, "mm": 1 / 304.8, "cm": 1 / 30.48, "m": 1 / 0.3048}[units]
    if ext.get("scale_ft_per_unit") and not units:
        k = ext["scale_ft_per_unit"]
    if scale:
        k = scale
    rooms, notes = [], []
    for i, r in enumerate(ext.get("rooms_raw", [])):
        typ = room_type(r["label"]) or "passage"
        room = {"id": f"u{i + 1}", "type": typ, "name": r["label"][:40].title() if r["label"].isupper() else r["label"][:40],
                "x": _r(r["x"] * k), "y": _r(r["y"] * k), "w": _r(r["w"] * k), "d": _r(r["d"] * k),
                "placed": True, "source": ext["method"], "confidence": 0.9 if r.get("rectangular", True) else 0.6,
                "note": "" if r.get("rectangular", True) else "Room is not rectangular – bounding box used"}
        stated = None
        for t in [r["label"]] + r.get("extra", []):
            ps = parse_size(t)
            if ps:
                stated = ps
                break
        if stated:
            a, b, hint = stated
            unit_hint = hint.rstrip("?") if hint != "ft?" else "ft"
            sa, sb = to_ft(a, unit_hint), to_ft(b, unit_hint)
            room["stated"] = f"{a:g} × {b:g}" + ("" if unit_hint == "ft" else f" {unit_hint}")
            best = min(abs(room["w"] - sa) + abs(room["d"] - sb), abs(room["w"] - sb) + abs(room["d"] - sa))
            if best > 1.5:
                room["confidence"] = 0.5
                room["note"] = (f"Written size {room['stated']} differs from measured {room['w']:g}' × {room['d']:g}' "
                                f"– check the units / scale")
        rooms.append(room)
    for j, u in enumerate(ext.get("unplaced", [])):
        ps = parse_size(u["text"])
        typ = u.get("type") or room_type(u["text"])
        if not typ:
            continue
        w = d = None
        if ps:
            hint = ps[2].rstrip("?") if ps[2] != "ft?" else "ft"
            w, d = _r(to_ft(ps[0], hint)), _r(to_ft(ps[1], hint))
        rooms.append({"id": f"p{j + 1}", "type": typ, "name": u["text"][:40], "x": 0, "y": 0, "w": w or 10, "d": d or 10,
                      "placed": False, "source": ext["method"], "confidence": 0.3,
                      "note": "Label found but no closed room around it – place it in the 2D editor"
                              + ("" if ps else "; size not written (10' × 10' shown)")})
    preview = [[round(a * k, 2), round(b * k, 2), round(c * k, 2), round(d * k, 2)] for a, b, c, d in ext.get("preview_raw", [])]
    tidy([r for r in rooms if r["placed"]], tol=1.0)
    titles = [{"text": t["text"], "x": t["x"] * k, "y": t["y"] * k} for t in ext.get("titles", [])]
    groups = group_floors(rooms, titles)
    if len(groups) > 1:
        notes.append(f"{len(groups)} separate drawings found on the sheet (probably floors) – confirm which floor each one is.")
    nd = ext.get("north_deg")
    if nd is not None:
        notes.append(f"North arrow found on the drawing: {nd:g}° (clockwise from up) – the dial is set to it, please check.")
    return {"rooms": rooms, "preview": preview, "notes": notes, "to_ft": k, "groups": groups, "north_deg": nd}


FLOOR_WORDS = [("stilt", "Stilt / Parking"), ("ground", "Ground Floor"), ("first", "First Floor"),
               ("second", "Second Floor"), ("third", "Third Floor"), ("terrace", "Terrace")]


def group_floors(rooms: list[dict], titles: list[dict], gap: float = 3.0) -> list[dict]:
    """Rooms that touch / nearly touch belong to one drawing; separate clusters are usually separate floors."""
    placed = [r for r in rooms if r["placed"]]
    parent = list(range(len(placed)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for i, a in enumerate(placed):
        for j in range(i + 1, len(placed)):
            b = placed[j]
            gx = max(a["x"], b["x"]) - min(a["x"] + a["w"], b["x"] + b["w"])
            gy = max(a["y"], b["y"]) - min(a["y"] + a["d"], b["y"] + b["d"])
            if gx <= gap and gy <= gap:
                parent[find(i)] = find(j)
    clusters: dict[int, list] = {}
    for i, r in enumerate(placed):
        clusters.setdefault(find(i), []).append(r)
    ordered = sorted(clusters.values(), key=lambda c: (min(r["x"] for r in c), min(r["y"] for r in c)))
    out = []
    for gi, c in enumerate(ordered):
        x0, y0 = min(r["x"] for r in c), min(r["y"] for r in c)
        x1, y1 = max(r["x"] + r["w"] for r in c), max(r["y"] + r["d"] for r in c)
        for r in c:
            r["group"] = gi
        name = None
        best = 1e9
        for t in titles:
            if x0 - 5 <= t["x"] <= x1 + 5:
                dist = min(abs(t["y"] - y0), abs(t["y"] - y1))
                if dist < best and dist < 25:
                    low = t["text"].lower()
                    for w, nm in FLOOR_WORDS:
                        if w in low:
                            name, best = nm, dist
                            break
        if not name:
            name = ["Ground Floor", "First Floor", "Second Floor", "Third Floor"][gi] if gi < 4 else f"Floor {gi + 1}"
        out.append({"id": gi, "name": name, "rooms": len(c), "w": round(x1 - x0, 2), "d": round(y1 - y0, 2)})
    for r in rooms:
        if not r["placed"]:
            r["group"] = 0
    return out


def rooms_from_vision(v: dict, img_w: float, img_h: float) -> dict:
    """AI-vision JSON → rooms. Positions come from each room's box on the picture, scaled by the rooms
    whose sizes are WRITTEN on the drawing (median ft per pixel)."""
    unit = (v.get("units") or "ft").lower()
    if unit not in ("ft", "m", "mm", "cm", "in"):
        unit = "ft"
    rooms_in = v.get("rooms") or []
    ratios = []
    for r in rooms_in:
        bb = r.get("bbox")
        w, d = r.get("w"), r.get("d")
        if bb and w and d and len(bb) == 4:
            bw, bh = abs(bb[2] - bb[0]) * img_w, abs(bb[3] - bb[1]) * img_h
            if bw > 2 and bh > 2:
                wf, df = to_ft(float(w), unit), to_ft(float(d), unit)
                # the written size may be width × depth or the other way round – take the better match
                a = (wf / bw + df / bh) / 2
                b = (df / bw + wf / bh) / 2
                spread_a = abs(wf / bw - df / bh)
                spread_b = abs(df / bw - wf / bh)
                ratios.append(a if spread_a <= spread_b else b)
    scale = sorted(ratios)[len(ratios) // 2] if ratios else None
    rooms, notes = [], []
    boxes = [r.get("bbox") for r in rooms_in if r.get("bbox") and len(r["bbox"]) == 4]
    minx = min((min(b[0], b[2]) for b in boxes), default=0) * img_w
    maxy = max((max(b[1], b[3]) for b in boxes), default=1) * img_h
    for i, r in enumerate(rooms_in):
        name = str(r.get("name") or "Room")[:40]
        typ = room_type(name) or "passage"
        bb = r.get("bbox") if r.get("bbox") and len(r["bbox"]) == 4 else None
        wf = to_ft(float(r["w"]), unit) if r.get("w") else None
        df = to_ft(float(r["d"]), unit) if r.get("d") else None
        try:
            grp = int(r.get("floor") or 0)
        except (TypeError, ValueError):
            grp = 0
        room = {"id": f"v{i + 1}", "type": typ, "name": name, "source": "ai-vision", "group": grp,
                "confidence": float(r.get("confidence") or 0.6), "note": "", "placed": bool(bb and scale)}
        if r.get("dims_text"):
            room["stated"] = str(r["dims_text"])[:30]
        if bb and scale:
            x0, x1 = sorted((bb[0] * img_w, bb[2] * img_w))
            y0, y1 = sorted((bb[1] * img_h, bb[3] * img_h))
            room["x"], room["y"] = _r((x0 - minx) * scale), _r((maxy - y1) * scale)
            mw, md = _r((x1 - x0) * scale), _r((y1 - y0) * scale)
            if wf and df:
                # keep the written size, oriented like the box on the picture
                if (wf >= df) == (mw >= md):
                    room["w"], room["d"] = _r(wf), _r(df)
                else:
                    room["w"], room["d"] = _r(df), _r(wf)
            else:
                room["w"], room["d"] = mw, md
                room["confidence"] = min(room["confidence"], 0.4)
                room["note"] = "Size not written on the drawing – measured from the picture, please confirm"
        else:
            room["x"] = room["y"] = 0
            room["w"], room["d"] = _r(wf or 10), _r(df or 10)
            room["confidence"] = min(room["confidence"], 0.3)
            room["note"] = "Position not found – place it in the 2D editor" + ("" if wf else "; size not written")
        rooms.append(room)
    if not scale:
        notes.append("No room had its size written on the drawing, so the scale is unknown – enter the sizes.")
    for g in {r["group"] for r in rooms}:
        tidy([r for r in rooms if r["placed"] and r["group"] == g], tol=1.25)
    floors = v.get("floors") or []
    gids = sorted({r["group"] for r in rooms}) or [0]
    groups = []
    for gi in gids:
        name = str(floors[gi]) if gi < len(floors) and floors[gi] else ["Ground Floor", "First Floor", "Second Floor", "Third Floor"][min(gi, 3)]
        low = name.lower()
        name = next((nm for w, nm in FLOOR_WORDS if w in low), name)
        groups.append({"id": gi, "name": name, "rooms": sum(1 for r in rooms if r["group"] == gi)})
    if len(groups) > 1:
        notes.append(f"{len(groups)} floor plans found on the picture – confirm which floor each one is.")
    for n in v.get("notes") or []:
        notes.append(f"AI note: {str(n)[:160]}")
    return {"rooms": rooms, "preview": [], "notes": notes, "to_ft": scale, "groups": groups,
            "north_deg": v.get("north_arrow_deg"), "plot": v.get("plot")}


def _rotate(rooms: list[dict], W: float, D: float, quarter: int) -> tuple[list[dict], float, float]:
    """Rotate room rectangles by quarter × 90° counter-clockwise inside a W × D box."""
    for _ in range(quarter % 4):
        for r in rooms:
            x, y, w, d = r["x"], r["y"], r["w"], r["d"]
            r["x"], r["y"], r["w"], r["d"] = _r(D - y - d), x, d, w
        W, D = D, W
    return rooms, W, D


def compass_from_north(north_deg: float) -> dict:
    """north_deg = direction of the north arrow, degrees clockwise from 'up' on the screen."""
    beta = math.radians(-north_deg)  # bearing of screen-up
    up = (round(math.sin(beta), 4), round(math.cos(beta), 4))
    right = (up[1], -up[0])
    return {"up": up, "right": right}


def facing_from_compass(comp: dict) -> str:
    """Road side = screen bottom → the direction of 'down'."""
    e, n = -comp["up"][0], -comp["up"][1]
    ang = (math.degrees(math.atan2(e, n)) + 360) % 360
    names = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]
    return names[int(((ang + 22.5) % 360) // 45)]


ROAD_QUARTER = {"bottom": 0, "left": 1, "top": 2, "right": 3}  # counter-clockwise quarter turns


def build_plan(levels_in: list[dict], opts: dict) -> dict:
    """Confirmed rooms (feet, y away from the bottom of the drawing) → design plan.

    levels_in: [{"name": "Ground Floor", "rooms": [...]}, ...] (bottom floor first)
    opts: north_deg (required), road_side bottom/top/left/right, floor_height_ft,
          plot_w_ft, plot_d_ft, road_width_m, front_gap_ft, left_gap_ft, area_type
    """
    north = float(opts.get("north_deg") or 0)
    q = ROAD_QUARTER.get(opts.get("road_side") or "bottom", 0)
    north = (north - 90 * q) % 360  # the drawing turned counter-clockwise → north turns with it
    comp = compass_from_north(north)
    levels, W, D = [], 0.0, 0.0
    for li, lv in enumerate(levels_in):
        rooms = [dict(r) for r in lv.get("rooms", []) if float(r.get("w", 0)) >= 2 and float(r.get("d", 0)) >= 2]
        if not rooms:
            continue
        for r in rooms:
            for k in ("x", "y", "w", "d"):
                r[k] = float(r.get(k) or 0)
        minx, miny = min(r["x"] for r in rooms), min(r["y"] for r in rooms)
        for r in rooms:
            r["x"], r["y"] = _r(r["x"] - minx), _r(r["y"] - miny)
        lw = max(r["x"] + r["w"] for r in rooms)
        ld = max(r["y"] + r["d"] for r in rooms)
        rooms, lw, ld = _rotate(rooms, lw, ld, q)
        W, D = max(W, lw), max(D, ld)
        clean = []
        for i, r in enumerate(rooms):
            typ = r.get("type") or "passage"
            clean.append({"id": str(r.get("id") or f"r{li}_{i + 1}"), "type": typ,
                          "name": str(r.get("name") or TYPE_NAMES.get(typ, typ))[:40],
                          "x": r["x"], "y": r["y"], "w": r["w"], "d": r["d"]})
        name = str(lv.get("name") or ["Ground Floor", "First Floor", "Second Floor", "Third Floor"][min(li, 3)])
        levels.append({"name": name, "stilt": name.lower().startswith("stilt"), "rooms": clean})
    if not levels:
        raise ValueError("No rooms to build the plan from.")
    floor_h = float(opts.get("floor_height_ft") or 10)
    levels_count = max(len(levels), int(opts.get("levels_count") or 1))
    plot_w = float(opts.get("plot_w_ft") or 0)
    plot_d = float(opts.get("plot_d_ft") or 0)
    road = float(opts.get("road_width_m") or 0)
    warnings, notes = [], []
    sb = None
    if plot_w and plot_d and road:
        try:
            sb = tn_setbacks(plot_w, plot_d, road, levels_count, floor_h, opts.get("area_type") or "other")
        except SetbackError as e:
            warnings.append(str(e))
    front = float(opts["front_gap_ft"]) if opts.get("front_gap_ft") not in (None, "") else (sb["ft"]["front"] if sb else 0)
    left = float(opts["left_gap_ft"]) if opts.get("left_gap_ft") not in (None, "") else (sb["ft"]["left"] if sb else 0)
    if not plot_w or not plot_d:
        plot_w, plot_d = W + left, D + front
        notes.append("Plot size not given – the plot is drawn around the building; setbacks not checked.")
    if sb:
        req = sb["ft"]
        act = {"front": front, "left": left, "right": plot_w - left - W, "rear": plot_d - front - D}
        for k in ("front", "rear", "left", "right"):
            if act[k] < req[k] - 0.1:
                warnings.append(f"Setback check: {k} gap is {act[k]:.2f} ft but TNCDBR needs {req[k]:g} ft "
                                f"({sb['m'][k]:g} m) for this road width / height.")
        if W > plot_w + 0.01 or D > plot_d + 0.01:
            warnings.append("The building is bigger than the plot – check the plot size or the drawing scale.")
        setbacks = {**sb, "ft": {k: round(max(0.0, v), 2) for k, v in act.items()},
                    "m": {k: round(max(0.0, v) * FT, 2) for k, v in act.items()}, "required_ft": req,
                    "required_m": sb["m"], "coverage_pct": round(100 * W * D / (plot_w * plot_d), 1)}
        setbacks["notes"] = sb["notes"] + ["Gaps shown are from your drawing; required values are checked above."]
    else:
        setbacks = {"rule": "Not checked", "area_type": opts.get("area_type") or "other", "road_width_m": road,
                    "corner": False, "height_m": round(0.45 + levels_count * floor_h * FT, 2), "max_height_m": 12.0,
                    "m": {k: 0.0 for k in ("front", "rear", "left", "right")},
                    "ft": {"front": round(front, 2), "left": round(left, 2), "rear": round(max(0.0, plot_d - front - D), 2),
                           "right": round(max(0.0, plot_w - left - W), 2)},
                    "buildable": {"x": left, "y": front, "w": W, "d": D},
                    "coverage_pct": round(100 * W * D / (plot_w * plot_d), 1) if plot_w and plot_d else 100.0,
                    "notes": ["Give plot size and road width to check Tamil Nadu setbacks."]}
    plan = {
        "version": 1, "units": "ft", "plot": {"w": round(plot_w, 2), "d": round(plot_d, 2)},
        "facing": facing_from_compass(comp), "compass": comp, "north_deg": round(north, 1), "setbacks": setbacks,
        "building": {"x": round(left, 2), "y": round(front, 2), "w": round(W, 2), "d": round(D, 2)},
        "floor_height_ft": floor_h, "levels": levels, "notes": notes,
        "requirements": {"source": "upload", "plot_w_ft": plot_w, "plot_d_ft": plot_d, "road_width_m": road,
                         "facing": facing_from_compass(comp), "levels": [{"name": l["name"]} for l in levels]},
        "from_upload": True,
    }
    out = add_openings(plan)
    out["warnings"] = warnings + out["warnings"]
    return out


def append_level(plan: dict, new: dict) -> dict:
    """Add the single level of plan `new` on top of `plan` (same origin, building grows if needed)."""
    lv = new["levels"][0]
    plan["levels"].append({"name": lv["name"], "stilt": False, "rooms": lv["rooms"]})
    b = plan["building"]
    b["w"] = max(b["w"], new["building"]["w"])
    b["d"] = max(b["d"], new["building"]["d"])
    plan.setdefault("notes", []).append(f"{lv['name']} added from an uploaded drawing – check it lines up "
                                        f"with the floor below in the 2D editor.")
    for l in plan["levels"]:
        l.pop("walls", None)
        l.pop("openings", None)
    return add_openings(plan)
