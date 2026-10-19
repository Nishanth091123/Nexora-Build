"""Default rate library – Tamil Nadu AVERAGE rates (Oct 2026, approximate).

These are starting values only. Every rate is editable in the app (Rate Library),
per state. Spec levels: Basic / Standard (default) / Premium.
For labour, the rate is a DAY WAGE (same for all spec levels).

code         – stable key used by the estimate engine (do not change)
kind         – material | labour | equipment | extra
"""

# (code, kind, category, name, unit, basic, standard, premium, note)
RATES: list[tuple] = [
    # ---------------- materials: structure ----------------
    ("cement", "material", "Cement", "Cement (PPC / OPC 53)", "bag", 360, 400, 440,
     "Basic: local PPC · Standard: branded PPC/OPC 53 · Premium: premium brand OPC 53 / PSC"),
    ("steel", "material", "Steel", "TMT steel bars", "kg", 58, 66, 74,
     "Basic: Fe500 · Standard: Fe500D branded · Premium: Fe550D / CRS"),
    ("binding_wire", "material", "Steel", "Binding wire", "kg", 75, 80, 85, ""),
    ("msand", "material", "Sand", "M-Sand (concrete / masonry)", "m3", 1750, 1850, 1950, "1 unit (100 cft) = 2.83 m³"),
    ("psand", "material", "Sand", "P-Sand (plastering)", "m3", 2000, 2150, 2300, ""),
    ("agg20", "material", "Aggregate", "Blue metal / jelly 20 mm", "m3", 1500, 1600, 1700, ""),
    ("agg40", "material", "Aggregate", "Jelly 40 mm (PCC)", "m3", 1300, 1400, 1500, ""),
    ("brick", "material", "Masonry", "Bricks (chamber / wire-cut)", "nos", 8, 10, 12,
     "Basic: chamber brick · Standard: good chamber/wire-cut · Premium: wire-cut"),
    ("aac", "material", "Masonry", "AAC blocks", "m3", 4300, 4700, 5200, ""),
    ("aac_adhesive", "material", "Masonry", "AAC block adhesive (40 kg)", "bag", 420, 480, 560, ""),
    ("solid_block", "material", "Masonry", "Solid concrete block 6\"", "nos", 36, 40, 45, ""),
    ("formwork", "material", "Formwork", "Centring sheets / props / plywood (hire + consumables)", "m2", 220, 250, 280, ""),
    ("anti_termite", "material", "Earthwork", "Anti-termite chemical treatment", "m2", 25, 35, 50, ""),
    ("filling_soil", "material", "Earthwork", "Filling earth / gravel", "m3", 450, 500, 550, "Plinth filling"),
    # ---------------- materials: finishes ----------------
    ("floor_tile", "material", "Flooring", "Floor tiles (vitrified)", "m2", 480, 750, 1300, "≈ ₹45 / ₹70 / ₹120 per sq ft"),
    ("wall_tile", "material", "Flooring", "Wall tiles (toilet / kitchen dado)", "m2", 430, 650, 1080, ""),
    ("tile_adhesive", "material", "Flooring", "Tile adhesive / grout", "m2", 40, 60, 90, ""),
    ("granite", "material", "Flooring", "Granite (kitchen top, steps)", "m2", 1300, 1950, 3200, ""),
    ("paint_int", "material", "Painting", "Interior paint system (putty + primer + 2 coats emulsion)", "m2", 60, 90, 140, ""),
    ("paint_ext", "material", "Painting", "Exterior paint system (primer + 2 coats)", "m2", 80, 120, 180, ""),
    ("enamel", "material", "Painting", "Enamel paint (doors, grills)", "m2", 70, 95, 130, ""),
    ("waterproof", "material", "Waterproofing", "Waterproofing (toilets, terrace)", "m2", 60, 100, 180, ""),
    # ---------------- materials: doors, windows ----------------
    ("door_main", "material", "Doors & Windows", "Main door with frame (complete)", "nos", 18000, 30000, 60000,
     "Basic: country wood · Standard: teak frame + panel · Premium: full teak / designer"),
    ("door_internal", "material", "Doors & Windows", "Internal flush door with frame", "nos", 8000, 12000, 20000, ""),
    ("door_toilet", "material", "Doors & Windows", "Toilet door (PVC / FRP) with frame", "nos", 4000, 6000, 10000, ""),
    ("window", "material", "Doors & Windows", "Windows (aluminium / UPVC with glass)", "m2", 3500, 6000, 9000, ""),
    ("grill", "material", "Doors & Windows", "MS window grills", "kg", 85, 95, 110, ""),
    ("hardware", "material", "Doors & Windows", "Door hardware set (hinges, locks, handles)", "nos", 800, 1500, 3500, ""),
    # ---------------- materials: services ----------------
    ("sanitary_set", "material", "Plumbing", "Sanitary set per toilet (EWC, basin, taps, shower)", "nos", 12000, 25000, 55000, ""),
    ("plumbing_toilet", "material", "Plumbing", "Plumbing pipes & fittings per toilet", "nos", 8000, 12000, 18000, ""),
    ("kitchen_plumb", "material", "Plumbing", "Kitchen sink + tap + piping", "nos", 5000, 9000, 18000, ""),
    ("oh_tank", "material", "Plumbing", "Overhead water tank", "litre", 7, 9, 11, ""),
    ("sump", "material", "Plumbing", "Underground sump (complete, per litre)", "litre", 9, 10, 12, "RCC / brick sump, lump rate per litre"),
    ("septic", "material", "Plumbing", "Septic tank + soak pit (complete)", "nos", 45000, 60000, 85000, ""),
    ("motor", "material", "Plumbing", "Water pump motor 1 HP + fittings", "nos", 8000, 12000, 18000, ""),
    ("elec_point", "material", "Electrical", "Electrical point (conduit, wire, switch, box)", "point", 600, 900, 1400, ""),
    ("elec_db", "material", "Electrical", "Distribution board + MCBs (per floor)", "nos", 6000, 10000, 18000, ""),
    ("earthing", "material", "Electrical", "Earthing pit", "nos", 4000, 6000, 9000, ""),
    ("eb_connection", "material", "Electrical", "EB service connection & meter board", "nos", 12000, 15000, 20000, ""),
    # ---------------- materials: external ----------------
    ("compound_wall", "material", "External Works", "Compound wall materials (1.5 m high, per running metre)", "rmt", 2600, 3000, 3600, "Foundation + brick + plaster + coping"),
    ("gate", "material", "External Works", "MS gate (fabricated, painted)", "nos", 25000, 40000, 75000, ""),
    ("rwh", "material", "External Works", "Rain water harvesting pit (complete)", "nos", 15000, 20000, 30000, "Mandatory in Tamil Nadu"),
    ("parking_floor", "material", "External Works", "Parking / sit-out paver or tiles", "m2", 450, 650, 1100, ""),

    # ---------------- labour (day wages, TN) ----------------
    ("mason", "labour", "Labour", "Mason (Kothanaar)", "day", 1100, 1100, 1100, ""),
    ("helper_m", "labour", "Labour", "Helper – male (Chithal)", "day", 800, 800, 800, ""),
    ("helper_f", "labour", "Labour", "Helper – female (Chithal)", "day", 700, 700, 700, ""),
    ("bar_bender", "labour", "Labour", "Bar bender", "day", 1000, 1000, 1000, ""),
    ("centring", "labour", "Labour", "Centring carpenter", "day", 1000, 1000, 1000, ""),
    ("carpenter", "labour", "Labour", "Carpenter (doors / windows)", "day", 1100, 1100, 1100, ""),
    ("plumber", "labour", "Labour", "Plumber", "day", 1100, 1100, 1100, ""),
    ("electrician", "labour", "Labour", "Electrician", "day", 1100, 1100, 1100, ""),
    ("tile_layer", "labour", "Labour", "Tile layer", "day", 1200, 1200, 1200, ""),
    ("painter", "labour", "Labour", "Painter", "day", 1000, 1000, 1000, ""),
    ("welder", "labour", "Labour", "Welder / fabricator", "day", 1000, 1000, 1000, ""),
    ("watchman", "labour", "Labour", "Watchman / curing", "day", 600, 600, 600, ""),

    # ---------------- equipment hire ----------------
    ("jcb", "equipment", "Equipment", "JCB excavator", "hour", 1200, 1200, 1200, ""),
    ("mixer", "equipment", "Equipment", "Concrete mixer (with operator)", "day", 1200, 1200, 1200, ""),
    ("vibrator", "equipment", "Equipment", "Needle vibrator", "day", 500, 500, 500, ""),
    ("tractor", "equipment", "Equipment", "Tractor / tipper (earth & debris)", "trip", 1500, 1500, 1500, ""),
    ("water_tanker", "equipment", "Equipment", "Water tanker (construction water)", "load", 700, 700, 700, ""),

    # ---------------- extras (percent or lump) ----------------
    ("transport_pct", "extra", "Extras", "Material transport & loading", "%", 2, 2, 2, "% of material cost"),
    ("water_eb_month", "extra", "Extras", "Temporary water + EB per month", "month", 3000, 3000, 3000, ""),
    ("contingency_pct", "extra", "Extras", "Contingency", "%", 3, 3, 3, "% of construction cost"),
]

DEFAULT_STATE = "Tamil Nadu"
