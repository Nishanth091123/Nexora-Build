"""Nexora Build – preliminary quantity & cost engine (Phase 2).

Pure Python (no database) so it can be unit-tested and reused by the AI assistant.

How it works
------------
Until a drawing exists (Design Studio, Phase 3) quantities come from a STANDARD
LAYOUT MODEL built from what the user confirmed: floor areas, floors, rooms,
structure type, floor height. Every assumption is listed in the result so the
user can see and change it. Nothing about the building is guessed silently:
missing essentials raise MissingInfo with a question for the user.

Quantities -> materials (with wastage) -> labour (man-days x day wage)
-> equipment -> extras. Spec level (basic/standard/premium) changes only the
RATE (quality/brand) of materials, never quantities or structural sizes.
Concrete is M20 minimum for all spec levels.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

SQFT_TO_M2 = 0.09290304
FT_TO_M = 0.3048

# ---------------- mix & productivity constants (editable later via settings) ----------------
CEMENT_BAG_M3 = 50 / 1440            # one 50 kg bag in m3 (bulk density 1440)
MIX = {                               # per m3 of WET concrete: cement bags, sand m3, aggregate m3
    "M20": (8.06, 0.42, 0.84),        # 1:1.5:3 nominal (dry volume factor 1.54)
    "PCC148": (3.40, 0.44, 0.88),     # 1:4:8 with 40 mm jelly
}


def mortar(ratio: int, wet_m3: float) -> tuple[float, float]:
    """Cement bags, sand m3 for cement:sand 1:ratio mortar (dry factor 1.33)."""
    dry = wet_m3 * 1.33
    cement_m3 = dry / (1 + ratio)
    return cement_m3 / CEMENT_BAG_M3, cement_m3 * ratio


WASTAGE = {"cement": 0.02, "steel": 0.03, "msand": 0.05, "psand": 0.05, "agg20": 0.03, "agg40": 0.03,
           "brick": 0.05, "aac": 0.05, "solid_block": 0.05, "floor_tile": 0.08, "wall_tile": 0.08,
           "granite": 0.10, "paint_int": 0.05, "paint_ext": 0.05, "binding_wire": 0.0}

STEEL_KG_PER_M3 = {"footing": 80, "column": 180, "plinth_beam": 130, "beam": 150, "slab": 90,
                   "lintel": 70, "sunshade": 70, "stair": 100, "band": 80}

# man-days per unit of work
LAB = {
    "excavation": {"helper_m": 0.10},
    "backfill": {"helper_m": 0.25},
    "filling": {"helper_m": 0.30},
    "pcc": {"mason": 0.10, "helper_m": 1.00, "helper_f": 0.60},
    "rcc": {"mason": 0.20, "helper_m": 1.20, "helper_f": 0.80},
    "steel": {"bar_bender": 0.006, "helper_m": 0.006},
    "formwork": {"centring": 0.12, "helper_m": 0.12},
    "brick230": {"mason": 0.75, "helper_m": 0.50, "helper_f": 0.50},
    "brick115": {"mason": 0.10, "helper_f": 0.12},
    "aac": {"mason": 0.55, "helper_m": 0.35, "helper_f": 0.35},
    "solid_block": {"mason": 0.60, "helper_m": 0.40, "helper_f": 0.40},
    "found_masonry": {"mason": 0.60, "helper_m": 0.50, "helper_f": 0.50},
    "plaster_int": {"mason": 0.07, "helper_f": 0.07},
    "plaster_ext": {"mason": 0.10, "helper_f": 0.10},
    "ceiling": {"mason": 0.09, "helper_f": 0.09},
    "floor_tile": {"tile_layer": 0.10, "helper_m": 0.10},
    "wall_tile": {"tile_layer": 0.13, "helper_m": 0.10},
    "granite": {"tile_layer": 0.15, "helper_m": 0.15},
    "paint_int": {"painter": 0.045, "helper_f": 0.015},
    "paint_ext": {"painter": 0.060, "helper_f": 0.020},
    "enamel": {"painter": 0.060},
    "waterproof": {"mason": 0.02, "helper_m": 0.04},
    "door": {"carpenter": 0.75, "helper_m": 0.25},
    "window": {"carpenter": 0.30, "helper_m": 0.15},
    "grill": {"welder": 0.008, "helper_m": 0.004},
    "elec_point": {"electrician": 0.18, "helper_m": 0.12},
    "toilet_plumb": {"plumber": 3.0, "helper_m": 2.0},
    "kitchen_plumb": {"plumber": 1.5, "helper_m": 1.0},
    "oh_tank": {"plumber": 1.0, "helper_m": 1.0},
    "compound_wall": {"mason": 0.35, "helper_m": 0.35, "helper_f": 0.30},
    "parking": {"mason": 0.08, "helper_m": 0.10},
}

CATEGORY_GROUP = {  # BOQ category -> cost breakdown group (donut)
    "Earthwork": "Civil Works", "Concrete (PCC)": "Civil Works", "RCC": "Civil Works", "Steel": "Civil Works",
    "Formwork": "Civil Works", "Masonry": "Civil Works", "Plastering": "Civil Works",
    "Flooring & Tiling": "Finishes", "Painting": "Finishes", "Waterproofing": "Finishes",
    "Doors & Windows": "Doors & Windows", "Plumbing & Sanitary": "Plumbing", "Electrical": "Electrical",
    "External Works": "External Works", "Additional Items": "Additional Items",
}

FLOOR_NAMES = ["Ground Floor", "First Floor", "Second Floor", "Third Floor", "Fourth Floor", "Fifth Floor"]


class MissingInfo(ValueError):
    """Raised when the user must confirm something before we can calculate."""

    def __init__(self, questions: list[str]):
        super().__init__("; ".join(questions))
        self.questions = questions


# ---------------------------------------------------------------- inputs
@dataclass
class Inputs:
    floor_areas_sqft: list[float]            # built-up area of each level, ground first
    stilt: bool = False                       # first level is stilt parking (no rooms/walls)
    floor_height_ft: float = 10.0
    structure: str = "rcc_framed"             # rcc_framed | load_bearing
    spec_level: str = "standard"              # basic | standard | premium
    masonry: str = "brick"                    # brick | aac | solid_block
    bedrooms: int = 0                         # totals for the whole building
    halls: int = 1
    kitchens: int = 1
    toilets: int = 0
    plot_width_ft: float | None = None
    plot_length_ft: float | None = None
    staircase: bool = True                    # to upper floors / terrace
    compound_wall: bool = False
    compound_wall_length_m: float | None = None  # default: plot perimeter minus gate
    gate: bool = False
    sump_litres: int = 0
    septic_tank: bool = False
    oh_tank_litres: int | None = None         # default 1000 per kitchen
    rwh: bool = True
    parking_area_sqft: float = 0
    extra_items: list[dict] = field(default_factory=list)   # [{"code": rate code, "qty": n, "note": ""}]
    approval_fees: float = 0
    contractor_margin_pct: float = 0
    gst_pct: float = 0
    contingency_pct: float | None = None      # default from rate library
    extra_notes: list[str] = field(default_factory=list)
    geometry: list[dict] | None = None        # per-level measured geometry from a design (Phase 3)

    @staticmethod
    def from_dict(d: dict) -> "Inputs":
        """Accepts form data: blank strings become defaults, numbers given as text are converted."""
        ints = {"bedrooms", "halls", "kitchens", "toilets", "sump_litres", "oh_tank_litres"}
        floats = {"floor_height_ft", "plot_width_ft", "plot_length_ft", "compound_wall_length_m", "parking_area_sqft",
                  "approval_fees", "contractor_margin_pct", "gst_pct", "contingency_pct"}
        bools = {"stilt", "staircase", "compound_wall", "gate", "septic_tank", "rwh"}
        out = {}
        for k, v in (d or {}).items():
            if k not in Inputs.__dataclass_fields__:
                continue
            if v == "" or v is None:
                continue  # keep the default
            try:
                if k in ints:
                    v = int(float(v))
                elif k in floats:
                    v = float(v)
                elif k in bools:
                    v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
                elif k == "floor_areas_sqft":
                    v = [float(x or 0) for x in v]
                elif k == "geometry":
                    v = [dict(x) for x in v] if isinstance(v, list) and v else None
            except (TypeError, ValueError):
                raise MissingInfo([f"'{k}' must be a number"])
            out[k] = v
        return Inputs(**out)


def levels_from_floors(floors: str) -> tuple[int, bool]:
    """'G' -> (1, False); 'G+2' -> (3, False); 'Stilt+2' -> (3, True)."""
    f = (floors or "G").strip().lower().replace(" ", "")
    stilt = f.startswith("stilt") or f.startswith("s+")
    n = 0
    if "+" in f:
        try:
            n = int(f.split("+", 1)[1])
        except ValueError:
            n = 0
    return n + 1, stilt


def validate(inp: Inputs) -> None:
    q = []
    if not inp.floor_areas_sqft or any((a or 0) <= 0 for a in inp.floor_areas_sqft):
        q.append("Please confirm the built-up area (sq ft) of every floor.")
    if len(inp.floor_areas_sqft) > 6:
        q.append("More than G+5 needs a structural design – this estimator supports up to G+5.")
    if inp.structure not in ("rcc_framed", "load_bearing"):
        q.append("Structure must be RCC framed or load bearing.")
    if inp.spec_level not in ("basic", "standard", "premium"):
        q.append("Spec level must be basic, standard or premium.")
    if inp.masonry not in ("brick", "aac", "solid_block"):
        q.append("Masonry must be brick, AAC or solid block.")
    if inp.bedrooms <= 0 and inp.toilets <= 0:
        q.append("How many bedrooms and toilets in total? (needed for walls, doors, plumbing and electrical)")
    if inp.kitchens < 0 or inp.halls < 0 or inp.toilets < 0 or inp.bedrooms < 0:
        q.append("Room counts cannot be negative.")
    if not (7 <= inp.floor_height_ft <= 15):
        q.append("Floor height should be between 7 and 15 ft – please confirm.")
    if q:
        raise MissingInfo(q)


# ---------------------------------------------------------------- engine
class Calc:
    def __init__(self, inp: Inputs, rates: dict[str, dict]):
        self.inp = inp
        self.spec = inp.spec_level
        self.rates = rates
        self.items: list[dict] = []
        self.assumptions: list[str] = []
        self.warnings: list[str] = []
        self._n = 0

    def rate(self, code: str) -> float:
        r = self.rates.get(code)
        if not r:
            self.warnings.append(f"Rate '{code}' missing in rate library – taken as ₹0")
            return 0.0
        return float(r.get(self.spec) or r.get("standard") or 0)

    def name(self, code: str) -> str:
        return (self.rates.get(code) or {}).get("name", code)

    def unit(self, code: str) -> str:
        return (self.rates.get(code) or {}).get("unit", "")

    def add(self, category: str, desc: str, floor: str, qty: float, unit: str,
            materials: dict[str, float] | None = None, labour_work: str | None = None,
            equipment: dict[str, float] | None = None, labour_days: dict[str, float] | None = None):
        if qty <= 0:
            return
        self._n += 1
        mats = []
        for code, q in (materials or {}).items():
            if q <= 0:
                continue
            qw = q * (1 + WASTAGE.get(code, 0))
            r = self.rate(code)
            mats.append({"code": code, "name": self.name(code), "qty": round(qw, 3), "unit": self.unit(code),
                         "rate": r, "amount": round(qw * r, 2)})
        days = dict(labour_days or {})
        if labour_work:
            for trade, per in LAB[labour_work].items():
                days[trade] = days.get(trade, 0) + per * qty
        labs = [{"code": t, "name": self.name(t), "days": round(d, 2), "rate": self.rate(t),
                 "amount": round(d * self.rate(t), 2)} for t, d in days.items() if d > 0]
        eqs = [{"code": c, "name": self.name(c), "qty": round(q, 2), "unit": self.unit(c), "rate": self.rate(c),
                "amount": round(q * self.rate(c), 2)} for c, q in (equipment or {}).items() if q > 0]
        m, l, e = (sum(x["amount"] for x in mats), sum(x["amount"] for x in labs), sum(x["amount"] for x in eqs))
        total = m + l + e
        self.items.append({
            "sl": self._n, "category": category, "group": CATEGORY_GROUP.get(category, "Civil Works"),
            "description": desc, "floor": floor, "qty": round(qty, 2), "unit": unit,
            "material_cost": round(m, 2), "labour_cost": round(l, 2), "equipment_cost": round(e, 2),
            "amount": round(total, 2), "rate": round(total / qty, 2) if qty else 0,
            "materials": mats, "labour": labs, "equipment": eqs,
        })

    # --- helpers for common work types ---
    def rcc(self, desc, floor, vol, steel_key, formwork_m2):
        c, s, a = MIX["M20"]
        mix_days = vol / 8.0
        self.add("RCC", f"RCC M20 – {desc}", floor, vol, "m³",
                 {"cement": c * vol, "msand": s * vol, "agg20": a * vol}, "rcc",
                 {"mixer": mix_days, "vibrator": mix_days})
        kg = vol * STEEL_KG_PER_M3[steel_key]
        self.add("Steel", f"Reinforcement (TMT) – {desc}", floor, kg, "kg",
                 {"steel": kg, "binding_wire": kg * 0.01}, "steel")
        if formwork_m2 > 0:
            self.add("Formwork", f"Centring & shuttering – {desc}", floor, formwork_m2, "m²",
                     {"formwork": formwork_m2}, "formwork")

    def pcc(self, desc, floor, vol):
        c, s, a = MIX["PCC148"]
        self.add("Concrete (PCC)", f"PCC 1:4:8 – {desc}", floor, vol, "m³",
                 {"cement": c * vol, "msand": s * vol, "agg40": a * vol}, "pcc", {"mixer": vol / 10})

    def masonry_wall(self, desc, floor, vol_230, area_115):
        m = self.inp.masonry
        if m == "brick":
            cb, sd = mortar(6, 0.25 * vol_230)
            self.add("Masonry", f"Brick masonry 230 mm in CM 1:6 – {desc}", floor, vol_230, "m³",
                     {"brick": 460 * vol_230, "cement": cb, "msand": sd}, "brick230")
            cb, sd = mortar(4, 0.029 * area_115)
            self.add("Masonry", f"Brick partition 115 mm in CM 1:4 – {desc}", floor, area_115, "m²",
                     {"brick": 53 * area_115, "cement": cb, "msand": sd}, "brick115")
        elif m == "aac":
            vol = vol_230 * (200 / 230) + area_115 * 0.10
            self.add("Masonry", f"AAC block masonry (200/100 mm) – {desc}", floor, vol, "m³",
                     {"aac": vol, "aac_adhesive": 0.7 * vol}, "aac")
        else:
            vol = vol_230 * (200 / 230) + area_115 * 0.10
            cb, sd = mortar(6, 0.15 * vol)
            self.add("Masonry", f"Solid block masonry in CM 1:6 – {desc}", floor, vol, "m³",
                     {"solid_block": 70 * vol, "cement": cb, "msand": sd}, "solid_block")

    def plaster(self, kind, desc, floor, area):
        if kind == "int":
            cb, sd = mortar(6, 0.0144 * area)
            self.add("Plastering", f"Internal plaster 12 mm CM 1:6 – {desc}", floor, area, "m²",
                     {"cement": cb, "psand": sd}, "plaster_int")
        elif kind == "ext":
            cb, sd = mortar(4, 0.024 * area)
            self.add("Plastering", f"External plaster 20 mm CM 1:4 (2 coats) – {desc}", floor, area, "m²",
                     {"cement": cb, "psand": sd}, "plaster_ext")
        else:
            cb, sd = mortar(3, 0.0072 * area)
            self.add("Plastering", f"Ceiling plaster 6 mm CM 1:3 – {desc}", floor, area, "m²",
                     {"cement": cb, "psand": sd}, "ceiling")


def split(total: int, parts: int) -> list[int]:
    """Distribute a whole number across parts as evenly as possible (first parts get more)."""
    if parts <= 0:
        return []
    base, extra = divmod(max(0, total), parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]


def calculate(inputs: dict, rates: dict[str, dict]) -> dict:
    inp = Inputs.from_dict(inputs)
    validate(inp)
    c = Calc(inp, rates)
    rcc_frame = inp.structure == "rcc_framed"

    levels = len(inp.floor_areas_sqft)
    areas = [a * SQFT_TO_M2 for a in inp.floor_areas_sqft]
    names = []
    for i in range(levels):
        if inp.stilt and i == 0:
            names.append("Stilt / Parking")
        else:
            names.append(FLOOR_NAMES[i - (1 if inp.stilt else 0)] if (i - (1 if inp.stilt else 0)) < len(FLOOR_NAMES) else f"Level {i}")
    room_levels = [i for i in range(levels) if not (inp.stilt and i == 0)]
    nrl = max(1, len(room_levels))

    H = inp.floor_height_ft * FT_TO_M
    slab_t = 0.125  # spans kept ≤ 3.6 m by the column grid
    beam_d = 0.45
    if inp.plot_width_ft and inp.plot_length_ft:
        aspect = min(inp.plot_width_ft, inp.plot_length_ft) / max(inp.plot_width_ft, inp.plot_length_ft)
        c.assumptions.append(f"Building footprint taken with the plot's proportion ({aspect:.2f}).")
    else:
        aspect = 0.75
        c.assumptions.append("Plot size not given – building footprint assumed rectangular, 3:4 proportion.")

    G = inp.geometry if (inp.geometry and len(inp.geometry) == levels) else None
    if inp.geometry and not G:
        c.warnings.append("Design geometry did not match the number of floors – standard layout model used.")

    def dims(a):
        w = math.sqrt(a * aspect)
        return w, a / w

    if rcc_frame and levels > 4:
        c.warnings.append("G+4 and above: column/footing sizes MUST come from a structural engineer's design.")
    if not rcc_frame and levels - (1 if inp.stilt else 0) > 2:
        c.warnings.append("Load bearing above G+1 is not recommended – consider RCC framed structure.")
    if not rcc_frame and inp.stilt:
        c.warnings.append("Stilt parking needs RCC framed structure – estimate treats it as RCC framed.")
        rcc_frame = True

    # distribute rooms over floors that have rooms
    bed_l, toi_l, kit_l, hall_l = (split(inp.bedrooms, nrl), split(inp.toilets, nrl),
                                   split(inp.kitchens, nrl), split(inp.halls, nrl))
    per_level = {}
    for k, li in enumerate(room_levels):
        per_level[li] = {"bed": bed_l[k], "toi": toi_l[k], "kit": kit_l[k], "hall": hall_l[k]}

    # ------------- geometry per level -------------
    geo = []
    for i, a in enumerate(areas):
        if G:
            gi = G[i]
            w, l = float(gi.get("width_m") or 0), float(gi.get("depth_m") or 0)
            if w <= 0 or l <= 0:
                w, l = dims(a)
            P = 2 * (w + l)
            is_stilt = bool(gi.get("stilt"))
            r = {"bed": int(gi.get("bed") or 0), "toi": int(gi.get("toi") or 0), "kit": int(gi.get("kit") or 0),
                 "hall": int(gi.get("hall") or 0)}
            ext, int230, part = float(gi.get("ext_m") or 0), float(gi.get("int230_m") or 0), float(gi.get("part_m") or 0)
            door_area = (int(gi.get("main_doors") or 0) * 2.1 + int(gi.get("int_doors") or 0) * 1.89
                         + int(gi.get("toilet_doors") or 0) * 1.575)
            geo.append(dict(a=a, w=w, l=l, P=P, Li=int230 + part, part=part, int230=int230, ext=ext,
                            h=H - (beam_d if rcc_frame else slab_t), r=r, stilt=is_stilt,
                            main_doors=int(gi.get("main_doors") or 0), int_doors=int(gi.get("int_doors") or 0),
                            toilet_doors=int(gi.get("toilet_doors") or 0),
                            win_area=float(gi.get("win_area_m2") or 0), n_win=int(gi.get("n_win") or 0),
                            door_area=door_area, parapet=float(gi.get("parapet_m") or 0),
                            terrace=float(gi.get("terrace_m2") or 0)))
            continue
        w, l = dims(a)
        P = 2 * (w + l)
        r = per_level.get(i, {"bed": 0, "toi": 0, "kit": 0, "hall": 0})
        is_stilt = inp.stilt and i == 0
        wall_factor = 0.12 if is_stilt else 1.0
        Li = 0.28 * a * wall_factor                 # internal wall length, m
        part = (r["toi"] * 2.4) if not is_stilt else 0.0
        int230 = max(0.0, Li - part)
        ext = P * (0.25 if is_stilt else 1.0)
        h_wall = H - (beam_d if rcc_frame else slab_t)
        main_doors = 1 if i == (1 if inp.stilt else 0) else 0
        int_doors = (r["bed"] + (1 if i > (1 if inp.stilt else 0) else 0)) if not is_stilt else 0
        toilet_doors = r["toi"]
        win_area = (r["bed"] * 1.8 + r["hall"] * 2.4 + r["kit"] * 1.08 + r["toi"] * 0.27
                    + (0.72 if inp.staircase else 0)) if not is_stilt else 0
        n_win = (r["bed"] + r["hall"] + r["kit"] + r["toi"] + (1 if inp.staircase else 0)) if not is_stilt else 0
        door_area = main_doors * 2.1 + int_doors * 1.89 + toilet_doors * 1.575
        geo.append(dict(a=a, w=w, l=l, P=P, Li=Li, part=part, int230=int230, ext=ext, h=h_wall, r=r,
                        stilt=is_stilt, main_doors=main_doors, int_doors=int_doors, toilet_doors=toilet_doors,
                        win_area=win_area, n_win=n_win, door_area=door_area))

    g0 = geo[0]
    A0 = max(areas)
    if G:
        gmax = max(geo, key=lambda g: g["w"] * g["l"])
        w0, l0 = gmax["w"], gmax["l"]
        A0 = max(A0, w0 * l0)
        c.assumptions.append("Walls, doors, windows, rooms and footprint measured from the saved design drawing "
                             "(geometry mode) – not from the standard layout model.")
    else:
        w0, l0 = dims(A0)
    P0 = 2 * (w0 + l0)
    c.assumptions += [
        f"Floor height {inp.floor_height_ft:g} ft; plinth 1.5 ft above ground; foundation depth 1.5 m.",
        ("Internal walls measured from the drawing" if G else "Internal walls ≈ 0.28 m per m² of floor")
        + "; toilet partitions 115 mm; external walls 230 mm.",
        "Door / window sizes: main 1.0×2.1 m, room 0.9×2.1 m, toilet 0.75×2.1 m; bedroom window 1.5×1.2 m.",
        "Concrete M20 (1:1.5:3) for all RCC; PCC 1:4:8 under foundations; brickwork CM 1:6, 460 bricks per m³.",
        f"Wastage included: cement 2%, steel 3%, sand 5%, bricks 5%, tiles 8%.",
    ]

    # ------------- foundation & plinth -------------
    F, PL = "Foundation", "Plinth"
    exc_total = back_total = 0.0
    if rcc_frame:
        nx, ny = math.ceil(w0 / 3.6) + 1, math.ceil(l0 / 3.6) + 1
        ncol = nx * ny
        if levels == 1:
            col_b, col_d, fs, fd = 0.23, 0.30, 1.2, 0.35
        elif levels == 2:
            col_b, col_d, fs, fd = 0.23, 0.38, 1.5, 0.40
        elif levels == 3:
            col_b, col_d, fs, fd = 0.23, 0.45, 1.8, 0.45
        else:
            col_b, col_d, fs, fd = 0.30, 0.45, 2.1, 0.50
        c.assumptions.append(
            f"RCC frame: {ncol} columns ({nx}×{ny} grid, ≈3.6 m spacing), column {int(col_b*1000)}×{int(col_d*1000)} mm, "
            f"footing {fs}×{fs}×{fd} m – preliminary sizes, final sizes from structural design.")
        exc = ncol * (fs + 0.6) ** 2 * 1.5
        pb_len = P0 + 0.28 * A0 * 0.6
        exc += pb_len * 0.6 * 0.45
        c.add("Earthwork", "Excavation for footings & plinth beam (JCB + manual dressing)", F, exc, "m³",
              None, "excavation", {"jcb": max(3, exc / 25)})
        c.add("Earthwork", "Anti-termite treatment", F, A0, "m²", {"anti_termite": A0})
        c.pcc("under footings", F, ncol * (fs + 0.2) ** 2 * 0.1)
        foot_vol = ncol * fs * fs * fd
        c.rcc("Footings", F, foot_vol, "footing", ncol * 4 * fs * fd)
        sub_h = 1.5 - fd + 0.45
        c.rcc("Columns up to plinth", F, ncol * col_b * col_d * sub_h, "column", ncol * 2 * (col_b + col_d) * sub_h)
        c.rcc("Plinth beam 230×300", PL, pb_len * 0.23 * 0.30, "plinth_beam", pb_len * 0.30 * 2)
        back = exc - ncol * (fs + 0.2) ** 2 * 0.1 - foot_vol - ncol * col_b * col_d * sub_h
        back = max(0.0, back * 0.85)
        c.add("Earthwork", "Backfilling with excavated earth, compacted", F, back, "m³", None, "backfill")
        exc_total, back_total = exc, back
    else:
        wall_len = P0 + 0.28 * A0 * 0.85
        exc = wall_len * 0.9 * 1.0
        c.assumptions.append("Load bearing: strip foundation 0.9 m wide × 1.0 m deep under all main walls, "
                             "RCC plinth band and lintel band 230×150.")
        c.add("Earthwork", "Excavation for strip foundation", F, exc, "m³", None, "excavation",
              {"jcb": max(3, exc / 25)})
        c.add("Earthwork", "Anti-termite treatment", F, A0, "m²", {"anti_termite": A0})
        c.pcc("strip foundation bed 150 mm", F, wall_len * 0.9 * 0.15)
        fm = wall_len * 0.45 * 0.85
        cb, sd = mortar(6, 0.25 * fm)
        c.add("Masonry", "Foundation masonry (stepped brickwork) in CM 1:6", F, fm, "m³",
              {"brick": 460 * fm, "cement": cb, "msand": sd}, "found_masonry")
        c.rcc("Plinth band 230×150", PL, wall_len * 0.23 * 0.15, "band", wall_len * 0.15 * 2)
        back = max(0.0, (exc - wall_len * 0.9 * 0.15 - fm) * 0.85)
        c.add("Earthwork", "Backfilling with excavated earth, compacted", F, back, "m³", None, "backfill")
        exc_total, back_total = exc, back

    fill = A0 * 0.30
    c.add("Earthwork", "Plinth filling (earth/gravel) 300 mm, compacted", PL, fill, "m³",
          {"filling_soil": fill}, "filling")
    c.pcc("flooring bed 75 mm at ground level", PL, A0 * 0.85 * 0.075)
    surplus = max(0.0, exc_total - back_total)
    if surplus > 0:
        c.add("Earthwork", "Disposal of surplus earth", F, surplus, "m³", None, None,
              {"tractor": math.ceil(surplus / 3)})

    # ------------- superstructure per level -------------
    for i, g in enumerate(geo):
        fl = names[i]
        a = g["a"]
        if rcc_frame:
            c.rcc("Columns", fl, ncol * col_b * col_d * H, "column", ncol * 2 * (col_b + col_d) * H)
            blen = g["P"] + g["Li"] * 0.6
            c.rcc("Beams 230×450", fl, blen * 0.23 * (beam_d - slab_t), "beam", blen * (0.23 + 2 * (beam_d - slab_t)))
        else:
            band_len = g["ext"] + g["int230"]
            c.rcc("Lintel band 230×150", fl, band_len * 0.23 * 0.15, "band", band_len * (0.23 + 0.30))
        slab_area = a * 1.05
        c.rcc(f"Roof slab {int(slab_t*1000)} mm (incl. sunshade/projection 5%)", fl, slab_area * slab_t,
              "slab", slab_area)
        if rcc_frame:
            lin_len = g["n_win"] * 1.6 + (g["main_doors"] + g["int_doors"] + g["toilet_doors"]) * 1.2
            c.rcc("Lintels 230×150", fl, lin_len * 0.23 * 0.15, "lintel", lin_len * 0.53)
        if g["n_win"]:
            ss_len = g["n_win"] * 1.6
            c.rcc("Sunshades 600 mm", fl, ss_len * 0.6 * 0.075, "sunshade", ss_len * 0.66)
        if inp.staircase:
            stair_vol = 2.0 if i < levels - 1 else 1.2   # flight to next floor / to terrace + headroom
            c.rcc("Staircase" + (" to terrace + headroom" if i == levels - 1 else ""), fl, stair_vol, "stair",
                  8 if i < levels - 1 else 6)

        # masonry (deduct openings)
        win_ded = g["win_area"] * 0.23
        door_ded = (g["main_doors"] * 2.1 + g["int_doors"] * 1.89) * 0.23
        vol230 = max(0.0, g["ext"] * 0.23 * g["h"] + g["int230"] * 0.23 * g["h"] - win_ded - door_ded)
        area115 = max(0.0, g["part"] * g["h"] - g["toilet_doors"] * 1.575)
        c.masonry_wall("walls", fl, vol230, area115)

        # plaster
        int_area = (g["ext"] * g["h"] + 2 * g["int230"] * g["h"] + 2 * g["part"] * g["h"]
                    - g["win_area"] - 2 * g["door_area"])
        ext_area = g["ext"] * (g["h"] + beam_d) - g["win_area"]
        if i == 0:
            ext_area += P0 * 0.45  # plinth face
        ceil_area = a * 0.92
        c.plaster("int", "walls", fl, max(0, int_area))
        c.plaster("ext", "outer walls", fl, max(0, ext_area))
        c.plaster("ceil", "ceiling", fl, ceil_area)

        # flooring & tiling
        r = g["r"]
        floor_area = a * 0.85
        cb, sd = mortar(4, 0.02 * floor_area)
        if g["stilt"]:
            c.add("Flooring & Tiling", "Parking flooring (paver / tiles)", fl, floor_area, "m²",
                  {"parking_floor": floor_area, "cement": cb, "msand": sd}, "parking")
        else:
            c.add("Flooring & Tiling", "Vitrified floor tiles on CM 1:4 bed (incl. skirting)", fl, floor_area, "m²",
                  {"floor_tile": floor_area * 1.06, "cement": cb, "msand": sd}, "floor_tile")
        wt = r["toi"] * 15.5 + r["kit"] * 1.8
        c.add("Flooring & Tiling", "Wall tiles – toilets (2.1 m) & kitchen dado", fl, wt, "m²",
              {"wall_tile": wt, "tile_adhesive": wt}, "wall_tile")
        gr = r["kit"] * 1.8 + (6.0 if (inp.staircase and i < levels - 1) else 0)
        c.add("Flooring & Tiling", "Granite – kitchen counter & staircase treads/risers", fl, gr, "m²",
              {"granite": gr}, "granite")

        # waterproofing
        wp = r["toi"] * 4.8 + g.get("terrace", 0)
        if i == levels - 1:
            wp += a + g["P"] * 0.3
        c.add("Waterproofing", "Waterproofing – toilets" + (" & terrace" if i == levels - 1 else ""), fl, wp, "m²",
              {"waterproof": wp}, "waterproof")

        # painting
        c.add("Painting", "Interior painting – putty, primer, 2 coats emulsion (walls + ceiling)", fl,
              max(0, int_area) + ceil_area, "m²", {"paint_int": max(0, int_area) + ceil_area}, "paint_int")
        c.add("Painting", "Exterior painting – primer + 2 coats", fl, max(0, ext_area), "m²",
              {"paint_ext": max(0, ext_area)}, "paint_ext")

        # doors & windows
        if g["main_doors"]:
            c.add("Doors & Windows", "Main door with frame & hardware", fl, g["main_doors"], "nos",
                  {"door_main": g["main_doors"], "hardware": g["main_doors"]}, "door")
        if g["int_doors"]:
            c.add("Doors & Windows", "Room doors (flush) with frame & hardware", fl, g["int_doors"], "nos",
                  {"door_internal": g["int_doors"], "hardware": g["int_doors"]}, "door")
        if g["toilet_doors"]:
            c.add("Doors & Windows", "Toilet doors (PVC/FRP) with frame", fl, g["toilet_doors"], "nos",
                  {"door_toilet": g["toilet_doors"], "hardware": g["toilet_doors"]}, "door")
        if g["win_area"]:
            c.add("Doors & Windows", "Windows & ventilators with glass", fl, g["win_area"], "m²",
                  {"window": g["win_area"]}, "window")
            kg = g["win_area"] * 15
            c.add("Doors & Windows", "MS grills for windows", fl, kg, "kg", {"grill": kg}, "grill")
            enamel = g["win_area"] + (g["main_doors"] * 2.1 + g["int_doors"] * 1.89) * 2 * 1.1
            c.add("Painting", "Enamel paint – doors & grills", fl, enamel, "m²", {"enamel": enamel}, "enamel")

        # plumbing & electrical
        if r["toi"]:
            c.add("Plumbing & Sanitary", "Toilet – sanitary fittings set", fl, r["toi"], "nos",
                  {"sanitary_set": r["toi"]}, None)
            c.add("Plumbing & Sanitary", "Toilet – water supply & drainage piping", fl, r["toi"], "nos",
                  {"plumbing_toilet": r["toi"]}, "toilet_plumb")
        if r["kit"]:
            c.add("Plumbing & Sanitary", "Kitchen sink, tap & piping", fl, r["kit"], "nos",
                  {"kitchen_plumb": r["kit"]}, "kitchen_plumb")
        points = r["bed"] * 8 + r["hall"] * 10 + r["kit"] * 8 + r["toi"] * 3 + (4 if not g["stilt"] else 6)
        c.add("Electrical", "Electrical points (conduit, wiring, switches)", fl, points, "point",
              {"elec_point": points}, "elec_point")
        c.add("Electrical", "Distribution board with MCBs", fl, 1, "nos", {"elec_db": 1},
              None, None, {"electrician": 1})

    # parapet at terrace
    top = geo[-1]
    par = top["P"] * 0.9 + sum(g.get("parapet", 0) for g in geo) * 0.9
    c.masonry_wall("terrace parapet 0.9 m", "Terrace", 0, par if inp.masonry == "brick" else par)
    c.plaster("int", "parapet inner face", "Terrace", par)
    c.plaster("ext", "parapet outer face", "Terrace", par)

    # ------------- services & external -------------
    EX = "External"
    oh = inp.oh_tank_litres if inp.oh_tank_litres is not None else 1000 * max(1, inp.kitchens)
    if oh > 0:
        c.add("Plumbing & Sanitary", f"Overhead tank {oh} L with fittings", "Terrace", oh, "litre",
              {"oh_tank": oh}, None, None, {"plumber": 1, "helper_m": 1})
    if inp.sump_litres > 0:
        c.add("Plumbing & Sanitary", f"Underground sump {inp.sump_litres} L (complete) + pump", EX,
              inp.sump_litres, "litre", {"sump": inp.sump_litres, "motor": 1}, None, None, {"plumber": 1})
    if inp.septic_tank:
        c.add("Plumbing & Sanitary", "Septic tank + soak pit (complete)", EX, 1, "nos", {"septic": 1})
    c.add("Electrical", "Earthing pits", EX, 2, "nos", {"earthing": 2}, None, None, {"electrician": 1})
    c.add("Electrical", "EB service connection & meter board", EX, 1, "nos", {"eb_connection": 1})
    if inp.rwh:
        c.add("External Works", "Rain water harvesting pit (TN mandatory)", EX, 1, "nos", {"rwh": 1})
    if inp.compound_wall:
        if inp.compound_wall_length_m:
            cw = inp.compound_wall_length_m
        elif inp.plot_width_ft and inp.plot_length_ft:
            cw = 2 * (inp.plot_width_ft + inp.plot_length_ft) * FT_TO_M - 3.6
            c.assumptions.append(f"Compound wall length = plot perimeter minus 3.6 m gate = {cw:.1f} m, 1.5 m high.")
        else:
            cw = 0
            c.warnings.append("Compound wall selected but plot size / wall length not given – not included.")
        c.add("External Works", "Compound wall 1.5 m high (complete)", EX, cw, "rmt",
              {"compound_wall": cw}, "compound_wall")
    if inp.gate:
        c.add("External Works", "MS gate (fabricated & painted)", EX, 1, "nos", {"gate": 1}, None, None,
              {"welder": 1, "helper_m": 1})
    if inp.parking_area_sqft > 0:
        pa = inp.parking_area_sqft * SQFT_TO_M2
        c.add("External Works", "Parking / sit-out flooring", EX, pa, "m²", {"parking_floor": pa}, "parking")

    # ------------- additional items chosen by the user from the rate library -------------
    for x in inp.extra_items or []:
        code, qty = x.get("code"), float(x.get("qty") or 0)
        if not code or qty <= 0:
            continue
        r = rates.get(code)
        if not r:
            c.warnings.append(f"Additional item '{code}' not found in rate library – skipped")
            continue
        kind = r.get("kind", "material")
        label = r.get("name", code) + (f" – {x['note']}" if x.get("note") else "")
        if kind == "labour":
            c.add("Additional Items", label, "Additional", qty, "day", None, None, None, {code: qty})
        elif kind == "equipment":
            c.add("Additional Items", label, "Additional", qty, r.get("unit", ""), None, None, {code: qty})
        else:
            c.add("Additional Items", label, "Additional", qty, r.get("unit", ""), {code: qty})

    # ------------- duration, site overheads -------------
    total_sqft = sum(inp.floor_areas_sqft)
    months = int(round(min(18, max(3, 3 + total_sqft / 700 + 0.8 * (levels - 1)))))
    c.add("Earthwork", "Construction water (tanker loads)", "Site", months * 8, "load", None, None,
          {"water_tanker": months * 8})
    c.add("Earthwork", "Watchman & curing during construction", "Site", months * 26, "day", None, None, None,
          {"watchman": months * 26})

    return summarize(c, inp, names, total_sqft, months)


def summarize(c: Calc, inp: Inputs, names: list[str], total_sqft: float, months: int) -> dict:
    items = c.items
    mat = sum(i["material_cost"] for i in items)
    lab = sum(i["labour_cost"] for i in items)
    eqp = sum(i["equipment_cost"] for i in items)

    # aggregate materials / labour / equipment
    def agg(key, qty_field):
        out: dict[str, dict] = {}
        for it in items:
            for x in it[key]:
                o = out.setdefault(x["code"], {"code": x["code"], "name": x["name"], "unit": x.get("unit", "day"),
                                               "qty": 0.0, "rate": x["rate"], "amount": 0.0})
                o["qty"] += x[qty_field]
                o["amount"] += x["amount"]
        for o in out.values():
            o["qty"] = round(o["qty"], 2)
            o["amount"] = round(o["amount"], 2)
        return sorted(out.values(), key=lambda o: -o["amount"])

    materials = agg("materials", "qty")
    labour = agg("labour", "days")
    for l in labour:
        l["unit"] = "man-days"
    equipment = agg("equipment", "qty")

    rate = c.rate
    transport = mat * rate("transport_pct") / 100
    water_eb = rate("water_eb_month") * months
    construction = mat + lab + eqp + transport + water_eb
    cont_pct = inp.contingency_pct if inp.contingency_pct is not None else rate("contingency_pct")
    contingency = construction * cont_pct / 100
    margin = construction * inp.contractor_margin_pct / 100
    gst = (construction + contingency + margin) * inp.gst_pct / 100
    approval = inp.approval_fees or 0
    extras = [
        {"name": "Material transport & loading", "basis": f"{rate('transport_pct'):g}% of materials", "amount": round(transport, 2)},
        {"name": "Temporary water + EB", "basis": f"{months} months", "amount": round(water_eb, 2)},
        {"name": "Contingency", "basis": f"{cont_pct:g}%", "amount": round(contingency, 2)},
        {"name": "Contractor margin", "basis": f"{inp.contractor_margin_pct:g}%", "amount": round(margin, 2)},
        {"name": "GST", "basis": f"{inp.gst_pct:g}%", "amount": round(gst, 2)},
        {"name": "Plan approval & fees", "basis": "as entered", "amount": round(approval, 2)},
    ]
    extras_total = sum(e["amount"] for e in extras)
    grand = mat + lab + eqp + extras_total
    if approval == 0:
        c.assumptions.append("Plan approval / permit fees not included (enter them if known).")
    if inp.contractor_margin_pct == 0:
        c.assumptions.append("No contractor margin (owner-managed construction). Set a % if a contractor builds it.")

    # floor-wise summary (order: Foundation, Plinth, floors..., Terrace, External, Site)
    order = ["Foundation", "Plinth"] + names + ["Terrace", "External", "Additional", "Site"]
    area_by_floor = {n: a for n, a in zip(names, inp.floor_areas_sqft)}
    floors = []
    for f in order:
        its = [i for i in items if i["floor"] == f]
        if not its:
            continue
        floors.append({"floor": f, "builtup_sqft": area_by_floor.get(f),
                       "material_cost": round(sum(i["material_cost"] for i in its), 2),
                       "labour_cost": round(sum(i["labour_cost"] for i in its), 2),
                       "equipment_cost": round(sum(i["equipment_cost"] for i in its), 2),
                       "total": round(sum(i["amount"] for i in its), 2)})

    groups: dict[str, float] = {}
    for i in items:
        groups[i["group"]] = groups.get(i["group"], 0) + i["amount"]
    groups["Extras"] = extras_total
    breakdown = [{"group": g, "amount": round(v, 2), "pct": round(100 * v / grand, 1) if grand else 0}
                 for g, v in sorted(groups.items(), key=lambda kv: -kv[1])]

    def mq(code):
        return next((m["qty"] for m in materials if m["code"] == code), 0)

    cement = mq("cement")
    steel = mq("steel")
    totals = {
        "materials": round(mat, 2), "labour": round(lab, 2), "equipment": round(eqp, 2),
        "extras": round(extras_total, 2), "grand_total": round(grand, 2),
        "builtup_sqft": round(total_sqft, 1), "builtup_m2": round(total_sqft * SQFT_TO_M2, 1),
        "cost_per_sqft": round(grand / total_sqft, 0) if total_sqft else 0,
        "cement_bags": math.ceil(cement), "steel_kg": math.ceil(steel),
        "bricks": math.ceil(mq("brick")), "msand_m3": round(mq("msand"), 1), "psand_m3": round(mq("psand"), 1),
        "aggregate_m3": round(mq("agg20") + mq("agg40"), 1),
        "cement_bags_per_sqft": round(cement / total_sqft, 2) if total_sqft else 0,
        "steel_kg_per_sqft": round(steel / total_sqft, 2) if total_sqft else 0,
        "duration_months": months,
        "man_days": round(sum(l["qty"] for l in labour), 0),
    }
    return {
        "engine_version": "2.0",
        "spec_level": inp.spec_level, "structure": inp.structure, "masonry": inp.masonry,
        "items": items, "materials": materials, "labour": labour, "equipment": equipment,
        "extras": extras, "floors": floors, "breakdown": breakdown, "totals": totals,
        "assumptions": c.assumptions, "warnings": c.warnings,
        "note": ("Preliminary estimate from a standard layout model. Quantities will be recalculated from the "
                 "actual drawing in Design Studio. Structural sizes must be confirmed by a qualified engineer."),
    }
