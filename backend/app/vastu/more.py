"""1.16 Vastu upgrade – data and helpers used by engine.analyse():
16-zone mandala, 32-pada main door check, site / fixture checks (asked, never guessed), remedies,
owner's own rules and Tamil text. Everything is traditional guidance, written neutrally."""
from __future__ import annotations

import math

ZONES16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
ZONE16_NAME = {"N": "North", "NNE": "North-North-East", "NE": "North-East", "ENE": "East-North-East", "E": "East",
               "ESE": "East-South-East", "SE": "South-East", "SSE": "South-South-East", "S": "South",
               "SSW": "South-South-West", "SW": "South-West", "WSW": "West-South-West", "W": "West",
               "WNW": "West-North-West", "NW": "North-West", "NNW": "North-North-West"}
# what each of the 16 zones traditionally suits (shown on the mandala – guidance only)
ZONE16_USE = {"N": "Wealth, opportunities – living, entrance", "NNE": "Health – open, light", "NE": "Clarity – pooja, water",
              "ENE": "Recreation – family lounge", "E": "Social links – living, entrance", "ESE": "Churning – toilet / utility ok",
              "SE": "Fire – kitchen", "SSE": "Strength – bedroom, kitchen ok", "S": "Rest, fame – bedroom",
              "SSW": "Disposal – toilet / store", "SW": "Stability – master bedroom", "WSW": "Study, savings – study / kids",
              "W": "Gains – dining, kids bedroom", "WNW": "Detox – toilet / store", "NW": "Support – guest bed, vehicles",
              "NNW": "Attraction – bedroom"}
ZONE16_TA = {"N": "வடக்கு", "NNE": "வட-வடகிழக்கு", "NE": "வடகிழக்கு", "ENE": "கிழக்கு-வடகிழக்கு", "E": "கிழக்கு",
             "ESE": "கிழக்கு-தென்கிழக்கு", "SE": "தென்கிழக்கு", "SSE": "தெற்கு-தென்கிழக்கு", "S": "தெற்கு",
             "SSW": "தெற்கு-தென்மேற்கு", "SW": "தென்மேற்கு", "WSW": "மேற்கு-தென்மேற்கு", "W": "மேற்கு",
             "WNW": "மேற்கு-வடமேற்கு", "NW": "வடமேற்கு", "NNW": "வடக்கு-வடமேற்கு"}
ZONE_TA = {"N": "வடக்கு", "NE": "வடகிழக்கு", "E": "கிழக்கு", "SE": "தென்கிழக்கு", "S": "தெற்கு", "SW": "தென்மேற்கு",
           "W": "மேற்கு", "NW": "வடமேற்கு", "C": "மையம் (பிரம்மஸ்தானம்)"}

# ---------------------------------------------------------------- 32 padas of the main door (8 per side)
PADAS = {  # in clockwise order along each side
    "E": ["Shikhi", "Parjanya", "Jayanta", "Indra", "Surya", "Satya", "Bhrisha", "Antariksha"],   # NE → SE
    "S": ["Anila", "Pusha", "Vitatha", "Grihakshata", "Yama", "Gandharva", "Bhringraj", "Mriga"],  # SE → SW
    "W": ["Pitru", "Dauvarika", "Sugriva", "Pushpadanta", "Varuna", "Asura", "Shosha", "Papayakshma"],  # SW → NW
    "N": ["Roga", "Naga", "Mukhya", "Bhallata", "Soma", "Bhujaga", "Aditi", "Diti"],  # NW → NE
}
PADA_GOOD = {"E3", "E4", "S3", "S4", "W3", "W4", "N3", "N4"}
PADA_OK = {"N2", "N5", "E2", "W5"}
NEXT_SIDE = {"E": "S", "S": "W", "W": "N", "N": "E"}  # the corner you walk towards (clockwise)
PREV_SIDE = {"E": "N", "S": "E", "W": "S", "N": "W"}
SIDE_NAME = {"N": "North", "E": "East", "S": "South", "W": "West"}

# ---------------------------------------------------------------- remedies (simple, traditional, neutral)
REMEDY = {
    "kitchen": ("If the kitchen cannot move: keep the stove in the South-East corner of the kitchen and cook facing East.",
                "சமையலறையை மாற்ற முடியாவிட்டால்: அடுப்பை சமையலறையின் தென்கிழக்கு மூலையில் வைத்து கிழக்கு நோக்கி சமைக்கவும்."),
    "master": ("Sleep with the head towards South; keep heavy furniture / wardrobe on the South-West side of the room.",
               "தெற்கு நோக்கி தலை வைத்து தூங்கவும்; கனமான அலமாரியை அறையின் தென்மேற்கு பக்கம் வைக்கவும்."),
    "bedroom": ("Sleep with the head towards South or East; keep the North-East part of the room light.",
                "தெற்கு அல்லது கிழக்கு நோக்கி தலை வைக்கவும்; அறையின் வடகிழக்கு பகுதியை இலேசாக வைக்கவும்."),
    "pooja": ("Keep the deity so that you face East or North while praying; keep the room clean and light.",
              "பிரார்த்திக்கும் போது கிழக்கு அல்லது வடக்கு நோக்கும்படி சுவாமியை வைக்கவும்; அறையை சுத்தமாக வைக்கவும்."),
    "toilet": ("Keep the door closed, give good ventilation / exhaust, seat along North–South and keep it dry.",
               "கதவை மூடி வைக்கவும், நல்ல காற்றோட்டம் / எக்ஸாஸ்ட், இருக்கை வடக்கு–தெற்காக, உலர்வாக வைக்கவும்."),
    "stair": ("Let the steps turn clockwise going up; do not keep a toilet or pooja under the staircase.",
              "ஏறும் போது படிகள் கடிகார சுற்றில் திரும்பட்டும்; படிக்கட்டின் கீழ் கழிவறை / பூஜை வேண்டாம்."),
    "hall": ("Seat the family facing North or East; keep the North-East corner open and light.",
             "குடும்பம் வடக்கு அல்லது கிழக்கு நோக்கி அமரும்படி; வடகிழக்கு மூலையை திறந்து இலேசாக வைக்கவும்."),
    "dining": ("Sit facing East or North while eating; keep the dining close to the kitchen.",
               "சாப்பிடும் போது கிழக்கு அல்லது வடக்கு நோக்கி அமரவும்; சமையலறைக்கு அருகில் வைக்கவும்."),
    "parking": ("Keep only light vehicles in the North-East side; no heavy storage there.",
                "வடகிழக்கில் இலேசான வாகனம் மட்டும்; கனமான பொருட்கள் வேண்டாம்."),
    "entrance": ("Keep the entrance bright, clean and uncluttered with a proper threshold; nameplate on the right side.",
                 "வாசலை வெளிச்சமாக, சுத்தமாக வைக்கவும்; முறையான நிலைப்படி; பெயர் பலகை வலது பக்கம்."),
    "door_pada": ("If the door cannot move: keep it bright and clean; a qualified Vastu consultant's traditional remedy can be considered.",
                  "வாசலை நகர்த்த முடியாவிட்டால்: வெளிச்சமாக, சுத்தமாக வைக்கவும்; தகுதியான வாஸ்து ஆலோசகரின் பரிகாரம் பார்க்கலாம்."),
    "brahmasthan": ("Keep the centre open, uncluttered and well lit.", "மையப் பகுதியை திறந்து, சுத்தமாக, வெளிச்சமாக வைக்கவும்."),
    "ne_light": ("Keep North-East clean and light; avoid heavy storage there.", "வடகிழக்கை சுத்தமாக, இலேசாக வைக்கவும்; கனமான பொருள் வேண்டாம்."),
    "sw_heavy": ("Place heavy furniture / storage on the South-West side.", "கனமான அலமாரி / பொருட்களை தென்மேற்கு பக்கம் வைக்கவும்."),
    "sump": ("Water underground suits North-East; if elsewhere, keep it covered and clean.", "நிலத்தடி நீர் வடகிழக்கில் சிறந்தது; வேறு இடமென்றால் மூடி சுத்தமாக வைக்கவும்."),
    "borewell": ("North-East is preferred for the borewell; keep the area clean.", "ஆழ்துளை கிணறுக்கு வடகிழக்கு சிறந்தது; சுத்தமாக வைக்கவும்."),
    "oh_tank": ("Keep the overhead tank on the South-West of the roof, raised on a platform.", "மேல்நிலை தொட்டியை கூரையின் தென்மேற்கில், மேடையில் உயர்த்தி வைக்கவும்."),
    "septic": ("North-West is preferred; keep it away from the North-East and the borewell.", "வடமேற்கு சிறந்தது; வடகிழக்கு மற்றும் ஆழ்துளை கிணற்றிலிருந்து தள்ளி வைக்கவும்."),
    "rwh": ("Rain-water pit suits North / East / North-East; slope the yard towards it.", "மழைநீர் குழி வடக்கு / கிழக்கு / வடகிழக்கில்; தரையை அதை நோக்கி சரிக்கவும்."),
    "gate": ("Gate in North / East / North-East preferred; avoid South-West.", "கேட் வடக்கு / கிழக்கு / வடகிழக்கில் சிறந்தது; தென்மேற்கு தவிர்க்கவும்."),
    "stair_turn": ("Steps that turn clockwise going up are preferred.", "ஏறும் போது கடிகார சுற்றில் திரும்பும் படிகள் சிறந்தவை."),
    "pooja_facing": ("Face East or North while praying.", "பிரார்த்திக்கும் போது கிழக்கு அல்லது வடக்கு நோக்கவும்."),
    "stove": ("Cook facing East (North is the next choice).", "கிழக்கு நோக்கி சமைக்கவும் (அடுத்தது வடக்கு)."),
    "bed_head": ("Sleep with the head towards South (East also suits); avoid North.", "தெற்கு நோக்கி தலை (கிழக்கும் சரி); வடக்கு தவிர்க்கவும்."),
    "toilet_seat": ("Place the WC along North–South so you face North or South.", "கழிவறை இருக்கை வடக்கு–தெற்காக இருக்கட்டும்."),
    "plot_shape": ("Square / rectangle is best; a North-East extension is welcome; other cuts can be squared with the compound wall / garden.",
                   "சதுரம் / செவ்வகம் சிறந்தது; வடகிழக்கு நீட்சி நல்லது; மற்ற வெட்டுகளை சுற்றுச்சுவர் / தோட்டத்தால் சரிசெய்யலாம்."),
    "roads": ("Roads on North or East are preferred; for South / West roads choose the right door pada.", "வடக்கு / கிழக்கு சாலை சிறந்தது; தெற்கு / மேற்கு என்றால் சரியான வாசல் பதம் தேர்வு செய்யவும்."),
    "t_junction": ("A road hitting the plot (veedhi soolai) is usually softened with a compound wall, trees or a consultant's remedy.",
                   "மனையை நோக்கி வரும் சாலை (வீதி சூலை) – சுற்றுச்சுவர், மரங்கள் அல்லது ஆலோசகர் பரிகாரம்."),
    "shape": ("Square / rectangular plots are preferred.", "சதுர / செவ்வக மனை சிறந்தது."),
}

TITLE_TA = {"kitchen": "சமையலறை", "master": "மாஸ்டர் படுக்கையறை", "bedroom": "படுக்கையறை", "pooja": "பூஜை அறை",
            "toilet": "கழிவறை", "stair": "படிக்கட்டு", "hall": "வரவேற்பறை (ஹால்)", "dining": "சாப்பாட்டு அறை",
            "parking": "வாகன நிறுத்தம்", "entrance": "முதன்மை வாசல்", "brahmasthan": "மையம் (பிரம்மஸ்தானம்)",
            "ne_light": "வடகிழக்கு இலேசாக", "sw_heavy": "தென்மேற்கு கனமாக", "shape": "மனை & கட்டட வடிவம்",
            "door_pada": "வாசல் பதம் (32 பதம்)", "sump": "சம்ப் (நிலத்தடி தொட்டி)", "borewell": "ஆழ்துளை கிணறு",
            "oh_tank": "மேல்நிலை தண்ணீர் தொட்டி", "septic": "செப்டிக் தொட்டி", "rwh": "மழைநீர் சேகரிப்பு குழி",
            "gate": "வெளி கேட்", "stair_turn": "படிக்கட்டு சுற்று", "pooja_facing": "பூஜையில் முகம்",
            "stove": "அடுப்பு – சமைப்பவர் முகம்", "bed_head": "தூங்கும் தலை திசை", "toilet_seat": "கழிவறை இருக்கை",
            "plot_shape": "மனை வடிவம் (வெட்டு / நீட்சி)", "roads": "சாலை பக்கங்கள்", "t_junction": "வீதி சூலை (T-சந்திப்பு)"}
WHY_TA = {"kitchen": "நெருப்பு தத்துவம் – தென்கிழக்கு (அக்னி) சிறந்தது, அடுத்தது வடமேற்கு.",
          "master": "தென்மேற்கு (நைருதி) குடும்பத் தலைவருக்கு நிலைத்தன்மை தரும்.",
          "bedroom": "மற்ற படுக்கையறைகள் மேற்கு, தெற்கு, வடமேற்கில் சிறந்தவை; வடகிழக்கு, தென்கிழக்கு தவிர்க்கவும்.",
          "pooja": "வடகிழக்கு (ஈசானியம்) மிகப் புனிதமான பகுதி; கிழக்கு அல்லது வடக்கும் சரி.",
          "toilet": "கழிவறை வடமேற்கு / மேற்கு / தெற்கில்; வடகிழக்கு அல்லது மையத்தில் வேண்டாம்.",
          "stair": "கனமான படிக்கட்டு தெற்கு / மேற்கு / தென்மேற்கில்; வடகிழக்கும் மையமும் காலியாக.",
          "hall": "வரவேற்பறை வடக்கு, கிழக்கு அல்லது வடகிழக்கில் சிறந்தது.",
          "dining": "சாப்பாட்டு அறை மேற்கில் (அல்லது கிழக்கில்), சமையலறை அருகில்.",
          "parking": "வாகனம் வடமேற்கு அல்லது தென்கிழக்கில்; வடகிழக்கை திறந்து வைக்கவும்.",
          "entrance": "வடக்கு, கிழக்கு அல்லது வடகிழக்கு வாசல் சிறந்தது; தென்மேற்கு தவிர்க்கப்படும்.",
          "brahmasthan": "பிரம்மஸ்தானம் திறந்து வெளிச்சமாக இருக்க வேண்டும்.",
          "ne_light": "வடகிழக்கு (ஈசானியம்) மிக இலேசான, சுத்தமான பகுதியாக இருக்க வேண்டும்.",
          "sw_heavy": "தென்மேற்கில் கனமான அறைகள் இருக்க வேண்டும்.",
          "shape": "சதுர / செவ்வக மனை சிறந்தது."}
STATUS_TA = {"matched": "பொருந்துகிறது", "partly": "பகுதியாக", "not_matched": "பொருந்தவில்லை"}

# ---------------------------------------------------------------- site / fixture questions (never guessed)
Z8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
SITE_FIELDS = [
    # key, English question, Tamil question, kind, options
    ("plot_shape", "Plot shape", "மனை வடிவம்", "choice", ["regular", "cut", "extension"]),
    ("shape_corner", "Which corner is cut / extended?", "எந்த மூலை வெட்டு / நீட்சி?", "zone", Z8),
    ("road_sides", "Roads on which sides? (the plan's front road is already known)", "எந்த பக்கங்களில் சாலை? (முன் சாலை தெரியும்)", "multi", ["N", "E", "S", "W"]),
    ("t_junction", "Does a road hit the plot straight (T-junction / veedhi soolai)?", "மனையை நோக்கி நேராக சாலை வருகிறதா (வீதி சூலை)?", "choice", ["no", "yes"]),
    ("t_junction_zone", "Where does that road hit?", "அந்த சாலை எங்கே மோதுகிறது?", "zone", Z8),
    ("gate", "Gate position (zone of the plot)", "கேட் இருக்கும் இடம்", "zone", Z8),
    ("sump", "Sump (underground tank) zone", "சம்ப் இருக்கும் இடம்", "zone_none", Z8 + ["C", "none"]),
    ("borewell", "Borewell zone", "ஆழ்துளை கிணறு இடம்", "zone_none", Z8 + ["C", "none"]),
    ("oh_tank", "Overhead tank zone (on the roof)", "மேல்நிலை தொட்டி இடம்", "zone_none", Z8 + ["C", "none"]),
    ("septic", "Septic tank zone", "செப்டிக் தொட்டி இடம்", "zone_none", Z8 + ["C", "none"]),
    ("rwh", "Rain-water harvesting pit zone", "மழைநீர் குழி இடம்", "zone_none", Z8 + ["C", "none"]),
    ("stair_turn", "Staircase turns (going up)", "படிக்கட்டு ஏறும் போது திரும்புவது", "choice", ["clockwise", "anticlockwise", "straight"]),
    ("pooja_facing", "Direction YOU face while praying", "பிரார்த்திக்கும் போது நீங்கள் நோக்கும் திசை", "zone", Z8),
    ("stove_facing", "Direction the cook faces at the stove", "சமைப்பவர் அடுப்பில் நோக்கும் திசை", "zone", Z8),
    ("bed_head", "Head side while sleeping (master bed)", "தூங்கும் போது தலை வைக்கும் திசை", "zone", Z8),
    ("toilet_seat", "Toilet seat (WC) axis", "கழிவறை இருக்கை அச்சு", "choice", ["N-S", "E-W"]),
]
SITE_KEYS = {f[0] for f in SITE_FIELDS}

# zone rules for fixtures: good, ok, (anything else = avoid)
FIXTURE = {
    "sump": ({"NE", "N", "E"}, {"NW"}, "Sump (underground tank)", "Underground water suits North-East / North / East."),
    "borewell": ({"NE", "N", "E"}, {"NW"}, "Borewell", "Borewell suits North-East / North / East."),
    "oh_tank": ({"SW"}, {"W", "S"}, "Overhead water tank", "The heaviest load on the roof suits South-West."),
    "septic": ({"NW"}, {"W", "S"}, "Septic tank", "Septic tank suits North-West; never North-East or South-West."),
    "rwh": ({"NE", "N", "E"}, {"NW"}, "Rain-water harvesting pit", "Rain water is collected towards North / East / North-East."),
    "gate": ({"NE", "N", "E"}, {"NW", "SE", "W", "S"}, "Gate", "Gate in North / East / North-East is preferred; South-West avoided."),
}
FACING = {  # direction answers: good, ok
    "pooja_facing": ({"E", "N"}, {"NE"}, "Facing while praying", "Facing East or North while praying is traditional."),
    "stove_facing": ({"E"}, {"N", "NE", "W"}, "Stove – cook faces", "Cooking facing East is traditional."),
    "bed_head": ({"S"}, {"E", "W", "SW", "SE"}, "Head side while sleeping", "Head towards South (or East) while sleeping; avoid North."),
}
FIX_KEY = {"stove_facing": "stove"}


def score_of(checks: list[dict]) -> int:
    cs = [c for c in checks if c["status"] in ("matched", "partly", "not_matched")]
    if not cs:
        return 0
    return round(100 * sum(1 if c["status"] == "matched" else 0.5 if c["status"] == "partly" else 0 for c in cs) / len(cs))


def zone16_of(comp: dict, bw: float, bd: float, cx: float, cy: float) -> str:
    from .engine import bearing_of
    xn = (cx - bw / 2) / (bw / 2 or 1)
    yn = (cy - bd / 2) / (bd / 2 or 1)
    if abs(xn) < 1 / 3 and abs(yn) < 1 / 3:
        return "C"
    b = bearing_of(comp, xn, yn)
    return ZONES16[int(((b + 11.25) % 360) // 22.5)]


def door_pada(plan: dict, o: dict, nx: float, ny: float, lang: str = "en") -> dict:
    """Main door on its wall, divided into 8 padas per side (32 around). Measured on the building wall."""
    from .engine import bearing_of
    comp = plan["compass"]
    bw, bd = float(plan["building"]["w"]), float(plan["building"]["d"])
    out_b = bearing_of(comp, nx, ny)
    side = ["N", "E", "S", "W"][int(round(out_b / 90)) % 4]
    want = (out_b + 90) % 360  # clockwise along the side
    horiz = abs(ny) > 0.5
    L = bw if horiz else bd
    pos = ((o["x1"] + o["x2"]) / 2) if horiz else ((o["y1"] + o["y2"]) / 2)
    door_w = abs(o["x2"] - o["x1"]) if horiz else abs(o["y2"] - o["y1"])
    tdir = (1.0, 0.0) if horiz else (0.0, 1.0)
    d_plus = abs(((bearing_of(comp, *tdir) - want + 180) % 360) - 180)
    forward = d_plus <= 90  # +x / +y runs clockwise
    t = (pos / L) if forward else ((L - pos) / L)
    t = min(max(t, 0.0), 0.9999)
    k = int(t * 8)
    code = f"{side}{k + 1}"
    status = "matched" if code in PADA_GOOD else "partly" if code in PADA_OK else "not_matched"
    name = PADAS[side][k]
    goods = [j for j in range(8) if f"{side}{j + 1}" in PADA_GOOD]
    j = min(goods, key=lambda j: abs((j + 0.5) / 8 - t))
    shift = ((j + 0.5) / 8 - t) * L
    towards = NEXT_SIDE[side] if shift > 0 else PREV_SIDE[side]
    pada_w = L / 8
    tr = (lambda en, ta: ta if lang == "ta" else en)
    if status == "matched":
        advice = tr(f"Door is in {code} {name} – a preferred pada.", f"வாசல் {code} {name} பதத்தில் – சிறந்த பதம்.")
    else:
        advice = tr(f"Move the door about {abs(shift):.1f} ft towards {SIDE_NAME[towards]} to reach {side}{j + 1} "
                    f"{PADAS[side][j]} (each pada is {pada_w:.1f} ft wide).",
                    f"வாசலை சுமார் {abs(shift):.1f} அடி {ZONE_TA[towards]} பக்கம் நகர்த்தினால் {side}{j + 1} "
                    f"{PADAS[side][j]} பதம் வரும் (ஒரு பதம் {pada_w:.1f} அடி).")
        if door_w > pada_w + 0.05:
            advice += tr(f" The door ({door_w:.1f} ft) is wider than one pada – centre it on {side}{j + 1}.",
                         f" வாசல் ({door_w:.1f} அடி) ஒரு பதத்தை விட அகலம் – {side}{j + 1} மையத்தில் வைக்கவும்.")
    return {"side": side, "side_name": SIDE_NAME[side], "pada": k + 1, "code": code, "name": name, "status": status,
            "position_ft": round(t * L, 2), "side_ft": round(L, 2), "pada_ft": round(pada_w, 2),
            "move_ft": 0 if status == "matched" else round(abs(shift), 2), "towards": None if status == "matched" else towards,
            "target": f"{side}{j + 1} {PADAS[side][j]}", "advice": advice,
            "good": sorted(PADA_GOOD), "padas": {s: [f"{s}{i + 1} {n}" for i, n in enumerate(v)] for s, v in PADAS.items()}}


def site_checks(plan: dict, site: dict, lang: str = "en") -> tuple[list[dict], list[dict]]:
    """Checks that need details not in the drawing. Unknown → a question (never guessed)."""
    tr = (lambda en, ta: ta if lang == "ta" else en)
    zn = (lambda z: ZONE_TA.get(z, z) if lang == "ta" else {"N": "North", "NE": "North-East", "E": "East", "SE": "South-East",
                                                             "S": "South", "SW": "South-West", "W": "West", "NW": "North-West",
                                                             "C": "Centre"}.get(z, z))
    site = site or {}
    checks, questions = [], []
    labels = {f[0]: (f[1], f[2], f[3], f[4]) for f in SITE_FIELDS}

    def ask(key):
        en, ta, kind, opts = labels[key]
        questions.append({"key": key, "question": tr(en, ta), "kind": kind, "options": opts})

    def add(rule, title_en, zone, status, msg, why_en, room="—"):
        checks.append({"rule": rule, "title": tr(title_en, TITLE_TA.get(rule, title_en)), "room": room, "room_id": None,
                       "level": -1, "level_name": tr("Site", "மனை"), "zone": zone if zone in Z8 + ["C"] else "",
                       "status": status, "message": msg, "why": why_en, "remedy": tr(*REMEDY.get(FIX_KEY.get(rule, rule), ("", ""))),
                       "suggest_zones": [], "better": ""})

    st_word = (lambda s: tr({"matched": "good", "partly": "acceptable", "not_matched": "avoid"}[s],
                            {"matched": "நல்லது", "partly": "பரவாயில்லை", "not_matched": "தவிர்க்கவும்"}[s]))
    for key, (good, ok, title, why) in FIXTURE.items():
        v = site.get(key)
        if not v:
            ask(key)
            continue
        if v == "none":
            continue
        s = "matched" if v in good else "partly" if v in ok else "not_matched"
        best = " / ".join(zn(z) for z in Z8 if z in good)
        add(key, title, v, s, f"{zn(v)} – {st_word(s)}" + ("" if s == "matched" else tr(f"; {best} preferred", f"; {best} சிறந்தது")), why)
    for key, (good, ok, title, why) in FACING.items():
        v = site.get(key)
        if not v:
            ask(key)
            continue
        s = "matched" if v in good else "partly" if v in ok else "not_matched"
        best = " / ".join(zn(z) for z in Z8 if z in good)
        add(FIX_KEY.get(key, key), title, "", s, tr(f"Faces {zn(v)} – {st_word(s)}", f"{zn(v)} நோக்கி – {st_word(s)}")
            + ("" if s == "matched" else tr(f"; {best} preferred", f"; {best} சிறந்தது")), why)
    v = site.get("stair_turn")
    has_stair = any(r["type"] == "stair" for lv in plan["levels"] for r in lv["rooms"])
    if has_stair:
        if not v:
            ask("stair_turn")
        else:
            s = "not_matched" if v == "anticlockwise" else "matched"
            add("stair_turn", "Staircase turn", "", s, tr({"clockwise": "Turns clockwise going up – good",
                                                            "straight": "Straight flight – fine",
                                                            "anticlockwise": "Turns anticlockwise – clockwise preferred"}[v],
                                                           {"clockwise": "கடிகார சுற்றில் – நல்லது", "straight": "நேரான படிகள் – சரி",
                                                            "anticlockwise": "எதிர் சுற்றில் – கடிகார சுற்று சிறந்தது"}[v]),
                "Steps that turn clockwise going up are traditional.")
    v = site.get("toilet_seat")
    has_wc = any(r["type"] in ("toilet", "common_toilet") for lv in plan["levels"] for r in lv["rooms"])
    if has_wc:
        if not v:
            ask("toilet_seat")
        else:
            add("toilet_seat", "Toilet seat axis", "", "matched" if v == "N-S" else "not_matched",
                tr("North–South – good" if v == "N-S" else "East–West – North–South preferred",
                   "வடக்கு–தெற்கு – நல்லது" if v == "N-S" else "கிழக்கு–மேற்கு – வடக்கு–தெற்கு சிறந்தது"),
                "WC along North–South is traditional.")
    # plot shape
    v = site.get("plot_shape")
    if not v:
        ask("plot_shape")
    elif v == "regular":
        add("plot_shape", "Plot shape", "", "matched", tr("Square / rectangular – good", "சதுரம் / செவ்வகம் – நல்லது"),
            "Square / rectangular plots are preferred.")
    else:
        c = site.get("shape_corner")
        if not c:
            ask("shape_corner")
        else:
            if v == "extension":
                s = "matched" if c in ("NE", "N", "E") else "not_matched"
            else:
                s = "not_matched" if c in ("NE",) else "partly"
            add("plot_shape", "Plot shape", c, s,
                tr(f"{v.title()} at {zn(c)} – {st_word(s)}", f"{zn(c)}-இல் {'நீட்சி' if v == 'extension' else 'வெட்டு'} – {st_word(s)}"),
                "A North-East extension is welcome; a North-East cut or other extensions are avoided.")
    # roads – the front road comes from the plan (facing); others are asked
    front = {"north": "N", "east": "E", "south": "S", "west": "W"}.get(str(plan.get("facing") or "").split("-")[0].lower())
    others = site.get("road_sides")
    if others is None:
        ask("road_sides")
    sides = sorted(set(([front] if front else []) + list(others or [])), key="NESW".index)
    if sides:
        s = "matched" if any(x in ("N", "E") for x in sides) else "partly"
        add("roads", "Road sides", "", s, tr(f"Road on {', '.join(zn(x) for x in sides)} – {st_word(s)}",
                                              f"{', '.join(zn(x) for x in sides)} பக்கம் சாலை – {st_word(s)}"),
            "Roads on North or East are preferred.")
    v = site.get("t_junction")
    if not v:
        ask("t_junction")
    elif v == "no":
        add("t_junction", "Road hitting the plot", "", "matched", tr("No road hits the plot – good", "வீதி சூலை இல்லை – நல்லது"),
            "A road ending at the plot (veedhi soolai) is traditionally avoided.")
    else:
        z = site.get("t_junction_zone")
        if not z:
            ask("t_junction_zone")
        else:
            s = "matched" if z in ("NE", "N", "E") else "not_matched"
            add("t_junction", "Road hitting the plot", z, s,
                tr(f"Road hits at {zn(z)} – " + ("considered good" if s == "matched" else "needs attention"),
                   f"{zn(z)}-இல் வீதி சூலை – " + ("நல்லதாக கருதப்படும்" if s == "matched" else "கவனம் தேவை")),
                "Veedhi soolai from North-East / North / East is traditionally fine; from other sides it is avoided.")
    return checks, questions


# ---------------------------------------------------------------- owner's own rules
def effective_rules(base: list[tuple], override: dict | None) -> list[tuple]:
    if not override:
        return base
    out = []
    for key, title, types, good, ok, bad, why in base:
        o = override.get(key) or {}
        if o:
            g = {z for z in o.get("good", []) if z in Z8 + ["C"]} or good
            k = {z for z in o.get("ok", []) if z in Z8 + ["C"]} - g
            b = {z for z in Z8 + ["C"]} - g - k if o.get("rest_avoid", True) else bad
            out.append((key, title, types, g, k, b, why + " (owner's rule)"))
        else:
            out.append((key, title, types, good, ok, bad, why))
    return out


def overview8(checks: list[dict]) -> dict:
    out = {}
    for z in Z8:
        cs = [c for c in checks if c.get("zone") == z]
        good = sum(1 for c in cs if c["status"] == "matched")
        bad = sum(1 for c in cs if c["status"] == "not_matched")
        part = sum(1 for c in cs if c["status"] == "partly")
        st = "Needs Attention" if bad else "Good" if part or not cs else "Excellent"
        out[z] = {"status": st, "matched": good, "partly": part, "not_matched": bad,
                  "items": [f"{c['title']}: {c['room']}" if c["room"] not in ("—", "") else c["title"] for c in cs][:6]}
    return out


def mandala_lines(plan: dict) -> list[dict]:
    """16 zone boundary rays (from the building centre, on its own proportions) – for drawing."""
    comp = plan["compass"]
    r, u = comp["right"], comp["up"]
    det = r[0] * u[1] - u[0] * r[1] or 1e-9
    out = []
    for k in range(16):
        b = math.radians(k * 22.5 + 11.25)
        e, n = math.sin(b), math.cos(b)
        dx = (e * u[1] - u[0] * n) / det
        dy = (r[0] * n - e * r[1]) / det
        m = max(abs(dx), abs(dy)) or 1
        out.append({"after": ZONES16[k], "dx": dx / m, "dy": dy / m})
    return out
