"""1.18 Staircase design – geometry, rule checks, waist-slab design (IS 456, limit state), bar bending schedule,
quantities for the estimate and the data the drawing sheet / 3D need.

Everything is worked out from the plan (floor height + the staircase room) and can be overridden in plan["stair"]:
  type: auto | straight | dog_legged | l_shape | u_shape | spiral     width_ft, riser_mm, tread_mm, waist_mm,
  internal (bool), finish: granite | tiles | kota | cement, railing: ss | ms | glass | wood, fck, fy
Limits used for the checks (commonly applied for houses – NBC 2016 Part 3/4 + IS 456; the approving authority's
rules decide): riser ≤ 190 mm, tread ≥ 250 mm, 2R + T = 550–700 mm, width ≥ 900 mm, headroom ≥ 2100 mm,
≤ 15 risers per flight. A value outside gives a warning – it is never blocked or changed behind the user's back.
"""
from __future__ import annotations

import math

MM_PER_FT = 304.8
LIMITS = {"riser_max": 190, "tread_min": 250, "width_min": 900, "headroom_min": 2100, "flight_max": 15,
          "two_r_t": (550, 700)}
TYPES = {"straight": "Straight flight", "dog_legged": "Dog-legged (two flights, half landing)",
         "l_shape": "L-shape (quarter landing)", "u_shape": "U / open-well", "spiral": "Spiral"}
BAR_AREA = {8: 50.27, 10: 78.54, 12: 113.1, 16: 201.06}


def _stair_room(plan: dict) -> dict | None:
    for lv in plan.get("levels", []):
        for r in lv.get("rooms", []):
            if r.get("type") == "stair":
                return r
    return None


def _levels_served(plan: dict) -> tuple[int, bool]:
    """(flights between floors, a flight up to the terrace / head room)."""
    n = len(plan.get("levels", []))
    sheets = plan.get("roof_sheets") or []
    full_sheet = any(s.get("place") == "full_roof" for s in sheets)
    return max(0, n - 1), not full_sheet


def geometry(plan: dict, o: dict | None = None) -> dict:
    o = {**(plan.get("stair") or {}), **(o or {})}
    room = _stair_room(plan)
    H = float(plan.get("floor_height_ft") or 10) * MM_PER_FT
    slab = 125.0
    rw = (room or {}).get("w", 7.5) * MM_PER_FT
    rd = (room or {}).get("d", 16) * MM_PER_FT
    long_, short = max(rw, rd), min(rw, rd)
    riser_t = float(o.get("riser_mm") or 0)
    n = math.ceil(H / (riser_t or 175.0) - 1e-9)
    riser = H / n
    tread = float(o.get("tread_mm") or 250)
    width = float(o.get("width_ft") or 0) * MM_PER_FT or None
    typ = o.get("type") or "auto"
    if typ == "auto":
        straight_len = (n - 1) * tread + 1000
        if room and long_ >= straight_len and short >= 900:
            typ = "straight"
        elif room and short >= 2 * 900 + 50:
            typ = "dog_legged"
        elif room:
            typ = "l_shape"
        else:
            typ = "dog_legged"
    if typ == "spiral":
        dia = float(o.get("dia_mm") or min(short, 2000))
        width = width or (dia / 2 - 150)
        flights = [{"risers": n, "going_mm": round((n - 1) * tread)}]
        landing = 0.0
    elif typ == "straight":
        width = width or min(short, 1000)
        flights = [{"risers": n, "going_mm": round((n - 1) * tread)}]
        landing = 0.0
    elif typ == "u_shape":
        a = n // 3
        flights = [{"risers": a, "going_mm": round((a - 1) * tread)}, {"risers": n - 2 * a, "going_mm": round((n - 2 * a - 1) * tread)},
                   {"risers": a, "going_mm": round((a - 1) * tread)}]
        width = width or min(1000, short / 2.2)
        landing = width
    else:  # dog-legged / L: two flights
        a = math.ceil(n / 2)
        flights = [{"risers": a, "going_mm": round((a - 1) * tread)}, {"risers": n - a, "going_mm": round((n - a - 1) * tread)}]
        width = width or (min(1000, (short - 50) / 2) if typ == "dog_legged" else min(1000, short))
        landing = width
    width = round(width)
    need_len = max(f["going_mm"] for f in flights) + landing + (landing if typ == "u_shape" else 0)
    need_wid = 2 * width + 50 if typ in ("dog_legged",) else (2 * width + 300 if typ == "u_shape" else width)
    if typ == "l_shape":
        need_len, need_wid = flights[0]["going_mm"] + width, flights[1]["going_mm"] + width
    # clear height from a step to the floor slab above (the slab is left open over the flights – the stair hole)
    headroom = H - slab - (300 if typ in ("dog_legged", "u_shape", "l_shape") else 0)  # beam at the hole edge
    checks = [
        _chk("Riser", round(riser), f"≤ {LIMITS['riser_max']} mm", riser <= LIMITS["riser_max"] + 0.5, "Steeper than usual – add a step."),
        _chk("Tread (going)", round(tread), f"≥ {LIMITS['tread_min']} mm", tread >= LIMITS["tread_min"], "Narrow tread – feet do not fit."),
        _chk("2R + T", round(2 * riser + tread), f"{LIMITS['two_r_t'][0]}–{LIMITS['two_r_t'][1]} mm",
             LIMITS["two_r_t"][0] <= 2 * riser + tread <= LIMITS["two_r_t"][1], "Uncomfortable step rhythm."),
        _chk("Width", width, f"≥ {LIMITS['width_min']} mm", width >= LIMITS["width_min"] - 1, "Narrow – check TNCDBR / NBC for this building."),
        _chk("Risers per flight", max(f["risers"] for f in flights), f"≤ {LIMITS['flight_max']}",
             max(f["risers"] for f in flights) <= LIMITS["flight_max"] or typ == "spiral", "Long flight – add a landing."),
        _chk("Headroom", round(headroom), f"≥ {LIMITS['headroom_min']} mm", headroom >= LIMITS["headroom_min"], "Low headroom – people hit their head."),
    ]
    if room:
        fits = need_len <= long_ + 1 and need_wid <= short + 1 if typ != "spiral" else (o.get("dia_mm") or short) <= short + 1
        checks.append(_chk("Fits the staircase room", f"{round(need_len)} × {round(need_wid)}",
                           f"room {round(long_)} × {round(short)} mm", fits, "Make the staircase room bigger or change the type."))
    return {"type": typ, "type_name": TYPES.get(typ, typ), "floor_height_mm": round(H), "risers": n, "riser_mm": round(riser, 1),
            "tread_mm": round(tread), "width_mm": width, "landing_mm": round(landing), "flights": flights,
            "need_mm": [round(need_len), round(need_wid)], "room_mm": [round(long_), round(short)] if room else None,
            "headroom_mm": round(headroom), "checks": checks, "ok": all(c["ok"] for c in checks),
            "internal": bool(o.get("internal", True)), "finish": o.get("finish") or "granite", "railing": o.get("railing") or "ss",
            "has_room": bool(room)}


def _chk(item, value, limit, ok, fix):
    return {"item": item, "value": value, "limit": limit, "ok": bool(ok), "note": "" if ok else fix}


def structure(g: dict, o: dict | None = None) -> dict:
    """Waist slab spanning along the flight + landing, simply supported (IS 456 cl. 33 / limit state)."""
    o = o or {}
    fck = float(o.get("fck") or 20)
    fy = float(o.get("fy") or 500)
    R, T = g["riser_mm"] / 1000, g["tread_mm"] / 1000
    going = max(f["going_mm"] for f in g["flights"]) / 1000
    span = going + (g["landing_mm"] / 1000 if g["type"] in ("dog_legged", "u_shape", "l_shape") else 0.3) + 0.23
    waist = float(o.get("waist_mm") or max(150.0, math.ceil(span * 1000 / 20 / 5) * 5))  # span / 20, min 150 mm
    cos = T / math.hypot(R, T)
    dl = 25 * (waist / 1000) / cos + 25 * R / 2 + 1.0   # waist (on plan) + steps + finish, kN/m²
    ll = 3.0                                             # IS 875-2 residential stairs
    wu = 1.5 * (dl + ll)                                  # per metre width
    mu = wu * span ** 2 / 8                               # kN·m per m width
    cover, bar = 20.0, 10
    d = waist - cover - 6
    d_req = math.sqrt(mu * 1e6 / (0.133 * fck * 1000))
    a = 0.87 * fy * fy / (1000 * fck)
    b_ = -0.87 * fy * d
    c_ = mu * 1e6
    disc = b_ * b_ - 4 * a * c_
    ast = (-b_ - math.sqrt(disc)) / (2 * a) if disc > 0 else float("inf")
    ast = max(ast, 0.0012 * 1000 * waist)
    for bar in (10, 12, 16):  # site practice: main bars at 100–200 mm c/c
        sp = min(200.0, 3 * d, math.floor(BAR_AREA[bar] * 1000 / ast / 10) * 10)
        if sp >= 100:
            break
    dist_ast = 0.0012 * 1000 * waist
    dsp = min(450.0, 5 * d, math.floor(BAR_AREA[8] * 1000 / dist_ast / 10) * 10)
    ok = d >= d_req and disc > 0
    return {"span_m": round(span, 2), "waist_mm": round(waist), "d_mm": round(d), "d_req_mm": round(d_req), "wu_kn_m": round(wu, 2),
            "mu_knm": round(mu, 2), "ast_mm2": round(ast), "main": {"dia": bar, "spacing": int(sp)}, "dist": {"dia": 8, "spacing": int(dsp)},
            "fck": fck, "fy": fy, "ok": ok,
            "note": ("Spiral stairs are usually steel / precast – this RCC result is only indicative; get the fabricator's design. "
                     if g["type"] == "spiral" else "")
                    + "Waist slab designed as simply supported along the flight (IS 456, limit state). Landing beam / wall support to be "
                    "confirmed by the engineer." + ("" if ok else " Depth not enough – increase the waist.")}


def bbs(g: dict, s: dict) -> list[dict]:
    """Bars for ONE staircase between two floors (all flights + landing)."""
    W = g["width_mm"] / 1000
    rows = []
    for i, f in enumerate(g["flights"], 1):
        slope = math.hypot(f["going_mm"] / 1000, f["risers"] * g["riser_mm"] / 1000)
        ld = 47 * s["main"]["dia"] / 1000
        main_len = slope + (g["landing_mm"] / 1000 if g["landing_mm"] else 0.3) + 2 * ld
        n_main = int(W / (s["main"]["spacing"] / 1000)) + 1
        n_dist = int(slope / (s["dist"]["spacing"] / 1000)) + 1
        rows.append(_bar(f"Flight {i} – main", s["main"]["dia"], n_main, main_len))
        rows.append(_bar(f"Flight {i} – distribution", 8, n_dist, W - 0.04))
        top = 0.3 * s["span_m"] + ld  # hogging bars at both supports (partial fixity)
        rows.append(_bar(f"Flight {i} – top bars at supports", s["main"]["dia"], 2 * n_main, top))
    if g["landing_mm"]:
        L = g["landing_mm"] / 1000
        span_w = 2 * W + 0.05 if g["type"] == "dog_legged" else W
        rows.append(_bar("Landing – main (across)", s["main"]["dia"], int(L / (s["main"]["spacing"] / 1000)) + 1, span_w + 2 * 0.3))
        rows.append(_bar("Landing – distribution", 8, int(span_w / (s["dist"]["spacing"] / 1000)) + 1, L + 0.3))
    return rows


def _bar(mark, dia, n, length):
    kg = n * length * dia * dia / 162.2
    return {"mark": mark, "dia": dia, "nos": n, "length_m": round(length, 2), "kg": round(kg, 1)}


def quantities(g: dict, s: dict, b: list[dict]) -> dict:
    """Per staircase between two floors."""
    W = g["width_mm"] / 1000
    R, T = g["riser_mm"] / 1000, g["tread_mm"] / 1000
    waist = s["waist_mm"] / 1000
    conc = 0.0
    shutter = 0.0
    for f in g["flights"]:
        slope = math.hypot(f["going_mm"] / 1000, f["risers"] * R)
        conc += slope * W * waist + (f["risers"] - 1) * (R * T / 2) * W
        shutter += slope * W + (f["risers"]) * R * W + 2 * slope * waist
    if g["landing_mm"]:
        L = g["landing_mm"] / 1000
        span_w = 2 * W + 0.05 if g["type"] == "dog_legged" else W
        conc += L * span_w * waist
        shutter += L * span_w
    steel = sum(r["kg"] for r in b)
    treads = g["risers"] - len(g["flights"])
    finish = (treads * T + g["risers"] * R) * W + (g["landing_mm"] / 1000 * W * (2 if g["type"] == "dog_legged" else 1) if g["landing_mm"] else 0)
    railing = sum(math.hypot(f["going_mm"] / 1000, f["risers"] * R) for f in g["flights"]) + (W if g["landing_mm"] else 0)
    return {"concrete_m3": round(conc, 3), "steel_kg": round(steel, 1), "formwork_m2": round(shutter, 2),
            "finish_m2": round(finish, 2), "railing_m": round(railing, 2)}


def design(plan: dict, o: dict | None = None) -> dict:
    g = geometry(plan, o)
    s = structure(g, {**(plan.get("stair") or {}), **(o or {})})
    b = bbs(g, s)
    q = quantities(g, s, b)
    floors, terrace = _levels_served(plan)
    return {**g, "structure": s, "bbs": b, "per_floor": q, "floors": floors, "terrace_flight": terrace,
            "summary": f"{g['type_name']} · {g['width_mm']} mm wide · {g['risers']} risers × {g['riser_mm']:g} mm, tread {g['tread_mm']} mm · "
                       f"waist {s['waist_mm']} mm, {s['main']['dia']} mm @ {s['main']['spacing']} c/c"}


def estimate_row(plan: dict) -> dict | None:
    """What the estimate needs (Inputs.stair)."""
    if not _stair_room(plan):
        return None
    d = design(plan)
    q = d["per_floor"]
    return {"concrete_m3": q["concrete_m3"], "steel_kg": q["steel_kg"], "formwork_m2": q["formwork_m2"], "finish_m2": q["finish_m2"],
            "railing_m": q["railing_m"], "finish": d["finish"], "railing": d["railing"], "label": d["type_name"].split(" (")[0],
            "terrace_flight": d["terrace_flight"]}


def has_stair(plan: dict) -> bool:
    return bool(_stair_room(plan)) and len(plan.get("levels", [])) > 1


def stair_detail(plan: dict):
    """Staircase Detail sheet: plan of the flights (treads, landing, UP arrow) + section with waist slab and bars."""
    from .sheets import Dwg
    d = design(plan)
    s = d["structure"]
    dw = Dwg("Staircase Detail")
    F = 1 / MM_PER_FT  # mm → ft (drawings are in feet)
    W = d["width_mm"] * F
    T = d["tread_mm"] * F
    R = d["riser_mm"] * F
    L = d["landing_mm"] * F
    fl = d["flights"]
    # ---------------- plan view
    if d["type"] in ("dog_legged", "u_shape") and len(fl) >= 2:
        g1 = fl[0]["going_mm"] * F
        gap = 50 * F
        dw.rect(0, 0, g1 + L, 2 * W + gap, "OUTLINE")
        y1 = W + gap  # flight 1 = upper strip going right, flight 2 = lower strip coming back → climbs clockwise
        for k in range(fl[0]["risers"]):
            dw.line(k * T, y1, k * T, y1 + W, "STAIR")
        for k in range(fl[1]["risers"]):
            dw.line(g1 - k * T, 0, g1 - k * T, W, "STAIR")
        dw.line(0, W, g1, W, "OUTLINE"); dw.line(0, W + gap, g1, W + gap, "OUTLINE")
        dw.line(g1, 0, g1, 2 * W + gap, "STAIR")
        ya = y1 + W / 2
        dw.line(0.3, ya, g1 - 0.6, ya, "MARK"); dw.line(g1 - 0.6, ya + 0.25, g1 - 0.3, ya, "MARK"); dw.line(g1 - 0.6, ya - 0.25, g1 - 0.3, ya, "MARK")
        dw.text(1.4, ya + 0.45, "UP", 0.5, layer="MARK", bold=True)
        dw.text(g1 / 2, W / 2, "UP (2nd flight)", 0.4, layer="DIM")
        dw.text(g1 + L / 2, W + gap / 2, f"LANDING {d['landing_mm']}", 0.45, layer="DIM")
        pw, ph = g1 + L, 2 * W + gap
    else:
        g1 = sum(f["going_mm"] for f in fl) * F
        dw.rect(0, 0, g1 + (L or 0.0), W, "OUTLINE")
        for k in range(d["risers"]):
            dw.line(k * T, 0, k * T, W, "STAIR")
        dw.line(0.3, W / 2, g1 - 0.6, W / 2, "MARK"); dw.line(g1 - 0.6, W / 2 + 0.25, g1 - 0.3, W / 2, "MARK"); dw.line(g1 - 0.6, W / 2 - 0.25, g1 - 0.3, W / 2, "MARK")
        dw.text(1.4, W / 2 + 0.45, "UP", 0.5, layer="MARK", bold=True)
        pw, ph = g1 + (L or 0), W
    dw.text(pw / 2, -1.2, f"PLAN – {d['type_name'].upper()}", 0.6, bold=True)
    dw.text(pw / 2, -2.1, f"WIDTH {d['width_mm']} · TREAD {d['tread_mm']} · RISER {d['riser_mm']:g} · {d['risers']} RISERS", 0.45, layer="DIM")
    # ---------------- section (flight 1 rising to the landing, flight 2 back up to the floor)
    ox = pw + 8
    wst = s["waist_mm"] * F
    x, z = ox, 0.0
    pts = [(x, z)]
    for k in range(fl[0]["risers"]):
        z += R; pts.append((x, z))
        if k < fl[0]["risers"] - 1:
            x += T; pts.append((x, z))
    for a, b in zip(pts, pts[1:]):
        dw.line(a[0], a[1], b[0], b[1], "OUTLINE")
    run = fl[0]["going_mm"] * F
    rise = fl[0]["risers"] * R
    k = wst / max(1e-6, T / math.hypot(R, T))
    dw.line(ox, -k, ox + run, rise - k, "SLAB")                       # soffit of the waist slab
    dw.line(ox + 0.1, -k + 0.12, ox + run, rise - k + 0.12, "REBAR")   # main bars, parallel to the soffit
    if len(fl) > 1:
        dw.line(ox + run, rise, ox + run + L, rise, "OUTLINE")         # landing
        dw.line(ox + run, rise - wst, ox + run + L, rise - wst, "SLAB")
        dw.line(ox + run, rise - k + 0.12, ox + run + L - 0.1, rise - wst + 0.12, "REBAR")
        x2, z2 = ox + run, rise                                        # second flight returns over the first (seen beyond)
        pts2 = [(x2, z2)]
        for k2 in range(fl[1]["risers"]):
            z2 += R; pts2.append((x2, z2))
            if k2 < fl[1]["risers"] - 1:
                x2 -= T; pts2.append((x2, z2))
        for a, b in zip(pts2, pts2[1:]):
            dw.line(a[0], a[1], b[0], b[1], "STAIR")                  # second flight (seen beyond)
    dw.line(ox - 1.5, 0, ox, 0, "GROUND")
    dw.text(ox + run / 2, -k - 1.2, f"WAIST SLAB {s['waist_mm']} THK · M{s['fck']:g} / Fe{s['fy']:g}", 0.45, layer="DIM")
    dw.text(ox + run / 2, -k - 2.0, f"MAIN {s['main']['dia']} Ø @ {s['main']['spacing']} c/c · DISTRIBUTION 8 Ø @ {s['dist']['spacing']} c/c", 0.45, layer="REBAR")
    dw.text(ox + run / 2, -k - 2.8, f"TOP BARS {s['main']['dia']} Ø AT SUPPORTS (0.3 × SPAN) · COVER 20 mm", 0.45, layer="REBAR")
    dw.text(ox + run / 2, max(rise, z) + 1.5, "SECTION THROUGH THE STAIR", 0.6, bold=True)
    # ---------------- checks
    ty = -4.5
    for c in d["checks"]:
        dw.text(0, ty, f"{'OK' if c['ok'] else 'CHECK'}  {c['item']}: {c['value']} ({c['limit']})", 0.42, anchor="start",
                layer="DIM" if c["ok"] else "MARK")
        ty -= 0.8
    return dw
