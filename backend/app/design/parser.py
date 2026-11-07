"""Turns a plain request ("30x40 east facing 2BHK, car parking, G+1, 30 ft road") into
structured requirements. Never guesses essentials: anything missing or ambiguous becomes a question.
Works for English / Tanglish; Tamil direction words are understood too.
"""
from __future__ import annotations

import math
import re

NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "single": 1, "double": 2,
             "oru": 1, "onnu": 1, "rendu": 2, "irandu": 2, "moonu": 3, "munu": 3, "naalu": 4, "nalu": 4,
             "anju": 5, "aaru": 6}
FACINGS = {
    "north-east": ["north east", "northeast", "north-east", "ne facing", "vadakku kizhakku"],
    "north-west": ["north west", "northwest", "north-west", "nw facing", "vadakku merku"],
    "south-east": ["south east", "southeast", "south-east", "se facing", "therku kizhakku"],
    "south-west": ["south west", "southwest", "south-west", "sw facing", "therku merku"],
    "east": ["east", "kizhakku", "கிழக்கு"], "west": ["west", "merku", "மேற்கு"],
    "north": ["north", "vadakku", "வடக்கு"], "south": ["south", "therku", "தெற்கு"],
}


def _num(s: str) -> float | None:
    s = s.strip().lower()
    if s in NUM_WORDS:
        return NUM_WORDS[s]
    try:
        return float(s)
    except ValueError:
        return None


NUM = r"(\d+(?:\.\d+)?|one|two|three|four|five|six|single|oru|onnu|rendu|irandu|moonu|munu|naalu|nalu|anju|aaru)"


def parse(text: str, defaults: dict | None = None) -> dict:
    """Return {"requirements": {...}, "questions": [...], "understood": [...]}."""
    d = dict(defaults or {})
    t = " " + (text or "").lower().replace("×", "x").replace("*", "x") + " "
    t = re.sub(r"\s+", " ", t)
    understood, questions = [], []

    # plot size
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:ft|feet|')?\s*(?:x|by)\s*(\d+(?:\.\d+)?)\s*(ft|feet|'|m|mtr|meter|metre|meters|metres)?", t)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        unit = m.group(3) or "ft"
        if unit.startswith("m") and unit not in ("ft",):
            a, b = a / 0.3048, b / 0.3048
            understood.append(f"Plot {m.group(1)} × {m.group(2)} m")
        else:
            understood.append(f"Plot {a:g} × {b:g} ft (first = road frontage)")
        d["plot_w_ft"], d["plot_d_ft"] = round(a, 2), round(b, 2)
    if not d.get("plot_w_ft") or not d.get("plot_d_ft"):
        questions.append("What is the plot size? (frontage × depth, e.g. 30 × 40 ft)")

    # facing
    for key, words in FACINGS.items():
        if any(re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", t) for w in words):
            d["facing"] = key
            understood.append(f"{key.title()} facing (road on the {key} side)")
            break
    if not d.get("facing"):
        questions.append("Which side is the road (plot facing)? East / West / North / South")

    # road width
    m = re.search(r"(\d+(?:\.\d+)?)\s*(ft|feet|'|m|mtr|meter|metre)s?\s*(?:wide\s*)?road", t) or \
        re.search(r"road\s*(?:width)?\s*(?:is|of|:)?\s*(\d+(?:\.\d+)?)\s*(ft|feet|'|m|mtr|meter|metre)?", t)
    if m:
        v = float(m.group(1))
        unit = (m.group(2) or "ft")
        road_m = v if unit.startswith("m") else v * 0.3048
        d["road_width_m"] = round(road_m, 2)
        understood.append(f"Road width {v:g} {'m' if unit.startswith('m') else 'ft'} ({road_m:.1f} m)")
    if not d.get("road_width_m"):
        questions.append("How wide is the road in front of the plot? (needed for the Tamil Nadu front setback)")

    # floors
    floors = None
    m = re.search(r"(?:g|ground)\s*\+\s*(\d)", t)
    if m:
        floors = int(m.group(1)) + 1
    elif re.search(r"\bduplex\b", t):
        floors = 2
    elif re.search(r"(ground floor only|single floor|single storey|single story|only ground|\bg only\b)", t):
        floors = 1
    m2 = re.search(r"stilt\s*\+\s*(\d)", t)
    if m2:
        floors = int(m2.group(1)) + 1
        d["stilt"] = True
    elif "stilt" in t:
        d["stilt"] = True
    if floors:
        d["floors"] = floors
        understood.append(f"{'Stilt' if d.get('stilt') else 'G'}{'' if floors == 1 else f'+{floors - 1}'} ({floors} level{'s' if floors > 1 else ''})")
    if not d.get("floors"):
        questions.append("How many floors? (G only, G+1, G+2 …)")

    # 1.19: "ground floor … first floor …" → rooms / houses per floor
    fw = floorwise(t, d, understood, questions)
    if fw:
        questions[:] = [q for q in questions if not q.startswith("How many floors")]
    # bedrooms / rooms
    if not fw:
        _bedrooms(t, d, understood, questions)

    # toilets
    m = None if fw else re.search(NUM + r"\s*(?:toilets?|bathrooms?|baths?|restrooms?)", t)
    if m:
        d["toilets"] = int(_num(m.group(1)) or 0)
        understood.append(f"{d['toilets']} toilet(s)")
    if "attached" in t:
        d["attached"] = True

    # extras
    if not fw and re.search(r"car\s*(parking|park)?|car\b", t):
        d["parking_car"] = True
        understood.append("Car parking")
    if re.search(r"bike|two.?wheeler|scooter", t):
        d["parking_bike"] = True
        understood.append("Two-wheeler parking")
    if re.search(r"pooja|puja|prayer|பூஜை", t):
        d["pooja"] = True
        understood.append("Pooja room")
    if "dining" in t:
        d["dining"] = True
    if "corner" in t:
        d["corner"] = True
        understood.append("Corner plot")
    if re.search(r"each floor|per floor|every floor|ovvoru floor", t):
        d["same_each_floor"] = True
        understood.append("Same rooms on each floor")

    req = build_requirements(d) if not questions else None
    return {"requirements": req, "partial": d, "questions": questions, "understood": understood}


def _bedrooms(t: str, d: dict, understood: list, questions: list):
    bed = None
    m = re.search(NUM + r"\s*bhk", t)
    if m:
        bed = _num(m.group(1))
        d.setdefault("hall", True)
        d.setdefault("kitchen", True)
    m = re.search(NUM + r"\s*(?:bed\s*rooms?|bedrooms?|beds?\b|br\b|படுக்கை)", t)
    if m:
        bed = _num(m.group(1))
    if bed is not None:
        d["bedrooms"] = int(bed)
        understood.append(f"{int(bed)} bedroom{'s' if bed != 1 else ''}")
    else:
        m = re.search(NUM + r"\s*rooms?", t)
        if m:
            n = int(_num(m.group(1)) or 0)
            questions.append(f"You said {n} rooms – do you mean {n} BEDROOMS, or {n} rooms in total "
                             f"(bedrooms + hall + kitchen)?")
        elif not d.get("bedrooms"):
            questions.append("How many bedrooms?")
    return bed


def build_requirements(d: dict) -> dict:
    """Distribute rooms over floors with sensible defaults (all shown to the user, all editable)."""
    if d.get("floor_specs"):  # 1.19 floor-by-floor request (houses per floor)
        levels = levels_from_specs(d)
        return {
            "plot_w_ft": d.get("plot_w_ft"), "plot_d_ft": d.get("plot_d_ft"), "facing": d.get("facing"),
            "road_width_m": d.get("road_width_m"), "area_type": d.get("area_type", "other"),
            "corner": bool(d.get("corner")), "side_road_width_m": d.get("side_road_width_m"),
            "floor_height_ft": float(d.get("floor_height_ft") or 10), "stilt": bool(d.get("stilt")),
            "staircase": len(levels) > 1, "levels": levels, "floor_specs": d["floor_specs"],
            "assumptions": list(d.get("_notes", [])) + ["Toilets per house: 1 BHK = 1 common, 2 BHK = 1 attached + 1 common, "
                                                        "3 BHK = 2 attached + 1 common – change them in the table."],
        }
    n = int(d.get("floors") or 1)
    stilt = bool(d.get("stilt"))
    beds = int(d.get("bedrooms") or 0)
    toilets = d.get("toilets")
    if toilets is None:
        toilets = max(1, beds)  # one per bedroom by default (shown to user as an assumption)
    toilets = int(toilets)
    room_levels = n - (1 if stilt else 0)
    same = bool(d.get("same_each_floor"))
    levels = []
    if stilt:
        levels.append({"name": "Stilt / Parking", "stilt": True, "bedrooms": 0, "attached_toilets": 0,
                       "common_toilets": 0, "kitchen": False, "hall": False, "dining": False, "pooja": False,
                       "parking_car": True, "parking_bike": True, "lounge": False})
    if same:
        bed_split = [beds] * room_levels
        toi_split = [toilets] * room_levels
    else:
        first = math.ceil(beds / room_levels) if beds else 0
        bed_split = [first] + [0] * (room_levels - 1)
        rest = beds - first
        for i in range(1, room_levels):
            take = math.ceil(rest / (room_levels - i)) if rest > 0 else 0
            bed_split[i] = take
            rest -= take
        # every floor with bedrooms gets at least one toilet; the rest follow the bedrooms
        toi_split = [1 if bed_split[i] or (i == 0) else 0 for i in range(room_levels)]
        remaining = max(0, toilets - sum(toi_split))
        if toilets < sum(toi_split):
            d.setdefault("_notes", []).append(
                f"Toilets increased to {sum(toi_split)} – one on every floor that has rooms.")
        while remaining > 0:
            gaps = [bed_split[i] - toi_split[i] for i in range(room_levels)]
            k = max(range(room_levels), key=lambda i: gaps[i])
            if gaps[k] <= 0:
                k = 0
            toi_split[k] += 1
            remaining -= 1
    names = ["Ground Floor", "First Floor", "Second Floor", "Third Floor", "Fourth Floor", "Fifth Floor"]
    for i in range(room_levels):
        b, tt = bed_split[i], toi_split[i]
        attached = min(b, tt if (d.get("attached", True)) else 0)
        common = tt - attached
        if b > 0 and attached == tt and tt > 0 and i == 0 and not same and b > 1:
            # keep one common toilet on the ground floor for visitors when possible
            attached, common = tt - 1, 1
        is_main = (i == 0) or same
        levels.append({
            "name": names[i + (1 if stilt else 0)] if i + (1 if stilt else 0) < len(names) else f"Level {i + 1}",
            "stilt": False, "bedrooms": b, "attached_toilets": attached, "common_toilets": common,
            "kitchen": bool(is_main and d.get("kitchen", True)), "hall": bool(is_main and d.get("hall", True)),
            "dining": bool(is_main and d.get("dining", True)), "pooja": bool(i == 0 and d.get("pooja")),
            "parking_car": bool(i == 0 and not stilt and d.get("parking_car")),
            "parking_bike": bool(i == 0 and not stilt and d.get("parking_bike")),
            "lounge": not is_main,
        })
    return {
        "plot_w_ft": d.get("plot_w_ft"), "plot_d_ft": d.get("plot_d_ft"), "facing": d.get("facing"),
        "road_width_m": d.get("road_width_m"), "area_type": d.get("area_type", "other"),
        "corner": bool(d.get("corner")), "side_road_width_m": d.get("side_road_width_m"),
        "floor_height_ft": float(d.get("floor_height_ft") or 10), "stilt": stilt,
        "staircase": n > 1 or bool(d.get("staircase", True)), "levels": levels,
        "assumptions": list(d.get("_notes", [])),
    }


# ---------------------------------------------------------------- 1.19 floor-wise requests + several houses per floor
FLOOR_MARKS = [  # (level index, regex) – -1 = stilt
    (-1, r"\bstilt\b|ஸ்டில்ட்"),
    (0, r"ground\s*floor|\bg\.?\s*f\b|\bground\b|keezh?a\s*(?:floor|thalam|veedu)?|kizha\s*(?:floor)?|கீழ்\s*(?:தளம்|வீடு)?|தரை\s*தளம்|கிரவுண்ட்\s*(?:ஃப்ளோர்|ப்ளோர்)?"),
    (1, r"first\s*floor|1st\s*floor|\bf\.?\s*f\b|\bfirst\b|1st\b|mudhal\s*(?:maadi|floor|thalam)|muthal\s*(?:maadi|floor)|முதல்\s*(?:தளம்|மாடி)|ஃபர்ஸ்ட்\s*(?:ஃப்ளோர்|ப்ளோர்)?|பர்ஸ்ட்\s*(?:ஃப்ளோர்|ப்ளோர்)?"),
    (2, r"second\s*floor|2nd\s*floor|\bs\.?\s*f\b|\bsecond\b|2nd\b|rendaam\s*(?:maadi|floor)|irandaam\s*(?:maadi|floor)|இரண்டாம்\s*(?:தளம்|மாடி)|செகண்ட்\s*(?:ஃப்ளோர்|ப்ளோர்)?"),
    (3, r"third\s*floor|3rd\s*floor|\bthird\b|3rd\b|moonaam\s*(?:maadi|floor)|மூன்றாம்\s*(?:தளம்|மாடி)|தேர்ட்\s*(?:ஃப்ளோர்|ப்ளோர்)?"),
]
RENT = r"rent|rental|tenant|lease|vaadagai|vadagai|வாடகை|ரெண்டல|ரென்ட|டெனன்ட|வாடகைக்கு"
OWN = r"owner|own\b|self|sontha|சொந்த|family stay|we stay|owner stay|ஓனர|சொந்தம"
COUNT = r"(\d+|one|two|three|four|five|oru|onnu|rendu|irandu|moonu|munu|naalu|nalu|anju)"


def _floor_segments(t: str) -> list[tuple[int, str]]:
    """Split the request at floor words: [(level index, text about that floor)] – only when 2+ floors are described."""
    hits = []
    for idx, rx in FLOOR_MARKS:
        for m in re.finditer(rx, t):
            hits.append((m.start(), m.end(), idx))
    hits.sort()
    keep, last_end = [], -1
    for s, e, idx in hits:  # drop overlaps ("first floor" vs "first")
        if s >= last_end:
            keep.append((s, e, idx))
            last_end = e
    if len({idx for *_, idx in keep}) < 2:
        return []
    segs = []
    for k, (s, e, idx) in enumerate(keep):
        end = keep[k + 1][0] if k + 1 < len(keep) else len(t)
        segs.append((idx, t[e:end]))
    # the same floor mentioned twice → join its parts
    out: dict[int, str] = {}
    for idx, txt in segs:
        out[idx] = (out.get(idx, "") + " " + txt).strip()
    return sorted(out.items())


def _toilets_for(bhk: int) -> tuple[int, int]:
    """(attached, common) toilets usual for a house of this size (shown to the user, editable)."""
    return {0: (0, 1), 1: (0, 1), 2: (1, 1), 3: (2, 1)}.get(bhk, (bhk - 1, 1))


def _floor_spec(seg: str) -> dict:
    """Rooms / houses asked for on one floor."""
    sp: dict = {}
    units = []
    ms = list(re.finditer(r"(\d)\s*-?\s*bhk|studio", seg))
    SEP = r"(?:\band\b|,|;|\+|&|\bplus\b|\bthen\b|\bum\b)"
    parts_before, parts_after = [], []
    for k, m in enumerate(ms):  # words between two houses: before the last "and / ," → the earlier house, after it → the later one
        lo = ms[k - 1].end() if k else 0
        between = seg[lo:m.start()]
        if k:
            cut = list(re.finditer(SEP, between))
            if cut:
                parts_after.append(between[:cut[-1].start()])
                between = between[cut[-1].end():]
            else:
                parts_after.append("")
        parts_before.append(between)
    if ms:
        parts_after.append(seg[ms[-1].end():])
    for k, m in enumerate(ms):
        bhk = 0 if m.group(0) == "studio" else int(m.group(1))
        before, after = parts_before[k][-40:], parts_after[k]
        cm = re.search(COUNT + r"\s*(?:nos?\.?|x|×)?\s*(?:" + RENT + r"|" + OWN + r"|separate|independent|portion|)?\s*(?:units?\s*(?:of)?\s*)?$", before)
        n = int(_num(cm.group(1)) or 1) if cm else 1
        m2 = re.match(r"\s*(?:units?|houses?|flats?|portions?|veedu)?\s*(?:x|×)\s*" + COUNT, after)
        if m2:
            n = int(_num(m2.group(1)) or 1)
        role = lambda x: "rental" if re.search(RENT, x) else ("owner" if re.search(OWN, x) else "")
        use = role(before) or role(after[:40])
        n = max(1, min(n, 6))
        for _ in range(n):
            units.append({"bhk": bhk, "use": use})
    m = re.search(COUNT + r"\s*(?:rental|separate|independent)?\s*(?:units|houses|flats|portions|veedu)", seg)
    if m and not units:
        units = [{"bhk": 1, "use": "rental" if re.search(RENT, seg) else ""} for _ in range(int(_num(m.group(1)) or 1))]
        sp["_bhk_missing"] = True
    if len(units) >= 2:
        sp["units"] = units
    elif units:
        u = units[0]
        sp["bedrooms"] = u["bhk"]
        sp["use"] = u["use"]
        sp["home"] = True
    else:
        m = re.search(NUM + r"\s*(?:bed\s*rooms?|bedrooms?|beds?\b|படுக்கை)", seg)
        if m:
            sp["bedrooms"] = int(_num(m.group(1)) or 0)
    m = re.search(NUM + r"\s*(?:toilets?|bathrooms?|baths?)", seg)
    if m:
        sp["toilets"] = int(_num(m.group(1)) or 0)
    if re.search(r"car\s*(?:parking|park)?|\bcar\b|கார்", seg):
        sp["parking_car"] = True
    if re.search(r"bike|two.?wheeler|scooter", seg):
        sp["parking_bike"] = True
    if re.search(r"pooja|puja|prayer|பூஜை", seg):
        sp["pooja"] = True
    if re.search(r"kitchen|samayal|சமையல்", seg):
        sp["kitchen"] = True
    if re.search(r"hall\b|living", seg):
        sp["hall"] = True
    if re.search(r"dining", seg):
        sp["dining"] = True
    if re.search(r"stair\w*\s*(?:inside|internal|ulla)|(?:inside|internal|ullaye|ulle)\s*\w*\s*stair|உள்", seg):
        sp["stair_inside"] = True
    if re.search(r"same as (?:the )?ground|same as below|keezha maadhiri|ground floor maadhiri", seg):
        sp["same_as"] = 0
    if re.search(r"open terrace|terrace only|mottai maadi", seg):
        sp["terrace_only"] = True
    return sp


def floorwise(t: str, d: dict, understood: list, questions: list) -> bool:
    """Fill d["floor_specs"] from a floor-by-floor request. True when the request was floor-wise."""
    segs = _floor_segments(t)
    if not segs:
        return False
    specs = {}
    for idx, seg in segs:
        sp = _floor_spec(seg)
        if "same_as" in sp and sp["same_as"] in specs:
            sp = {**specs[sp["same_as"]], **{k: v for k, v in sp.items() if k != "same_as"}}
            sp.pop("parking_car", None)
        specs[idx] = sp
    if -1 in specs or d.get("stilt"):
        d["stilt"] = True
        if 0 not in specs and any(i >= 1 for i in specs):  # Stilt + 2: the floor above the stilt is called "first floor"
            specs = {(i - 1 if i >= 1 else i): v for i, v in specs.items()}
    ids = sorted(i for i in specs if i >= 0)
    top = max(ids) if ids else 0
    floors = top + 1 + (1 if d.get("stilt") else 0)
    if d.get("floors") and int(d["floors"]) > floors:
        names = ["Ground", "First", "Second", "Third", "Fourth"]
        for i in range(top + 1, int(d["floors"]) - (1 if d.get("stilt") else 0)):
            questions.append(f"What should be on the {names[i] if i < len(names) else f'level {i}'} floor? "
                             f"(rooms / houses, or 'open terrace')")
    else:
        d["floors"] = floors
    for i in range(0, top + 1):
        if i not in specs:
            names = ["Ground", "First", "Second", "Third", "Fourth"]
            questions.append(f"What should be on the {names[i]} floor? (rooms / houses)")
    for idx, sp in specs.items():
        if sp.get("_bhk_missing"):
            questions.append(f"{['Stilt', 'Ground', 'First', 'Second', 'Third', 'Fourth'][idx + 1 + (1 if d.get('stilt') and idx >= 0 else 0)]} floor: how many bedrooms in each house "
                             f"(1 BHK / 2 BHK …)?")
        if idx >= 0 and not sp.get("units") and not sp.get("bedrooms") and not sp.get("terrace_only") and not sp.get("parking_car"):
            questions.append(f"{['Ground', 'First', 'Second', 'Third', 'Fourth'][idx]} floor: which rooms / how many bedrooms?")
    d["floor_specs"] = {str(k): v for k, v in specs.items()}
    d["bedrooms"] = sum(int(sp.get("bedrooms") or 0) + sum(u["bhk"] for u in sp.get("units", [])) for sp in specs.values())
    for idx in sorted(specs):
        sp = specs[idx]
        nm = "Stilt" if idx < 0 else ["Ground floor", "First floor", "Second floor", "Third floor", "Fourth floor"][idx + (1 if d.get("stilt") else 0)]
        bits = []
        if sp.get("parking_car"):
            bits.append("car parking")
        if sp.get("stair_inside"):
            bits.append("staircase inside")
        if sp.get("units"):
            bits += [f"{u['bhk']} BHK{' ' + u['use'] if u['use'] else ''}" for u in sp["units"]]
            bits.append(f"({len(sp['units'])} separate houses, each with its own main door)")
        elif sp.get("bedrooms"):
            bits.append(f"{sp['bedrooms']} BHK{' ' + sp['use'] if sp.get('use') else ''}" if sp.get("home") else f"{sp['bedrooms']} bedrooms")
        if sp.get("pooja"):
            bits.append("pooja")
        understood.append(f"{nm}: {', '.join(bits) or '—'}")
    return True


def unit_rooms(u: dict, label: str) -> dict:
    """Rooms of one house on a shared floor."""
    bhk = int(u.get("bhk") or u.get("bedrooms") or 0)
    att, com = _toilets_for(bhk)
    if u.get("attached_toilets") is not None:
        att, com = int(u["attached_toilets"]), int(u.get("common_toilets") or 0)
    return {"label": label, "use": u.get("use") or "", "bhk": bhk, "bedrooms": bhk, "attached_toilets": min(att, bhk),
            "common_toilets": com, "kitchen": True, "hall": True, "dining": bhk >= 2 and not u.get("no_dining"),
            "pooja": bool(u.get("pooja"))}


def levels_from_specs(d: dict) -> list[dict]:
    specs = {int(k): v for k, v in (d.get("floor_specs") or {}).items()}
    stilt = bool(d.get("stilt"))
    names = ["Ground Floor", "First Floor", "Second Floor", "Third Floor", "Fourth Floor", "Fifth Floor"]
    levels = []
    if stilt:
        sp = specs.get(-1, {})
        levels.append({"name": "Stilt / Parking", "stilt": True, "bedrooms": 0, "attached_toilets": 0, "common_toilets": 0,
                       "kitchen": False, "hall": False, "dining": False, "pooja": False, "parking_car": True,
                       "parking_bike": bool(sp.get("parking_bike", True)), "lounge": False})
    top = max([i for i in specs if i >= 0] or [0])
    first_home = True
    for i in range(0, top + 1):
        sp = specs.get(i, {})
        lv = {"name": names[i + (1 if stilt else 0)] if i + (1 if stilt else 0) < len(names) else f"Level {i + 1}",
              "stilt": False, "bedrooms": 0, "attached_toilets": 0, "common_toilets": 0, "kitchen": False, "hall": False,
              "dining": False, "pooja": bool(sp.get("pooja")), "parking_car": bool(sp.get("parking_car") and i == 0 and not stilt),
              "parking_bike": bool(sp.get("parking_bike") and i == 0 and not stilt), "lounge": False}
        if sp.get("units"):
            letters = "ABCDEF"
            lv["units"] = [unit_rooms(u, letters[k]) for k, u in enumerate(sp["units"])]
            lv["bedrooms"] = sum(u["bedrooms"] for u in lv["units"])
            lv["pooja"] = False
        elif sp.get("terrace_only"):
            lv["lounge"] = True
        else:
            b = int(sp.get("bedrooms") or 0)
            att, com = _toilets_for(b)
            if sp.get("toilets") is not None:
                t_ = int(sp["toilets"])
                att, com = min(b, max(0, t_ - 1)) if t_ > 1 else 0, (1 if t_ >= 1 else 0) if t_ <= b else t_ - min(b, t_ - 1)
            home = bool(sp.get("home") or sp.get("kitchen") or first_home)
            lv.update({"bedrooms": b, "attached_toilets": att, "common_toilets": com, "kitchen": home, "hall": home,
                       "dining": home and (b >= 2 or bool(sp.get("dining"))), "lounge": not home})
            if sp.get("use"):
                lv["use"] = sp["use"]
            if home:
                first_home = False
        levels.append(lv)
    return levels


def floor_line(lv: dict) -> str:
    """1.19 One readable line per floor for the confirm step."""
    if lv.get("stilt"):
        return f"{lv['name']}: parking (stilt)"
    if lv.get("units"):
        hs = [f"House {u['label']} {u['bhk']} BHK" + (f" ({u['use']})" if u.get("use") else "") for u in lv["units"]]
        return f"{lv['name']}: {len(hs)} separate houses – " + ", ".join(hs)
    bits = [f"{lv.get('bedrooms', 0)} bedroom(s)"]
    t = (lv.get("attached_toilets") or 0) + (lv.get("common_toilets") or 0)
    if t:
        bits.append(f"{t} toilet(s)")
    for k, n in (("hall", "hall"), ("kitchen", "kitchen"), ("dining", "dining"), ("pooja", "pooja"), ("parking_car", "car parking")):
        if lv.get(k):
            bits.append(n)
    return f"{lv['name']}: " + ", ".join(bits)
