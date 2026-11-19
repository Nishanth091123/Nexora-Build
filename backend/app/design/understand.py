"""1.22 – understand a house request written in Tamil, English or Tanglish (or a mix), in any word order.

The old keyword reader (parser.parse) stays as the offline fallback. When a free AI key is set, the AI reads the
sentence first and fills the same fields; its answer is checked before it is used:
  * a number is accepted only if that number really is in the user's text (no invented sizes);
  * values must be inside sensible limits;
  * anything the plan generator cannot do yet (exact position of a room, "kitchen next to dining") is listed as
    "not applied" – never dropped silently.
Returns the parser's shape: {"requirements", "partial", "questions", "understood"} plus "checklist" and "ai".
"""
from __future__ import annotations

import logging
import re

from .. import llm
from . import parser

log = logging.getLogger("nexora.understand")

TA_DIGITS = str.maketrans("௦௧௨௩௪௫௬௭௮௯", "0123456789")
FACINGS = ("east", "west", "north", "south", "north-east", "north-west", "south-east", "south-west")
SIZE_KINDS = {"hall": "hall", "living": "hall", "lounge": "lounge", "kitchen": "kitchen", "dining": "dining",
              "master": "master", "master bedroom": "master", "bedroom": "bedroom", "toilet": "common_toilet",
              "common toilet": "common_toilet", "pooja": "pooja", "stair": "stair", "staircase": "stair",
              "parking": "parking_car", "car parking": "parking_car", "car": "parking_car", "bike": "parking_bike"}

PROMPT = """You help a civil engineer in Tamil Nadu. Read the house request below. It may be Tamil, English, Tanglish
(Tamil in English letters) or a mix, in any word order, with spelling mistakes. Understand what the person WANTS.
Return ONLY JSON:
{"language": "ta" | "en" | "tanglish",
 "plot_w_ft": number|null, "plot_d_ft": number|null,      // plot frontage (road side) x depth, in feet
 "facing": "east"|"west"|"north"|"south"|"north-east"|"north-west"|"south-east"|"south-west"|null,  // side the road is on
 "road_width_m": number|null,                              // convert feet to metres (x 0.3048)
 "floors": number|null,                                    // G = 1, G+1 = 2, duplex = 2
 "stilt": true|false|null, "bedrooms": number|null, "toilets": number|null, "attached": true|false|null,
 "kitchen": true|false|null, "hall": true|false|null, "dining": true|false|null, "pooja": true|false|null,
 "parking_car": true|false|null, "parking_bike": true|false|null, "staircase": true|false|null,
 "corner": true|false|null, "same_each_floor": true|false|null,
 "room_sizes": [{"room": "kitchen", "w": number, "d": number}],   // ONLY sizes the person wrote for a room (feet)
 "other": [ {"text": "short English summary of anything else asked", "kind": "position" | "adjacent" | "style" | "other"} ]
}
Rules: never invent a number; null when not said; "no dining" / "dining vendam" = false; "car parking venum" = true;
a size written as 10'6" is 10.5; put every wish about where a room should be, or what is next to what, into "other".
REQUEST:
"""


def _norm(text: str) -> str:
    return (text or "").translate(TA_DIGITS)


def _nums_in(text: str) -> set[float]:
    out = set()
    for m in re.finditer(r"\d+(?:\.\d+)?", text):
        v = float(m.group(0))
        out.add(v)
        out.add(round(v * 0.3048, 2))  # metres written, feet used (road width)
        out.add(round(v / 0.3048, 2))
    for m in re.finditer(r"(\d+)\s*'\s*(\d+)", text):  # 10'6"
        out.add(float(m.group(1)) + float(m.group(2)) / 12)
    return out


def _seen(v: float, nums: set[float]) -> bool:
    return any(abs(v - n) <= max(0.06, 0.02 * n) for n in nums)


BOOLS = ("stilt", "attached", "kitchen", "hall", "dining", "pooja", "parking_car", "parking_bike", "staircase",
         "corner", "same_each_floor")
LIMITS = {"plot_w_ft": (8, 300), "plot_d_ft": (8, 400), "road_width_m": (1.5, 60), "floors": (1, 6),
          "bedrooms": (0, 12), "toilets": (0, 14)}


def understand(text: str, defaults: dict | None = None) -> dict:
    text = _norm(text)
    base = parser.parse(text, defaults)  # offline fallback and cross-check
    d = dict(base["partial"])
    understood = list(base["understood"])
    checklist: list[dict] = [{"item": u, "status": "done"} for u in understood]
    ai_used = False
    try:
        data, model = llm.ask(PROMPT + text, want_json=True, budget=25.0)
        ai_used = isinstance(data, dict)
    except Exception as e:  # no key, no network, quota – the keyword reader answers
        log.info("understand: AI not used (%s)", str(e)[:120])
        data, model = {}, ""
    if ai_used:
        nums = _nums_in(text)
        changed = []
        fw = bool(d.get("floor_specs"))  # floor-by-floor requests keep their own table; the AI only fixes plot / road / facing
        words = bool(re.search(r"[஀-௿]|\b(?:muppathu|muppadhu|nalupathu|naarpathu|irupathu|ainthu|aimbathu|nootru|pathu)\b", text, re.I))
        for k, (lo, hi) in LIMITS.items():
            v = data.get(k)
            # sizes must be numbers the person really wrote (or spelled in Tamil words); counts like floors / bedrooms may be words
            if fw and k in ("floors", "bedrooms", "toilets"):
                continue
            if isinstance(v, (int, float)) and lo <= v <= hi and (k in ("floors", "bedrooms", "toilets") or words or _seen(float(v), nums)):
                if d.get(k) in (None, "") or abs(float(d[k]) - float(v)) > 0.01:
                    if d.get(k) not in (None, ""):
                        changed.append(f"{k}: {d[k]} → {v}")
                    d[k] = int(v) if k in ("floors", "bedrooms", "toilets") else float(v)
        f = data.get("facing")
        if f in FACINGS and f != d.get("facing"):
            if d.get("facing"):
                changed.append(f"facing: {d['facing']} → {f}")
            d["facing"] = f
        for k in ([] if fw else BOOLS):
            v = data.get(k)
            if isinstance(v, bool):
                if k in ("kitchen", "hall", "dining", "pooja", "parking_car", "parking_bike") or d.get(k) is None:
                    d[k] = v
                elif v and not d.get(k):
                    d[k] = v
        rs = {}
        for item in data.get("room_sizes") or []:
            try:
                kind = SIZE_KINDS.get(str(item.get("room", "")).strip().lower())
                w, dd = float(item["w"]), float(item["d"])
            except (KeyError, TypeError, ValueError):
                continue
            if kind and 3 <= w <= 60 and 3 <= dd <= 60 and ((_seen(w, nums) and _seen(dd, nums)) or words):
                rs[kind] = [w, dd]
                checklist.append({"item": f"{kind.replace('_', ' ').title()} size {w:g}' × {dd:g}'", "status": "done",
                                  "note": "used as the wanted size; the plot must have space for it"})
        if rs:
            d["room_sizes"] = rs
        for o in data.get("other") or []:
            t = str((o or {}).get("text") or "").strip()[:160]
            if t:
                checklist.append({"item": t, "status": "not_applied",
                                  "note": "The plan generator cannot place rooms by instruction yet – adjust it in the 2D editor, "
                                          "or upload your own drawing so every room stays exactly where you drew it."})
        for c in changed:
            checklist.append({"item": f"Two readings differed ({c}) – the AI reading was used", "status": "check"})
        if d.get("floors") and "floor_specs" not in d:
            pass
    # the same questions as the old reader, but only for what is still missing
    questions = []
    for key, q in (("plot_w_ft", "What is the plot size? (frontage × depth, e.g. 30 × 40 ft)"),
                   ("facing", "Which side is the road (plot facing)? East / West / North / South"),
                   ("road_width_m", "How wide is the road in front of the plot? (needed for the Tamil Nadu front setback)"),
                   ("floors", "How many floors? (G only, G+1, G+2 …)")):
        if not d.get(key) and not d.get("floor_specs"):
            questions.append(q)
    if not d.get("plot_d_ft") and d.get("plot_w_ft"):
        questions.append("What is the plot depth (ft)?")
    if d.get("bedrooms") in (None, "") and not d.get("floor_specs"):
        questions.append(next((q for q in base["questions"] if "bedroom" in q.lower() or "bhk" in q.lower()),
                              "How many bedrooms?"))
    # one readable line per understood fact (plot / road lines are rebuilt when the AI corrected a value)
    understood = [x for x in understood if not x.startswith(("Plot", "Road width", "North ", "South ", "East ", "West "))]
    if d.get("plot_w_ft") and d.get("plot_d_ft"):
        understood.insert(0, f"Plot {d['plot_w_ft']:g} × {d['plot_d_ft']:g} ft (first = road frontage)")
    if d.get("facing"):
        understood.insert(1, f"{str(d['facing']).title()} facing (road on the {d['facing']} side)")
    if d.get("road_width_m"):
        understood.insert(2, f"Road width {d['road_width_m'] / 0.3048:.0f} ft ({d['road_width_m']:.1f} m)")
    und = list(understood)
    for c in checklist:
        if c["status"] == "not_applied":
            und.append("⚠ Not applied: " + c["item"])
        elif c["status"] == "check":
            und.append("⚠ " + c["item"])
        elif c["item"] not in und and not c["item"].startswith(("Plot", "Road width", "North ", "South ", "East ", "West ")):
            und.append(c["item"])
    req = None
    if not questions:
        try:
            req = parser.build_requirements(d)
        except Exception as e:  # pragma: no cover
            log.warning("build_requirements failed: %s", e)
    return {"requirements": req, "partial": d, "questions": questions, "understood": und,
            "checklist": checklist, "ai": ai_used, "model": model if ai_used else ""}
