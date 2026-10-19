"""Civil quantity calculators. Pure Python, deterministic – the AI only explains these numbers.

Every calculator: run(params) -> {"title", "inputs", "steps", "results", "assumptions", "missing"}.
Dimensions are never guessed: if one is missing it is returned in "missing" so the assistant asks for it.
Only standard choices (mix, wastage, coverage) have defaults, and those are listed as assumptions.
"""
from __future__ import annotations

import math

FT = 0.3048
SQFT_M2 = 0.09290304
CEMENT_BAG_M3 = 0.0347       # 50 kg bag at 1440 kg/m³
DRY_CONCRETE = 1.54          # dry volume of ingredients / wet concrete
DRY_MORTAR = 1.33            # incl. allowance for voids and wastage

MIXES = {"M7.5": (1, 4, 8), "M10": (1, 3, 6), "M15": (1, 2, 4), "M20": (1, 1.5, 3), "M25": (1, 1, 2)}


class CalcError(ValueError):
    pass


def _f(p: dict, k: str) -> float | None:
    v = p.get(k)
    if v in (None, ""):
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise CalcError(f"'{k}' must be a number")
    return v


def _len_m(v: float, unit: str) -> float:
    return v * FT if (unit or "m").lower() in ("ft", "feet", "foot") else v


def _out(title, inputs, steps, results, assumptions=None, missing=None, note=""):
    return {"title": title, "inputs": inputs, "steps": steps, "results": results,
            "assumptions": assumptions or [], "missing": missing or [], "note": note}


def _need(p: dict, spec: list[tuple[str, str]]) -> list[str]:
    return [label for k, label in spec if p.get(k) in (None, "", 0, "0")]


def _r(x, d=2):
    return round(x, d)


# ------------------------------------------------------------------ concrete
def concrete(p: dict) -> dict:
    unit = p.get("unit", "m")
    vol = _f(p, "volume_m3")
    missing = []
    if not vol:
        missing = _need(p, [("length", "Length"), ("width", "Width"), ("depth", "Depth / thickness")])
        if missing:
            return _out("Concrete materials", [], [], [], missing=missing)
        n = _f(p, "count") or 1
        vol = _len_m(_f(p, "length"), unit) * _len_m(_f(p, "width"), unit) * _len_m(_f(p, "depth"), unit) * n
    grade = (p.get("grade") or "M20").upper().replace(" ", "")
    if grade not in MIXES:
        raise CalcError(f"Grade must be one of {', '.join(MIXES)}")
    c, s, a = MIXES[grade]
    total = c + s + a
    dry = vol * DRY_CONCRETE
    cem_m3 = dry * c / total
    bags = cem_m3 / CEMENT_BAG_M3
    sand = dry * s / total
    agg = dry * a / total
    water = bags * 50 * 0.5
    ass = [f"Nominal mix {grade} = {c}:{s:g}:{a:g} (cement : sand : aggregate by volume)",
           "Dry volume = 1.54 × wet volume; 1 bag cement = 50 kg = 0.0347 m³", "Water-cement ratio 0.5"]
    if grade in ("M20", "M25"):
        ass.append("For M20 and above a design mix (IS 10262) is preferred; for M25 it is required – "
                   "quantities here are approximate.")
    return _out(f"Concrete {grade} – materials", [("Wet volume", f"{vol:.3f} m³ ({vol / FT ** 3:.1f} cft)")],
                [f"Dry volume = {vol:.3f} × 1.54 = {dry:.3f} m³",
                 f"Cement = {dry:.3f} × {c}/{total:g} = {cem_m3:.3f} m³ ÷ 0.0347 = {bags:.1f} bags",
                 f"Sand = {dry:.3f} × {s:g}/{total:g} = {sand:.3f} m³",
                 f"Aggregate = {dry:.3f} × {a:g}/{total:g} = {agg:.3f} m³"],
                [{"label": "Cement", "value": math.ceil(bags), "unit": "bags"},
                 {"label": "Sand (M-Sand)", "value": _r(sand), "unit": f"m³ ({sand / FT ** 3:.0f} cft)"},
                 {"label": "Aggregate 20 mm", "value": _r(agg), "unit": f"m³ ({agg / FT ** 3:.0f} cft)"},
                 {"label": "Water", "value": round(water), "unit": "litres"}], ass)


# ------------------------------------------------------------------ brick work
BRICKS = {"modular": (0.19, 0.09, 0.09, "Modular brick 190×90×90 mm"),
          "traditional": (0.23, 0.11, 0.075, "Traditional brick 230×110×75 mm")}


def brickwork(p: dict) -> dict:
    unit = p.get("unit", "ft")
    missing = _need(p, [("length", "Wall length"), ("height", "Wall height")])
    if missing:
        return _out("Brick work", [], [], [], missing=missing)
    thick_mm = _f(p, "thickness_mm") or 230
    L, H = _len_m(_f(p, "length"), unit), _len_m(_f(p, "height"), unit)
    openings = _f(p, "openings_m2") or 0
    bt = p.get("brick") or "traditional"
    bl, bw, bh, bname = BRICKS.get(bt, BRICKS["traditional"])
    joint = 0.01
    area = max(L * H - openings, 0)
    vol = area * thick_mm / 1000
    per_m3 = 1 / ((bl + joint) * (bw + joint) * (bh + joint))
    n = vol * per_m3
    mortar_wet = vol - n * bl * bw * bh
    mortar_dry = mortar_wet * DRY_MORTAR
    mix = (p.get("mix") or ("1:6" if thick_mm >= 200 else "1:4")).replace(" ", "")
    try:
        mc, ms = [float(x) for x in mix.split(":")]
    except ValueError:
        raise CalcError("Mix must look like 1:6")
    cem = mortar_dry * mc / (mc + ms)
    sand = mortar_dry * ms / (mc + ms)
    return _out("Brick work", [("Wall", f"{L:.2f} m × {H:.2f} m, {thick_mm:g} mm thick"),
                               ("Openings deducted", f"{openings:g} m²"), ("Brick", bname), ("Mortar", mix)],
                [f"Net area = {L:.2f} × {H:.2f} − {openings:g} = {area:.2f} m²",
                 f"Volume = {area:.2f} × {thick_mm / 1000:.3f} = {vol:.3f} m³",
                 f"Bricks per m³ with 10 mm joints = {per_m3:.0f}", f"Bricks = {vol:.3f} × {per_m3:.0f} = {n:.0f}",
                 f"Mortar (wet) = {mortar_wet:.3f} m³ → dry × 1.33 = {mortar_dry:.3f} m³"],
                [{"label": "Bricks (+5% wastage)", "value": math.ceil(n * 1.05), "unit": "nos"},
                 {"label": "Cement", "value": math.ceil(cem / CEMENT_BAG_M3), "unit": "bags"},
                 {"label": "Sand", "value": _r(sand), "unit": f"m³ ({sand / FT ** 3:.0f} cft)"},
                 {"label": "Wall area", "value": _r(area), "unit": f"m² ({area / SQFT_M2:.0f} sq ft)"}],
                ["10 mm mortar joints", "Dry mortar = 1.33 × wet volume", "5% wastage on bricks"])


# ------------------------------------------------------------------ AAC blocks
def aac(p: dict) -> dict:
    unit = p.get("unit", "ft")
    missing = _need(p, [("length", "Wall length"), ("height", "Wall height")])
    if missing:
        return _out("AAC block work", [], [], [], missing=missing)
    t = _f(p, "thickness_mm") or 200
    L, H = _len_m(_f(p, "length"), unit), _len_m(_f(p, "height"), unit)
    area = max(L * H - (_f(p, "openings_m2") or 0), 0)
    per_m2 = 1 / (0.6 * 0.2)
    n = area * per_m2
    vol = area * t / 1000
    return _out("AAC block work", [("Wall", f"{L:.2f} m × {H:.2f} m, {t:g} mm blocks")],
                [f"Net area = {area:.2f} m²", f"Blocks 600×200 mm face → {per_m2:.2f} per m²",
                 f"Blocks = {area:.2f} × {per_m2:.2f} = {n:.0f}"],
                [{"label": "AAC blocks (+3% wastage)", "value": math.ceil(n * 1.03), "unit": f"nos (600×200×{t:g})"},
                 {"label": "Block volume", "value": _r(vol, 3), "unit": "m³"},
                 {"label": "Wall area", "value": _r(area), "unit": "m²"}],
                ["Block face 600 × 200 mm, thin-bed adhesive joints (≈3 mm)",
                 "Adhesive quantity: follow the maker's chart for the block thickness"])


# ------------------------------------------------------------------ plaster
def plaster(p: dict) -> dict:
    area = _f(p, "area_m2")
    if not area and _f(p, "area_sqft"):
        area = _f(p, "area_sqft") * SQFT_M2
    if not area:
        return _out("Plastering", [], [], [], missing=["Plaster area (m² or sq ft)"])
    t = _f(p, "thickness_mm") or 12
    mix = (p.get("mix") or ("1:4" if t >= 18 else "1:5")).replace(" ", "")
    mc, ms = [float(x) for x in mix.split(":")]
    wet = area * t / 1000
    dry = wet * DRY_MORTAR
    cem = dry * mc / (mc + ms)
    sand = dry * ms / (mc + ms)
    return _out("Plastering", [("Area", f"{area:.2f} m² ({area / SQFT_M2:.0f} sq ft)"), ("Thickness", f"{t:g} mm"),
                               ("Mix", mix)],
                [f"Wet mortar = {area:.2f} × {t / 1000:.3f} = {wet:.3f} m³", f"Dry = {wet:.3f} × 1.33 = {dry:.3f} m³",
                 f"Cement = {cem:.3f} m³ = {cem / CEMENT_BAG_M3:.1f} bags"],
                [{"label": "Cement", "value": math.ceil(cem / CEMENT_BAG_M3), "unit": "bags"},
                 {"label": "Sand (P-Sand)", "value": _r(sand), "unit": f"m³ ({sand / FT ** 3:.0f} cft)"}],
                ["Dry mortar = 1.33 × wet volume (voids + wastage)",
                 "Typical: 12 mm internal walls 1:5, 20 mm external 1:4, 6–10 mm ceiling 1:4"])


# ------------------------------------------------------------------ steel
def steel(p: dict) -> dict:
    missing = _need(p, [("dia_mm", "Bar diameter (mm)"), ("length_m", "Length of each bar (m)")])
    if missing:
        return _out("Steel weight", [], [], [], missing=missing)
    d, L, n = _f(p, "dia_mm"), _f(p, "length_m"), _f(p, "count") or 1
    per_m = d * d / 162
    kg = per_m * L * n
    bars12 = math.ceil(L * n / 12)
    return _out("Steel weight", [("Bar", f"{d:g} mm × {L:g} m × {n:g} nos")],
                [f"Weight per metre = d²/162 = {d:g}²/162 = {per_m:.3f} kg/m", f"Total = {per_m:.3f} × {L:g} × {n:g} = {kg:.1f} kg"],
                [{"label": "Steel", "value": _r(kg, 1), "unit": "kg"},
                 {"label": "Weight per metre", "value": _r(per_m, 3), "unit": "kg/m"},
                 {"label": "12 m bars needed (no lap / cut waste)", "value": bars12, "unit": "nos"}],
                ["Unit weight = d²/162 kg/m (steel 7850 kg/m³)", "Add laps and 3–5% cutting wastage for ordering"])


# ------------------------------------------------------------------ tiles
TILE_PER_BOX = {"600x600": 4, "800x800": 3, "600x1200": 2, "300x300": 11, "300x600": 8, "400x400": 6}


def tiles(p: dict) -> dict:
    unit = p.get("unit", "ft")
    area = _f(p, "area_m2")
    if not area and _f(p, "area_sqft"):
        area = _f(p, "area_sqft") * SQFT_M2
    if not area:
        miss = _need(p, [("length", "Room length"), ("width", "Room width")])
        if miss:
            return _out("Floor tiles", [], [], [], missing=miss)
        area = _len_m(_f(p, "length"), unit) * _len_m(_f(p, "width"), unit)
    size = (p.get("tile_size") or "600x600").lower().replace(" ", "").replace("×", "x")
    try:
        a, b = [float(x) for x in size.split("x")]
    except ValueError:
        raise CalcError("Tile size like 600x600 (mm)")
    w = _f(p, "wastage_pct")
    w = 7 if w is None else w
    per = a * b / 1e6
    n = area / per * (1 + w / 100)
    out = [{"label": "Tiles", "value": math.ceil(n), "unit": f"nos ({size} mm)"},
           {"label": "Area", "value": _r(area), "unit": f"m² ({area / SQFT_M2:.0f} sq ft)"}]
    box = _f(p, "per_box") or TILE_PER_BOX.get(size)
    if box:
        out.append({"label": "Boxes", "value": math.ceil(n / box), "unit": f"boxes ({box:g} per box – check the maker)"})
    return _out("Floor tiles", [("Area", f"{area:.2f} m²"), ("Tile", f"{size} mm"), ("Wastage", f"{w:g}%")],
                [f"Tile area = {per:.3f} m²", f"Tiles = {area:.2f} ÷ {per:.3f} × {1 + w / 100:.2f} = {n:.0f}"], out,
                [f"{w:g}% wastage for cutting / breakage (use 10% for diagonal laying)"])


# ------------------------------------------------------------------ paint
def paint(p: dict) -> dict:
    area = _f(p, "area_m2")
    if not area and _f(p, "area_sqft"):
        area = _f(p, "area_sqft") * SQFT_M2
    if not area:
        return _out("Painting", [], [], [], missing=["Wall / ceiling area to paint (m² or sq ft)"])
    coats = _f(p, "coats") or 2
    cov = _f(p, "coverage_m2_per_l") or 10
    paint_l = area * coats / cov
    return _out("Painting", [("Area", f"{area:.2f} m² ({area / SQFT_M2:.0f} sq ft)"), ("Coats", f"{coats:g}")],
                [f"Paint = {area:.2f} × {coats:g} ÷ {cov:g} = {paint_l:.1f} L"],
                [{"label": "Emulsion paint", "value": math.ceil(paint_l), "unit": "litres"},
                 {"label": "Primer (1 coat)", "value": math.ceil(area / 9), "unit": "litres"},
                 {"label": "Wall putty (2 coats)", "value": math.ceil(area * 1.0), "unit": "kg"}],
                [f"Coverage {cov:g} m² per litre per coat", "Primer 9 m²/L", "Putty ≈ 1 kg/m² for 2 coats"])


# ------------------------------------------------------------------ area conversion
AREA_UNITS = {"sqft": 1.0, "m2": 1 / SQFT_M2, "cent": 435.6, "ground": 2400.0, "acre": 43560.0,
              "hectare": 107639.1, "sqyd": 9.0}


def area(p: dict) -> dict:
    v = _f(p, "value")
    if v is None:
        return _out("Area conversion", [], [], [], missing=["Area value"])
    u = (p.get("from_unit") or "sqft").lower()
    if u not in AREA_UNITS:
        raise CalcError(f"Unit must be one of {', '.join(AREA_UNITS)}")
    sqft = v * AREA_UNITS[u]
    res = [{"label": k, "value": _r(sqft / f, 4 if f > 1000 else 2), "unit": k} for k, f in AREA_UNITS.items() if k != u]
    return _out("Area conversion", [("Given", f"{v:g} {u}")], [f"{v:g} {u} = {sqft:,.2f} sq ft"], res,
                ["1 cent = 435.6 sq ft, 1 ground = 2400 sq ft, 1 acre = 43,560 sq ft = 100 cents"])


# ------------------------------------------------------------------ staircase
def staircase(p: dict) -> dict:
    unit = p.get("unit", "ft")
    h = _f(p, "floor_height")
    if not h:
        return _out("Staircase", [], [], [], missing=["Floor-to-floor height"])
    H = _len_m(h, unit) * 1000
    max_r = min(_f(p, "max_riser_mm") or 175, 190)
    tread = max(_f(p, "tread_mm") or 275, 250)
    n = math.ceil(H / max_r)
    r = H / n
    going = (n - 1) * tread
    width = _f(p, "width_mm") or 1000
    landing = n > 15
    return _out("Staircase", [("Floor-to-floor", f"{H:.0f} mm"), ("Tread", f"{tread:g} mm")],
                [f"Risers = {H:.0f} ÷ {max_r:g} → {n}", f"Actual riser = {H:.0f} ÷ {n} = {r:.1f} mm",
                 f"Treads = {n} − 1 = {n - 1}; going = {n - 1} × {tread:g} = {going:.0f} mm",
                 f"Comfort check 2R + T = {2 * r + tread:.0f} mm (550–700 is good)"],
                [{"label": "Risers", "value": n, "unit": f"nos × {r:.0f} mm"},
                 {"label": "Treads", "value": n - 1, "unit": f"nos × {tread:g} mm"},
                 {"label": "Total going (straight)", "value": round(going / 1000, 2), "unit": f"m ({going / 304.8:.1f} ft)"},
                 {"label": "Suggested layout", "value": "Dog-legged with mid landing" if landing or going > 3500 else "Straight / dog-legged",
                  "unit": f"width {width:g} mm"}],
                ["NBC 2016 Part 4 (residential): riser ≤ 190 mm, tread ≥ 250 mm, width ≥ 0.9 m, headroom ≥ 2.2 m"])


# ------------------------------------------------------------------ water tank / sump
def water_tank(p: dict) -> dict:
    n = _f(p, "persons")
    if not n:
        return _out("Water tank / sump", [], [], [], missing=["Number of persons"])
    lpcd = _f(p, "lpcd") or 135
    days = _f(p, "sump_days") or 2
    daily = n * lpcd
    sump = daily * days
    depth = _f(p, "sump_depth_m") or 1.5
    side = math.sqrt(sump / 1000 / depth)
    return _out("Water tank / sump", [("Persons", f"{n:g}"), ("Demand", f"{lpcd:g} L per person per day")],
                [f"Daily demand = {n:g} × {lpcd:g} = {daily:.0f} L", f"Sump = {daily:.0f} × {days:g} days = {sump:.0f} L",
                 f"Sump plan at {depth:g} m water depth = {sump / 1000:.2f} m³ ÷ {depth:g} → {side:.2f} m × {side:.2f} m"],
                [{"label": "Overhead tank", "value": int(math.ceil(daily / 500) * 500), "unit": "litres (≈ 1 day)"},
                 {"label": "Sump", "value": int(math.ceil(sump / 500) * 500), "unit": f"litres ({days:g} days)"},
                 {"label": "Sump inside size", "value": f"{side:.2f} × {side:.2f} × {depth + 0.3:.2f}", "unit": "m (incl. 0.3 m free board)"}],
                [f"{lpcd:g} L/person/day (IS 1172)", "Free board 0.3 m above water level"])


# ------------------------------------------------------------------ excavation
def excavation(p: dict) -> dict:
    unit = p.get("unit", "m")
    miss = _need(p, [("length", "Pit length"), ("width", "Pit width"), ("depth", "Pit depth")])
    if miss:
        return _out("Excavation", [], [], [], missing=miss)
    n = _f(p, "count") or 1
    L, B, D = (_len_m(_f(p, k), unit) for k in ("length", "width", "depth"))
    v = L * B * D * n
    return _out("Excavation", [("Pit", f"{L:.2f} × {B:.2f} × {D:.2f} m × {n:g}")],
                [f"Volume = {L:.2f} × {B:.2f} × {D:.2f} × {n:g} = {v:.2f} m³"],
                [{"label": "Excavation", "value": _r(v), "unit": f"m³ ({v / FT ** 3:.0f} cft)"},
                 {"label": "Loose soil to handle (+25% bulking)", "value": _r(v * 1.25), "unit": "m³"}],
                ["Working space and side slopes are not included – add them for deep pits"])


CALCS = {
    "concrete": (concrete, "Concrete (cement, sand, jelly)", "கான்கிரீட் பொருட்கள்",
                 [("length", "Length", "len"), ("width", "Width", "len"), ("depth", "Depth / thickness", "len"),
                  ("count", "Number of items", "num"), ("volume_m3", "…or volume (m³)", "num"),
                  ("grade", "Grade", "M7.5|M10|M15|M20|M25")]),
    "brickwork": (brickwork, "Brick work (bricks, cement, sand)", "செங்கல் கட்டு",
                  [("length", "Wall length", "len"), ("height", "Wall height", "len"),
                   ("thickness_mm", "Thickness (mm)", "230|115"), ("openings_m2", "Openings to deduct (m²)", "num"),
                   ("brick", "Brick size", "traditional|modular"), ("mix", "Mortar mix", "1:6|1:5|1:4")]),
    "aac": (aac, "AAC block work", "AAC பிளாக்",
            [("length", "Wall length", "len"), ("height", "Wall height", "len"),
             ("thickness_mm", "Block thickness (mm)", "100|150|200|230"), ("openings_m2", "Openings to deduct (m²)", "num")]),
    "plaster": (plaster, "Plastering", "பூச்சு",
                [("area_sqft", "Area (sq ft)", "num"), ("area_m2", "…or area (m²)", "num"),
                 ("thickness_mm", "Thickness (mm)", "12|15|20|6"), ("mix", "Mix", "1:4|1:5|1:6|1:3")]),
    "steel": (steel, "Steel bar weight", "கம்பி எடை",
              [("dia_mm", "Bar diameter (mm)", "8|10|12|16|20|25|32"), ("length_m", "Length of each bar (m)", "num"),
               ("count", "Number of bars", "num")]),
    "tiles": (tiles, "Floor tiles", "டைல்ஸ் எண்ணிக்கை",
              [("length", "Room length", "len"), ("width", "Room width", "len"), ("area_sqft", "…or area (sq ft)", "num"),
               ("tile_size", "Tile size (mm)", "600x600|800x800|600x1200|300x300|300x600|400x400"),
               ("wastage_pct", "Wastage %", "num")]),
    "paint": (paint, "Painting", "பெயிண்ட்",
              [("area_sqft", "Area (sq ft)", "num"), ("area_m2", "…or area (m²)", "num"), ("coats", "Coats", "2|1|3"),
               ("coverage_m2_per_l", "Coverage (m²/L/coat)", "num")]),
    "area": (area, "Area conversion (cent, ground, acre)", "பரப்பு மாற்றம்",
             [("value", "Area", "num"), ("from_unit", "Unit", "sqft|m2|cent|ground|acre|hectare|sqyd")]),
    "staircase": (staircase, "Staircase risers & treads", "படிக்கட்டு",
                  [("floor_height", "Floor-to-floor height", "len"), ("max_riser_mm", "Max riser (mm)", "num"),
                   ("tread_mm", "Tread (mm)", "num"), ("width_mm", "Width (mm)", "num")]),
    "water_tank": (water_tank, "Water tank & sump size", "தண்ணீர் தொட்டி",
                   [("persons", "Persons", "num"), ("lpcd", "Litres / person / day", "num"),
                    ("sump_days", "Sump storage (days)", "num"), ("sump_depth_m", "Sump water depth (m)", "num")]),
    "excavation": (excavation, "Excavation (footing pits)", "தோண்டுதல்",
                   [("length", "Pit length", "len"), ("width", "Pit width", "len"), ("depth", "Pit depth", "len"),
                    ("count", "Number of pits", "num")]),
}


def catalog() -> list[dict]:
    return [{"key": k, "name": v[1], "name_ta": v[2],
             "params": [{"key": pk, "label": pl, "type": "num" if pt in ("num", "len") else "select",
                         "options": pt.split("|") if pt not in ("num", "len") else [], "length": pt == "len"}
                        for pk, pl, pt in v[3]]}
            for k, v in CALCS.items()]


def run(kind: str, params: dict) -> dict:
    if kind not in CALCS:
        raise CalcError(f"Unknown calculator '{kind}'")
    out = CALCS[kind][0](dict(params or {}))
    out["kind"] = kind
    return out
