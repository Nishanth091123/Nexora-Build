"""1.12 – Preliminary RCC structural design from a saved floor plan (IS 456:2000, gravity loads).

Column grid from wall junctions (spans ≤ 4.5 m), beams on wall lines, slab panels = rooms, isolated footings.
Limit-state design with simple, conservative rules:
  slabs  – IS 456 Annex D / Table 26 coefficients (two-way), wl²/10 (one-way); min steel 0.12 %.
  beams  – wl²/10 (continuous) or wl²/8 (single span); Mu ≤ Mu,lim = 0.133 fck b d² (Fe500); shear Table 19.
  columns– short axially loaded, Pu = 0.4 fck Ac + 0.67 fy Asc (0.8–4 % steel); tributary area by nearest column.
  footings – area from the SAFE BEARING CAPACITY given by the user (never assumed), punching + one-way shear,
             bending at the column face.
NOT included: lateral (wind / earthquake, IS 875-3 / IS 1893) analysis. Results are a preliminary design for
estimating and discussion – a qualified structural engineer must check and sign the final design.
Units in: plan in feet. Calculations in kN, m, mm. Output sizes in mm.
"""
from __future__ import annotations

import math

FT = 0.3048
ZONES = ("II", "III", "IV", "V")
TC_M20 = [(0.15, 0.28), (0.25, 0.36), (0.5, 0.48), (0.75, 0.56), (1.0, 0.62), (1.25, 0.67), (1.5, 0.72), (2.0, 0.79)]
# IS 456 Table 26, case 4 "two adjacent edges discontinuous": ly/lx → (short −, short +); long: −0.047 / +0.035
ALPHA = [(1.0, 0.047, 0.035), (1.1, 0.053, 0.040), (1.2, 0.060, 0.045), (1.3, 0.065, 0.049), (1.4, 0.071, 0.053),
         (1.5, 0.075, 0.056), (1.75, 0.084, 0.063), (2.0, 0.091, 0.069)]
BAR_AREA = {8: 50.27, 10: 78.54, 12: 113.1, 16: 201.06, 20: 314.16, 25: 490.87}


class NeedInfo(ValueError):
    def __init__(self, questions: list[str]):
        super().__init__("; ".join(questions))
        self.questions = questions


def _interp(table, x, col=1):
    if x <= table[0][0]:
        return table[0][col]
    for a, b in zip(table, table[1:]):
        if x <= b[0]:
            return a[col] + (b[col] - a[col]) * (x - a[0]) / (b[0] - a[0])
    return table[-1][col]


def tau_c(pt: float, fck: float) -> float:
    k = 1.0 if fck <= 20 else 1.03 if fck <= 25 else 1.06  # small grade bonus (Table 19 trend)
    return _interp(TC_M20, max(0.15, pt)) * k


def ast_req(mu_knm: float, b: float, d: float, fck: float, fy: float) -> float:
    """mm² for Mu (kN·m), b, d in mm (singly reinforced)."""
    mu = mu_knm * 1e6
    x = 1 - 4.6 * mu / (fck * b * d * d)
    if x <= 0:
        return float("inf")
    return 0.5 * fck / fy * (1 - math.sqrt(x)) * b * d


def ceil_to(v: float, step: float) -> float:
    return math.ceil(v / step - 1e-9) * step


def pick_bars(ast: float, dias=(12, 16, 20), nmin=2, nmax=6) -> tuple[int, int]:
    for dia in dias:
        n = max(nmin, math.ceil(ast / BAR_AREA[dia]))
        if n <= nmax:
            return n, dia
    dia = dias[-1]
    return max(nmin, math.ceil(ast / BAR_AREA[dia])), dia


# ---------------------------------------------------------------- inputs
def clean_inputs(raw: dict) -> dict:
    q = []
    fck = int(raw.get("fck") or 20)
    fy = int(raw.get("fy") or 500)
    if fck not in (20, 25, 30):
        q.append("Concrete grade must be M20, M25 or M30.")
    if fy not in (415, 500, 550):
        q.append("Steel grade must be Fe415, Fe500 or Fe550.")
    sbc = raw.get("sbc_kn_m2")
    if sbc in (None, "", 0):
        q.append("Safe bearing capacity of the soil (kN/m²) – from the soil test report. Typical values: soft clay "
                 "50–100, stiff clay / sandy soil 150–200, hard murrum / gravel 250–300. Please enter the value for "
                 "THIS site; it is not assumed.")
    else:
        sbc = float(sbc)
        if not 40 <= sbc <= 600:
            q.append("Safe bearing capacity looks wrong – enter 40 to 600 kN/m².")
    zone = str(raw.get("seismic_zone") or "").upper().replace("ZONE", "").strip()
    if zone not in ZONES:
        q.append("Seismic zone of the site (IS 1893): II, III, IV or V. (Most of Tamil Nadu is II or III; Chennai is III.)")
    depth = float(raw.get("foundation_depth_m") or 1.5)
    if not 0.9 <= depth <= 4:
        q.append("Foundation depth should be 0.9 to 4 m.")
    if q:
        raise NeedInfo(q)
    return {"fck": fck, "fy": fy, "sbc_kn_m2": sbc, "seismic_zone": zone, "foundation_depth_m": depth,
            "live_load": float(raw.get("live_load") or 2.0), "roof_live_load": float(raw.get("roof_live_load") or 1.5),
            "floor_finish": float(raw.get("floor_finish") or 1.0), "wall_density": float(raw.get("wall_density") or 20.0)}


# ---------------------------------------------------------------- grid
def _segments(plan: dict):
    hs, vs = [], []
    for lv in plan["levels"]:
        for w in lv.get("walls", []):
            if w["kind"] not in ("ext", "int230"):
                continue
            if w["y1"] == w["y2"]:
                hs.append((min(w["x1"], w["x2"]), max(w["x1"], w["x2"]), w["y1"]))
            else:
                vs.append((min(w["y1"], w["y2"]), max(w["y1"], w["y2"]), w["x1"]))
    return hs, vs


def column_points(plan: dict, max_span_ft: float = 4.5 / FT, merge_ft: float = 3.5) -> list[tuple[float, float]]:
    hs, vs = _segments(plan)
    pts = []
    for x0, x1, y in hs:
        pts += [(x0, y), (x1, y)]
    for y0, y1, x in vs:
        pts += [(x, y0), (x, y1)]
    for x0, x1, y in hs:
        for y0, y1, x in vs:
            if x0 - 0.01 <= x <= x1 + 0.01 and y0 - 0.01 <= y <= y1 + 0.01:
                pts.append((x, y))
    # merge close points (keep the first – corners/junctions are listed first)
    out: list[tuple[float, float]] = []
    for p in pts:
        if all(math.hypot(p[0] - q[0], p[1] - q[1]) > merge_ft for q in out):
            out.append((round(p[0], 2), round(p[1], 2)))
    # never put a column inside a room of any floor (e.g. upper-floor wall junction above the car parking):
    # such walls sit on beams / slab instead
    def inside_room(p):
        for lv in plan["levels"]:
            for r in lv["rooms"]:
                if r["x"] + 0.6 < p[0] < r["x"] + r["w"] - 0.6 and r["y"] + 0.6 < p[1] < r["y"] + r["d"] - 0.6:
                    return True
        return False
    out = [p for p in out if not inside_room(p)]
    # snap nearly-equal x (and y) values to one grid line (within 1.2 ft) so the grid reads cleanly
    for axis in (0, 1):
        vals = sorted({p[axis] for p in out})
        groups, cur = [], [vals[0]] if vals else []
        for v in vals[1:]:
            if v - cur[-1] <= 1.2:
                cur.append(v)
            else:
                groups.append(cur)
                cur = [v]
        if cur:
            groups.append(cur)
        snap = {v: round(sum(g) / len(g), 2) if not any(abs(x - round(x)) < 0.01 for x in g) else next(x for x in g if abs(x - round(x)) < 0.01)
                for g in groups for v in g}
        out = [((snap[p[0]], p[1]) if axis == 0 else (p[0], snap[p[1]])) for p in out]
    out = list(dict.fromkeys(out))
    # long walls: add intermediate columns so no beam span exceeds max_span
    changed = True
    while changed:
        changed = False
        for x0, x1, y in hs:
            on = sorted(p[0] for p in out if abs(p[1] - y) < 0.6 and x0 - 0.6 <= p[0] <= x1 + 0.6)
            for a, b in zip(on, on[1:]):
                if b - a > max_span_ft and not inside_room(((a + b) / 2, y)):
                    out.append((round((a + b) / 2, 2), y))
                    changed = True
                    break
        for y0, y1, x in vs:
            on = sorted(p[1] for p in out if abs(p[0] - x) < 0.6 and y0 - 0.6 <= p[1] <= y1 + 0.6)
            for a, b in zip(on, on[1:]):
                if b - a > max_span_ft and not inside_room((x, (a + b) / 2)):
                    out.append((x, round((a + b) / 2, 2)))
                    changed = True
                    break
    return out


def beam_spans(plan: dict, cols: list[tuple[float, float]]) -> list[dict]:
    hs, vs = _segments(plan)
    spans = {}
    for x0, x1, y in hs:
        on = sorted({p[0] for p in cols if abs(p[1] - y) < 0.6 and x0 - 0.6 <= p[0] <= x1 + 0.6})
        for a, b in zip(on, on[1:]):
            spans[("h", round(y, 2), round(a, 2), round(b, 2))] = {"dir": "h", "x1": a, "y1": y, "x2": b, "y2": y, "n_on_line": len(on)}
    for y0, y1, x in vs:
        on = sorted({p[1] for p in cols if abs(p[0] - x) < 0.6 and y0 - 0.6 <= p[1] <= y1 + 0.6})
        for a, b in zip(on, on[1:]):
            spans[("v", round(x, 2), round(a, 2), round(b, 2))] = {"dir": "v", "x1": x, "y1": a, "x2": x, "y2": b, "n_on_line": len(on)}
    return list(spans.values())


# ---------------------------------------------------------------- design
def design(plan: dict, raw: dict) -> dict:
    inp = clean_inputs(raw)
    fck, fy = inp["fck"], inp["fy"]
    H = float(plan.get("floor_height_ft") or 10) * FT
    n = len(plan["levels"])
    warnings, notes = [], []
    cols = column_points(plan)
    if len(cols) < 4:
        raise NeedInfo(["Too few walls to place columns – open a complete design (walls on every floor)."])
    beams = beam_spans(plan, cols)

    # ---- slabs (each room = one panel, per level)
    slabs = []
    for li, lv in enumerate(plan["levels"]):
        roof_above = True
        for r in lv["rooms"]:
            if r["type"] in ("terrace", "stair", "parking") and r["type"] != "parking":
                continue
            lx, ly = sorted((r["w"] * FT, r["d"] * FT))
            ratio = ly / lx if lx else 9
            two_way = ratio <= 2.0
            D = max(125, ceil_to(lx * 1000 / (32 if two_way else 26) + 25, 5))
            ll = inp["roof_live_load"] if li == n - 1 else inp["live_load"]
            while True:
                d = D - 20 - 5
                w = 25 * D / 1000 + inp["floor_finish"] + ll + (1.0 if li == n - 1 else 0)  # +1 kN/m² weathering course on roof
                wu = 1.5 * w
                if two_way:
                    ax_neg, ax_pos = _interp(ALPHA, ratio, 1), _interp(ALPHA, ratio, 2)
                    m_neg, m_pos = ax_neg * wu * lx * lx, ax_pos * wu * lx * lx
                    m_long = 0.035 * wu * lx * lx
                else:
                    m_neg = m_pos = wu * lx * lx / 10
                    m_long = 0
                if max(m_neg, m_pos) * 1e6 <= 0.133 * fck * 1000 * d * d or D >= 250:
                    break
                D += 10
            ast_min = 0.0012 * 1000 * D
            a_x = max(ast_req(max(m_neg, m_pos), 1000, d, fck, fy), ast_min)
            a_y = max(ast_req(m_long, 1000, d - 8, fck, fy) if m_long else 0, ast_min)

            def spacing(ast):
                for dia in (8, 10, 12):
                    s = math.floor(1000 * BAR_AREA[dia] / ast / 10) * 10
                    s = min(s, 3 * d, 300)
                    if s >= 100:
                        return dia, int(s)
                return 12, 100
            dx, sx = spacing(a_x)
            dy, sy = spacing(a_y if two_way else ast_min)
            slabs.append({"level": lv["name"], "room": r["name"], "x": r["x"], "y": r["y"], "w": r["w"], "d": r["d"],
                          "lx_m": round(lx, 2), "ly_m": round(ly, 2), "type": "Two-way" if two_way else "One-way",
                          "D_mm": int(D), "load_kn_m2": round(w, 2),
                          "short_steel": f"{dx} mm @ {sx} c/c", "long_steel": f"{dy} mm @ {sy} c/c" + ("" if two_way else " (distribution)"),
                          "short_dia": dx, "short_s": sx, "long_dia": dy, "long_s": sy,
                          "concrete_m3": round(lx * ly * D / 1000, 3)})

    # ---- beams (same lines on every floor; roof beams carry parapet only on the outside)
    slab_by_level = {}
    for s in slabs:
        slab_by_level.setdefault(s["level"], []).append(s)
    beam_out = []
    for li, lv in enumerate(plan["levels"]):
        for bm in beams:
            L = (abs(bm["x2"] - bm["x1"]) + abs(bm["y2"] - bm["y1"])) * FT
            if L < 0.6:
                continue
            # tributary width: half of the short span of each slab panel along this beam
            trib, wslab = 0.0, 0.0
            for s in slab_by_level.get(lv["name"], []):
                if bm["dir"] == "h":
                    touches = (abs(s["y"] - bm["y1"]) < 0.6 or abs(s["y"] + s["d"] - bm["y1"]) < 0.6) and \
                        min(s["x"] + s["w"], bm["x2"]) - max(s["x"], bm["x1"]) > 0.5
                else:
                    touches = (abs(s["x"] - bm["x1"]) < 0.6 or abs(s["x"] + s["w"] - bm["x1"]) < 0.6) and \
                        min(s["y"] + s["d"], bm["y2"]) - max(s["y"], bm["y1"]) > 0.5
                if touches:
                    trib += s["lx_m"] / 2
                    wslab = max(wslab, s["load_kn_m2"])
            roof = li == n - 1
            wall = inp["wall_density"] * 0.23 * (1.0 if roof else max(0.0, H - 0.45))  # parapet 1 m on roof
            b = 230
            D = max(300, ceil_to(L * 1000 / 12, 25))
            single = bm["n_on_line"] <= 2
            while True:
                d = D - 25 - 8 - 8
                w = wslab * trib + wall + 25 * b * D / 1e6
                wu = 1.5 * w
                mu = wu * L * L / (8 if single else 10)
                if mu * 1e6 <= 0.133 * fck * b * d * d or D >= 600:
                    break
                D += 25
            ast = max(ast_req(mu, b, d, fck, fy), 0.85 * b * d / fy)
            nb, db = pick_bars(ast, (12, 16, 20), 2, 4)
            top_ast = max(0.5 * ast, 2 * BAR_AREA[12]) if not single else 2 * BAR_AREA[12]
            nt, dt = pick_bars(top_ast, (12, 16), 2, 4)
            vu = wu * L / 2
            tv = vu * 1000 / (b * d)
            pt = 100 * nb * BAR_AREA[db] / (b * d)
            tc = tau_c(pt, fck)
            asv = 2 * BAR_AREA[8]
            if tv > tc:
                sv = 0.87 * fy * asv * d / ((vu * 1000) - tc * b * d)
            else:
                sv = 0.87 * fy * asv / (0.4 * b)
            sv = int(max(75, min(sv, 0.75 * d, 300) // 25 * 25))
            if tv > 2.8:
                warnings.append(f"{lv['name']} beam {L:.1f} m: shear too high for 230 mm width – structural engineer to check.")
            beam_out.append({"level": lv["name"], "x1": bm["x1"], "y1": bm["y1"], "x2": bm["x2"], "y2": bm["y2"], "dir": bm["dir"],
                             "span_m": round(L, 2), "b_mm": b, "D_mm": int(D), "load_kn_m": round(w, 1), "mu_knm": round(mu, 1),
                             "bottom": f"{nb}-{db} mm", "top": f"{nt}-{dt} mm", "stirrups": f"2L-8 mm @ {sv} c/c",
                             "nb": nb, "db": db, "nt": nt, "dt": dt, "sv": sv,
                             "concrete_m3": round(L * b * D / 1e6, 3)})

    # ---- columns: tributary area by nearest column (1 ft samples of every room and wall)
    load = [0.0] * len(cols)

    def nearest(x, y):
        return min(range(len(cols)), key=lambda i: (cols[i][0] - x) ** 2 + (cols[i][1] - y) ** 2)
    for li, lv in enumerate(plan["levels"]):
        roof = li == n - 1
        for r in lv["rooms"]:
            ll = inp["roof_live_load"] if roof else inp["live_load"]
            D = next((s["D_mm"] for s in slab_by_level.get(lv["name"], []) if s["room"] == r["name"]), 125)
            q = 25 * D / 1000 + inp["floor_finish"] + ll + (1.0 if roof else 0)
            nx, ny = max(1, int(r["w"])), max(1, int(r["d"]))
            a = (r["w"] * FT / nx) * (r["d"] * FT / ny)
            for i in range(nx):
                for j in range(ny):
                    load[nearest(r["x"] + (i + 0.5) * r["w"] / nx, r["y"] + (j + 0.5) * r["d"] / ny)] += q * a
        for w in lv.get("walls", []):
            if w["kind"] not in ("ext", "int230", "int115"):
                continue
            t = 0.23 if w["kind"] != "int115" else 0.115
            h = 1.0 if roof and w["kind"] == "ext" else max(0.0, H - 0.45)
            L = math.hypot(w["x2"] - w["x1"], w["y2"] - w["y1"])
            k = max(1, int(L))
            for s_ in range(k):
                f = (s_ + 0.5) / k
                load[nearest(w["x1"] + (w["x2"] - w["x1"]) * f, w["y1"] + (w["y2"] - w["y1"]) * f)] += \
                    inp["wall_density"] * t * h * L * FT / k
    for bm in beam_out:  # beam self weight to the two end columns
        sw = 25 * bm["b_mm"] * bm["D_mm"] / 1e6 * bm["span_m"] / 2
        load[nearest(bm["x1"], bm["y1"])] += sw
        load[nearest(bm["x2"], bm["y2"])] += sw
    zone = inp["seismic_zone"]
    min_b, min_d = (300, 300) if zone in ("III", "IV", "V") else (230, 300)
    col_out = []
    for i, (x, y) in enumerate(cols):
        P = load[i] * 1.1  # + column self weight / misc (10 %)
        pu = 1.5 * P
        b, D = min_b, min_d
        while True:
            ag = b * D
            p = 0.01
            cap = (0.4 * fck * (1 - p) + 0.67 * fy * p) * ag / 1000
            if cap >= pu or (b >= 450 and D >= 600):
                break
            if D <= b + 75:
                D += 75
            else:
                b += 75
        asc_req = max(0.008 * b * D, (pu * 1000 - 0.4 * fck * b * D) / (0.67 * fy - 0.4 * fck))
        nb, db = 4, 12
        for dia in (12, 16, 20):
            nb = max(4, math.ceil(asc_req / BAR_AREA[dia]))
            nb += nb % 2
            if nb <= 8:
                db = dia
                break
        else:
            db = 20
        tie_s = int(min(min(b, D), 16 * db, 300) // 25 * 25)
        if zone in ("III", "IV", "V"):
            tie_s = min(tie_s, 150)
        leff_ratio = 0.85 * H * 1000 / min(b, D)
        if leff_ratio > 12:
            warnings.append(f"Column at ({x:.1f}', {y:.1f}'): slender (Leff/b {leff_ratio:.1f} > 12) – engineer to check.")
        col_out.append({"x": x, "y": y, "P_kn": round(P, 1), "Pu_kn": round(pu, 1), "b_mm": int(b), "D_mm": int(D),
                        "bars": f"{nb}-{db} mm", "nb": nb, "db": db, "ties": f"8 mm @ {tie_s} c/c", "tie_s": tie_s,
                        "steel_pct": round(100 * nb * BAR_AREA[db] / (b * D), 2),
                        "concrete_m3": round(b * D / 1e6 * (n * H + inp["foundation_depth_m"]), 3)})

    # ---- footings
    sbc = inp["sbc_kn_m2"]
    foot_out = []
    for c in col_out:
        Pf = c["P_kn"] * 1.1  # + footing & soil self weight
        B = max(1.0, ceil_to(math.sqrt(Pf / sbc), 0.15))
        qu = 1.5 * c["P_kn"] / (B * B)
        a, bcol = c["b_mm"] / 1000, c["D_mm"] / 1000
        d = 0.25
        while d < 1.2:
            b0 = 2 * ((a + d) + (bcol + d))
            vp = qu * (B * B - (a + d) * (bcol + d))
            tp = vp / (b0 * d) / 1000
            cant = (B - min(a, bcol)) / 2
            v1 = qu * B * max(0.0, cant - d)
            t1 = v1 / (B * d) / 1000
            if tp <= 0.25 * math.sqrt(fck) and t1 <= tau_c(0.25, fck):
                break
            d += 0.05
        mu = qu * B * cant * cant / 2
        ast = max(ast_req(mu, B * 1000, d * 1000, fck, fy), 0.0012 * B * 1000 * (d * 1000 + 60)) / B  # per m
        sp = int(min(200, math.floor(1000 * BAR_AREA[12] / ast / 10) * 10))
        dia = 12 if sp >= 100 else 16
        if dia == 16:
            sp = int(min(200, math.floor(1000 * BAR_AREA[16] / ast / 10) * 10))
        Dt = ceil_to(d * 1000 + 50 + 6, 50)
        foot_out.append({"x": c["x"], "y": c["y"], "B_m": round(B, 2), "D_mm": int(Dt), "steel": f"{dia} mm @ {sp} c/c both ways",
                         "dia": dia, "s": sp, "pressure_kn_m2": round(Pf / (B * B), 1), "col": f"{c['b_mm']}x{c['D_mm']}",
                         "concrete_m3": round(B * B * Dt / 1000, 3), "pcc_m3": round((B + 0.2) ** 2 * 0.1, 3)})
    for i, f in enumerate(foot_out):  # overlapping footings → combined footing needed
        for g in foot_out[i + 1:]:
            dist = math.hypot(f["x"] - g["x"], f["y"] - g["y"]) * FT
            if dist < (f["B_m"] + g["B_m"]) / 2 + 0.15:
                warnings.append(f"Footings at ({f['x']:.1f}', {f['y']:.1f}') and ({g['x']:.1f}', {g['y']:.1f}') overlap – "
                                "use a combined / strip footing (engineer).")

    # ---- marks: group identical members
    def mark(items, key, prefix):
        groups = {}
        for it in items:
            k = key(it)
            if k not in groups:
                groups[k] = f"{prefix}{len(groups) + 1}"
            it["mark"] = groups[k]
        return groups
    mark(col_out, lambda c: (c["b_mm"], c["D_mm"], c["bars"], c["ties"]), "C")
    mark(foot_out, lambda f: (f["B_m"], f["D_mm"], f["steel"]), "F")
    mark(beam_out, lambda b: (b["b_mm"], b["D_mm"], b["bottom"], b["top"], b["stirrups"]), "B")
    mark(slabs, lambda s: (s["D_mm"], s["short_steel"], s["long_steel"]), "S")
    for f, c in zip(foot_out, col_out):
        f["col_mark"] = c["mark"]

    def schedule(items, fields):
        rows = {}
        for it in items:
            r = rows.setdefault(it["mark"], {**{k: it[k] for k in fields}, "mark": it["mark"], "count": 0})
            r["count"] += 1
        return sorted(rows.values(), key=lambda r: int(r["mark"][1:]))

    # ---- quantities & checks
    conc = {"Footings": sum(f["concrete_m3"] for f in foot_out), "Columns": sum(c["concrete_m3"] for c in col_out),
            "Beams": sum(b["concrete_m3"] for b in beam_out), "Slabs": sum(s["concrete_m3"] for s in slabs)}
    steel_kg_m3 = {"Footings": 60, "Columns": 180, "Beams": 150, "Slabs": 90}
    qty = [{"member": k, "concrete_m3": round(v, 2), "steel_kg": round(v * steel_kg_m3[k])} for k, v in conc.items()]
    if n >= 3 and zone in ("III", "IV", "V"):
        warnings.append("G+2 or taller in seismic zone III+: earthquake (IS 1893) analysis and ductile detailing "
                        "(IS 13920) by a structural engineer are required.")
    notes += [
        f"Concrete M{fck}, steel Fe{fy}. Covers: slab 20 mm, beam 25 mm, column 40 mm, footing 50 mm.",
        f"Loads: live {inp['live_load']} kN/m² (roof {inp['roof_live_load']}), floor finish {inp['floor_finish']} kN/m², "
        f"masonry {inp['wall_density']} kN/m³, safe bearing capacity {sbc:g} kN/m² (given), foundation depth "
        f"{inp['foundation_depth_m']} m.",
        "Gravity loads only (IS 456). Wind / earthquake analysis is not part of this preliminary design.",
        "Lap length 50 d (tension), development length 47 d (Fe500, M20). Hooks 135° for ties and stirrups.",
        "PRELIMINARY DESIGN – to be checked and signed by a qualified structural engineer before construction.",
    ]
    return {
        "inputs": inp, "floor_height_m": round(H, 2), "levels": [lv["name"] for lv in plan["levels"]],
        "columns": col_out, "beams": beam_out, "slabs": slabs, "footings": foot_out,
        "column_schedule": schedule(col_out, ["b_mm", "D_mm", "bars", "ties", "Pu_kn"]),
        "beam_schedule": schedule(beam_out, ["b_mm", "D_mm", "bottom", "top", "stirrups", "span_m"]),
        "slab_schedule": schedule(slabs, ["D_mm", "type", "short_steel", "long_steel"]),
        "footing_schedule": schedule(foot_out, ["B_m", "D_mm", "steel", "col"]),
        "quantities": qty, "warnings": list(dict.fromkeys(warnings)), "notes": notes,
        "summary": {"columns": len(col_out), "beams": len(beam_out), "slabs": len(slabs), "footings": len(foot_out),
                    "concrete_m3": round(sum(conc.values()), 2), "steel_kg": round(sum(q["steel_kg"] for q in qty))},
    }
