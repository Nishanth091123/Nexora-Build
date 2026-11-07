"""1.18 Material Library – the complete material list of a house, stage by stage, with market brands (NAMES only,
no logos, no prices). The owner enters every rate and tags each brand A / B / C (A = Premium, B = Standard, C = Basic).

Each category: key, name, stage, default unit, the estimate rate code it feeds (or None) and how one unit of the
variant converts to the rate code's unit (factor). A variant can override rate_code / factor in its spec.
Seeding only ADDS missing brands / variants – nothing the owner edited is touched.
"""
from __future__ import annotations

SQFT_PER_M2 = 10.7639

# key, name, stage, unit, rate_code, factor (rate in the code's unit = variant rate × factor)
CATEGORIES: list[tuple[str, str, str, str, str | None, float]] = [
    # ---- 1. foundation & structure
    ("cement", "Cement", "Structure", "bag", "cement", 1.0),
    ("steel", "TMT steel bars", "Structure", "kg", "steel", 1.0),
    ("binding_wire", "Binding wire", "Structure", "kg", "binding_wire", 1.0),
    ("sand", "Sand (M-Sand / P-Sand)", "Structure", "m3", "msand", 1.0),
    ("aggregate", "Aggregate (jelly)", "Structure", "m3", "agg20", 1.0),
    ("masonry", "Bricks & blocks", "Structure", "nos", "brick", 1.0),
    ("admixture", "Admixtures & curing", "Structure", "litre", None, 1.0),
    ("anti_termite", "Anti-termite chemical", "Structure", "litre", None, 1.0),
    # ---- 2. waterproofing
    ("waterproofing", "Waterproofing", "Waterproofing", "litre", None, 1.0),
    # ---- 3. flooring & tiling
    ("floor_tiles", "Floor tiles", "Flooring", "sq ft", "floor_tile", SQFT_PER_M2),
    ("wall_tiles", "Wall tiles (toilet / kitchen)", "Flooring", "sq ft", "wall_tile", SQFT_PER_M2),
    ("granite_marble", "Granite & marble", "Flooring", "sq ft", "granite", SQFT_PER_M2),
    ("tile_adhesive", "Tile adhesive & grout", "Flooring", "bag", None, 1.0),
    # ---- 4. doors, windows & joinery
    ("plywood", "Plywood & boards", "Doors & windows", "sq ft", None, 1.0),
    ("doors", "Doors", "Doors & windows", "nos", "door_internal", 1.0),
    ("windows", "Windows", "Doors & windows", "sq ft", "window", SQFT_PER_M2),
    ("hardware", "Door / window hardware", "Doors & windows", "set", "hardware", 1.0),
    ("grills_gate", "Grills, railings & gate", "Doors & windows", "kg", "grill", 1.0),
    # ---- 5. plumbing & sanitary
    ("pipes", "Pipes & fittings", "Plumbing", "length", None, 1.0),
    ("sanitary", "Sanitaryware", "Plumbing", "nos", None, 1.0),
    ("cp_fittings", "Taps & CP fittings", "Plumbing", "nos", None, 1.0),
    ("water_tank", "Water tanks", "Plumbing", "nos", "oh_tank", 1.0),
    ("pump", "Water pump", "Plumbing", "nos", "motor", 1.0),
    # ---- 6. electrical
    ("wires", "Wires & cables", "Electrical", "coil", None, 1.0),
    ("switches", "Switches & sockets", "Electrical", "nos", None, 1.0),
    ("db_mcb", "DB, MCB & RCCB", "Electrical", "nos", None, 1.0),
    ("fans_lights", "Fans & lights", "Electrical", "nos", None, 1.0),
    # ---- 7. painting
    ("putty_primer", "Putty & primer", "Painting", "bag", None, 1.0),
    ("paint_interior", "Interior paint", "Painting", "litre", None, 1.0),
    ("paint_exterior", "Exterior paint", "Painting", "litre", None, 1.0),
    ("enamel", "Enamel & wood finish", "Painting", "litre", None, 1.0),
    # ---- 8. roofing
    ("roofing_sheets", "Roofing sheets", "Roofing", "sq ft", "sheet_galvalume", SQFT_PER_M2),
]

LOCAL = "Local supplier"

BRANDS: dict[str, list[str]] = {
    "cement": ["UltraTech", "Ramco", "Dalmia", "Chettinad", "ACC", "Ambuja", "Sankar (India Cements)", "Coromandel King",
               "Zuari", "Priya", "Maha", "Bharathi", "JSW Cement"],
    "steel": ["TATA Tiscon", "JSW Neosteel", "SAIL", "Vizag Steel (RINL)", "Jindal Panther", "Kamachi", "ARS", "Agni",
              "Sunvik", "Pulkit", "Kamdhenu", "Indus"],
    "binding_wire": [LOCAL],
    "sand": [LOCAL],
    "aggregate": [LOCAL],
    "masonry": [LOCAL, "Magicrete", "Biltech", "Renacon", "UltraTech Xtralite", "HIL Aerecon", "Siporex"],
    "admixture": ["Dr. Fixit (Pidilite)", "Fosroc", "Sika", "MYK Laticrete"],
    "anti_termite": ["Bayer", "Dhanuka", LOCAL],
    "waterproofing": ["Dr. Fixit (Pidilite)", "Fosroc", "Sika", "Asian Paints SmartCare", "MYK Laticrete", "Ardex Endura"],
    "floor_tiles": ["Kajaria", "Somany", "H&R Johnson", "Nitco", "Orientbell", "Asian Granito (AGL)", "Simpolo", "Varmora",
                    "RAK Ceramics", "Cera"],
    "wall_tiles": ["Kajaria", "Somany", "H&R Johnson", "Nitco", "Orientbell", "Asian Granito (AGL)", "Varmora"],
    "granite_marble": [LOCAL],
    "tile_adhesive": ["MYK Laticrete", "Roff", "Weber (Saint-Gobain)", "Ardex Endura", "Dr. Fixit (Pidilite)"],
    "plywood": ["CenturyPly", "Greenply", "Kitply", "Archidply", "Sharon Ply", "Austin Plywood"],
    "doors": [LOCAL, "CenturyPly", "Greenply", "Sintex"],
    "windows": ["Fenesta", "LX Hausys", "Encraft", "Prominance", "Kommerling", LOCAL],
    "hardware": ["Dorset", "Godrej", "Hettich", "Ebco", "Europa"],
    "grills_gate": [LOCAL],
    "pipes": ["Ashirvad", "Supreme", "Finolex", "Astral", "Prince", "Jain"],
    "sanitary": ["Hindware", "Parryware", "Jaquar", "Cera", "Kohler", "Roca", "Johnson"],
    "cp_fittings": ["Jaquar", "Hindware", "Parryware", "Cera", "Kohler", "Grohe"],
    "water_tank": ["Sintex", "Supreme", "Vectus", "Penguin"],
    "pump": ["Crompton", "Kirloskar", "CRI", "Texmo", "V-Guard"],
    "wires": ["Finolex", "Polycab", "Havells", "RR Kabel", "KEI", "Anchor"],
    "switches": ["Anchor (Panasonic)", "Legrand", "Schneider", "Havells", "GM Modular", "Great White"],
    "db_mcb": ["Havells", "Schneider", "Legrand", "ABB", "Lauritz Knudsen (L&T)"],
    "fans_lights": ["Crompton", "Havells", "Orient", "Usha", "Bajaj", "Atomberg", "Philips", "Wipro"],
    "putty_primer": ["Birla White", "JK White", "Asian Paints", "Berger"],
    "paint_interior": ["Asian Paints", "Berger", "Nerolac", "Dulux", "Nippon", "Indigo", "JSW Paints", "Birla Opus"],
    "paint_exterior": ["Asian Paints", "Berger", "Nerolac", "Dulux", "Nippon", "Indigo", "JSW Paints", "Birla Opus"],
    "enamel": ["Asian Paints", "Berger", "Nerolac", "Dulux"],
    "roofing_sheets": ["Tata BlueScope", "JSW Colouron+", "Jindal", "Everest", "Ramco Hilux", "Visaka"],
}

# variants for every brand of the category: (name, unit or "", spec)
VARIANTS: dict[str, list[tuple[str, str, dict]]] = {
    "cement": [("OPC 53 grade", "bag", {"type": "OPC 53", "weight_kg": 50}), ("OPC 43 grade", "bag", {"type": "OPC 43", "weight_kg": 50}),
               ("PPC", "bag", {"type": "PPC", "weight_kg": 50}), ("PSC", "bag", {"type": "PSC", "weight_kg": 50})],
    "steel": [(g, "kg", {"grade": g, "dia_mm": [8, 10, 12, 16, 20, 25, 32]}) for g in ("Fe 500", "Fe 500D", "Fe 550D")],
    "binding_wire": [("Annealed binding wire 18 / 20 gauge", "kg", {})],
    "sand": [("M-Sand (concrete / masonry)", "m3", {"rate_code": "msand"}), ("P-Sand (plastering)", "m3", {"rate_code": "psand"}),
             ("River sand", "m3", {"rate_code": "msand"})],
    "aggregate": [("Blue metal 20 mm", "m3", {"rate_code": "agg20", "size_mm": 20}), ("Jelly 40 mm (PCC)", "m3", {"rate_code": "agg40", "size_mm": 40}),
                  ("Blue metal 12 mm", "m3", {"size_mm": 12, "rate_code": None})],
    "admixture": [("Integral waterproofing liquid", "litre", {}), ("Concrete plasticiser", "litre", {}), ("Curing compound", "litre", {})],
    "anti_termite": [("Anti-termite chemical (chlorpyrifos)", "litre", {})],
    "waterproofing": [("Terrace waterproof coating", "litre", {}), ("Bathroom / sunken membrane", "litre", {}),
                      ("Polymer cementitious coating (2 part)", "kit", {})],
    "floor_tiles": [("600x600 GVT glossy", "sq ft", {"size": "600x600", "type": "GVT", "finish": "glossy"}),
                    ("600x600 vitrified matt", "sq ft", {"size": "600x600", "type": "Vitrified", "finish": "matt"}),
                    ("800x800 PGVT glossy", "sq ft", {"size": "800x800", "type": "PGVT", "finish": "glossy"}),
                    ("600x1200 GVT", "sq ft", {"size": "600x1200", "type": "GVT", "finish": "glossy"}),
                    ("800x1600 slab tile", "sq ft", {"size": "800x1600", "type": "GVT slab", "finish": "glossy"}),
                    ("300x300 anti-skid (toilet)", "sq ft", {"size": "300x300", "type": "Ceramic", "finish": "anti-skid"}),
                    ("Parking tile 400x400", "sq ft", {"size": "400x400", "type": "Heavy duty", "finish": "rustic", "rate_code": "parking_floor"})],
    "wall_tiles": [("300x450 ceramic glossy", "sq ft", {"size": "300x450", "type": "Ceramic", "finish": "glossy"}),
                   ("300x600 ceramic", "sq ft", {"size": "300x600", "type": "Ceramic", "finish": "glossy"}),
                   ("250x375 ceramic", "sq ft", {"size": "250x375", "type": "Ceramic", "finish": "matt"})],
    "granite_marble": [(n, "sq ft", {"stone": n}) for n in ("Black Galaxy granite", "Absolute Black granite", "Tan Brown granite",
                                                          "Steel Grey granite", "Kashmir White granite", "Makrana marble", "Italian marble")],
    "tile_adhesive": [("Tile adhesive (C1, 20 kg)", "bag", {}), ("Tile adhesive (C2, large tiles)", "bag", {}), ("Epoxy grout", "kg", {})],
    "plywood": [("BWP 710 – 18 mm", "sq ft", {"grade": "BWP", "mm": 18}), ("MR – 18 mm", "sq ft", {"grade": "MR", "mm": 18}),
                ("MR – 12 mm", "sq ft", {"grade": "MR", "mm": 12}), ("MR – 6 mm", "sq ft", {"grade": "MR", "mm": 6})],
    "doors": [("Main door – teak with frame", "nos", {"rate_code": "door_main"}), ("Flush door with frame", "nos", {"rate_code": "door_internal"}),
              ("WPC door with frame", "nos", {"rate_code": "door_internal"}), ("PVC / FRP toilet door", "nos", {"rate_code": "door_toilet"})],
    "windows": [("UPVC sliding window", "sq ft", {"type": "UPVC sliding"}), ("UPVC casement window", "sq ft", {"type": "UPVC casement"}),
                ("Aluminium sliding window", "sq ft", {"type": "Aluminium"}), ("Wooden window", "sq ft", {"type": "Wood"})],
    "hardware": [("Door hardware set (hinges, tower bolt, handle)", "set", {}), ("Main door lock", "nos", {"rate_code": None}),
                 ("Window hardware set", "set", {"rate_code": None})],
    "grills_gate": [("MS window grill", "kg", {"rate_code": "grill"}), ("SS staircase railing", "rmt", {"rate_code": None}),
                    ("MS gate (fabricated)", "nos", {"rate_code": "gate"})],
    "pipes": [("CPVC pipe 3/4\" (3 m)", "length", {}), ("UPVC pipe 1\" (3 m)", "length", {}), ("PVC SWR pipe 110 mm (3 m)", "length", {}),
              ("PVC SWR pipe 75 mm (3 m)", "length", {})],
    "sanitary": [("EWC floor mounted", "nos", {}), ("Wall-hung EWC with concealed tank", "nos", {}), ("Wash basin with pedestal", "nos", {}),
                 ("Complete toilet set (EWC, basin, taps, shower)", "set", {"rate_code": "sanitary_set"})],
    "cp_fittings": [("Pillar tap", "nos", {}), ("Wall mixer", "nos", {}), ("Overhead shower set", "nos", {}), ("Health faucet", "nos", {})],
    "water_tank": [("500 litre tank", "nos", {"litres": 500, "factor": 1 / 500}), ("1000 litre tank", "nos", {"litres": 1000, "factor": 1 / 1000}),
                   ("2000 litre tank", "nos", {"litres": 2000, "factor": 1 / 2000})],
    "pump": [("1 HP monoblock pump", "nos", {"hp": 1}), ("0.5 HP pump", "nos", {"hp": 0.5}), ("Openwell submersible 1 HP", "nos", {"hp": 1})],
    "wires": [(f"FR / FRLS wire {s} sq mm (90 m)", "coil", {"sq_mm": s}) for s in (1.0, 1.5, 2.5, 4.0, 6.0)],
    "switches": [("Modular switch 6A", "nos", {}), ("Modular socket 6/16A", "nos", {}), ("Modular plate + box", "nos", {})],
    "db_mcb": [("DB 8 way (SPN)", "nos", {}), ("MCB single pole", "nos", {}), ("RCCB 40A 30mA", "nos", {})],
    "fans_lights": [("Ceiling fan 1200 mm", "nos", {}), ("BLDC ceiling fan", "nos", {}), ("LED panel 12 W", "nos", {}), ("LED batten 20 W", "nos", {})],
    "putty_primer": [("Wall putty (40 kg)", "bag", {}), ("Interior primer (20 L)", "can", {}), ("Exterior primer (20 L)", "can", {})],
    "paint_interior": [("Premium emulsion", "litre", {"finish": "sheen"}), ("Standard emulsion", "litre", {"finish": "matt"}),
                       ("Economy emulsion", "litre", {"finish": "matt"})],
    "paint_exterior": [("Premium exterior emulsion", "litre", {"finish": "sheen"}), ("Standard exterior emulsion", "litre", {"finish": "matt"})],
    "enamel": [("Synthetic enamel", "litre", {"finish": "gloss"}), ("PU wood finish", "litre", {"finish": "gloss"})],
    "roofing_sheets": [("Colour-coated Galvalume 0.47 mm", "sq ft", {"rate_code": "sheet_galvalume"}),
                       ("GI sheet 0.50 mm", "sq ft", {"rate_code": "sheet_gi"}), ("PUF panel 50 mm", "sq ft", {"rate_code": "sheet_puff"}),
                       ("Fibre cement (ACC) sheet", "sq ft", {"rate_code": "sheet_acc"}), ("Polycarbonate 4 mm", "sq ft", {"rate_code": "sheet_polycarbonate"})],
}

# product names that are well known for a brand (shown instead of the generic names)
BRAND_VARIANTS: dict[tuple[str, str], list[tuple[str, str, dict]]] = {
    ("masonry", LOCAL): [("Chamber brick 9\"x4\"x3\"", "nos", {"rate_code": "brick"}), ("Wire-cut brick", "nos", {"rate_code": "brick"}),
                         ("Solid concrete block 6\"", "nos", {"rate_code": "solid_block"}), ("Solid concrete block 4\"", "nos", {"rate_code": None})],
    ("paint_interior", "Asian Paints"): [("Royale (luxury emulsion)", "litre", {"finish": "sheen"}), ("Apcolite Premium Emulsion", "litre", {"finish": "matt"}),
                                         ("Tractor Emulsion", "litre", {"finish": "matt"})],
    ("paint_exterior", "Asian Paints"): [("Apex Ultima", "litre", {"finish": "sheen"}), ("Apex", "litre", {"finish": "matt"}), ("Ace", "litre", {"finish": "matt"})],
    ("paint_interior", "Berger"): [("Silk Glamor", "litre", {"finish": "sheen"}), ("Easy Clean", "litre", {"finish": "matt"}), ("Bison", "litre", {"finish": "matt"})],
    ("paint_exterior", "Berger"): [("WeatherCoat", "litre", {"finish": "matt"})],
    ("paint_interior", "Dulux"): [("Velvet Touch", "litre", {"finish": "sheen"}), ("Promise", "litre", {"finish": "matt"})],
    ("paint_exterior", "Dulux"): [("Weathershield", "litre", {"finish": "matt"})],
    ("paint_interior", "Nerolac"): [("Impressions", "litre", {"finish": "sheen"}), ("Beauty", "litre", {"finish": "matt"})],
    ("paint_exterior", "Nerolac"): [("Excel", "litre", {"finish": "matt"})],
}
for _b in ("Magicrete", "Biltech", "Renacon", "UltraTech Xtralite", "HIL Aerecon", "Siporex"):
    BRAND_VARIANTS[("masonry", _b)] = [(f"AAC block 600x200x{t}", "m3", {"rate_code": "aac", "size": f"600x200x{t}"}) for t in (100, 150, 200)]
for _b in ("Everest", "Ramco Hilux", "Visaka"):
    BRAND_VARIANTS[("roofing_sheets", _b)] = [("Fibre cement (ACC) sheet", "sq ft", {"rate_code": "sheet_acc"})]

CAT = {c[0]: c for c in CATEGORIES}
SEED_VERSION = 1  # bump when new brands / variants are added to the lists above


def variants_for(cat: str, brand: str) -> list[tuple[str, str, dict]]:
    return BRAND_VARIANTS.get((cat, brand)) or VARIANTS.get(cat, [])


def seed_market(db) -> None:
    """Add missing brands / variants. Never changes or removes what the owner edited."""
    from .models import AppSetting, MarketBrand, MarketVariant
    flag = db.get(AppSetting, "market_seed")
    if flag and (flag.value or {}).get("v", 0) >= SEED_VERSION:
        return  # seeded once – brands the owner removed are not brought back
    have_b = {(b.category, b.name.lower()): b for b in db.query(MarketBrand).all()}
    have_v = {(v.brand_id, v.name.lower()) for v in db.query(MarketVariant.brand_id, MarketVariant.name).all()}
    for cat, names in BRANDS.items():
        for name in names:
            b = have_b.get((cat, name.lower()))
            if not b:
                b = MarketBrand(category=cat, name=name)
                db.add(b)
                db.flush()
            for vname, unit, spec in variants_for(cat, name):
                if (b.id, vname.lower()) not in have_v:
                    db.add(MarketVariant(brand_id=b.id, category=cat, name=vname, unit=unit or CAT[cat][3], spec=dict(spec)))
    if flag:
        flag.value = {"v": SEED_VERSION}
    else:
        db.add(AppSetting(key="market_seed", value={"v": SEED_VERSION}))
    db.commit()
