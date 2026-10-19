"""Vastu check of a plan – traditional room-direction guidance, reported neutrally ("rules matched").

Directions come from the plan's compass (from the facing, or the north arrow the user confirmed).
Each room's zone = direction of its centre from the building centre (8 directions + Centre / Brahmasthan),
measured on the building's own proportions. Results are guidance, not engineering rules.
"""
from __future__ import annotations

import math

ZONES = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
ZONE_NAME = {"N": "North", "NE": "North-East", "E": "East", "SE": "South-East", "S": "South", "SW": "South-West",
             "W": "West", "NW": "North-West", "C": "Centre (Brahmasthan)"}
SIDES = {"North": {"NW", "N", "NE"}, "East": {"NE", "E", "SE"}, "South": {"SE", "S", "SW"}, "West": {"SW", "W", "NW"}}

# rule: (key, title, room types, good zones, acceptable zones, avoid zones, why)
RULES = [
    ("kitchen", "Kitchen", ["kitchen"], {"SE"}, {"NW", "E", "S"}, {"NE", "SW", "N", "C"},
     "Fire element – South-East (Agni) is preferred, North-West is the next choice."),
    ("master", "Master Bedroom", ["master"], {"SW"}, {"S", "W"}, {"NE", "SE", "C"},
     "South-West (Nairutya) gives stability to the head of the family."),
    ("bedroom", "Bedrooms", ["bedroom"], {"S", "W", "NW", "SW"}, {"N", "E"}, {"NE", "SE", "C"},
     "Other bedrooms suit West, South and North-West; avoid North-East and South-East."),
    ("pooja", "Pooja Room", ["pooja"], {"NE", "E", "N"}, {"C", "W"}, {"S", "SW", "SE", "NW"},
     "North-East (Eesanya) is the most sacred zone; East or North also suit."),
    ("toilet", "Toilets", ["toilet", "common_toilet"], {"NW", "W", "S"}, {"SE", "N", "E"}, {"NE", "SW", "C"},
     "Toilets suit North-West / West / South; never North-East or the centre."),
    ("stair", "Staircase", ["stair"], {"S", "W", "SW"}, {"NW", "SE"}, {"NE", "C", "N", "E"},
     "Heavy staircase in South / West / South-West; keep North-East and the centre free."),
    ("hall", "Living Room", ["hall", "lounge"], {"N", "NE", "E", "NW"}, {"W", "S", "C"}, {"SW", "SE"},
     "Living rooms suit North, East or North-East."),
    ("dining", "Dining", ["dining"], {"W", "E"}, {"N", "S", "C", "NW", "SE"}, {"NE", "SW"},
     "Dining suits West (or East), close to the kitchen."),
    ("parking", "Parking", ["parking"], {"NW", "SE"}, {"N", "E", "S", "W", "NE"}, {"SW"},
     "Vehicles suit North-West or South-East; keep North-East open (light vehicles only)."),
]
ENTRANCE = ("entrance", "Main Entrance", {"N", "NE", "E"}, {"NW", "SE", "W", "S"}, {"SW"},
            "Entrance in North, East or North-East is preferred; South-West is avoided.")
TIPS = [
    "Keep the North-East corner light, clean and open (no heavy storage, toilet or staircase there).",
    "Place the overhead water tank over the South-West part of the roof.",
    "Sump / borewell suits the North-East of the plot; septic tank suits North-West.",
    "Let the floor and the plot slope gently towards North / East / North-East for rainwater.",
    "Keep the centre of the house (Brahmasthan) open – no pillars, toilets or staircase.",
    "Prefer more windows and openings on the North and East walls for light and air.",
]


def north_of(comp: dict) -> float:
    """Clockwise angle of north from screen-up, from the compass vectors."""
    return round((math.degrees(math.atan2(comp["right"][1], comp["up"][1])) + 360) % 360, 1)


def set_north(plan: dict, north_deg: float) -> dict:
    """Override the plan's north arrow (degrees clockwise from screen-up)."""
    from ..drawing.convert import compass_from_north, facing_from_compass
    plan["compass"] = compass_from_north(float(north_deg) % 360)
    plan["north_deg"] = round(float(north_deg) % 360, 1)
    plan["facing"] = facing_from_compass(plan["compass"])
    return plan


def bearing_of(comp: dict, dx: float, dy: float) -> float:
    """Screen vector (dx right, dy up) → compass bearing (0 = North, 90 = East)."""
    e = dx * comp["right"][0] + dy * comp["up"][0]
    n = dx * comp["right"][1] + dy * comp["up"][1]
    return (math.degrees(math.atan2(e, n)) + 360) % 360


def zone_of(comp: dict, bw: float, bd: float, cx: float, cy: float) -> str:
    xn = (cx - bw / 2) / (bw / 2 or 1)
    yn = (cy - bd / 2) / (bd / 2 or 1)
    if abs(xn) < 1 / 3 and abs(yn) < 1 / 3:
        return "C"
    b = bearing_of(comp, xn, yn)
    return ZONES[int(((b + 22.5) % 360) // 45)]


def _room_kind(r: dict, master_ids: set) -> str:
    if r["type"] == "bedroom" and r["id"] in master_ids:
        return "master"
    return r["type"]


def masters(level: dict) -> set:
    beds = [r for r in level["rooms"] if r["type"] == "bedroom"]
    named = {r["id"] for r in beds if "master" in r["name"].lower() or "m.bed" in r["name"].lower()}
    if named:
        return named
    if beds:
        return {max(beds, key=lambda r: r["w"] * r["d"])["id"]}
    return set()


def analyse(plan: dict) -> dict:
    comp = plan["compass"]
    bw, bd = plan["building"]["w"], plan["building"]["d"]
    rooms_out, checks = [], []
    zone_rooms: dict[str, list[str]] = {}
    master_done = False
    for li, lv in enumerate(plan["levels"]):
        mids = masters(lv) if not master_done else set()
        if mids:
            master_done = True
        for r in lv["rooms"]:
            z = zone_of(comp, bw, bd, r["x"] + r["w"] / 2, r["y"] + r["d"] / 2)
            kind = _room_kind(r, mids)
            rooms_out.append({"id": r["id"], "level": li, "level_name": lv["name"], "name": r["name"], "type": r["type"],
                              "kind": kind, "zone": z, "zone_name": ZONE_NAME[z]})
            zone_rooms.setdefault(z, []).append(r["name"] if li == 0 else f"{r['name']} ({lv['name']})")
            for key, title, types, good, ok, bad, why in RULES:
                if kind not in types:
                    continue
                if z in good:
                    status = "matched"
                elif z in bad:
                    status = "not_matched"
                else:
                    status = "partly"
                best = " / ".join(ZONE_NAME[g] for g in sorted(good, key=ZONES.index))
                msg = ({"matched": f"{ZONE_NAME[z]} – good placement",
                        "partly": f"{ZONE_NAME[z]} – acceptable; {best} is better",
                        "not_matched": f"{ZONE_NAME[z]} – avoid; {best} preferred"}[status])
                checks.append({"rule": key, "title": title, "room": r["name"], "room_id": r["id"], "level": li,
                               "level_name": lv["name"], "zone": z, "status": status, "message": msg, "why": why,
                               "suggest_zones": sorted(good, key=ZONES.index)})
    # entrance – the main door on the ground floor
    for li, lv in enumerate(plan["levels"]):
        doors = [o for o in lv.get("openings", []) if o["type"] == "main_door"]
        if doors:
            o = doors[0]
            cx, cy = (o["x1"] + o["x2"]) / 2, (o["y1"] + o["y2"]) / 2
            room = next((r for r in lv["rooms"] if r["id"] == o["room"]), None)
            rcx = room["x"] + room["w"] / 2 if room else bw / 2
            rcy = room["y"] + room["d"] / 2 if room else bd / 2
            # the door faces away from the room it opens into
            if o["y1"] == o["y2"]:
                nx, ny = 0.0, (-1.0 if rcy > cy else 1.0)
            else:
                nx, ny = (-1.0 if rcx > cx else 1.0), 0.0
            b = bearing_of(comp, nx, ny)
            z = ZONES[int(((b + 22.5) % 360) // 45)]
            key, title, good, ok, bad, why = ENTRANCE
            status = "matched" if z in good else "not_matched" if z in bad else "partly"
            msg = {"matched": f"Faces {ZONE_NAME[z]} – auspicious",
                   "partly": f"Faces {ZONE_NAME[z]} – acceptable (choose the right pada)",
                   "not_matched": f"Faces {ZONE_NAME[z]} – avoid; North/East preferred"}[status]
            checks.insert(0, {"rule": key, "title": title, "room": "Main door", "room_id": o["room"], "level": li,
                              "level_name": lv["name"], "zone": z, "status": status, "message": msg, "why": why,
                              "suggest_zones": ["N", "NE", "E"]})
            break
    # zone rules (whole building, ground floor)
    g0 = [r for r in rooms_out if r["level"] == 0]
    centre_bad = [r["name"] for r in g0 if r["zone"] == "C" and r["type"] in ("toilet", "common_toilet", "stair", "kitchen")]
    checks.append({"rule": "brahmasthan", "title": "Centre (Brahmasthan)", "room": ", ".join(centre_bad) or "—",
                   "room_id": None, "level": 0, "level_name": plan["levels"][0]["name"], "zone": "C",
                   "status": "not_matched" if centre_bad else "matched",
                   "message": (f"{', '.join(centre_bad)} in the centre – keep it open" if centre_bad
                               else "Centre is free of toilet / staircase / kitchen"),
                   "why": "The Brahmasthan should stay open and light.", "suggest_zones": []})
    ne_bad = [r["name"] for r in g0 if r["zone"] == "NE" and r["type"] in ("toilet", "common_toilet", "stair", "kitchen", "store")]
    checks.append({"rule": "ne_light", "title": "North-East kept light", "room": ", ".join(ne_bad) or "—", "room_id": None,
                   "level": 0, "level_name": plan["levels"][0]["name"], "zone": "NE",
                   "status": "not_matched" if ne_bad else "matched",
                   "message": (f"{', '.join(ne_bad)} in North-East – move if possible" if ne_bad
                               else "No toilet / staircase / kitchen / store in North-East"),
                   "why": "North-East (Eesanya) should be the lightest, cleanest part.", "suggest_zones": []})
    sw = [r for r in g0 if r["zone"] == "SW"]
    sw_heavy = [r["name"] for r in sw if r["kind"] in ("master", "bedroom", "stair", "store")]
    sw_bad = [r["name"] for r in sw if r["type"] in ("toilet", "common_toilet", "kitchen", "terrace", "sitout", "parking")]
    checks.append({"rule": "sw_heavy", "title": "South-West kept heavy", "room": ", ".join(sw_heavy or sw_bad) or "—",
                   "room_id": None, "level": 0, "level_name": plan["levels"][0]["name"], "zone": "SW",
                   "status": "not_matched" if sw_bad and not sw_heavy else "matched" if sw_heavy else "partly",
                   "message": (f"{', '.join(sw_heavy)} in South-West – good" if sw_heavy
                               else f"{', '.join(sw_bad)} in South-West – better a bedroom or staircase" if sw_bad
                               else "South-West has no heavy room"),
                   "why": "South-West should carry the heaviest rooms.", "suggest_zones": []})
    checks.append({"rule": "shape", "title": "Plot & building shape", "room": "—", "room_id": None, "level": 0,
                   "level_name": "", "zone": "", "status": "matched",
                   "message": "Rectangular plot and building – good",
                   "why": "Square / rectangular plots are preferred.", "suggest_zones": []})

    matched = sum(1 for c in checks if c["status"] == "matched")
    partly = sum(1 for c in checks if c["status"] == "partly")
    total = len(checks)
    # direction overview
    overview = {}
    for side, zones in SIDES.items():
        cs = [c for c in checks if c["zone"] in zones and c["rule"] not in ("shape",)]
        bad = sum(1 for c in cs if c["status"] == "not_matched")
        good = sum(1 for c in cs if c["status"] == "matched")
        if bad and bad >= good:
            st = "Needs Attention"
        elif bad or any(c["status"] == "partly" for c in cs):
            st = "Good"
        else:
            st = "Excellent"
        overview[side] = {"status": st, "matched": good, "not_matched": bad,
                          "rooms": [n for z in zones for n in zone_rooms.get(z, [])][:8]}
    # suggestions
    suggestions = []
    for c in checks:
        if c["status"] == "not_matched":
            if c["suggest_zones"]:
                suggestions.append(f"{c['title']}: move {c['room']} ({c['level_name']}) towards "
                                   f"{' / '.join(ZONE_NAME[z] for z in c['suggest_zones'])} – now {ZONE_NAME.get(c['zone'], c['zone'])}.")
            else:
                suggestions.append(f"{c['title']}: {c['message']}.")
    for c in checks:
        if c["status"] == "partly" and c["suggest_zones"]:
            suggestions.append(f"{c['title']}: {c['room']} is acceptable in {ZONE_NAME.get(c['zone'], c['zone'])}; "
                               f"{' / '.join(ZONE_NAME[z] for z in c['suggest_zones'])} is better if you can.")
    label = ("Most rules matched" if matched >= total * 0.75 else
             "Many rules matched – some improvements possible" if matched >= total * 0.5 else
             "Several rules not matched – see suggestions")
    return {"checks": checks, "rooms": rooms_out, "overview": overview, "zones": {z: zone_rooms.get(z, []) for z in ZONES + ["C"]},
            "summary": {"matched": matched, "partly": partly, "not_matched": total - matched - partly, "total": total,
                        "label": label},
            "suggestions": suggestions, "tips": TIPS, "north_deg": plan.get("north_deg", north_of(comp)), "facing": plan.get("facing"),
            "note": "Vastu guidance is traditional advice, not a building rule – structural safety and TNCDBR come first."}


# ---------------------------------------------------------------- apply suggestions (designs only)
MOVABLE = {"kitchen", "bedroom", "pooja", "dining", "common_toilet", "toilet", "store", "utility", "hall", "lounge",
           "passage", "stair"}
MIN = {"bedroom": (9, 80), "kitchen": (6.5, 50), "pooja": (3.5, 12), "dining": (7, 56), "common_toilet": (4, 24),
       "toilet": (4, 24), "store": (3, 12), "utility": (3, 12), "hall": (9, 90), "lounge": (8, 72), "passage": (3, 9),
       "stair": (7, 70)}


def _score(res: dict) -> float:
    return sum({"matched": 1, "partly": 0.4, "not_matched": -1}[c["status"]] for c in res["checks"])


def _fits(r: dict, w: float, d: float) -> bool:
    side, area = MIN.get(r["type"], (3, 9))
    return min(w, d) >= side - 0.01 and w * d >= area - 0.5


def improve(plan: dict, max_steps: int = 6) -> dict:
    """Swap whole rooms (same floor, no attached toilet / dress) when it improves the Vastu result."""
    import copy

    from ..design.geometry import add_openings
    p = copy.deepcopy(plan)
    before = analyse(p)
    base = _score(before)
    changes = []
    for _ in range(max_steps):
        res = analyse(p)
        best = None
        failing = [c for c in res["checks"] if c["status"] != "matched" and c.get("room_id")]
        for c in failing:
            lv = p["levels"][c["level"]]
            ids = {r["id"]: r for r in lv["rooms"]}
            a = ids.get(c["room_id"])
            if not a or a["type"] not in MOVABLE or any(x.get("parent") == a["id"] for x in lv["rooms"]):
                continue
            if a["type"] == "stair" and len(p["levels"]) > 1:
                continue
            for b in lv["rooms"]:
                if b["id"] == a["id"] or b["type"] not in MOVABLE or b.get("parent") or a.get("parent"):
                    continue
                if b["type"] == "stair" and len(p["levels"]) > 1:
                    continue
                if any(x.get("parent") == b["id"] for x in lv["rooms"]):
                    continue
                if not (_fits(a, b["w"], b["d"]) and _fits(b, a["w"], a["d"])):
                    continue
                trial = copy.deepcopy(p)
                tl = trial["levels"][c["level"]]
                ta = next(r for r in tl["rooms"] if r["id"] == a["id"])
                tb = next(r for r in tl["rooms"] if r["id"] == b["id"])
                for k in ("x", "y", "w", "d"):
                    ta[k], tb[k] = tb[k], ta[k]
                for l in trial["levels"]:
                    l.pop("walls", None)
                    l.pop("openings", None)
                trial = add_openings(trial)
                s = _score(analyse(trial))
                if c["level"] == 0 and not any(o["type"] == "main_door" for o in trial["levels"][0]["openings"]):
                    continue
                access_before = sum(1 for w in p.get("warnings", []) if "no access" in w)
                access_after = sum(1 for w in trial.get("warnings", []) if "no access" in w)
                if access_after > access_before:
                    continue
                gain = s - base
                if gain > 0.5 and (best is None or gain > best[0]):
                    nz = zone_of(trial["compass"], trial["building"]["w"], trial["building"]["d"],
                                 ta["x"] + ta["w"] / 2, ta["y"] + ta["d"] / 2)
                    best = (gain, trial, f"{lv['name']}: {a['name']} ↔ {b['name']} – {a['name']} now in {ZONE_NAME[nz]}")
        if not best:
            break
        base += best[0]
        p = best[1]
        changes.append(best[2])
    after = analyse(p)
    p.setdefault("notes", [])
    if changes:
        p["notes"] = p["notes"] + ["Vastu suggestions applied: " + "; ".join(changes)]
    remaining = [f"{c['title']}: {c['message']}" for c in after["checks"] if c["status"] == "not_matched"]
    return {"plan": p, "changes": changes, "before": before["summary"], "after": after["summary"], "result": after,
            "remaining": remaining}
