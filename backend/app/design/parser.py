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

    # bedrooms / rooms
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

    # toilets
    m = re.search(NUM + r"\s*(?:toilets?|bathrooms?|baths?|restrooms?)", t)
    if m:
        d["toilets"] = int(_num(m.group(1)) or 0)
        understood.append(f"{d['toilets']} toilet(s)")
    if "attached" in t:
        d["attached"] = True

    # extras
    if re.search(r"car\s*(parking|park)?|car\b", t):
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


def build_requirements(d: dict) -> dict:
    """Distribute rooms over floors with sensible defaults (all shown to the user, all editable)."""
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
