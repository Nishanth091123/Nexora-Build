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


def _plot_cuts(plan: dict) -> list[tuple[str, str]]:
    """1.18: corners of an irregular plot that are cut (missing) or extended, as compass zones."""
    P = plan.get("plot") or {}
    pts = [tuple(p) for p in P.get("poly") or []]
    if len(pts) < 3:
        return []
    from ..design.plot import _inside
    W, D = P["w"], P["d"]
    comp = plan.get("compass") or {"up": (0, 1), "right": (1, 0)}
    out = []
    for fx, fy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        # sample the quarter of the bounding box at this corner
        n = tot = 0
        for i in range(12):
            for j in range(12):
                x = (fx * 0.5 + (i + 0.5) / 24) * W
                y = (fy * 0.5 + (j + 0.5) / 24) * D
                tot += 1
                n += 0 if _inside(x, y, pts) else 1
        miss = n / tot
        z = zone_of(comp, W, D, (0.05 + 0.9 * fx) * W, (0.05 + 0.9 * fy) * D)
        if miss > 0.12:
            out.append((z, "cut"))
    return out


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


def analyse(plan: dict, site: dict | None = None, rules: dict | None = None, lang: str = "en") -> dict:
    """1.16: floor-wise scores, 8 + 16 zones, main door 32-pada, site / fixture checks (asked when unknown),
    remedies, owner's own rules and Tamil text (lang="ta")."""
    from . import more as M
    ta = lang == "ta"
    tr = (lambda en, t: t if ta else en)
    zn = (lambda z: M.ZONE_TA.get(z, z) if ta else ZONE_NAME.get(z, z))
    comp = plan["compass"]
    bw, bd = plan["building"]["w"], plan["building"]["d"]
    RL = M.effective_rules(RULES, rules)
    rooms_out, checks = [], []
    zone_rooms: dict[str, list[str]] = {}
    zones16: list[dict] = []
    master_done = False

    def room_msg(status, z, good):
        best = " / ".join(zn(g) for g in sorted(good, key=lambda q: (ZONES + ["C"]).index(q)))
        if ta:
            return {"matched": f"{zn(z)} – நல்ல இடம்", "partly": f"{zn(z)} – பரவாயில்லை; {best} சிறந்தது",
                    "not_matched": f"{zn(z)} – தவிர்க்கவும்; {best} பரிந்துரை"}[status], best
        return {"matched": f"{ZONE_NAME[z]} – good placement", "partly": f"{ZONE_NAME[z]} – acceptable; {best} is better",
                "not_matched": f"{ZONE_NAME[z]} – avoid; {best} preferred"}[status], best

    for li, lv in enumerate(plan["levels"]):
        mids = masters(lv) if not master_done else set()
        if mids:
            master_done = True
        for r in lv["rooms"]:
            cx, cy = r["x"] + r["w"] / 2, r["y"] + r["d"] / 2
            z = zone_of(comp, bw, bd, cx, cy)
            z16 = M.zone16_of(comp, bw, bd, cx, cy)
            kind = _room_kind(r, mids)
            rooms_out.append({"id": r["id"], "level": li, "level_name": lv["name"], "name": r["name"], "type": r["type"],
                              "kind": kind, "zone": z, "zone_name": zn(z), "zone16": z16})
            zones16.append({"level": li, "room": r["name"], "zone16": z16})
            zone_rooms.setdefault(z, []).append(r["name"] if li == 0 else f"{r['name']} ({lv['name']})")
            for key, title, types, good, ok, bad, why in RL:
                if kind not in types:
                    continue
                status = "matched" if z in good else "not_matched" if z in bad else "partly"
                msg, best = room_msg(status, z, good)
                checks.append({"rule": key, "title": tr(title, M.TITLE_TA.get(key, title)), "room": r["name"], "room_id": r["id"],
                               "level": li, "level_name": lv["name"], "zone": z, "zone16": z16, "status": status,
                               "message": msg, "why": tr(why, M.WHY_TA.get(key, why)),
                               "current": zn(z), "better": "" if status == "matched" else best,
                               "remedy": "" if status == "matched" else tr(*M.REMEDY[key]),
                               "suggest_zones": sorted(good, key=lambda q: (ZONES + ["C"]).index(q))})
    # entrance – the main door on the ground floor + its pada
    door = None
    for li, lv in enumerate(plan["levels"]):
        doors = [o for o in lv.get("openings", []) if o["type"] == "main_door"]
        if doors:
            o = doors[0]
            cx, cy = (o["x1"] + o["x2"]) / 2, (o["y1"] + o["y2"]) / 2
            room = next((r for r in lv["rooms"] if r["id"] == o["room"]), None)
            rcx = room["x"] + room["w"] / 2 if room else bw / 2
            rcy = room["y"] + room["d"] / 2 if room else bd / 2
            if o["y1"] == o["y2"]:
                nx, ny = 0.0, (-1.0 if rcy > cy else 1.0)
            else:
                nx, ny = (-1.0 if rcx > cx else 1.0), 0.0
            b = bearing_of(comp, nx, ny)
            z = ZONES[int(((b + 22.5) % 360) // 45)]
            key, title, good, ok, bad, why = ENTRANCE
            status = "matched" if z in good else "not_matched" if z in bad else "partly"
            msg = tr({"matched": f"Faces {ZONE_NAME[z]} – auspicious",
                      "partly": f"Faces {ZONE_NAME[z]} – acceptable (choose the right pada)",
                      "not_matched": f"Faces {ZONE_NAME[z]} – avoid; North/East preferred"}[status],
                     {"matched": f"{zn(z)} நோக்கி – சுபம்", "partly": f"{zn(z)} நோக்கி – பரவாயில்லை (சரியான பதம் தேர்வு செய்யவும்)",
                      "not_matched": f"{zn(z)} நோக்கி – தவிர்க்கவும்; வடக்கு / கிழக்கு சிறந்தது"}[status])
            checks.insert(0, {"rule": key, "title": tr(title, M.TITLE_TA[key]), "room": tr("Main door", "முதன்மை வாசல்"),
                              "room_id": o["room"], "level": li, "level_name": lv["name"], "zone": z, "status": status,
                              "message": msg, "why": tr(why, M.WHY_TA[key]), "current": zn(z),
                              "better": "" if status == "matched" else tr("North / East / North-East", "வடக்கு / கிழக்கு / வடகிழக்கு"),
                              "remedy": "" if status == "matched" else tr(*M.REMEDY[key]), "suggest_zones": ["N", "NE", "E"]})
            door = M.door_pada(plan, o, nx, ny, lang)
            checks.insert(1, {"rule": "door_pada", "title": tr("Main door pada (32 padas)", M.TITLE_TA["door_pada"]),
                              "room": f"{door['code']} {door['name']}", "room_id": o["room"], "level": li,
                              "level_name": lv["name"], "zone": "", "status": door["status"], "message": door["advice"],
                              "why": tr("Each side is divided into 8 padas; N3-N4, E3-E4, S3-S4, W3-W4 are preferred for the door.",
                                        "ஒவ்வொரு பக்கமும் 8 பதங்கள்; N3-N4, E3-E4, S3-S4, W3-W4 வாசலுக்கு சிறந்தவை."),
                              "current": f"{door['code']} {door['name']}",
                              "better": "" if door["status"] == "matched" else door["target"],
                              "remedy": "" if door["status"] == "matched" else tr(*M.REMEDY["door_pada"]), "suggest_zones": []})
            break
    # whole-building zone rules – checked on EVERY floor (1.16 floor-wise)
    for li, lv in enumerate(plan["levels"]):
        g0 = [r for r in rooms_out if r["level"] == li]
        centre_bad = [r["name"] for r in g0 if r["zone"] == "C" and r["type"] in ("toilet", "common_toilet", "stair", "kitchen")]
        st = "not_matched" if centre_bad else "matched"
        checks.append({"rule": "brahmasthan", "title": tr("Centre (Brahmasthan)", M.TITLE_TA["brahmasthan"]),
                       "room": ", ".join(centre_bad) or "—", "room_id": None, "level": li, "level_name": lv["name"], "zone": "C",
                       "status": st, "message": (tr(f"{', '.join(centre_bad)} in the centre – keep it open",
                                                    f"{', '.join(centre_bad)} மையத்தில் – திறந்து வைக்கவும்") if centre_bad
                                                 else tr("Centre is free of toilet / staircase / kitchen",
                                                         "மையத்தில் கழிவறை / படிக்கட்டு / சமையலறை இல்லை")),
                       "why": tr("The Brahmasthan should stay open and light.", M.WHY_TA["brahmasthan"]),
                       "current": tr("Centre", "மையம்"), "better": tr("Keep open", "திறந்து வைக்கவும்") if centre_bad else "",
                       "remedy": tr(*M.REMEDY["brahmasthan"]) if centre_bad else "", "suggest_zones": []})
        ne_bad = [r["name"] for r in g0 if r["zone"] == "NE" and r["type"] in ("toilet", "common_toilet", "stair", "kitchen", "store")]
        checks.append({"rule": "ne_light", "title": tr("North-East kept light", M.TITLE_TA["ne_light"]),
                       "room": ", ".join(ne_bad) or "—", "room_id": None, "level": li, "level_name": lv["name"], "zone": "NE",
                       "status": "not_matched" if ne_bad else "matched",
                       "message": (tr(f"{', '.join(ne_bad)} in North-East – move if possible", f"{', '.join(ne_bad)} வடகிழக்கில் – முடிந்தால் மாற்றவும்")
                                   if ne_bad else tr("No toilet / staircase / kitchen / store in North-East",
                                                     "வடகிழக்கில் கழிவறை / படிக்கட்டு / சமையலறை / ஸ்டோர் இல்லை")),
                       "why": tr("North-East (Eesanya) should be the lightest, cleanest part.", M.WHY_TA["ne_light"]),
                       "current": zn("NE"), "better": tr("Light / open use", "இலேசான பயன்பாடு") if ne_bad else "",
                       "remedy": tr(*M.REMEDY["ne_light"]) if ne_bad else "", "suggest_zones": []})
        sw = [r for r in g0 if r["zone"] == "SW"]
        sw_heavy = [r["name"] for r in sw if r["kind"] in ("master", "bedroom", "stair", "store")]
        sw_bad = [r["name"] for r in sw if r["type"] in ("toilet", "common_toilet", "kitchen", "terrace", "sitout", "parking")]
        st = "not_matched" if sw_bad and not sw_heavy else "matched" if sw_heavy else "partly"
        checks.append({"rule": "sw_heavy", "title": tr("South-West kept heavy", M.TITLE_TA["sw_heavy"]),
                       "room": ", ".join(sw_heavy or sw_bad) or "—", "room_id": None, "level": li, "level_name": lv["name"],
                       "zone": "SW", "status": st,
                       "message": (tr(f"{', '.join(sw_heavy)} in South-West – good", f"{', '.join(sw_heavy)} தென்மேற்கில் – நல்லது") if sw_heavy
                                   else tr(f"{', '.join(sw_bad)} in South-West – better a bedroom or staircase",
                                           f"{', '.join(sw_bad)} தென்மேற்கில் – படுக்கையறை / படிக்கட்டு சிறந்தது") if sw_bad
                                   else tr("South-West has no heavy room", "தென்மேற்கில் கனமான அறை இல்லை")),
                       "why": tr("South-West should carry the heaviest rooms.", M.WHY_TA["sw_heavy"]),
                       "current": zn("SW"), "better": tr("Bedroom / staircase / store", "படுக்கையறை / படிக்கட்டு / ஸ்டோர்") if st != "matched" else "",
                       "remedy": tr(*M.REMEDY["sw_heavy"]) if st != "matched" else "", "suggest_zones": []})
    # site / fixtures (asked when not known – never guessed)
    sc, questions = M.site_checks(plan, site or {}, lang)
    checks += sc
    try:  # 1.17 sheet roof slope (traditional: lower towards North / East)
        from ..design.roof import vastu_check
        vc = vastu_check(plan)
    except Exception:
        vc = None
    if vc:
        ok = vc["status"] == "matched"
        checks.append({"rule": "roof_slope", "title": tr("Sheet roof slope", "கூரை சரிவு (ஷீட்)"), "room": "—", "room_id": None,
                       "level": -1, "level_name": tr("Site", "மனை"), "zone": "", "status": vc["status"],
                       "message": tr(vc["message"], "ஷீட் கூரை வடக்கு / கிழக்கு நோக்கி சரிகிறது – நல்லது" if ok else
                                     "ஷீட் கூரை தெற்கு / மேற்கு நோக்கி சரிகிறது – வடக்கு / கிழக்கு சிறந்தது"),
                       "why": tr("Rain water traditionally flows towards North / East.", "மழைநீர் வடக்கு / கிழக்கு நோக்கி ஓடுவது பாரம்பரியம்."),
                       "current": "", "better": "" if ok else tr("Slope down to North / East", "வடக்கு / கிழக்கு நோக்கி சரிவு"),
                       "remedy": "" if ok else tr("Turn the mono-pitch so the low side is North or East.",
                                                  "தாழ்வான பக்கம் வடக்கு அல்லது கிழக்கு வரும்படி திருப்பவும்."), "suggest_zones": []})
    pc = _plot_cuts(plan)  # 1.18 irregular plot: corner cuts / extensions
    if pc:
        good = [z for z, kind in pc if kind == "extension" and z in ("NE", "N", "E")]
        bad = [(z, kind) for z, kind in pc if (z, kind) not in [(g, "extension") for g in good]]
        st = "matched" if not bad else ("not_matched" if any(z in ("NE", "SW") for z, _ in bad) else "partly")
        desc = ", ".join(f"{'cut' if k == 'cut' else 'extension'} in {z}" for z, k in pc)
        checks.append({"rule": "plot_cut", "title": tr("Plot shape (cuts / extensions)", "மனை வடிவம் (வெட்டு / நீட்சி)"), "room": "—",
                       "room_id": None, "level": -1, "level_name": tr("Site", "மனை"), "zone": bad[0][0] if bad else "", "status": st,
                       "message": tr(f"Irregular plot: {desc}.", f"ஒழுங்கற்ற மனை: {desc}."),
                       "why": tr("A North-East extension is considered good; a cut in North-East or South-West, or an extension in "
                                 "other corners, is not preferred.", "வடகிழக்கு நீட்சி நல்லது; வடகிழக்கு / தென்மேற்கு வெட்டு நல்லதல்ல."),
                       "current": desc, "better": "" if st == "matched" else tr("Square up the plot with the compound wall / use the odd corner as garden",
                                                                               "சுற்றுச்சுவரால் சதுரமாக்கு / கோணத்தை தோட்டமாக பயன்படுத்து"),
                       "remedy": "" if st == "matched" else tr("Leave the odd corner open (garden / parking); keep the house rectangular.",
                                                              "கோணத்தை திறந்து விடு (தோட்டம் / பார்க்கிங்); வீடு செவ்வகமாக இருக்கட்டும்."),
                       "suggest_zones": []})
    if len(plan["levels"]) > 1 and any(r["type"] == "stair" for lv in plan["levels"] for r in lv["rooms"]):  # 1.18
        checks.append({"rule": "stair_turn", "title": tr("Staircase climbing direction", "படிக்கட்டு ஏறும் திசை"), "room": tr("Staircase", "படிக்கட்டு"),
                       "room_id": None, "level": 0, "level_name": "", "zone": "", "status": "matched",
                       "message": tr("The staircase climbs clockwise (as designed in Nexora) – good",
                                     "படிக்கட்டு கடிகார திசையில் ஏறுகிறது (Nexora வடிவமைப்பு) – நல்லது"),
                       "why": tr("Clockwise climbing (turning right while going up) is preferred.", "வலப்புறமாக திரும்பி ஏறுவது சிறந்தது."),
                       "current": "", "better": "", "remedy": "", "suggest_zones": []})
    if not any(c["rule"] == "plot_shape" for c in checks):
        checks.append({"rule": "shape", "title": tr("Building shape", "கட்டட வடிவம்"), "room": "—", "room_id": None, "level": 0,
                       "level_name": "", "zone": "", "status": "matched",
                       "message": tr("Rectangular building – good", "செவ்வக கட்டடம் – நல்லது"),
                       "why": tr("Square / rectangular shapes are preferred.", M.WHY_TA["shape"]), "current": "", "better": "",
                       "remedy": "", "suggest_zones": []})

    matched = sum(1 for c in checks if c["status"] == "matched")
    partly = sum(1 for c in checks if c["status"] == "partly")
    total = len(checks)
    overview = {}
    for side, zones in SIDES.items():
        cs = [c for c in checks if c["zone"] in zones and c["rule"] not in ("shape",)]
        bad = sum(1 for c in cs if c["status"] == "not_matched")
        good = sum(1 for c in cs if c["status"] == "matched")
        st = "Needs Attention" if bad and bad >= good else "Good" if bad or any(c["status"] == "partly" for c in cs) else "Excellent"
        overview[side] = {"status": st, "matched": good, "not_matched": bad,
                          "rooms": [n for z in zones for n in zone_rooms.get(z, [])][:8]}
    floors = []
    for li, lv in enumerate(plan["levels"]):
        cs = [c for c in checks if c["level"] == li]
        floors.append({"level": li, "name": lv["name"], "score": M.score_of(cs), "matched": sum(1 for c in cs if c["status"] == "matched"),
                       "partly": sum(1 for c in cs if c["status"] == "partly"),
                       "not_matched": sum(1 for c in cs if c["status"] == "not_matched"), "total": len(cs)})
    cs = [c for c in checks if c["level"] == -1]
    if cs:
        floors.append({"level": -1, "name": tr("Site & fixtures", "மனை & பொருத்தங்கள்"), "score": M.score_of(cs),
                       "matched": sum(1 for c in cs if c["status"] == "matched"), "partly": sum(1 for c in cs if c["status"] == "partly"),
                       "not_matched": sum(1 for c in cs if c["status"] == "not_matched"), "total": len(cs)})
    suggestions = []
    for c in checks:
        if c["status"] == "not_matched":
            if c["suggest_zones"]:
                suggestions.append(tr(f"{c['title']}: move {c['room']} ({c['level_name']}) towards "
                                      f"{' / '.join(ZONE_NAME[z] for z in c['suggest_zones'])} – now {ZONE_NAME.get(c['zone'], c['zone'])}.",
                                      f"{c['title']}: {c['room']} ({c['level_name']}) – {' / '.join(zn(z) for z in c['suggest_zones'])} பக்கம் மாற்றவும் "
                                      f"(இப்போது {zn(c['zone'])})."))
            else:
                suggestions.append(f"{c['title']}: {c['message']}.")
    for c in checks:
        if c["status"] == "partly" and c["suggest_zones"]:
            suggestions.append(tr(f"{c['title']}: {c['room']} is acceptable in {ZONE_NAME.get(c['zone'], c['zone'])}; "
                                  f"{' / '.join(ZONE_NAME[z] for z in c['suggest_zones'])} is better if you can.",
                                  f"{c['title']}: {c['room']} {zn(c['zone'])}-இல் பரவாயில்லை; முடிந்தால் "
                                  f"{' / '.join(zn(z) for z in c['suggest_zones'])} சிறந்தது."))
    label = (tr("Most rules matched", "பெரும்பாலான விதிகள் பொருந்துகின்றன") if matched >= total * 0.75 else
             tr("Many rules matched – some improvements possible", "பல விதிகள் பொருந்துகின்றன – சில மேம்பாடுகள் சாத்தியம்") if matched >= total * 0.5 else
             tr("Several rules not matched – see suggestions", "பல விதிகள் பொருந்தவில்லை – பரிந்துரைகளை பார்க்கவும்"))
    tips_ta = ["வடகிழக்கு மூலையை இலேசாக, சுத்தமாக, திறந்து வைக்கவும் (கனமான பொருள், கழிவறை, படிக்கட்டு வேண்டாம்).",
               "மேல்நிலை தண்ணீர் தொட்டியை கூரையின் தென்மேற்கில் வைக்கவும்.",
               "சம்ப் / ஆழ்துளை கிணறு வடகிழக்கில்; செப்டிக் தொட்டி வடமேற்கில்.",
               "தரையும் மனையும் வடக்கு / கிழக்கு / வடகிழக்கு நோக்கி சற்று சரிவாக இருக்கட்டும்.",
               "வீட்டின் மையம் (பிரம்மஸ்தானம்) திறந்து இருக்கட்டும் – தூண், கழிவறை, படிக்கட்டு வேண்டாம்.",
               "வடக்கு, கிழக்கு சுவர்களில் அதிக ஜன்னல்கள் – வெளிச்சமும் காற்றும்."]
    return {"checks": checks, "rooms": rooms_out, "overview": overview, "overview8": M.overview8(checks),
            "zones": {z: zone_rooms.get(z, []) for z in ZONES + ["C"]},
            "zones16": zones16, "zone16_use": M.ZONE16_USE, "zone16_names": M.ZONE16_TA if ta else M.ZONE16_NAME,
            "mandala": M.mandala_lines(plan), "door": door, "floors": floors, "score": M.score_of(checks),
            "questions": questions, "lang": lang,
            "summary": {"matched": matched, "partly": partly, "not_matched": total - matched - partly, "total": total,
                        "label": label, "score": M.score_of(checks)},
            "suggestions": suggestions, "tips": tips_ta if ta else TIPS,
            "north_deg": plan.get("north_deg", north_of(comp)), "facing": plan.get("facing"),
            "note": tr("Vastu guidance is traditional advice, not a building rule – structural safety and TNCDBR come first.",
                       "வாஸ்து என்பது பாரம்பரிய வழிகாட்டல், கட்டட விதி அல்ல – கட்டமைப்பு பாதுகாப்பும் TNCDBR விதிகளும் முதன்மை.")}


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


def improve(plan: dict, max_steps: int = 6, **kw) -> dict:
    """Swap whole rooms (same floor, no attached toilet / dress) when it improves the Vastu result."""
    import copy

    from ..design.geometry import add_openings
    p = copy.deepcopy(plan)
    analyse = (lambda q: _analyse(q, kw.get("site"), kw.get("rules")))
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


# ---------------------------------------------------------------- 7.7: re-plan for Vastu when room swaps are not enough
def _bare(plan: dict) -> dict:
    from ..design.geometry import add_openings
    for lv in plan["levels"]:
        lv.pop("walls", None)
        lv.pop("openings", None)
    return add_openings(plan)


def _mirror(plan: dict) -> dict:
    """Same rooms, left and right exchanged (the road side stays the same)."""
    import copy
    p = copy.deepcopy(plan)
    bw = float(p["building"]["w"])
    for lv in p["levels"]:
        for r in lv["rooms"]:
            r["x"] = round(bw - float(r["x"]) - float(r["w"]), 2)
    return _bare(p)


def _level_reqs(plan: dict) -> list[dict]:
    """Room list per floor: from the design's own requirements, or counted from the drawing's rooms."""
    req = (plan.get("requirements") or {}).get("levels")
    if req and len(req) == len(plan["levels"]):
        return [{k: v for k, v in lv.items() if not str(k).startswith("_")} for lv in req]
    out = []
    for lv in plan["levels"]:
        rooms = lv.get("rooms") or []
        typ = [r.get("type") for r in rooms]
        names = [str(r.get("name") or "").lower() for r in rooms]
        toilets = [r for r in rooms if r.get("type") in ("toilet", "common_toilet")]
        attached = sum(1 for r in toilets if r.get("parent") or "attach" in str(r.get("name") or "").lower())
        beds = typ.count("bedroom")
        out.append({
            "name": lv.get("name"), "stilt": bool(lv.get("stilt")),
            "bedrooms": beds, "attached_toilets": min(attached, beds),
            "common_toilets": len(toilets) - min(attached, beds),
            "kitchen": "kitchen" in typ, "hall": "hall" in typ, "dining": "dining" in typ,
            "pooja": "pooja" in typ, "lounge": "lounge" in typ and "hall" not in typ,
            "parking_car": any(t == "parking" and "bike" not in n for t, n in zip(typ, names)),
            "parking_bike": any(t == "parking" and "bike" in n for t, n in zip(typ, names)),
        })
    return out


def _replan(plan: dict) -> dict:
    import copy

    from ..design.layout import build_level
    reqs = _level_reqs(plan)
    bw, bd = float(plan["building"]["w"]), float(plan["building"]["d"])
    multi = len(reqs) > 1
    p = copy.deepcopy(plan)
    template = None
    for i, (lv, req) in enumerate(zip(p["levels"], reqs)):
        rooms, info = build_level(dict(req, name=lv.get("name") or req.get("name") or f"Level {i}"),
                                  bw, bd, plan["compass"], multi, template)
        if i == 0 and multi:
            template = info
        lv["rooms"] = rooms
    return _bare(p)


_analyse = analyse  # (improve() binds the user's site answers / own rules around it)


def best_for_vastu(plan: dict, **kw) -> dict:
    """Try: room swaps on the plan as it is, on its mirror image, on a fresh layout of the same rooms in the same
    building outline, and on that layout's mirror. Return the one that follows Vastu best (never a worse one)."""
    before = analyse(plan, kw.get("site"), kw.get("rules"))
    base = improve(plan, **kw)
    best, best_score, how = base, _score(base["result"]), None
    tries = [("Rooms mirrored left ↔ right (same sizes, same road side)", lambda: _mirror(plan))]
    try:
        fresh = _replan(plan)
        tries += [("New room arrangement for Vastu (same building size and rooms)", lambda: fresh),
                  ("New room arrangement for Vastu, mirrored", lambda: _mirror(fresh))]
    except Exception:  # rooms do not fit a fresh layout – keep swaps / mirror only
        pass
    for label, make in tries:
        try:
            cand = improve(make(), **kw)
        except Exception:
            continue
        sc = _score(cand["result"])
        if sc > best_score + 0.5:
            best, best_score, how = cand, sc, label
    if how:
        best = dict(best)
        best["changes"] = [how] + list(best["changes"])
        best["before"] = before["summary"]
        best["plan"].setdefault("notes", [])
        best["plan"]["notes"] = best["plan"]["notes"] + [f"Vastu: {how}"]
    return best


def options_for_vastu(plan: dict, **kw) -> dict:
    """1.16: up to 3 improved plan options (with scores) to compare side by side. Nothing is saved here."""
    from . import more as M
    cur = analyse(plan, kw.get("site"), kw.get("rules"))
    cands = [("Rooms swapped (same layout)", lambda: plan),
             ("Rooms mirrored left ↔ right", lambda: _mirror(plan))]
    try:
        fresh = _replan(plan)
        cands += [("New room arrangement", lambda: fresh), ("New room arrangement, mirrored", lambda: _mirror(fresh))]
    except Exception:
        pass
    seen, out = {tuple((r["id"], round(r["x"], 1), round(r["y"], 1)) for lv in plan["levels"] for r in lv["rooms"])}, []
    for label, make in cands:
        try:
            c = improve(make(), **kw)
        except Exception:
            continue
        sig = tuple((r["id"], round(r["x"], 1), round(r["y"], 1)) for lv in c["plan"]["levels"] for r in lv["rooms"])
        if sig in seen:
            continue
        seen.add(sig)
        res = c["result"]
        if res["score"] < cur["score"]:  # never offer a worse plan
            continue
        out.append({"label": label, "changes": c["changes"], "plan": c["plan"], "score": res["score"],
                    "summary": res["summary"], "floors": res["floors"], "remaining": c["remaining"]})
    out.sort(key=lambda o: -o["score"])
    return {"current": {"score": cur["score"], "summary": cur["summary"], "floors": cur["floors"]}, "options": out[:3]}
