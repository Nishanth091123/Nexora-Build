"""1.19 Rain-water harvesting, sump, overhead tank and septic tank – size, position, sketch, estimate, approval.

Everything here is a preliminary size from the drawing and the inputs on the screen. Rules used (shown in the output):
  • Rain-water harvesting is compulsory in Tamil Nadu – TNCDBR 2019 Rule 63(1) → structures as in Annexure XXII.
    Recharge well as in the CMDA standard drawing (1.0 m dia, perforated rings, filter media); one well for every
    100 m² of roof / paved area is used as the starting number – the local body's annexure decides.
  • Water demand 135 litres / person / day (NBC 2016 Part 9 for houses with full flushing) – editable.
  • Septic tank sizes from IS 2470 (Part 1) table for the number of users, cleaning once a year – editable.
Nothing that must be measured is guessed: soil type and whether a sewer line / well exists are asked."""
from __future__ import annotations

import math

LPCD = 135
SEPTIC_TABLE = [  # users, length m, breadth m, liquid depth m  (IS 2470 Part 1, desludging once a year)
    (5, 1.5, 0.75, 1.0), (10, 2.0, 0.90, 1.0), (15, 2.0, 0.90, 1.3), (20, 2.3, 1.10, 1.3), (50, 5.0, 1.60, 1.3),
]
OHT_SIZES = [500, 750, 1000, 1500, 2000, 3000, 5000, 7500, 10000]
FT = 0.3048


def _houses(plan: dict) -> int:
    n = 0
    for lv in plan["levels"]:
        us = {r.get("unit") for r in lv["rooms"] if r.get("unit")}
        if us:
            n += len(us)
        elif any(r["type"] == "kitchen" for r in lv["rooms"]):
            n += 1
    return max(1, n)


def roof_area_m2(plan: dict) -> float:
    """Top roof + open terraces of every floor (the catchment that drains to the rain-water pipes)."""
    b = plan["building"]
    a = b["w"] * b["d"]
    return round(a * FT * FT, 1)


def defaults(plan: dict) -> dict:
    h = _houses(plan)
    return {"persons": 5 * h, "lpcd": LPCD, "sump_days": 1.5, "oht_days": 0.5, "rwh_per_m2": 100,
            "houses": h}


def questions(inp: dict) -> list[str]:
    q = []
    if not inp.get("soil"):
        q.append("Soil type at the site (sandy / mixed / clayey / hard rock) – decides the recharge well depth")
    if inp.get("sewer") in (None, ""):
        q.append("Is there an underground sewer line in the road? (yes / no)")
    if inp.get("well") in (None, ""):
        q.append("Is there an open well or borewell in the plot? (none / borewell / open well) – septic tank distance rule")
    return q


def _free_spots(plan: dict) -> list[dict]:
    """Open rectangles of the front setback (plot ft) that are not in the car's path to the parking."""
    b = plan["building"]
    pw = float(plan["plot"]["w"])
    from ..structural.engine import entrance_runs
    runs = [(a + b["x"], c + b["x"]) for a, c, _ in entrance_runs(plan)]
    fy = b["y"]  # front open depth
    spots = []
    if fy >= 4:
        xs = [0.0]
        for a, c in runs:
            xs += [a - 0.5, c + 0.5]
        xs.append(pw)
        for i in range(0, len(xs), 2):
            x0, x1 = xs[i], xs[i + 1]
            if x1 - x0 >= 4:
                spots.append({"x": x0 + 0.5, "y": 0.5, "w": x1 - x0 - 1.0, "d": fy - 1.0, "where": "front open space"})
    side = [("left", 0.0, b["x"]), ("right", b["x"] + b["w"], pw - b["x"] - b["w"])]
    for nm, x0, w in side:
        if w >= 3.2:
            spots.append({"x": x0 + 0.3, "y": b["y"], "w": w - 0.6, "d": b["d"], "where": f"{nm} side open space"})
    rear = float(plan["plot"]["d"]) - b["y"] - b["d"]
    if rear >= 3.2:
        spots.append({"x": 0.5, "y": b["y"] + b["d"] + 0.3, "w": pw - 1.0, "d": rear - 0.6, "where": "rear open space"})
    if fy >= 4:  # last choice: under the driveway with a vehicle-load cover slab
        for a, c in runs:
            spots.append({"x": a, "y": 0.5, "w": c - a, "d": fy - 1.0, "where": "under the driveway (heavy-duty cover slab)"})
    return spots


def size(plan: dict, inp: dict | None = None, rates: dict | None = None, spec: str = "standard") -> dict:
    inp = {**defaults(plan), **{k: v for k, v in (inp or {}).items() if v not in (None, "")}}
    persons = int(float(inp["persons"]))
    lpcd = float(inp["lpcd"])
    daily = persons * lpcd
    out = {"inputs": inp, "questions": questions(inp), "notes": [], "warnings": []}

    # --- sump
    sump_l = math.ceil(daily * float(inp["sump_days"]) / 500) * 500
    sump_l = int(float(inp.get("sump_litres") or sump_l))
    depth = 1.8
    side = math.sqrt(sump_l / 1000 / depth)
    out["sump"] = {"litres": sump_l, "water_depth_m": depth, "inner_l_m": round(max(side, 1.2), 2),
                   "inner_b_m": round(max(sump_l / 1000 / depth / max(side, 1.2), 1.0), 2), "freeboard_m": 0.3,
                   "basis": f"{persons} persons × {lpcd:g} L/day × {float(inp['sump_days']):g} days = {daily * float(inp['sump_days']):,.0f} L"}
    # --- overhead tank
    need = daily * float(inp["oht_days"])
    oht = next((s for s in OHT_SIZES if s >= need), OHT_SIZES[-1])
    oht = int(float(inp.get("oht_litres") or oht))
    out["oht"] = {"litres": oht, "basis": f"{persons} × {lpcd:g} × {float(inp['oht_days']):g} day = {need:,.0f} L → {oht:,} L tank",
                  "count": 1 if oht <= 5000 else math.ceil(oht / 5000)}
    # --- septic
    users = persons
    row = next((r for r in SEPTIC_TABLE if r[0] >= users), None)
    if row:
        L, B, D = row[1], row[2], row[3]
    else:
        L, B, D = 5.0 * users / 50, 1.6, 1.3
        out["warnings"].append("More than 50 users: septic tank / STP to be designed by a PHE engineer.")
    out["septic"] = {"users": users, "inner_l_m": L, "inner_b_m": B, "liquid_depth_m": D, "freeboard_m": 0.3,
                     "chambers": "2 (first 2/3 of the length, second 1/3)",
                     "basis": f"IS 2470 (Part 1) table for {users} users, desludging once a year",
                     "needed": str(inp.get("sewer", "")).lower() not in ("yes", "y", "true", "1")}
    if not out["septic"]["needed"]:
        out["notes"].append("Sewer line available: connect to the sewer through the last inspection chamber – no septic tank.")
    else:
        out["septic"]["soak_pit"] = "Soak pit / dispersion trench after the septic tank – size from a percolation test (IS 2470 Part 2)."
    # --- rain water harvesting
    roof = roof_area_m2(plan)
    soil = str(inp.get("soil") or "").lower()
    n_wells = max(1, math.ceil(roof / float(inp["rwh_per_m2"])))
    depth_m = {"sandy": 3.0, "mixed": 3.5, "clayey": 4.5, "clay": 4.5}.get(soil)
    rock = soil.startswith("hard") or soil == "rock"
    out["rwh"] = {"roof_m2": roof, "wells": n_wells, "dia_m": 1.0, "depth_m": depth_m,
                  "type": "Recharge through the borewell (filter chamber + casing pipe)" if rock else
                  "Recharge well – perforated RCC rings, 1.0 m dia, filter media (pebbles + coarse sand)",
                  "basis": f"Roof {roof:g} m² → 1 well per {float(inp['rwh_per_m2']):g} m² (starting number; "
                           f"TNCDBR 2019 Rule 63(1) / Annexure XXII decides)",
                  "storm_m3": round(roof * 0.05 * 0.85, 2),
                  "pipes": max(2, math.ceil(roof / 40))}
    if depth_m is None and not rock:
        out["rwh"]["depth_m"] = None
    # --- positions (plot ft)
    spots = _free_spots(plan)
    pos = []
    used = []

    def place(name, w_ft, d_ft, prefer_front=True, avoid=None):
        """Best free rectangle: not under the driveway if possible, the preferred zone, and (septic) far from the sump."""
        best, key = None, None
        for sp in spots:
            if sp["w"] < w_ft or sp["d"] < d_ft:
                continue
            for xx in (sp["x"], sp["x"] + sp["w"] - w_ft):
                for yy in (sp["y"], sp["y"] + sp["d"] - d_ft):
                    rect = (xx, yy, w_ft, d_ft)
                    if not all(rect[0] >= u[0] + u[2] + 1 or rect[0] + w_ft + 1 <= u[0] or rect[1] >= u[1] + u[3] + 1
                               or rect[1] + d_ft + 1 <= u[1] for u in used):
                        continue
                    drive = "driveway" in sp["where"]
                    front = sp["where"] == "front open space"
                    dist = math.hypot(xx - avoid[0], yy - avoid[1]) if avoid else 0
                    k = (drive, (not front) if prefer_front else front, -round(dist / 3), yy if prefer_front else -yy)
                    if avoid:  # far from the sump matters more than the zone
                        k = (drive and dist < 10, -round(dist / 3), drive, (not front) if prefer_front else front)
                    if key is None or k < key:
                        best, key = (rect, sp["where"]), k
        if not best:
            out["warnings"].append(f"No open space big enough for the {name} – place it by hand on the sketch "
                                   f"(keep it at least 1 ft from the building).")
            return None
        rect, where = best
        used.append(rect)
        pos.append({"item": name, "x": round(rect[0], 2), "y": round(rect[1], 2), "w": round(w_ft, 2), "d": round(d_ft, 2), "where": where})
        if "driveway" in where:
            out["notes"].append(f"{name} is under the driveway: use an RCC cover slab designed for car load and a raised, sealed manhole cover.")
        return rect
    sw = out["sump"]["inner_l_m"] / FT + 1.0  # + walls
    sd = out["sump"]["inner_b_m"] / FT + 1.0
    srect = place("Sump", sw, sd, True)
    if out["septic"]["needed"]:
        place("Septic tank", L / FT + 1.0, B / FT + 1.0, True, avoid=srect)
    for i in range(n_wells):
        place(f"RWH well {i + 1}", 4.3, 4.3, False)
    out["positions"] = pos
    sp = next((p for p in pos if p["item"] == "Sump"), None)
    st = next((p for p in pos if p["item"] == "Septic tank"), None)
    if sp and st:
        dist = math.hypot(sp["x"] - st["x"], sp["y"] - st["y"]) * FT
        out["sump_septic_m"] = round(dist, 1)
        if dist < 3:
            out["warnings"].append(f"Sump and septic tank are only {dist:.1f} m apart – keep them as far apart as the plot allows "
                                   f"and make the sump fully watertight.")
    if out["septic"]["needed"] and str(inp.get("well", "")).lower() not in ("", "none", "no"):
        out["warnings"].append("IS 2470 asks the septic tank / soak pit to be at least 15 m from a well or borewell – "
                               "check the distance on site; on a small plot ask the local body.")
    # --- estimate (rates from the rate library – the app never prices by itself)
    lines = []
    if rates:
        def r(code):
            x = rates.get(code)
            return float(x[spec]) if x else None
        items = [("Underground sump", "sump", sump_l, "litre"), ("Overhead tank", "oh_tank", oht, "litre"),
                 ("Rain water harvesting well", "rwh", n_wells, "nos")]
        if out["septic"]["needed"]:
            items.append(("Septic tank + soak pit", "septic", 1, "nos"))
        for name, code, q, u in items:
            rate = r(code)
            lines.append({"item": name, "code": code, "qty": q, "unit": u, "rate": rate,
                          "amount": round(q * rate) if rate is not None else None})
    out["estimate"] = lines
    out["estimate_total"] = sum(x["amount"] or 0 for x in lines)
    return out


def pdf(plan: dict, res: dict, project: dict, approval: dict | None = None) -> bytes:
    from .pdfdoc import Doc, plot_sketch
    d = Doc("Water & Drainage Services – RWH, Sump, Tanks, Septic", project,
            "Preliminary sizes from the drawing. Verify with the local body (TNCDBR 2019 Rule 63 / Annexure XXII) and site conditions.")
    if res["questions"]:
        d.h("Still to confirm")
        d.bullets(res["questions"])
    s, o, t, w = res["sump"], res["oht"], res["septic"], res["rwh"]
    d.h("Sizes")
    rows = [["Underground sump", f"{s['litres']:,} L", f"{s['inner_l_m']} × {s['inner_b_m']} m inside, water depth {s['water_depth_m']} m "
                                                     f"+ {s['freeboard_m']} m free board", s["basis"]],
            ["Overhead tank", f"{o['litres']:,} L", f"{o['count']} tank(s)", o["basis"]]]
    if t["needed"]:
        rows.append(["Septic tank", f"{t['users']} users", f"{t['inner_l_m']} × {t['inner_b_m']} m inside, liquid depth "
                                                          f"{t['liquid_depth_m']} m + {t['freeboard_m']} m; {t['chambers']}", t["basis"]])
    rows.append(["Rain water harvesting", f"{w['wells']} no.", f"{w['type']}; dia {w['dia_m']} m, depth "
                                                              f"{(str(w['depth_m']) + ' m') if w['depth_m'] else 'to be fixed after soil type'}",
                 w["basis"]])
    rows.append(["Rain water pipes", f"{w['pipes']} no.", "110 mm PVC down pipes from the terrace outlets to the RWH well", ""])
    d.table(["Item", "Size", "Details", "Basis"], rows, [22, 14, 40, 34])
    if res.get("positions"):
        d.h("Positions (from the front-left corner of the plot)")
        d.table(["Item", "From left boundary", "From front boundary", "Size on plan", "Where"],
                [[p["item"], f"{p['x']:.1f} ft", f"{p['y']:.1f} ft", f"{p['w']:.1f} × {p['d']:.1f} ft", p["where"]]
                 for p in res["positions"]], [22, 18, 18, 20, 22])
        cols = {"Sump": "#0369a1", "Septic tank": "#b45309"}
        d.sketch(plot_sketch(plan, [{**p, "label": p["item"], "color": cols.get(p["item"], "#15803d")} for p in res["positions"]]), 180, 110)
    if res["warnings"] or res["notes"]:
        d.h("Notes")
        d.bullets(res["warnings"] + res["notes"])
    if res.get("estimate"):
        d.h("Estimate (rates from your rate library)")
        d.table(["Item", "Qty", "Unit", "Rate ₹", "Amount ₹"],
                [[x["item"], f"{x['qty']:,}", x["unit"], f"{x['rate']:,.0f}" if x["rate"] is not None else "rate not set",
                  f"{x['amount']:,.0f}" if x["amount"] is not None else "–"] for x in res["estimate"]]
                + [["Total", "", "", "", f"{res['estimate_total']:,.0f}"]], [40, 14, 10, 16, 20], bold_last=True)
    d.h("Approval")
    if approval and approval.get("status") == "approved":
        d.para(f"Approved by {approval.get('by') or '-'} on {approval.get('date') or '-'}" +
               (f" – {approval['note']}" if approval.get("note") else ""))
    else:
        d.para("Not approved yet.")
    d.signatures(["Client", "Site engineer"])
    return d.build()
