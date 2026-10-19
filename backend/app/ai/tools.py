"""Tools the assistant uses. Every number comes from Nexora's engines (design, estimate, vastu, site, calculators);
the language model only chooses the tool and explains the result.

Each tool returns a ToolResult. If information is missing, it returns questions (with form fields) instead of
guessing – the conversation remembers what was asked so the next answer continues the same task.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import DEFAULT_STATE
from ..design import parser
from ..design.geometry import estimate_inputs
from ..design.layout import LayoutError, generate
from ..design.setbacks import SetbackError, tn_setbacks
from ..estimate.engine import MissingInfo, calculate, levels_from_floors
from ..models import Design, Project, User
from ..routers.estimate import rates_dict, rates_for
from ..vastu import engine as vastu_engine
from . import calc, knowledge
from .textsearch import BM25

FT = 0.3048


@dataclass
class ToolResult:
    tool: str
    facts: str = ""                       # compact text given to the language model
    cards: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    questions: list = field(default_factory=list)
    fallback: str = ""                    # answer used when no AI provider is reachable
    state: dict = field(default_factory=dict)   # merged into the conversation state
    chips: list = field(default_factory=list)   # follow-up suggestions
    pending: dict | None = None           # set → waiting for the user's answers


class ToolDenied(Exception):
    pass


# ------------------------------------------------------------------ helpers
def need(perms: dict | None, *modules: str) -> None:
    """perms None = no project chosen (general questions only)."""
    if perms is None:
        return
    if not any(perms.get(m) for m in modules):
        raise ToolDenied(f"You don't have {' / '.join(modules)} access on this project – ask the owner.")


def project_defaults(p: Project | None) -> tuple[dict, list[str]]:
    """Details the user already entered on the project (never guessed). Returns (defaults, notes)."""
    if not p:
        return {}, []
    d, notes = {}, []
    to_ft = 3.28084 if p.unit == "m" else 1.0
    if p.plot_width and p.plot_length:
        d["plot_w_ft"], d["plot_d_ft"] = round(p.plot_width * to_ft, 2), round(p.plot_length * to_ft, 2)
        notes.append(f"plot {d['plot_w_ft']:g} × {d['plot_d_ft']:g} ft")
    if p.facing:
        d["facing"] = p.facing.lower()
        notes.append(f"{p.facing} facing")
    if p.road_width:
        d["road_width_m"] = float(p.road_width)
        notes.append(f"road {p.road_width:g} m")
    if p.floors:
        lv, stilt = levels_from_floors(p.floors)
        d["floors"] = lv
        if stilt:
            d["stilt"] = True
        notes.append(f"floors {p.floors}")
    return d, notes


def spec_of(text: str, p: Project | None) -> str:
    t = (text or "").lower()
    for s in ("basic", "standard", "premium"):
        if s in t:
            return s
    if re.search(r"budget|low cost|cheap|economy|சிக்கன", t):
        return "basic"
    if re.search(r"luxury|high end|பிரீமியம்", t):
        return "premium"
    return (p.spec_level if p and p.spec_level else "standard")


def run_estimate(db: Session, inputs: dict, state: str) -> dict:
    used, fallback, rows = rates_for(db, state)
    res = calculate(inputs, rates_dict(rows))
    res["rates_state"] = used
    if fallback:
        res["warnings"].insert(0, f"No rates saved for {state} yet – Tamil Nadu rates used.")
    return res


def material_rows(res: dict) -> list[dict]:
    t = res["totals"]
    rows = [("Cement", t["cement_bags"], "bags"), ("Steel (TMT)", t["steel_kg"], "kg"),
            ("Bricks", t["bricks"], "nos"), ("M-Sand", t["msand_m3"], "m³"), ("P-Sand", t["psand_m3"], "m³"),
            ("Aggregate", t["aggregate_m3"], "m³")]
    mats = {m["code"]: m for m in res.get("materials", [])}
    for code, label in (("aac", "AAC blocks"), ("floor_tile", "Floor tiles"), ("wall_tile", "Wall tiles"),
                        ("paint_int", "Interior painting")):
        if code in mats and mats[code]["qty"]:
            rows.append((label, round(mats[code]["qty"], 1), mats[code].get("unit", "")))
    return [{"label": a, "qty": b, "unit": c} for a, b, c in rows if b]


def estimate_card(res: dict, title: str, source: str, inputs: dict, state: str) -> dict:
    t = res["totals"]
    return {"type": "estimate", "title": title, "source": source, "spec_level": res.get("spec_level"),
            "rates_state": res.get("rates_state", state), "totals": {k: t[k] for k in (
                "grand_total", "cost_per_sqft", "builtup_sqft", "materials", "labour", "equipment", "extras",
                "duration_months", "cement_bags", "steel_kg")},
            "materials": material_rows(res), "breakdown": res.get("breakdown", [])[:8],
            "floors": res.get("floors", []), "warnings": res.get("warnings", [])[:4],
            "assumptions": res.get("assumptions", [])[:6], "inputs": inputs, "state": state}


def estimate_facts(res: dict) -> str:
    t = res["totals"]
    mats = ", ".join(f"{m['label']} {m['qty']:g} {m['unit']}" for m in material_rows(res))
    groups = ", ".join(f"{b['group']} ₹{b['amount']:,.0f}" for b in res.get("breakdown", [])[:6])
    return (f"Estimate ({res.get('spec_level')} spec, {res.get('rates_state')} rates): total ₹{t['grand_total']:,.0f}, "
            f"₹{t['cost_per_sqft']:,.0f}/sq ft for {t['builtup_sqft']:g} sq ft built-up; about {t['duration_months']} months. "
            f"Materials: {mats}. Cost groups: {groups}. Assumptions: {'; '.join(res.get('assumptions', [])[:4])}")


# ------------------------------------------------------------------ plan (design)
PLAN_FIELDS = {
    "plot": [{"key": "plot_w_ft", "label": "Plot frontage (ft)", "type": "num"},
             {"key": "plot_d_ft", "label": "Plot depth (ft)", "type": "num"}],
    "facing": [{"key": "facing", "label": "Road side (facing)", "type": "select",
                "options": ["east", "west", "north", "south", "north-east", "north-west", "south-east", "south-west"]}],
    "road": [{"key": "road_width_ft", "label": "Road width (ft)", "type": "num"}],
    "floors": [{"key": "floors", "label": "Floors", "type": "select", "options": ["1", "2", "3", "4"],
                "labels": ["G only", "G+1", "G+2", "G+3"]}],
    "bedrooms": [{"key": "bedrooms", "label": "Bedrooms (total)", "type": "num"}],
}


def _plan_fields(questions: list[str], partial: dict) -> list[dict]:
    out = []
    for q in questions:
        ql = q.lower()
        key = ("plot" if "plot size" in ql else "facing" if "facing" in ql or "road (" in ql or "which side" in ql
               else "road" if "road" in ql else "floors" if "floors" in ql else "bedrooms" if "bedroom" in ql or "rooms" in ql
               else None)
        if key:
            for f in PLAN_FIELDS[key]:
                if f["key"] not in [o["key"] for o in out]:
                    v = partial.get(f["key"])
                    if f["key"] == "road_width_ft" and partial.get("road_width_m"):
                        v = round(partial["road_width_m"] / FT, 1)
                    out.append({**f, "value": v})
    return out


def plan_summary(plan: dict) -> tuple[list[str], str]:
    feats, lines = [], []
    s = plan["summary"]
    for lv in plan["levels"]:
        rooms = lv["summary"]["rooms"]
        lines.append(f"{lv['name']}: " + ", ".join(f"{r['name']} {r['size']}" for r in rooms
                                                    if r["type"] not in ("passage",)))
    named = {}
    for lv in plan["levels"]:
        for r in lv["summary"]["rooms"]:
            named.setdefault(r["type"], []).append(r)
    if s.get("bedrooms"):
        feats.append(f"{s['bedrooms']} Bedroom{'s' if s['bedrooms'] > 1 else ''}"
                     + (" (incl. Master)" if "master" in named else ""))
    for typ, label in (("hall", "Living hall"), ("dining", "Dining"), ("kitchen", "Kitchen"), ("pooja", "Pooja room")):
        if typ in named:
            feats.append(f"{label} {named[typ][0]['size']}")
    toilets = len(named.get("toilet", [])) + len(named.get("common_toilet", []))
    if toilets:
        feats.append(f"{toilets} Toilet{'s' if toilets > 1 else ''}")
    if "parking" in named:
        feats.append(f"Car parking {named['parking'][0]['size']}")
    if "stair" in named:
        feats.append("Staircase to the upper floor / terrace")
    sb = plan.get("setbacks", {}).get("ft", {})
    if sb:
        feats.append(f"TN setbacks: front {sb.get('front', 0):g} ft, sides {sb.get('left', 0):g}/{sb.get('right', 0):g} ft, "
                     f"rear {sb.get('rear', 0):g} ft")
    return feats, "\n".join(lines)


def tool_plan(db: Session, user: User, p: Project | None, perms: dict | None, text: str, pending: dict | None,
              form: dict | None, original: str, previous: str = "") -> ToolResult:
    need(perms, "design")
    defaults, def_notes = project_defaults(p)
    combined = text
    partial = {}
    if pending and pending.get("tool") == "plan":
        partial = dict(pending.get("partial") or {})
        combined = (text + " . " + pending.get("text", "")).strip()  # newest words first – they win
        # answer to "N rooms – bedrooms or total?"
        m = re.search(r"(\d+)\s*rooms?", pending.get("text", "").lower())
        if m and "bedrooms" not in partial:
            low = text.lower()
            if re.search(r"bed|படுக்கை", low):
                partial["bedrooms"] = int(m.group(1))
            elif re.search(r"total|mothama|motham|மொத்த|all", low):
                partial["bedrooms"] = max(int(m.group(1)) - 2, 1)
            if "bedrooms" in partial:
                combined = re.sub(rf"\b{m.group(1)}\s*rooms?\b", f"{partial['bedrooms']} bedrooms", combined, flags=re.I)
    elif previous and not re.search(r"\d+\s*(?:x|×|by|\*)\s*\d+", text.lower()):
        combined = (text + " . " + previous).strip()  # "make it 3 bedrooms" → change the last plan
    reqs = None
    if form and form.get("requirements"):
        reqs = form["requirements"]
    elif form and form.get("answers") is not None:
        a = {**defaults, **partial, **{k: v for k, v in form["answers"].items() if v not in (None, "")}}
        if a.get("road_width_ft"):
            a["road_width_m"] = round(float(a.pop("road_width_ft")) * FT, 2)
        missing = [lbl for k, lbl in [("plot_w_ft", "Plot frontage (ft)"), ("plot_d_ft", "Plot depth (ft)"),
                                      ("facing", "Road side (facing)"), ("road_width_m", "Road width"),
                                      ("floors", "Floors"), ("bedrooms", "Bedrooms")] if a.get(k) in (None, "")]
        if missing:
            qs = [f"Please give: {', '.join(missing)}"]
            return ToolResult("plan", questions=qs, cards=[{"type": "questions", "tool": "plan", "questions": qs,
                              "fields": _plan_fields(["plot size", "facing", "road", "floors", "bedroom"], a)}],
                              pending={"tool": "plan", "text": combined, "partial": a},
                              fallback="Please fill the missing details.")
        for k in ("plot_w_ft", "plot_d_ft", "road_width_m"):
            a[k] = float(a[k])
        for k in ("floors", "bedrooms"):
            a[k] = int(float(a[k]))
        if a.get("toilets") not in (None, ""):
            a["toilets"] = int(float(a["toilets"]))
        partial = a
        reqs = parser.build_requirements(a)
    if reqs is None:
        parsed = parser.parse(combined, {**defaults, **partial})
        if parsed["questions"]:
            qs = parsed["questions"]
            used = [n for n in def_notes]
            return ToolResult(
                "plan", questions=qs,
                facts=(f"Understood so far: {', '.join(parsed['understood']) or 'nothing yet'}. "
                       f"From the project details: {', '.join(used) or 'none'}. Still needed: {' | '.join(qs)}"),
                cards=[{"type": "questions", "tool": "plan", "questions": qs, "understood": parsed["understood"],
                        "fields": _plan_fields(qs, parsed["partial"])}],
                pending={"tool": "plan", "text": combined, "partial": parsed["partial"], "original": original},
                fallback="Before I draw the plan I need a few details:\n" + "\n".join(f"• {q}" for q in qs))
        reqs = parsed["requirements"]
        partial = parsed["partial"]
    try:
        plan = generate(reqs)
    except LayoutError as e:
        opts = [{"label": s["label"], "requirements": s["requirements"], "notes": s.get("notes", [])}
                for s in (e.suggestions or [])]
        qs = list(e.questions)
        return ToolResult(
            "plan", questions=qs,
            facts=("The requested rooms do NOT fit this plot after Tamil Nadu setbacks: " + " ".join(qs)
                   + (" Options that fit: " + "; ".join(o["label"] for o in opts) if opts else "")),
            cards=[{"type": "questions", "tool": "plan", "questions": qs, "options": opts, "fields": []}],
            pending={"tool": "plan", "text": combined, "partial": partial},
            fallback="These rooms don't fit the plot after the Tamil Nadu setbacks.\n" + "\n".join(f"• {q}" for q in qs)
                     + ("\nChoose one of the options below." if opts else ""))
    except SetbackError as e:
        return ToolResult("plan", questions=[str(e)], facts=f"Setback problem: {e}",
                          cards=[{"type": "questions", "tool": "plan", "questions": [str(e)], "fields": []}],
                          pending={"tool": "plan", "text": combined, "partial": partial}, fallback=str(e))

    state = (p.state if p and p.state else DEFAULT_STATE)
    spec = spec_of(combined, p)
    est = None
    try:
        if perms is None or perms.get("estimate") or perms.get("design"):
            inp = estimate_inputs(plan, {"spec_level": spec, "structure": (p.structure_type if p else "rcc_framed")})
            est = run_estimate(db, inp, state)
    except (MissingInfo, ValueError, KeyError):
        est = None
    feats, rooms_txt = plan_summary(plan)
    s = plan["summary"]
    pw, pd = plan["plot"]["w"], plan["plot"]["d"]
    floors_label = "G" if s["levels"] == 1 else f"G+{s['levels'] - 1}"
    title = f"{pw:g}×{pd:g} {plan['facing'].title()}-facing house ({s['builtup_sqft']:g} sq ft, {floors_label})"
    card = {"type": "plan", "title": title,
            "subtitle": f"{s['bedrooms']} bedrooms · {s['toilets']} toilets · built-up {s['builtup_sqft']:g} sq ft "
                        f"· carpet {s['carpet_sqft']:g} sq ft",
            "plan": plan, "features": feats, "request": combined, "spec_level": spec, "state": state,
            "notes": plan.get("notes", [])[:5], "warnings": plan.get("warnings", [])[:4]}
    facts = f"Plan generated: {title}. Rooms – {rooms_txt}. Features: {'; '.join(feats)}."
    if plan.get("notes"):
        facts += " Notes: " + "; ".join(plan["notes"][:4])
    if est:
        card["estimate"] = estimate_card(est, "Estimated quantities & cost", "plan", est.get("inputs") or {}, state)
        card["estimate"]["inputs"] = estimate_inputs(plan, {"spec_level": spec,
                                                            "structure": (p.structure_type if p else "rcc_framed")})
        facts += " " + estimate_facts(est)
    if def_notes and any(k in (partial or {}) for k in ("facing", "road_width_m", "plot_w_ft")):
        facts += f" Some details came from the project record: {', '.join(def_notes)}."
    fb = f"{title}\n" + "\n".join(f"• {f}" for f in feats)
    if est:
        t = est["totals"]
        fb += f"\nEstimated cost ₹{t['grand_total']:,.0f} (₹{t['cost_per_sqft']:,.0f}/sq ft, {spec} spec)."
    return ToolResult("plan", facts=facts, cards=[card], fallback=fb,
                      state={"last_plan_request": combined, "last_tool": "plan"},
                      chips=["Suggest 1st floor changes", "Add Vastu improvements", "Calculate cost estimate (premium)",
                             "Compare with 2BHK plan"])


# ------------------------------------------------------------------ estimate
EST_FIELDS = [{"key": "builtup_sqft", "label": "Built-up area (sq ft)", "type": "num"},
              {"key": "area_basis", "label": "That area is", "type": "select", "options": ["per_floor", "total"],
               "labels": ["per floor", "total of all floors"]},
              {"key": "floors", "label": "Floors", "type": "select", "options": ["1", "2", "3", "4"],
               "labels": ["G only", "G+1", "G+2", "G+3"]},
              {"key": "bedrooms", "label": "Bedrooms (total)", "type": "num"},
              {"key": "toilets", "label": "Toilets (total)", "type": "num"},
              {"key": "spec_level", "label": "Specification", "type": "select", "options": ["standard", "basic", "premium"]}]


def _latest_design(db: Session, project_id: int) -> Design | None:
    return (db.query(Design).filter(Design.project_id == project_id, Design.is_hidden.is_(False))
            .order_by(Design.version.desc()).first())


def tool_estimate(db: Session, user: User, p: Project | None, perms: dict | None, text: str, args: dict,
                  pending: dict | None, form: dict | None, last_plan: dict | None, original: str) -> ToolResult:
    need(perms, "estimate", "design")
    state = p.state if p and p.state else DEFAULT_STATE
    spec = spec_of(text, p)
    vals = {}
    if pending and pending.get("tool") == "estimate":
        vals.update(pending.get("values") or {})
    if form and form.get("answers") is not None:
        vals.update({k: v for k, v in form["answers"].items() if v not in (None, "")})
        spec = vals.get("spec_level") or spec
    else:
        for k in ("builtup_sqft", "area_basis", "floors", "bedrooms", "toilets"):
            if args.get(k) not in (None, ""):
                vals[k] = args[k]

    # 1) the plan we just drew in this chat (or the plot was given → draw a plan first)
    plot_given = re.search(r"\d+\s*(?:x|×|by|\*)\s*\d+", text.lower())
    if not form and not vals.get("builtup_sqft") and (plot_given or (pending and pending.get("tool") == "plan")):
        r = tool_plan(db, user, p, perms, text, pending, None, original)
        r.tool = "estimate"
        return r
    if not vals and not form:
        if last_plan:
            inp = estimate_inputs(last_plan, {"spec_level": spec, "structure": p.structure_type if p else "rcc_framed"})
            res = run_estimate(db, inp, state)
            return ToolResult("estimate", facts="Estimate of the plan drawn earlier in this chat. " + estimate_facts(res),
                              cards=[estimate_card(res, f"Estimate – plan from this chat ({spec})", "chat_plan", inp, state)],
                              fallback=_est_fallback(res), chips=["Show premium spec cost", "Material quantities only",
                                                                  "Suggest cost-saving ideas"])
        if p:
            d = _latest_design(db, p.id)
            if d:
                inp = estimate_inputs(d.plan, {"spec_level": spec, "structure": p.structure_type or "rcc_framed"})
                res = run_estimate(db, inp, state)
                return ToolResult("estimate",
                                  facts=f"Estimate of the saved design '{d.title}' (v{d.version}). " + estimate_facts(res),
                                  cards=[estimate_card(res, f"Estimate – {d.title} (v{d.version}, {spec})", "design", inp, state)
                                         | {"design_id": d.id}],
                                  fallback=_est_fallback(res), chips=["Show basic spec cost", "Show premium spec cost",
                                                                      "Suggest cost-saving ideas"])
    # 2) built-up area route – ask what is missing, never assume
    missing = []
    if not vals.get("builtup_sqft"):
        missing.append("What is the built-up area (sq ft)? Or give the plot size (e.g. 30×40) and I will draw a plan first.")
    if not vals.get("floors"):
        missing.append("How many floors? (G only, G+1, G+2 …)")
    elif int(float(vals["floors"])) > 1 and not vals.get("area_basis"):
        missing.append(f"Is {float(vals['builtup_sqft']):g} sq ft per floor or the total of all floors?"
                       if vals.get("builtup_sqft") else "Is that area per floor or the total of all floors?")
    if vals.get("bedrooms") in (None, ""):
        missing.append("How many bedrooms in total?")
    if vals.get("toilets") in (None, ""):
        missing.append("How many toilets in total?")
    if missing:
        fields = [dict(f, value=vals.get(f["key"], spec if f["key"] == "spec_level" else None)) for f in EST_FIELDS]
        return ToolResult("estimate", questions=missing,
                          facts="Cannot estimate yet. Missing: " + " | ".join(missing),
                          cards=[{"type": "questions", "tool": "estimate", "questions": missing, "fields": fields}],
                          pending={"tool": "estimate", "values": vals, "original": original},
                          fallback="To estimate correctly I need:\n" + "\n".join(f"• {q}" for q in missing))
    floors = int(float(vals["floors"]))
    area = float(vals["builtup_sqft"])
    per = area if floors == 1 or vals.get("area_basis") == "per_floor" else area / floors
    inp = {"floor_areas_sqft": [round(per, 1)] * floors, "stilt": False, "floor_height_ft": 10,
           "structure": p.structure_type if p and p.structure_type else "rcc_framed", "spec_level": spec,
           "masonry": "brick", "bedrooms": int(float(vals["bedrooms"])), "halls": 1, "kitchens": 1,
           "toilets": int(float(vals["toilets"])), "staircase": floors > 1, "rwh": True,
           "plot_width_ft": None, "plot_length_ft": None}
    try:
        res = run_estimate(db, inp, state)
    except MissingInfo as e:
        return ToolResult("estimate", questions=e.questions, facts="Missing: " + " | ".join(e.questions),
                          cards=[{"type": "questions", "tool": "estimate", "questions": e.questions,
                                  "fields": [dict(f, value=vals.get(f["key"])) for f in EST_FIELDS]}],
                          pending={"tool": "estimate", "values": vals}, fallback="\n".join(e.questions))
    return ToolResult("estimate", facts=f"Estimate from built-up area {per:g} sq ft × {floors} floor(s). " + estimate_facts(res),
                      cards=[estimate_card(res, f"Estimate – {per * floors:g} sq ft, {'G' if floors == 1 else f'G+{floors - 1}'} ({spec})",
                                           "area", inp, state)],
                      fallback=_est_fallback(res), chips=["Show premium spec cost", "Suggest cost-saving ideas",
                                                          "Draw a plan for this"])


def _est_fallback(res: dict) -> str:
    t = res["totals"]
    return (f"Estimated cost ₹{t['grand_total']:,.0f} (₹{t['cost_per_sqft']:,.0f}/sq ft, {t['builtup_sqft']:g} sq ft, "
            f"{res.get('spec_level')} spec). Cement {t['cement_bags']} bags, steel {t['steel_kg']:,} kg.")


# ------------------------------------------------------------------ vastu
def tool_vastu(db: Session, user: User, p: Project | None, perms: dict | None, last_plan: dict | None,
               form: dict | None) -> ToolResult:
    need(perms, "vastu")
    plan, label, design_id = None, "", None
    if form and form.get("design_id") and p:
        d = db.get(Design, int(form["design_id"]))
        if d and d.project_id == p.id:
            plan, label, design_id = copy.deepcopy(d.plan), f"{d.title} (v{d.version})", d.id
    if plan is None and last_plan:
        plan, label = copy.deepcopy(last_plan), "the plan drawn in this chat"
    if plan is None and p:
        d = _latest_design(db, p.id)
        if d:
            plan, label, design_id = copy.deepcopy(d.plan), f"{d.title} (v{d.version})", d.id
    if plan is None:
        q = "Which plan should I check? Draw one here first (e.g. '30x40 east facing 2BHK, 30 ft road, G+1') or save a design in Design Studio."
        return ToolResult("vastu", questions=[q], facts=q, fallback=q,
                          cards=[{"type": "questions", "tool": "vastu", "questions": [q], "fields": []}])
    if "north_deg" not in plan:
        plan["north_deg"] = vastu_engine.north_of(plan["compass"])
    r = vastu_engine.analyse(plan)
    s = r["summary"]
    bad = [c for c in r.get("checks", []) if c.get("status") != "matched"][:6]
    facts = (f"Vastu check of {label}: {s['matched']} of {s['total']} rules matched, {s.get('partly', 0)} partly. "
             "Suggestions: " + " ".join(r.get("suggestions", [])[:6]) + " Note: " + r.get("note", ""))
    card = {"type": "vastu", "title": f"Vastu check – {label}", "summary": s, "checks": r.get("checks", [])[:14],
            "overview": r.get("overview"), "design_id": design_id,
            "suggestions": r.get("suggestions", [])[:6]}
    return ToolResult("vastu", facts=facts, cards=[card],
                      fallback=f"Vastu: {s['matched']} of {s['total']} rules matched. Open the Vastu page for the improved plan.",
                      chips=["How to fix the remaining Vastu issues?", "Get Vastu improved plan"])


# ------------------------------------------------------------------ calculators
def tool_calc(kind: str, params: dict, pending: dict | None, form: dict | None) -> ToolResult:
    if form and form.get("kind"):
        kind = form["kind"]
        params = {k: v for k, v in (form.get("params") or {}).items() if v not in (None, "")}
    elif pending and pending.get("tool") == "calc" and (not kind or kind == pending.get("kind")):
        kind = pending.get("kind")
        params = {**(pending.get("params") or {}), **(params or {})}
    if kind not in calc.CALCS:
        names = ", ".join(v[1] for v in calc.CALCS.values())
        return ToolResult("calc", facts=f"Available calculators: {names}", fallback=f"I can calculate: {names}.")
    try:
        out = calc.run(kind, params)
    except calc.CalcError as e:
        out = {"missing": [str(e)], "title": calc.CALCS[kind][1]}
    if out["missing"]:
        cat = next(c for c in calc.catalog() if c["key"] == kind)
        fields = [dict(f, value=params.get(f["key"])) for f in cat["params"]]
        qs = [f"Please give: {', '.join(out['missing'])}"]
        return ToolResult("calc", questions=qs, facts=f"{cat['name']}: missing {', '.join(out['missing'])}",
                          cards=[{"type": "questions", "tool": "calc", "kind": kind, "questions": qs, "fields": fields,
                                  "unit": params.get("unit", "ft")}],
                          pending={"tool": "calc", "kind": kind, "params": params},
                          fallback=qs[0])
    res_txt = "; ".join(f"{r['label']} {r['value']} {r['unit']}" for r in out["results"])
    facts = (f"{out['title']}: inputs {'; '.join(f'{a} {b}' for a, b in out['inputs'])}. Steps: {' | '.join(out['steps'])}. "
             f"Results: {res_txt}. "
             f"Assumptions: {'; '.join(out['assumptions'])}")
    return ToolResult("calc", facts=facts, cards=[{"type": "calc", **out}],
                      fallback=out["title"] + "\n" + "\n".join(f"• {r['label']}: {r['value']} {r['unit']}" for r in out["results"]),
                      state={"last_tool": "calc"})


# ------------------------------------------------------------------ setbacks
def tool_setback(args: dict, p: Project | None) -> ToolResult:
    d, _ = project_defaults(p)
    w = args.get("plot_w_ft") or d.get("plot_w_ft")
    dp = args.get("plot_d_ft") or d.get("plot_d_ft")
    road = (float(args["road_width_ft"]) * FT) if args.get("road_width_ft") else (
        float(args["road_width_m"]) if args.get("road_width_m") else d.get("road_width_m"))
    floors = args.get("floors") or d.get("floors")
    missing = [lbl for v, lbl in ((w, "plot frontage (ft)"), (dp, "plot depth (ft)"), (road, "road width"),
                                  (floors, "number of floors")) if not v]
    if missing:
        q = "For the Tamil Nadu setback I need the " + ", ".join(missing) + "."
        return ToolResult("setback", questions=[q], facts=q, fallback=q,
                          cards=[{"type": "questions", "tool": "setback", "questions": [q], "fields": [
                              {"key": "plot_w_ft", "label": "Plot frontage (ft)", "type": "num", "value": w},
                              {"key": "plot_d_ft", "label": "Plot depth (ft)", "type": "num", "value": dp},
                              {"key": "road_width_ft", "label": "Road width (ft)", "type": "num",
                               "value": round(road / FT, 1) if road else None},
                              {"key": "floors", "label": "Floors", "type": "select", "options": ["1", "2", "3", "4"],
                               "labels": ["G only", "G+1", "G+2", "G+3"], "value": floors}]}],
                          pending={"tool": "setback", "args": {k: v for k, v in args.items() if v}})
    try:
        r = tn_setbacks(float(w), float(dp), float(road), int(float(floors)), 10, "other", False, None)
    except SetbackError as e:
        return ToolResult("setback", facts=str(e), fallback=str(e), questions=[str(e)])
    ft = r["ft"]
    b = r["buildable"]
    facts = (f"{r['rule']}: plot {float(w):g}×{float(dp):g} ft, road {road:.1f} m, height {r['height_m']} m. "
             f"Setbacks front {ft['front']:g} ft, rear {ft['rear']:g} ft, left {ft['left']:g} ft, right {ft['right']:g} ft. "
             f"Buildable {b['w']:g} × {b['d']:g} ft per floor ({r['coverage_pct']}% coverage). Notes: {'; '.join(r.get('notes', []))}")
    return ToolResult("setback", facts=facts, cards=[{"type": "setback", **r}],
                      fallback=f"Front {ft['front']:g} ft, rear {ft['rear']:g} ft, sides {ft['left']:g}/{ft['right']:g} ft; "
                               f"buildable {b['w']:g} × {b['d']:g} ft.",
                      chips=["Draw a plan within these setbacks"])


# ------------------------------------------------------------------ knowledge base
_KB = knowledge.entries()
_BM = BM25([f"{e['title']} {e['title_ta']} {e['tags']} {e['tags']} {e['text']}" for e in _KB])


def kb_search(query: str, k: int = 4, category: str | None = None) -> list[dict]:
    sc = _BM.scores(query)
    if category:
        sc = [s * (1.6 if _KB[i]["category"] == category else 1) for i, s in enumerate(sc)]
    order = sorted(range(len(sc)), key=lambda i: -sc[i])
    top = [i for i in order[:k] if sc[i] >= 1.2]
    return [_KB[i] | {"score": round(sc[i], 2)} for i in top]


# ------------------------------------------------------------------ site
def tool_site(db: Session, user: User, p: Project | None, perms: dict | None) -> ToolResult:
    if not p:
        q = "Choose a project first (top bar) – site status belongs to a project."
        return ToolResult("site", facts=q, fallback=q, questions=[q])
    need(perms, "site")
    from ..routers import site as site_router
    try:
        ov = site_router.overview(project_id=p.id, day=None, user=user, db=db)
    except HTTPException as e:
        return ToolResult("site", facts=str(e.detail), fallback=str(e.detail))
    pr = ov["progress"]
    ins = [i.get("text") or i.get("title") or str(i) for i in (ov.get("insights") or [])][:6]
    facts = (f"Site status of {p.name} on {ov['date']}: progress {pr['overall']}% (planned {pr.get('planned')}%), "
             f"{'ahead' if (pr.get('variance_days') or 0) >= 0 else 'behind'} by {abs(pr.get('variance_days') or 0)} days, "
             f"health {pr['health']}. Today: {ov['cards']['activities']} activities ({ov['cards']['activities_done']} done), "
             f"{ov['cards']['workers']} workers, material received {ov['cards']['material_pct']}% of estimate, "
             f"{ov['cards']['issues']} open issues. Insights: {' | '.join(ins)}")
    card = {"type": "site", "title": f"Site status – {p.name}", "date": ov["date"], "progress": pr, "cards": ov["cards"],
            "insights": ov.get("insights", [])[:6], "activities": ov.get("activities", [])[:6]}
    return ToolResult("site", facts=facts, cards=[card], fallback=facts,
                      chips=["What should we focus on next?", "How to avoid delays in slab work?"])


# ------------------------------------------------------------------ drawing
def tool_drawing(db: Session, user: User, p: Project | None, perms: dict | None, file) -> ToolResult:
    if not p or not file.project_id:
        q = "Choose a project first (top bar) – drawings are saved and analysed inside a project."
        return ToolResult("drawing", facts=q, fallback=q, questions=[q])
    need(perms, "design")
    from ..routers import drawing as drawing_router
    from ..llm import LLMError
    try:
        a = drawing_router._finish(db, user, file, 0)
    except HTTPException as e:
        msg = e.detail if isinstance(e.detail, str) else (e.detail or {}).get("message", "Could not read the drawing")
        return ToolResult("drawing", facts=f"Drawing could not be read: {msg}", fallback=msg)
    except LLMError as e:
        return ToolResult("drawing", facts=f"Drawing could not be read: {e}", fallback=str(e))
    rooms = (a.get("result") or {}).get("rooms", [])
    lines = [f"{r.get('name')} {r.get('w', 0):g}×{r.get('d', 0):g} ft" for r in rooms[:30]]
    qs = a.get("questions", [])
    facts = (f"Drawing {a.get('file_name')} read by {a.get('method')}: {len(rooms)} rooms – {', '.join(lines)}. "
             f"Points to confirm: {' | '.join(qs[:4])}")
    card = {"type": "drawing", "analysis_id": a.get("id"), "file_name": a.get("file_name"), "method": a.get("method"),
            "rooms": rooms[:40], "questions": qs[:5]}
    return ToolResult("drawing", facts=facts, cards=[card], fallback=facts,
                      chips=["Check Vastu for this drawing", "Estimate cost for this drawing"])


# ------------------------------------------------------------------ photo check (one site photo, on request)
def tool_photo(db: Session, user: User, p: Project | None, perms: dict | None, file, lang: str) -> ToolResult:
    need(perms, "site", "ai")
    from ..llm import LLMError
    from . import photo
    try:
        rec = photo.check(db, user.id, file, {"ta": "Tamil", "tanglish": "Tanglish"}.get(lang, "English"))
    except LLMError as e:
        msg = f"AI photo check is not available right now ({str(e)[:160]})."
        return ToolResult("photo", facts=msg, fallback=msg)
    r = rec.result
    fs = r.get("findings", [])
    facts = (f"Photo shows: {r.get('photo_type', '')}. Clear enough: {r.get('photo_ok')}. Summary: {r.get('overall', '')}. "
             + " ".join(f"[{x.get('severity')}/{x.get('confidence')} confidence] {x.get('issue')}: cause {x.get('likely_cause')}; "
                        f"check {x.get('what_to_check')}; fix {x.get('suggested_fix')}." for x in fs)
             + f" Cannot judge from photo: {'; '.join(r.get('cannot_judge', []))}")
    card = {"type": "photo", "file_id": file.id, "file_name": file.original_name, "result": r}
    fb = (r.get("overall") or "Photo checked.") + "\n" + "\n".join(f"• {x.get('issue')} ({x.get('severity')})" for x in fs)
    return ToolResult("photo", facts=facts, cards=[card], fallback=fb,
                      chips=["How to repair this?", "Is this a structural problem?"])
