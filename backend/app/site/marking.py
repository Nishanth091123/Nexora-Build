"""1.19 Site marking guide – everything the site team needs to mark the building on the ground, from the drawing.

Reference: the road crown at the gate is the bench mark (BM ±0). Every level is given in mm from the BM and from
the ground floor finished floor level (FFL). Values that need a site measurement (existing ground level, sewer
level) are ASKED – the guide shows "?" for anything that depends on them. Auto values (plinth, parking level,
sunken depth …) are shown as "auto" and can be changed; changed values are shown as "manual"."""
from __future__ import annotations

import math
import string

from ..design.sheets import PARAPET, PLINTH, SILL
from ..structural.engine import column_points, entrance_runs

FT_MM = 304.8
WET = ("toilet", "common_toilet", "kitchen", "utility", "wash")
OPEN = ("parking", "stilt_open", "portico", "terrace", "balcony", "sitout", "passage")


def ftin(v: float) -> str:
    neg = v < 0
    v = abs(v)
    f = int(v)
    i = round((v - f) * 12)
    if i == 12:
        f, i = f + 1, 0
    return f"{'-' if neg else ''}{f}'-{i}\""


def mm(v_ft: float) -> int:
    return round(v_ft * FT_MM)


def lv_txt(v):
    if v is None:
        return "?"
    return f"{'+' if v > 0 else '±' if v == 0 else '−'}{abs(v) / 1000:.3f}"


def _letters(n: int) -> list[str]:
    al = [c for c in string.ascii_uppercase if c not in "IO"]
    return [al[i] if i < len(al) else al[i // len(al) - 1] + al[i % len(al)] for i in range(n)]


def grid(plan: dict, struct: dict | None) -> dict:
    pts = [(c["x"], c["y"]) for c in (struct or {}).get("columns", [])] or column_points(plan)
    xs = sorted({round(p[0], 2) for p in pts})
    ys = sorted({round(p[1], 2) for p in pts})
    gx = dict(zip(xs, _letters(len(xs))))
    gy = {y: str(i + 1) for i, y in enumerate(ys)}
    return {"x": [{"name": gx[x], "pos_ft": x} for x in xs], "y": [{"name": gy[y], "pos_ft": y} for y in ys],
            "points": [{"x": p[0], "y": p[1], "id": f"{gx[round(p[0], 2)]}{gy[round(p[1], 2)]}"} for p in pts]}


def _wall_side(r: dict, o: dict) -> tuple[str, float]:
    """Which wall of the room the opening is on and its distance from that wall's start corner (ft)."""
    if abs(o["y1"] - o["y2"]) < 1e-6:
        side = "front" if abs(o["y1"] - r["y"]) < 0.3 else "back"
        return side, min(o["x1"], o["x2"]) - r["x"]
    side = "left" if abs(o["x1"] - r["x"]) < 0.3 else "right"
    return side, min(o["y1"], o["y2"]) - r["y"]


def build(plan: dict, inp: dict | None = None, struct: dict | None = None) -> dict:
    inp = {k: v for k, v in (inp or {}).items() if v not in (None, "")}
    b = plan["building"]
    H = float(plan.get("floor_height_ft") or 10) * FT_MM
    q: list[str] = []
    warn: list[str] = []
    src: dict[str, str] = {}

    def val(key, auto, label):
        if key in inp:
            src[key] = "manual"
            return float(inp[key])
        src[key] = "auto" if auto is not None else "asked"
        if auto is None:
            q.append(label)
        return auto
    egl = val("egl_mm", None, "Existing ground level at the building centre, in mm above (+) or below (−) the road crown at the gate")
    auto_ffl = None if egl is None else max(egl + mm(PLINTH), 450.0)
    ffl = val("plinth_mm", auto_ffl, "Ground floor finished level (FFL) above the road crown, mm") if egl is not None or "plinth_mm" in inp else None
    if ffl is None and "plinth_mm" not in inp and egl is None:
        src["plinth_mm"] = "needs ground level"
    runs = entrance_runs(plan)
    park = val("parking_mm", 150.0, "") if runs else None
    sunk = val("sunken_mm", 300.0, "")
    sewer = inp.get("sewer_mm")
    sewer = float(sewer) if sewer not in (None, "") else None
    found_m = float(((struct or {}).get("inputs") or {}).get("foundation_depth_m") or inp.get("foundation_depth_m") or 0) or None
    if not found_m:
        q.append("Foundation depth below ground (m) – from the structural design or the soil report")

    g = grid(plan, struct)
    out: dict = {"questions": [x for x in q if x], "warnings": warn, "sources": src,
                 "inputs": {"egl_mm": egl, "plinth_mm": ffl, "parking_mm": park, "sunken_mm": sunk, "sewer_mm": sewer,
                            "foundation_depth_m": found_m, "bm_note": inp.get("bm_note", "")}}

    # ---------------------------------------------------------------- 1. reference & setting out
    diag = math.hypot(b["w"], b["d"])
    out["reference"] = {
        "bm": inp.get("bm_note") or "Road crown (centre of the road) in front of the gate = BM ±0.000. Paint a mark on a "
                                    "fixed object (culvert, electric post base, neighbour's compound pillar) and write its level.",
        "front_line_ft": b["y"], "left_line_ft": b["x"],
        "steps": [
            f"Stretch a string line parallel to the road at {ftin(b['y'])} ({mm(b['y'])} mm) from the front boundary – this is grid line "
            f"{g['y'][0]['name'] if g['y'] else '1'} (front face of the building).",
            f"On that line, mark the left grid line {g['x'][0]['name'] if g['x'] else 'A'} at {ftin(b['x'])} ({mm(b['x'])} mm) from the left boundary.",
            "From that point, set the left grid line at right angles with the 3-4-5 method: 3 m along the front line, 4 m along "
            "the side line – the diagonal between the two marks must be exactly 5 m (use 6-8-10 m for long lines).",
            "Mark every grid line by tape from the first one (offsets below), always measuring from the same zero – never add "
            "up short pieces.",
            f"Check the two diagonals of the building outline: both must be {ftin(diag)} ({mm(diag)} mm); difference ≤ 10 mm.",
            "Fix batter boards about 1.5 m outside the building and transfer every grid line onto them with nails, so the "
            "lines can be re-strung after excavation.",
        ],
        "diagonal_ft": round(diag, 2), "diagonal_mm": mm(diag),
    }
    out["grid"] = {
        "x": [{"name": c["name"], "from_first_mm": mm(c["pos_ft"] - g["x"][0]["pos_ft"]), "from_left_boundary_mm": mm(b["x"] + c["pos_ft"]),
               "ftin": ftin(c["pos_ft"] - g["x"][0]["pos_ft"])} for c in g["x"]],
        "y": [{"name": c["name"], "from_first_mm": mm(c["pos_ft"] - g["y"][0]["pos_ft"]), "from_front_boundary_mm": mm(b["y"] + c["pos_ft"]),
               "ftin": ftin(c["pos_ft"] - g["y"][0]["pos_ft"])} for c in g["y"]],
        "points": g["points"],
    }

    # ---------------------------------------------------------------- 2. footing pits
    fts = []
    for f in (struct or {}).get("footings", []):
        gid = next((p["id"] for p in g["points"] if abs(p["x"] - f["x"]) < 0.6 and abs(p["y"] - f["y"]) < 0.6), "")
        B = float(f["B_m"])
        dep = found_m
        fts.append({"mark": f.get("mark", ""), "grid": gid, "x_mm": mm(f["x"]), "y_mm": mm(f["y"]), "footing_m": f"{B:.2f} × {B:.2f}",
                    "pcc_m": f"{B + 0.3:.2f} × {B + 0.3:.2f} × 0.10", "pit_m": f"{B + 0.6:.2f} × {B + 0.6:.2f}",
                    "pit_depth_mm": round(dep * 1000 + 100) if dep else None,
                    "pcc_bottom": (egl - dep * 1000 - 100) if (egl is not None and dep) else None,
                    "footing_thk_mm": f.get("D_mm")})
    out["footings"] = fts
    if not fts:
        out["footing_note"] = "Footing sizes come from the structural design – run Structure for this drawing first (it asks soil SBC and seismic zone)."

    # ---------------------------------------------------------------- 3. level table
    rows = [{"item": "Road crown at the gate (BM)", "level": 0.0}]
    rows.append({"item": "Existing ground level (centre of building)", "level": egl})
    if fts and egl is not None and found_m:
        rows.append({"item": "Bottom of footing PCC", "level": egl - found_m * 1000 - 100})
        rows.append({"item": "Bottom of footing (top of PCC)", "level": egl - found_m * 1000})
    if park is not None:
        rows.append({"item": "Car parking finished level", "level": park})
    n = len(plan["levels"])
    if ffl is not None:
        rows.append({"item": "Top of plinth beam (approx. FFL − floor finish & bed)", "level": ffl - 125})
        for i, lv in enumerate(plan["levels"]):
            f = ffl + i * H
            rows.append({"item": f"{lv['name']} – finished floor level (FFL)", "level": f})
            rows.append({"item": f"{lv['name']} – window sill", "level": f + mm(SILL['window'])})
            rows.append({"item": f"{lv['name']} – door top / lintel bottom", "level": f + 2100})
            top = ffl + (i + 1) * H
            rows.append({"item": f"{lv['name']} – roof slab bottom", "level": top - 50 - 125})
            rows.append({"item": f"{lv['name']} – roof slab top (structural)", "level": top - 50})
        rows.append({"item": "Terrace finished level", "level": ffl + n * H})
        rows.append({"item": "Parapet top", "level": ffl + n * H + mm(PARAPET)})
    for r in rows:
        r["from_bm"] = lv_txt(r["level"])
        r["from_ffl"] = lv_txt(r["level"] - ffl) if (ffl is not None and r["level"] is not None) else "?"
    out["levels"] = rows

    # ---------------------------------------------------------------- 4. room marking with doors / windows
    rooms_out = []
    for li, lv in enumerate(plan["levels"]):
        ops = lv.get("openings", [])
        for r in lv["rooms"]:
            if r["type"] in ("terrace",):
                continue
            items = []
            for o in ops:
                if o.get("room") != r["id"] and not (o.get("room2") == r["id"]):
                    continue
                side, dist = _wall_side(r, o)
                win = o["type"] in ("window", "vent")
                sill = mm(SILL["vent"]) if o["type"] == "vent" else mm(SILL["window"]) if win else 0
                head = sill + mm(o.get("h", 4 if win else 7)) if win else mm(o.get("h", 7))
                items.append({"type": o["type"].replace("_", " "), "mark": o.get("mark", ""), "wall": side,
                              "from_corner_mm": mm(dist), "width_mm": mm(o.get("w", 3)), "sill_mm": sill, "head_mm": head})
            rooms_out.append({"floor": lv["name"], "room": r["name"], "unit": r.get("unit_name", ""),
                              "x_mm": mm(r["x"]), "y_mm": mm(r["y"]), "size": f"{ftin(r['w'])} × {ftin(r['d'])}",
                              "size_mm": f"{mm(r['w'])} × {mm(r['d'])}", "diag_mm": mm(math.hypot(r["w"], r["d"])),
                              "openings": items})
    out["rooms"] = rooms_out
    out["rooms_note"] = ("Room corners are measured from grid point " + (g["points"][0]["id"] if g["points"] else "A1") +
                         " (front-left). Check each room's diagonals before building the walls. Door / window positions "
                         "are from the left (or front) corner of that wall, seen from inside the room.")

    # ---------------------------------------------------------------- 5. sunken toilets
    sk = []
    for li, lv in enumerate(plan["levels"]):
        for r in lv["rooms"]:
            if r["type"] not in ("toilet", "common_toilet"):
                continue
            fall = round(max(r["w"], r["d"]) * FT_MM / 100)
            sk.append({"floor": lv["name"], "room": r["name"], "size": f"{ftin(r['w'])} × {ftin(r['d'])}",
                       "sunk_mm": int(sunk) if li > 0 else 0,
                       "how": (f"Slab sunk {int(sunk)} mm below the floor slab top; fill with brick-bat / light filling after "
                               f"waterproofing the sunk." if li > 0 else "Ground floor: no sunk slab – make the floor bed with the slope."),
                       "toilet_ffl": "Room FFL − 15 mm (step down at the door so water stays inside)",
                       "slope": f"1 : 100 towards the floor trap = {fall} mm fall over the longest side",
                       "trap": "Floor trap in the corner away from the door, near the outer wall / shaft"})
    out["sunken"] = sk

    # ---------------------------------------------------------------- 6. car parking ramp
    rp = None
    if runs and park is not None:
        run_ft = b["y"]
        rise = park  # road crown → parking level
        rp = {"rise_mm": int(rise), "available_mm": mm(run_ft),
              "len_1_10_mm": round(abs(rise) * 10), "len_1_8_mm": round(abs(rise) * 8),
              "slope": f"1 : {mm(run_ft) / rise:.0f}" if rise > 0 else "flat / falls to the road",
              "steps": []}
        rp["steps"] = [
            "Fix the ramp start at the gate line (road crown level ±0, or the kerb top if higher).",
            f"Parking finished level {lv_txt(park)} m from the BM – rise of {int(rise)} mm.",
            f"Ramp length needed: {rp['len_1_10_mm']} mm at 1:10 (comfortable) or {rp['len_1_8_mm']} mm at 1:8 (steepest for cars).",
            f"Open front space available: {rp['available_mm']} mm.",
            "Mark the ramp with pegs every 1 m and write the level on each peg (rise ÷ length × distance).",
            "Keep a 1 : 100 cross slope to the side drain; finish with a rough (broom / grooved) surface.",
        ]
        if rise > 0 and mm(run_ft) < rp["len_1_8_mm"]:
            warn.append(f"Parking ramp is steeper than 1:8 ({rp['slope']}) – lower the parking level or start the ramp inside "
                        f"the plot only if the local body allows.")
        if ffl is not None:
            step = ffl - park
            if step > 0:
                nr = math.ceil(step / 165)
                rp["entry_steps"] = f"Parking → house entry: {int(step)} mm = {nr} steps of {step / nr:.0f} mm risers."
    out["ramp"] = rp

    # ---------------------------------------------------------------- 7. staircase marking
    out["stair"] = _stair(plan, ffl)

    # ---------------------------------------------------------------- 8. terrace slope
    top = plan["levels"][-1]
    covered = [r for r in top["rooms"] if r["type"] not in ("terrace", "balcony", "sitout")]
    if covered:
        x0 = min(r["x"] for r in covered); x1 = max(r["x"] + r["w"] for r in covered)
        y0 = min(r["y"] for r in covered); y1 = max(r["y"] + r["d"] for r in covered)
        area_m2 = (x1 - x0) * (y1 - y0) * 0.0929
        n_out = max(2, math.ceil(area_m2 / 40))
        corners = [(x0, y1, "back-left"), (x1, y1, "back-right"), (x0, y0, "front-left"), (x1, y0, "front-right")]
        outs = corners[:min(n_out, 4)]
        if n_out > 4:
            outs += [((x0 + x1) / 2, y1, "back-middle")]
        far = 0.0
        for i in range(11):
            for j in range(11):
                px, py = x0 + (x1 - x0) * i / 10, y0 + (y1 - y0) * j / 10
                far = max(far, min(math.hypot(px - ox, py - oy) for ox, oy, _ in outs))
        fall = round(far * FT_MM / 100)
        out["terrace"] = {"area_m2": round(area_m2, 1), "outlets": [{"where": w, "x_mm": mm(x), "y_mm": mm(y)} for x, y, w in outs],
                          "slope": "1 : 100 towards the outlets", "far_mm": mm(far), "fall_mm": fall,
                          "screed": f"Screed / brick-bat coba 25 mm at the outlets, about {25 + fall} mm at the farthest point.",
                          "steps": ["Mark the outlets first (100 mm / 4\" outlets with grating, 110 mm PVC down pipes).",
                                    "Fix level pads (dots) every 1.5 m: thickness = 25 mm + distance to the nearest outlet ÷ 100.",
                                    "Run a string between pads; lay the slope; keep the corners rounded (fillet) at the parapet."]}
    # ---------------------------------------------------------------- 9. drainage
    out["drainage"] = _drainage(plan, egl, sewer, warn)
    # ---------------------------------------------------------------- 10. gate / compound
    pw, pd = float(plan["plot"]["w"]), float(plan["plot"]["d"])
    gates = [{"what": "Car gate", "from_left_mm": mm(a + b["x"]), "width_mm": mm(min(c - a, 14.0))} for a, c, _ in runs]
    if not gates:
        gates = [{"what": "Gate", "from_left_mm": mm(b["x"] + b["w"] / 2 - 2), "width_mm": mm(4)}]
    perim = (2 * (pw + pd)) if not plan["plot"].get("poly") else float((plan["plot"].get("info") or {}).get("perimeter_ft") or 2 * (pw + pd))
    out["compound"] = {"gates": gates, "wall_length_m": round((perim - sum(x["width_mm"] for x in gates) / FT_MM) * 0.3048, 1),
                       "note": "Compound wall on the plot boundary (inside your land). Gate posts with a 230 mm pillar each side; "
                               "gate opens inwards – never over the road."}
    return out


def _stair(plan: dict, ffl: float | None) -> dict | None:
    from ..design import stair as st
    try:
        g = st.geometry(plan)
        s = st.structure(g)
    except Exception:  # no staircase / not enough room
        return None
    R, T = g["riser_mm"], g["tread_mm"]
    th = math.atan2(R, T)
    waist = s.get("waist_mm") or 150
    v_off = round(waist / math.cos(th))
    room = st._stair_room(plan)
    steps = []
    k = 0
    for fi, fl in enumerate(g["flights"]):
        for j in range(fl["risers"]):
            k += 1
            steps.append({"step": k, "flight": fi + 1, "along_mm": round((j + 1) * T) if j + 1 < fl["risers"] else round(fl["going_mm"]),
                          "height_mm": round(k * R), "level": lv_txt(ffl + k * R) if ffl is not None else "?"})
    land = g["flights"][0]["risers"] * R
    return {
        "type": g["type_name"], "risers": g["risers"], "riser_mm": R, "tread_mm": T, "width_mm": g["width_mm"],
        "waist_mm": waist, "vertical_offset_mm": v_off, "landing_mm": g["landing_mm"], "landing_level_from_ffl": round(land),
        "headroom_mm": g["headroom_mm"], "headroom_ok": g["headroom_mm"] >= 2100,
        "start": (f"First riser at the front edge of the staircase ({ftin(room['x'])} , {ftin(room['y'])} from grid origin)"
                  if room else ""),
        "steps": [
            "Mark the floor level (FFL) line on the side wall with a water level / laser.",
            f"Mark the first riser line on the floor. From it, mark every tread {T} mm along the wall and every riser {R:.0f} mm "
            "up – the corners are the nosing points.",
            "Join the nosing points – this is the pitch line (check it is straight).",
            f"Draw the waist (soffit) line parallel to the pitch line, {v_off} mm vertically below it "
            f"(= waist {waist} mm ÷ cos {math.degrees(th):.0f}°). This is the bottom of the shuttering.",
            f"Landing top at FFL + {land:.0f} mm, landing width {g['landing_mm']} mm.",
            f"Headroom under the beam / slab above: {g['headroom_mm']} mm (min 2100 mm) – check before casting.",
        ],
        "table": steps,
    }


def _drainage(plan: dict, egl: float | None, sewer: float | None, warn: list) -> dict:
    b = plan["building"]
    pw = float(plan["plot"]["w"])
    gf = plan["levels"][0]["rooms"]
    wet = [r for r in gf if r["type"] in WET]
    for lv in plan["levels"][1:]:  # stacks from upper floors come down outside the nearest wall too
        for r in lv["rooms"]:
            if r["type"] in WET and not any(abs(r["x"] - w["x"]) < 2 and abs(r["y"] - w["y"]) < 2 for w in wet):
                wet.append(r)
    if not wet:
        return {"chambers": [], "note": "No wet rooms in the drawing."}
    lw, rw = b["x"], pw - b["x"] - b["w"]
    side = "left" if lw >= rw else "right"
    xs = (b["x"] - 1.5) if side == "left" else (b["x"] + b["w"] + 1.5)
    if (lw if side == "left" else rw) < 2.5:
        warn.append("Side open space is less than 2.5 ft – drain line and chambers will be tight; consider the rear or the front.")
    pts = []
    for r in wet:
        pts.append({"room": r["name"], "y": r["y"] + r["d"] / 2})
    ys = sorted({round(p["y"] / 4) * 4 for p in pts}, reverse=True)  # one chamber every few ft of wet rooms, back to front
    chain = [{"name": f"IC{i + 1}", "x_ft": xs, "y_ft": b["y"] + y} for i, y in enumerate(ys)]
    chain.append({"name": f"IC{len(chain) + 1} (last)", "x_ft": xs, "y_ft": 1.5})
    out = []
    inv = None if egl is None else egl - 450
    dist = 0.0
    prev = None
    for i, c in enumerate(chain):
        if prev:
            dist = abs(prev["y_ft"] - c["y_ft"])
            if inv is not None:
                inv -= dist * FT_MM / 40
        rooms = [p["room"] for p in pts if abs(b["y"] + p["y"] - c["y_ft"]) < 3] if i < len(chain) - 1 else []
        out.append({"chamber": c["name"], "from_left_mm": mm(c["x_ft"]), "from_front_mm": mm(c["y_ft"]),
                    "rooms": ", ".join(rooms), "pipe_from_prev_mm": mm(dist) if prev else 0,
                    "invert": lv_txt(inv) if inv is not None else "?",
                    "depth_mm": round(egl - inv) if inv is not None else None, "size": "450 × 450 mm inside (up to 0.9 m deep), 600 × 600 mm if deeper"})
        prev = c
    res = {"side": side, "slope": "1 : 40 for 100 / 110 mm soil & waste pipes (1 : 60 for a 150 mm main line)",
           "chambers": out,
           "steps": ["Mark the chamber centres with pegs on the drain side; first chamber invert 450 mm below ground.",
                     "Fix level pegs on the trench every 2 m; invert at each peg = previous invert − distance ÷ 40.",
                     "Toilet (soil) lines enter a chamber with a bend in the flow direction; kitchen / bath waste through a gully trap.",
                     "Test every line with water before backfilling."]}
    if sewer is not None and inv is not None:
        res["sewer"] = f"Last chamber invert {lv_txt(inv)} m vs sewer invert {lv_txt(sewer)} m."
        if inv < sewer + 50:
            warn.append("The last chamber is lower than the sewer line – gravity connection is not possible; raise the plinth or plan a "
                        "lifting sump / septic tank.")
    return res


def pdf(plan: dict, g: dict, project: dict) -> bytes:
    from reportlab.graphics.shapes import Line, String
    from reportlab.lib import colors

    from .pdfdoc import Doc, plot_sketch
    d = Doc("Site Marking Guide", project, "From the active drawing. BM = road crown at the gate (±0.000). "
                                         "Levels in metres; distances in mm unless marked. Check on site before work starts.")
    if g["questions"]:
        d.h("Still to measure / confirm (values shown as ? until given)")
        d.bullets(g["questions"])
    if g["warnings"]:
        d.h("Warnings")
        d.bullets(g["warnings"])
    d.h("1. Bench mark & setting out")
    d.para(g["reference"]["bm"])
    for i, s in enumerate(g["reference"]["steps"], 1):
        d.para(f"{i}. {s}")
    d.h("Grid offsets", 3)
    gx, gy = g["grid"]["x"], g["grid"]["y"]
    d.table(["Grid", "From first line", "ft-in", "From boundary"],
            [[c["name"], f"{c['from_first_mm']} mm", c["ftin"], f"{c['from_left_boundary_mm']} mm from LEFT"] for c in gx] +
            [[c["name"], f"{c['from_first_mm']} mm", c["ftin"], f"{c['from_front_boundary_mm']} mm from FRONT"] for c in gy], [12, 20, 18, 30])
    b = plan["building"]

    def grid_lines(dr, X, Y, s):
        for c in gx:
            x = c["from_left_boundary_mm"] / FT_MM
            dr.add(Line(X(x), Y(b["y"] - 2), X(x), Y(b["y"] + b["d"] + 2), strokeColor=colors.HexColor("#94a3b8"), strokeWidth=0.4, strokeDashArray=[2, 2]))
            dr.add(String(X(x), Y(b["y"] + b["d"] + 3), c["name"], fontSize=6, textAnchor="middle"))
        for c in gy:
            y = c["from_front_boundary_mm"] / FT_MM
            dr.add(Line(X(b["x"] - 2), Y(y), X(b["x"] + b["w"] + 2), Y(y), strokeColor=colors.HexColor("#94a3b8"), strokeWidth=0.4, strokeDashArray=[2, 2]))
            dr.add(String(X(b["x"] - 3), Y(y) - 2, c["name"], fontSize=6, textAnchor="end"))
        dr.add(Line(X(b["x"]), Y(b["y"]), X(b["x"] + b["w"]), Y(b["y"] + b["d"]), strokeColor=colors.HexColor("#dc2626"), strokeWidth=0.4))
        dr.add(Line(X(b["x"] + b["w"]), Y(b["y"]), X(b["x"]), Y(b["y"] + b["d"]), strokeColor=colors.HexColor("#dc2626"), strokeWidth=0.4))
    d.sketch(plot_sketch(plan, [], grid_lines), 180, 120)
    d.page()
    d.h("2. Footing pits")
    if g["footings"]:
        d.table(["Footing", "Grid", "Centre (x, y) mm", "Footing m", "PCC m", "Pit m", "Pit depth mm", "PCC bottom"],
                [[f["mark"], f["grid"], f"{f['x_mm']}, {f['y_mm']}", f["footing_m"], f["pcc_m"], f["pit_m"],
                  f["pit_depth_mm"] or "?", lv_txt(f["pcc_bottom"])] for f in g["footings"]], [9, 8, 16, 13, 16, 13, 12, 12])
        d.para("Pit size includes 150 mm working space each side beyond the PCC. Depth is from the existing ground.", True)
    else:
        d.para(g.get("footing_note", ""))
    d.h("3. Level table")
    src = g["sources"]
    d.para("Plinth / FFL: " + src.get("plinth_mm", "") + " · Parking: " + src.get("parking_mm", "-") + " · Sunken: " + src.get("sunken_mm", ""), True)
    d.table(["Item", "From BM (m)", "From GF FFL (m)"], [[r["item"], r["from_bm"], r["from_ffl"]] for r in g["levels"]], [60, 20, 20])
    d.page()
    d.h("4. Room marking (doors & windows)")
    d.para(g["rooms_note"], True)
    for r in g["rooms"]:
        ops = "; ".join(f"{o['type']} {o['mark']} on {o['wall']} wall at {o['from_corner_mm']} mm, {o['width_mm']} wide, sill {o['sill_mm']} / top {o['head_mm']}"
                        for o in r["openings"]) or "—"
        d.table([f"{r['floor']} – {r['room']}" + (f" ({r['unit']})" if r["unit"] else ""), ""],
                [["Corner from grid origin", f"x {r['x_mm']} mm, y {r['y_mm']} mm"], ["Size", f"{r['size']} ({r['size_mm']} mm), diagonal {r['diag_mm']} mm"],
                 ["Openings", ops]], [28, 72], zebra=False)
        d.space(1.5)
    d.page()
    if g["sunken"]:
        d.h("5. Sunken toilets")
        d.table(["Floor / toilet", "Sunk", "How", "Slope", "Trap"],
                [[f"{s['floor']} – {s['room']} ({s['size']})", f"{s['sunk_mm']} mm", s["how"] + " " + s["toilet_ffl"], s["slope"], s["trap"]]
                 for s in g["sunken"]], [22, 8, 34, 18, 18])
    if g.get("ramp"):
        d.h("6. Car parking ramp")
        d.bullets(g["ramp"]["steps"] + ([g["ramp"]["entry_steps"]] if g["ramp"].get("entry_steps") else []))
    if g.get("stair"):
        s = g["stair"]
        d.h("7. Staircase marking")
        d.para(f"{s['type']}: {s['risers']} risers of {s['riser_mm']:.0f} mm, treads {s['tread_mm']} mm, width {s['width_mm']} mm, waist {s['waist_mm']} mm.")
        if s["start"]:
            d.para(s["start"])
        for i, x in enumerate(s["steps"], 1):
            d.para(f"{i}. {x}")
        d.table(["Step", "Flight", "Along the wall mm", "Height from FFL mm", "Level (m, BM)"],
                [[x["step"], x["flight"], x["along_mm"], x["height_mm"], x["level"]] for x in s["table"]], [10, 10, 25, 25, 25])
    if g.get("terrace"):
        t = g["terrace"]
        d.h("8. Terrace slope to outlets")
        d.para(f"Roof {t['area_m2']} m², {len(t['outlets'])} outlets ({', '.join(o['where'] for o in t['outlets'])}). {t['slope']}; "
               f"farthest point {t['far_mm']} mm from an outlet → fall {t['fall_mm']} mm. {t['screed']}")
        d.bullets(t["steps"])
    dr = g.get("drainage") or {}
    if dr.get("chambers"):
        d.h("9. Drainage – chambers and invert levels")
        d.para(f"Line on the {dr['side']} side. {dr['slope']}.")
        d.table(["Chamber", "From left mm", "From front mm", "Serves", "Pipe from previous", "Invert (m, BM)", "Depth mm", "Size"],
                [[c["chamber"], c["from_left_mm"], c["from_front_mm"], c["rooms"], c["pipe_from_prev_mm"], c["invert"], c["depth_mm"] or "?", c["size"]]
                 for c in dr["chambers"]], [10, 10, 10, 18, 10, 11, 9, 22])
        d.bullets(dr["steps"] + ([dr["sewer"]] if dr.get("sewer") else []))
    c = g.get("compound") or {}
    if c:
        d.h("10. Gate & compound wall")
        d.bullets([f"{x['what']}: {x['width_mm']} mm wide, starting {x['from_left_mm']} mm from the left boundary" for x in c["gates"]] +
                  [f"Compound wall about {c['wall_length_m']} m long.", c["note"]])
    d.space(4)
    d.signatures(["Marked by (site engineer)", "Checked by"])
    return d.build()
