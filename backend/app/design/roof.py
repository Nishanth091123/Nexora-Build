"""1.17 – Roofing sheets (metal / cement / polycarbonate) on a design.

plan["roof_sheets"] = list of sheet roofs, each:
  id, place      full_roof  – sheet roof INSTEAD of the RCC roof slab of the top floor
                 on_terrace – a shed on top of the RCC terrace (whole or part)
                 headroom   – the staircase head room (mumty) gets a sheet instead of a slab
                 area       – a part of a floor: sit-out, car parking, utility / wash, balcony …
  level          floor index the sheet belongs to (its roof / its area)
  x, y, w, d     covered area in building coordinates (ft) – without the overhang
  sheet          gi | galvalume | puff | acc | polycarbonate
  thk_mm, colour sheet thickness and colour
  shape          gable | mono | hip
  ridge          "x" (ridge runs across the front) | "y" (ridge runs front-to-back)   – gable / hip
  high           front | back | left | right                                          – mono-pitch (the high side)
  slope_deg      roof slope (degrees)
  height_ft      clear height at the eave above the floor / terrace it stands on (on_terrace, area)
  overhang_ft    eave projection beyond the covered area
  support        truss | purlin (purlins on posts / walls only – small spans)
  truss          {"top": "...", "bottom": "...", "web": "...", "purlin": "...", "purlin_ft": 4.0} – member sizes as entered

Everything is drawn / estimated from these numbers only. Member sizes are written as entered (the defaults are shown
in the form and must be confirmed by the engineer)."""
from __future__ import annotations

import math

FT_M = 0.3048
SHEETS = {
    "gi": {"label": "GI sheet", "thk": [0.40, 0.45, 0.50, 0.63], "colour": "#9ca3af", "kgm2": 4.5, "profile": "corrugated"},
    "galvalume": {"label": "Galvalume colour-coated sheet", "thk": [0.40, 0.45, 0.47, 0.50], "colour": "#b91c1c", "kgm2": 4.2,
                  "profile": "trapezoidal"},
    "puff": {"label": "PUF insulated sandwich panel", "thk": [30, 40, 50], "colour": "#e5e7eb", "kgm2": 11.0, "profile": "trapezoidal"},
    "acc": {"label": "Fibre-cement (ACC) sheet", "thk": [4.0, 6.0], "colour": "#9ca3af", "kgm2": 17.0, "profile": "corrugated"},
    "polycarbonate": {"label": "Polycarbonate sheet", "thk": [2.0, 3.0, 6.0], "colour": "#cfe8f7", "kgm2": 2.0, "profile": "corrugated"},
}
PLACES = {"full_roof": "Full roof (instead of RCC slab)", "on_terrace": "Shed on the RCC terrace",
          "headroom": "Staircase head room (mumty)", "area": "Part of a floor (sit-out / parking / utility / balcony)"}
SHAPES = {"gable": "Gable (two slopes)", "mono": "Mono-pitch (one slope)", "hip": "Hip (four slopes)"}
SUPPORTS = {"truss": "MS steel truss + purlins", "purlin": "Purlins on posts / walls"}
DEFAULT_TRUSS = {"top": "ISA 50x50x6", "bottom": "ISA 50x50x6", "web": "ISA 40x40x5", "purlin": "40x40x2 mm SHS",
                 "post": "80 NB MS pipe", "purlin_ft": 4.0}
PLINTH, SLAB, PARAPET, HEADROOM = 1.5, 125 / 304.8, 3.0, 8.0


def _f(v, lo, hi, default):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def clean(items, plan: dict) -> list[dict]:
    """Validate what the screen sent. Unknown keys are dropped; numbers are clamped to sensible limits."""
    out = []
    if not isinstance(items, list):
        return out
    n = len(plan.get("levels") or [])
    b = plan.get("building") or {}
    bw, bd = float(b.get("w") or 0), float(b.get("d") or 0)
    for k, s in enumerate(items[:12]):
        if not isinstance(s, dict) or s.get("place") not in PLACES or s.get("sheet") not in SHEETS:
            continue
        lv = int(_f(s.get("level", n - 1), 0, max(0, n - 1), n - 1))
        x = _f(s.get("x"), 0, bw, 0)
        y = _f(s.get("y"), 0, bd, 0)
        w = _f(s.get("w"), 1, bw - x if bw else 200, bw - x)
        d = _f(s.get("d"), 1, bd - y if bd else 200, bd - y)
        tr = s.get("truss") if isinstance(s.get("truss"), dict) else {}
        out.append({
            "id": str(s.get("id") or f"rs{k + 1}")[:20], "place": s["place"], "level": lv,
            "x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "d": round(d, 2),
            "sheet": s["sheet"], "thk_mm": _f(s.get("thk_mm"), 0.2, 100, SHEETS[s["sheet"]]["thk"][1] if len(SHEETS[s["sheet"]]["thk"]) > 1 else SHEETS[s["sheet"]]["thk"][0]),
            "colour": s["colour"] if isinstance(s.get("colour"), str) and len(s["colour"]) == 7 and s["colour"].startswith("#") else SHEETS[s["sheet"]]["colour"],
            "shape": s.get("shape") if s.get("shape") in SHAPES else "gable",
            "ridge": s.get("ridge") if s.get("ridge") in ("x", "y") else "x",
            "high": s.get("high") if s.get("high") in ("front", "back", "left", "right") else "back",
            "slope_deg": _f(s.get("slope_deg"), 3, 45, 15), "height_ft": _f(s.get("height_ft"), 6, 25, 9),
            "overhang_ft": _f(s.get("overhang_ft"), 0, 4, 1.5),
            "support": s.get("support") if s.get("support") in SUPPORTS else "truss",
            "truss": {**DEFAULT_TRUSS, **{kk: str(vv)[:40] for kk, vv in tr.items() if kk in DEFAULT_TRUSS and kk != "purlin_ft"},
                      "purlin_ft": _f(tr.get("purlin_ft"), 1.5, 8, 4.0)},
            "note": str(s.get("note") or "")[:120],
        })
    return out


def levels_z(plan: dict) -> list[float]:
    H = float(plan.get("floor_height_ft") or 10)
    return [PLINTH + i * H for i in range(len(plan["levels"]) + 1)]


def geom(plan: dict, s: dict) -> dict:
    """Numbers used by drawings, 3D and the estimate (ft unless noted)."""
    zs = levels_z(plan)
    ov = s["overhang_ft"]
    x0, x1, y0, y1 = s["x"] - ov, s["x"] + s["w"] + ov, s["y"] - ov, s["y"] + s["d"] + ov
    if s["place"] == "full_roof":
        eave = zs[s["level"] + 1]  # walls of the top floor carry the roof (no slab)
    elif s["place"] == "headroom":
        eave = zs[-1] + HEADROOM
    elif s["place"] == "on_terrace":
        eave = zs[-1] + s["height_ft"]
    else:
        eave = zs[s["level"]] + s["height_ft"]
    t = math.tan(math.radians(s["slope_deg"]))
    W, D = x1 - x0, y1 - y0
    if s["shape"] == "mono":
        span = D if s["high"] in ("front", "back") else W
        along = W if s["high"] in ("front", "back") else D
        rise = span * t
        ridge_len = 0.0
        eave_len = along  # gutter on the low side
    else:
        span = D if s["ridge"] == "x" else W
        along = W if s["ridge"] == "x" else D
        rise = span / 2 * t
        ridge_len = along if s["shape"] == "gable" else max(0.0, along - span)
        eave_len = 2 * along if s["shape"] == "gable" else 2 * (W + D)
    plan_area = W * D
    slope_area = plan_area / math.cos(math.radians(s["slope_deg"]))
    hip_len = 4 * math.hypot(span / 2, span / 2) / math.cos(math.radians(s["slope_deg"])) * 0.5 if s["shape"] == "hip" else 0.0
    # steel (kg/m² of plan area) – trusses get heavier with the span; purlins only for small spans
    span_m = span * FT_M
    if s["support"] == "truss":
        kg_m2 = 6.0 + 1.6 * span_m  # trusses + purlins + bracing (typical light roofs)
        n_truss = max(2, math.ceil(along * FT_M / 3.0) + 1)
    else:
        kg_m2 = 7.0
        n_truss = 0
    posts = 0
    post_h = 0.0
    if s["place"] in ("on_terrace", "area"):
        posts = max(4, 2 * (math.ceil(along * FT_M / 3.0) + 1))
        post_h = s["height_ft"] + rise / 2
    kg = plan_area * FT_M ** 2 * kg_m2 + posts * post_h * FT_M * 8.0  # 80 NB pipe ≈ 8 kg/m
    return {"x0": x0, "x1": x1, "y0": y0, "y1": y1, "eave": eave, "ridge_z": eave + rise, "rise": rise, "span": span,
            "along": along, "ridge_len": ridge_len, "hip_len": hip_len, "eave_len": eave_len, "plan_area": plan_area,
            "slope_area": slope_area, "n_truss": n_truss, "posts": posts, "post_h": post_h, "steel_kg": kg}


def full_roof(plan: dict) -> bool:
    n = len(plan.get("levels") or [])
    return any(s["place"] == "full_roof" and s["level"] == n - 1 for s in plan.get("roof_sheets") or [])


def headroom_sheet(plan: dict) -> bool:
    return any(s["place"] == "headroom" for s in plan.get("roof_sheets") or [])


def top_height(plan: dict) -> float:
    """Highest point of any sheet roof (ft above ground) – 0 when none."""
    return max((geom(plan, s)["ridge_z"] for s in plan.get("roof_sheets") or []), default=0.0)


def describe(s: dict) -> str:
    sh = SHEETS[s["sheet"]]
    thk = f"{s['thk_mm']:g} mm"
    return f"{sh['label']} {thk}, {SHAPES[s['shape']].split(' (')[0].lower()} {s['slope_deg']:g}°"


# ---------------------------------------------------------------- drawing helpers (elevation / section)
def _profile(d, a0: float, a1: float, zfun, layer="SHEET", gap=0.8):
    """Sheet corrugation lines across a sloped face seen from the side."""
    k = a0 + gap / 2
    while k < a1 - 0.1:
        d.line(k, zfun(k), k, zfun(k) - 0.35, layer)
        k += gap


def draw_side(d, plan: dict, view: str):
    """Draw every sheet roof on a front elevation (view='front', horizontal = x) or the section (view='section',
    horizontal = y). Returns the top height."""
    top = 0.0
    for idx, s in enumerate(plan.get("roof_sheets") or []):
        g = geom(plan, s)
        a0, a1 = (g["x0"], g["x1"]) if view == "front" else (g["y0"], g["y1"])
        e, rz = g["eave"], g["ridge_z"]
        top = max(top, rz + 0.3)
        thick = 0.25
        # which way does the slope run in this view?
        if s["shape"] == "mono":
            across = s["high"] in ("left", "right") if view == "front" else s["high"] in ("front", "back")
            if across:  # we see the slope as a sloped line
                hi_right = s["high"] == "right" if view == "front" else s["high"] == "back"
                za = (lambda k: e + (k - a0) / (a1 - a0) * g["rise"]) if hi_right else (lambda k: rz - (k - a0) / (a1 - a0) * g["rise"])
                d.line(a0, za(a0), a1, za(a1), "SHEET")
                d.line(a0, za(a0) + thick, a1, za(a1) + thick, "SHEET")
                _truss_side(d, s, a0, a1, za, g, view)
            else:  # we look at the sloped face: band from eave to ridge
                d.rect(a0, e, a1 - a0, g["rise"] + thick, "SHEET", "#e0f2fe")
                k = a0 + 0.4
                while k < a1:
                    d.line(k, e, k, rz + thick, "HATCH")
                    k += 0.8
        else:
            gable_end = (s["ridge"] == "y") if view == "front" else (s["ridge"] == "x")
            am = (a0 + a1) / 2
            if gable_end or s["shape"] == "hip":
                if gable_end:
                    zf = lambda k: e + (1 - abs(k - am) / ((a1 - a0) / 2)) * g["rise"]
                    d.line(a0, e, am, rz, "SHEET"); d.line(am, rz, a1, e, "SHEET")
                    d.line(a0, e + thick, am, rz + thick, "SHEET"); d.line(am, rz + thick, a1, e + thick, "SHEET")
                    _truss_side(d, s, a0, a1, zf, g, view)
                else:  # hip seen from the long side: trapezoid
                    inset = (g["span"] / 2)
                    d.line(a0, e, a0 + inset, rz, "SHEET"); d.line(a0 + inset, rz, a1 - inset, rz, "SHEET")
                    d.line(a1 - inset, rz, a1, e, "SHEET"); d.line(a0, e, a1, e, "SHEET")
            else:  # long side of a gable: sloped face from eave to ridge
                d.rect(a0, e, a1 - a0, g["rise"] + thick, "SHEET", "#e0f2fe")
                k = a0 + 0.4
                while k < a1:
                    d.line(k, e, k, rz + thick, "HATCH")
                    k += 0.8
                d.line(a0, rz + thick, a1, rz + thick, "SHEET")
        # posts
        if g["posts"]:
            base = e - s["height_ft"]
            for p in (a0 + s["overhang_ft"], a1 - s["overhang_ft"]):
                d.rect(p - 0.15, base, 0.3, s["height_ft"], "TRUSS", "#fed7aa")
        label = f"{SHEETS[s['sheet']]['label'].upper()} {s['thk_mm']:g} MM · {s['slope_deg']:g}°"
        d.text((a0 + a1) / 2, rz + 1.0 + 0.8 * idx, label, 0.5, layer="DIM")
    return top


def _truss_side(d, s: dict, a0: float, a1: float, zf, g: dict, view: str):
    """Truss seen in elevation: bottom chord, top chord (the sheet line) and web members."""
    if s["support"] != "truss":
        d.line(a0, g["eave"] - 0.2, a1, g["eave"] - 0.2, "TRUSS")
        return
    e = g["eave"]
    d.line(a0 + s["overhang_ft"], e, a1 - s["overhang_ft"], e, "TRUSS")  # bottom chord
    n = max(4, int((a1 - a0) / 3) // 2 * 2)
    for i in range(1, n):
        k = a0 + s["overhang_ft"] + i * ((a1 - a0) - 2 * s["overhang_ft"]) / n
        d.line(k, e, k, zf(k), "TRUSS")  # vertical
        if i < n - 1:
            k2 = a0 + s["overhang_ft"] + (i + 1) * ((a1 - a0) - 2 * s["overhang_ft"]) / n
            d.line(k, e, k2, zf(k2), "TRUSS") if (i < n / 2) else d.line(k2, e, k, zf(k), "TRUSS")


def roof_plan(plan: dict):
    """Roof plan: top floor outline (parapet / walls), every sheet with ridge, slope arrows and a label."""
    from .sheets import Dwg, _extent
    d = Dwg("Roof Plan")
    lv = plan["levels"][-1]
    x0, x1, y0, y1 = _extent(lv)
    Y = lambda v: v  # plan y grows away from the road – the road side is at the bottom of the sheet
    d.rect(x0, Y(y0), x1 - x0, y1 - y0, "OUTLINE")
    d.rect(x0 + 0.5, Y(y0) + 0.5, x1 - x0 - 1, y1 - y0 - 1, "PARAPET")
    for s in plan.get("roof_sheets") or []:
        g = geom(plan, s)
        d.rect(g["x0"], Y(g["y0"]), g["x1"] - g["x0"], g["y1"] - g["y0"], "SHEET", "#e0f2fe")
        xm, ym = (g["x0"] + g["x1"]) / 2, (g["y0"] + g["y1"]) / 2
        if s["shape"] != "mono":
            if s["ridge"] == "x":
                i0, i1 = (g["x0"], g["x1"]) if s["shape"] == "gable" else (g["x0"] + g["span"] / 2, g["x1"] - g["span"] / 2)
                d.line(i0, Y(ym), i1, Y(ym), "CENTRE")
                arrows = [(xm, ym, 0, -1), (xm, ym, 0, 1)]
            else:
                i0, i1 = (g["y0"], g["y1"]) if s["shape"] == "gable" else (g["y0"] + g["span"] / 2, g["y1"] - g["span"] / 2)
                d.line(xm, Y(i0), xm, Y(i1), "CENTRE")
                arrows = [(xm, ym, -1, 0), (xm, ym, 1, 0)]
            if s["shape"] == "hip":
                for cx, cy in ((g["x0"], g["y0"]), (g["x1"], g["y0"]), (g["x0"], g["y1"]), (g["x1"], g["y1"])):
                    tx = min(max(cx, i0), i1) if s["ridge"] == "x" else xm
                    ty = ym if s["ridge"] == "x" else min(max(cy, i0), i1)
                    d.line(cx, Y(cy), tx, Y(ty), "CENTRE")
        else:
            dx, dy = {"front": (0, 1), "back": (0, -1), "left": (1, 0), "right": (-1, 0)}[s["high"]]  # arrow = downhill
            arrows = [(xm, ym, dx, dy)]
        for ax, ay, dx, dy in arrows:  # slope arrows (pointing downhill)
            L = min(g["x1"] - g["x0"], g["y1"] - g["y0"]) * 0.28
            sx, sy = ax + dx * L * 0.2, ay + dy * L * 0.2
            ex, ey = ax + dx * L, ay + dy * L
            d.line(sx, Y(sy), ex, Y(ey), "MARK")
            px, py = -dy, dx
            d.line(ex, Y(ey), ex - dx * 0.8 + px * 0.5, Y(ey - dy * 0.8 + py * 0.5), "MARK")
            d.line(ex, Y(ey), ex - dx * 0.8 - px * 0.5, Y(ey - dy * 0.8 - py * 0.5), "MARK")
        d.text(xm, Y(ym) - 0.4, describe(s).upper(), 0.5, layer="TEXT", mask=True)
        d.text(xm, Y(ym) - 1.2, f"{PLACES[s['place']].split(' (')[0].upper()} · {g['plan_area']:.0f} SQ FT", 0.45, layer="DIM", mask=True)
        d.dim_h(g["x0"], g["x1"], Y(g["y0"]) - 1.5)
        d.dim_v(g["x1"] + 1.5, Y(g["y0"]), Y(g["y1"]))
    d.text((x0 + x1) / 2, Y(y0) - 4.0, "ROOF PLAN", 0.85, bold=True)
    d.text((x0 + x1) / 2, Y(y0) - 5.2, "(road side at the bottom · arrows point down the slope)", 0.5, layer="DIM")
    return d


def truss_detail(plan: dict):
    """Each sheet roof's truss below the previous one (readable on one sheet)."""
    from .sheets import Dwg
    out = Dwg("Truss Detail")
    oz = 0.0
    for s in plan.get("roof_sheets") or []:
        one = _truss_one(plan, s)
        x0, z0, x1, z1 = one.bounds()
        for it in one.items:
            it = dict(it)
            for k in ("y", "y1", "y2"):
                if k in it:
                    it[k] = it[k] + oz - z1
            out.items.append(it)
        oz -= (z1 - z0) + 4
    return out


def _truss_one(plan: dict, s: dict):
    """Truss / purlin detail of one sheet roof: span, rise, members (as entered), purlin spacing."""
    from .sheets import Dwg
    d = Dwg("Truss")
    ox = 0.0
    for s in [s]:
        g = geom(plan, s)
        span, rise = g["span"] - 2 * s["overhang_ft"], g["rise"] * (g["span"] - 2 * s["overhang_ft"]) / max(g["span"], 0.1)
        ov = s["overhang_ft"]
        mono = s["shape"] == "mono"
        top = (lambda k: k / span * rise) if mono else (lambda k: (1 - abs(k - span / 2) / (span / 2)) * rise)
        d.line(ox - ov, top(0) - (ov / span * rise if mono else ov / (span / 2) * rise), ox, top(0), "SHEET")
        d.line(ox + span, top(span), ox + span + ov, top(span) - (0 if mono else ov / (span / 2) * rise) + (ov / span * rise if mono else 0), "SHEET")
        if s["support"] == "truss":
            d.line(ox, 0, ox + span, 0, "TRUSS")
            n = max(4, int(span / 3) // 2 * 2)
            pts = [ox + i * span / n for i in range(n + 1)]
            for i in range(n):
                d.line(pts[i], top(pts[i] - ox), pts[i + 1], top(pts[i + 1] - ox), "TRUSS")
            for i in range(1, n):
                d.line(pts[i], 0, pts[i], top(pts[i] - ox), "TRUSS")
                j = i + 1 if i < n / 2 else i - 1
                d.line(pts[i], 0, pts[j], top(pts[j] - ox), "TRUSS")
            d.text(ox + span / 2, -1.4, f"BOTTOM CHORD {s['truss']['bottom']}", 0.45, layer="DIM")
            d.text(ox + span / 2, max(top(span / 2), rise) + 1.6, f"TOP CHORD {s['truss']['top']}", 0.45, layer="DIM")
            d.text(ox + span / 2, max(top(span / 2), rise) + 0.8, f"WEB {s['truss']['web']}", 0.45, layer="DIM")
        else:
            d.line(ox, 0, ox, top(0), "TRUSS"); d.line(ox + span, 0, ox + span, top(span), "TRUSS")
            d.text(ox + span / 2, -1.4, "PURLINS ON POSTS / WALLS", 0.45, layer="DIM")
        # purlins (small squares on the top chord)
        k = 0.0
        while k <= span + 0.01:
            z = top(k)
            d.rect(ox + k - 0.2, z, 0.4, 0.4, "TRUSS", "#fdba74")
            k += s["truss"]["purlin_ft"]
        d.dim_h(ox, ox + span, -2.8, f"SPAN {span:.1f} FT")
        d.dim_v(ox + span + ov + 1.5, 0, rise, f"RISE {rise:.1f} FT")
        d.text(ox + span / 2, -4.2, f"{describe(s).upper()}", 0.5, bold=True)
        d.text(ox + span / 2, -5.0, f"PURLIN {s['truss']['purlin']} @ {s['truss']['purlin_ft']:g} FT C/C"
               + (f" · POSTS {s['truss']['post']}" if g["posts"] else "") + (f" · {g['n_truss']} TRUSSES" if g["n_truss"] else ""), 0.42, layer="DIM")
        d.text(ox + span / 2, -5.8, "MEMBER SIZES AS ENTERED – CONFIRM WITH THE STRUCTURAL ENGINEER", 0.38, layer="MARK")
        pass
    return d


# ---------------------------------------------------------------- estimate
def estimate_rows(plan: dict) -> list[dict]:
    """Metric numbers for the estimate engine (one row per sheet roof)."""
    out = []
    n = len(plan.get("levels") or [])
    names = [lv["name"] for lv in plan.get("levels") or []]
    for s in plan.get("roof_sheets") or []:
        g = geom(plan, s)
        stair = next((r for r in plan["levels"][-1]["rooms"] if r["type"] == "stair"), None) if n else None
        out.append({
            "place": s["place"], "sheet": s["sheet"], "thk_mm": s["thk_mm"], "shape": s["shape"], "support": s["support"],
            "floor": "Terrace" if s["place"] in ("full_roof", "on_terrace", "headroom") else names[s["level"]],
            "slope_m2": round(g["slope_area"] * FT_M ** 2, 2), "plan_m2": round(g["plan_area"] * FT_M ** 2, 2),
            "ridge_m": round((g["ridge_len"] + g["hip_len"]) * FT_M, 2), "eave_m": round(g["eave_len"] * FT_M, 2),
            "steel_kg": round(g["steel_kg"], 1), "posts": g["posts"], "n_truss": g["n_truss"],
            "covered_m2": round(s["w"] * s["d"] * FT_M ** 2, 2),
            "stair_m2": round(stair["w"] * stair["d"] * FT_M ** 2, 2) if stair else 0.0,
            "label": describe(s),
        })
    return out


def vastu_check(plan: dict) -> dict | None:
    """Traditional guidance: a sloped roof should be lower towards North / East (water flows North-East)."""
    from ..vastu.engine import bearing_of
    sheets = plan.get("roof_sheets") or []
    if not sheets or "compass" not in plan:
        return None
    comp = plan["compass"]
    good = bad = 0
    for s in sheets:
        if s["shape"] != "mono":
            continue
        # downhill direction in plan coords (x right, y away from road)
        dx, dy = {"front": (0, 1), "back": (0, -1), "left": (1, 0), "right": (-1, 0)}[s["high"]]
        b = bearing_of(comp, dx, dy)
        if b <= 112.5 or b >= 337.5:  # N, NE, E
            good += 1
        else:
            bad += 1
    if not good and not bad:
        return {"status": "matched", "message": "Gable / hip sheet roof – slopes on both sides"}
    return {"status": "matched" if not bad else "not_matched",
            "message": "Sheet roof slopes down towards North / East – good" if not bad else
                       "Sheet roof slopes down towards South / West – North / East preferred"}
