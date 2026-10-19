"""Chat orchestration: understand the message → run one tool (engines) → let the language model explain it.

Safety rules built in:
  * Numbers given to a calculator must appear in what the user wrote – the model cannot invent dimensions.
  * Missing information becomes a question (with a small form); the conversation remembers the open question.
  * The model is told to use only the tool result and the numbered sources, and to cite them.
  * If no AI provider is reachable, the engines' result is still shown with a plain-language fallback text.
"""
from __future__ import annotations

import json
import logging
import re

from sqlalchemy.orm import Session

from .. import llm
from ..models import AIConversation, AIMessage, AppSetting, Design, Project, StoredFile, User
from ..seed import DEFAULT_SETTINGS
from . import calc, docs, lang, tools
from .tools import ToolDenied, ToolResult

log = logging.getLogger("nexora.ai")

AGENTS = {
    "general": ("General Assistant", "பொது உதவியாளர்", "General queries and guidance", None),
    "drawing": ("Drawing Analyst", "வரைபட ஆய்வாளர்", "Analyze plans, sections, elevations", "design"),
    "quantity": ("Quantity Expert", "அளவு நிபுணர்", "Calculate quantities and BOQ", "design"),
    "design": ("Design Advisor", "வடிவமைப்பு ஆலோசகர்", "Floor plans, structural suggestions", "design"),
    "site": ("Site Engineer", "சைட் இன்ஜினியர்", "Site issues and solutions", "site"),
    "material": ("Material Expert", "பொருள் நிபுணர்", "Cement, concrete, steel, bricks etc.", "material"),
    "vastu": ("Vastu Advisor", "வாஸ்து ஆலோசகர்", "Vastu analysis and suggestions", "vastu"),
    "code": ("Code & Standards", "விதிமுறைகள்", "Building codes and IS standards", "code"),
}
AGENT_FOCUS = {
    "general": "You help with all civil engineering questions for houses in India (Tamil Nadu by default).",
    "drawing": "You focus on reading drawings: rooms, sizes, scale, north direction and what to confirm.",
    "quantity": "You focus on quantities, BOQ and cost; always show the calculation basis.",
    "design": "You focus on floor plans, room sizes, setbacks, light/ventilation and practical structural layout.",
    "site": "You focus on site problems: causes, step-by-step fixes, prevention, and when an engineer must check.",
    "material": "You focus on choosing materials: types, grades, IS codes, where to use, pros/cons and checks.",
    "vastu": "You focus on Vastu guidance, always noting that structure and building rules come first.",
    "code": "You focus on IS codes, NBC and TNCDBR – quote only clauses given in the sources.",
}
CALC_KB = {"concrete": ["is456-mix", "is456-grade"], "brickwork": ["is2212-brick"], "plaster": ["is1661-plaster"],
           "steel": ["is1786"], "staircase": ["nbc-stair"], "tiles": ["mat-tiles"], "paint": ["mat-paint"],
           "water_tank": ["design-sump-tank"], "aac": ["mat-blocks"]}
TOOLS = ("photo", "plan", "estimate", "vastu", "calc", "setback", "docs", "site", "knowledge", "chat", "drawing")


def ai_settings(db: Session) -> dict:
    row = db.get(AppSetting, "ai")
    return {**DEFAULT_SETTINGS["ai"], **((row.value if row else {}) or {})}


# ------------------------------------------------------------------ routing
NUM = r"(\d+(?:\.\d+)?)"


def _numbers(text: str) -> set[float]:
    t = (text or "").replace(",", "")
    out = {float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)}
    out |= {float(x) + 1 for x in re.findall(r"(?:g|ground|stilt)\s*\+\s*(\d)", t.lower())}  # G+1 → 2 levels
    if re.search(r"ground floor only|single floor|\bg only\b|only ground", t.lower()):
        out.add(1.0)
    return out


def _guard_params(params: dict, allowed_text: str) -> dict:
    """Keep only numeric values the user really wrote (select options like M20 / 1:6 are standard choices)."""
    nums = _numbers(allowed_text)
    out = {}
    for k, v in (params or {}).items():
        if v in (None, ""):
            continue
        if isinstance(v, (int, float)) or (isinstance(v, str) and re.fullmatch(r"\d+(?:\.\d+)?", v.strip())):
            if any(abs(float(v) - n) < 1e-6 for n in nums):
                out[k] = v
        else:
            out[k] = v
    return out


def regex_route(text: str, agent: str, has_attachment: bool, pending: dict | None) -> tuple[str, dict]:
    t = " " + (text or "").lower() + " "
    if has_attachment:
        return "drawing", {}
    if re.search(r"vastu|vaastu|vasthu|வாஸ்து", t) and not re.search(r"\d+\s*(x|×|by)\s*\d+", t):
        return "vastu", {}
    if re.search(r"setback|set back|செட்பேக்", t):
        m = re.search(NUM + r"\s*(?:x|×|by|\*)\s*" + NUM, t)
        r = re.search(NUM + r"\s*(?:ft|feet|')\s*(?:wide\s*)?road|road\s*(?:width)?\s*" + NUM, t)
        f = re.search(r"g\s*\+\s*(\d)", t)
        args = {}
        if m:
            args.update(plot_w_ft=float(m.group(1)), plot_d_ft=float(m.group(2)))
        if r:
            args["road_width_ft"] = float(r.group(1) or r.group(2))
        if f:
            args["floors"] = int(f.group(1)) + 1
        return "setback", args
    plan_words = r"plan|layout|bhk|bedroom|bed room|veedu|வீடு|படுக்கை|வரைபடம்"
    cost_words = r"cost|estimate|budget|boq|selavu|salavu|செலவு|மதிப்பீடு|evlo aagum|how much will|total amount"
    if re.search(cost_words, t) and not re.search(r"cement for|bricks for|steel for|tiles for|paint for", t):
        return "estimate", estimate_args(t)
    if re.search(plan_words, t) and (re.search(r"\d+\s*(x|×|by|\*)\s*\d+", t) or re.search(r"draw|suggest|design|generate|create|make|போட|வரை", t)):
        return "plan", {}
    kind, params = calc_from_text(t)
    if kind:
        return "calc", {"kind": kind, "params": params}
    if re.search(r"site status|progress|today.*site|site.*today|delay|behind schedule|dpr|சைட்", t):
        return "site", {}
    if re.search(r"document|my file|uploaded|contract|agreement|specification|soil report|ஆவண", t):
        return "docs", {"query": text}
    if pending and pending.get("tool") == "estimate":
        return "estimate", estimate_args(t)
    if pending and pending.get("tool") in ("plan", "calc", "setback"):
        return pending["tool"], {}
    if re.search(r"^\s*(hi|hello|hey|vanakkam|வணக்கம்|thanks|thank you|nandri|நன்றி)\b", t):
        return "chat", {}
    return "knowledge", {"query": text}


def estimate_args(t: str) -> dict:
    t = " " + t.lower() + " "
    args: dict = {}
    m = re.search(NUM + r"\s*(?:sq\.?\s*ft|sqft|square feet|சதுர)", t)
    if m:
        args["builtup_sqft"] = float(m.group(1))
    f = re.search(r"g\s*\+\s*(\d)", t)
    if f:
        args["floors"] = int(f.group(1)) + 1
    elif re.search(r"ground floor only|single floor|\bg only\b|only ground", t):
        args["floors"] = 1
    if re.search(r"per floor|each floor|ovvoru|ஒவ்வொரு", t):
        args["area_basis"] = "per_floor"
    elif re.search(r"total|motham|மொத்த", t):
        args["area_basis"] = "total"
    b = re.search(NUM + r"\s*(?:bhk|bed)", t)
    if b:
        args["bedrooms"] = int(float(b.group(1)))
    tl = re.search(NUM + r"\s*(?:toilets?|bath)", t)
    if tl:
        args["toilets"] = int(float(tl.group(1)))
    return args


def calc_from_text(t: str) -> tuple[str | None, dict]:
    """Very small pattern reader used when no AI provider is available."""
    dims = re.search(NUM + r"\s*(ft|m|feet|mtr)?\s*(?:x|×|by|\*)\s*" + NUM + r"\s*(ft|m|feet|mtr)?(?:\s*(?:x|×|by|\*)\s*" + NUM + r"\s*(ft|m|feet|mm|mtr)?)?", t)
    unit = "m" if dims and (dims.group(2) or dims.group(4) or "").startswith("m") else "ft"
    if re.search(r"cent|ground|acre|hectare", t) and re.search(r"convert|to sq|in sq|sq ?ft|how many|எத்தனை", t):
        m = re.search(NUM + r"\s*(cents?|grounds?|acres?|hectares?|sq\.?\s*ft|sqft|m2|sqm|sq\.?\s*m)", t)
        if m:
            u = m.group(2)
            u = ("cent" if u.startswith("cent") else "ground" if u.startswith("ground") else "acre" if u.startswith("acre")
                 else "hectare" if u.startswith("hect") else "m2" if u in ("m2", "sqm") or u.replace(" ", "").replace(".", "") == "sqm" else "sqft")
            return "area", {"value": float(m.group(1)), "from_unit": u}
        return "area", {}
    if re.search(r"steel weight|weight of .*bar|kg per (m|meter|metre)|\d+\s*mm\s*(bar|rod|kambi)", t):
        d = re.search(NUM + r"\s*mm", t)
        L = re.search(NUM + r"\s*(?:m|meter|metre)\b", t)
        n = re.search(NUM + r"\s*(?:nos|bars|rods|numbers)", t)
        p = {}
        if d:
            p["dia_mm"] = float(d.group(1))
        if L:
            p["length_m"] = float(L.group(1))
        if n:
            p["count"] = float(n.group(1))
        return "steel", p
    if re.search(r"stair|riser|tread|படிக்கட்டு|padikattu", t):
        h = re.search(r"(?:height|ht)\s*(?:is|of)?\s*" + NUM + r"\s*(ft|feet|m)?|" + NUM + r"\s*(ft|feet|m)\s*(?:floor|height)", t)
        p = {}
        if h:
            p["floor_height"] = float(h.group(1) or h.group(3))
            p["unit"] = "m" if (h.group(2) or h.group(4) or "ft").startswith("m") else "ft"
        return "staircase", p
    if re.search(r"sump|water tank|overhead tank|தொட்டி", t):
        n = re.search(NUM + r"\s*(?:persons?|people|members|peru|பேர்)", t)
        return "water_tank", ({"persons": float(n.group(1))} if n else {})
    if re.search(r"tiles?|டைல்", t) and re.search(r"how many|count|need|evlo|எத்தனை|for", t):
        p = {}
        if dims:
            p.update(length=float(dims.group(1)), width=float(dims.group(3)), unit=unit)
        s = re.search(r"(\d{3,4})\s*[x×]\s*(\d{3,4})\s*mm|(\d{3,4})\s*[x×]\s*(\d{3,4})", t)
        if s:
            p["tile_size"] = f"{s.group(1) or s.group(3)}x{s.group(2) or s.group(4)}"
            if dims and dims.group(1) == (s.group(1) or s.group(3)):
                p.pop("length", None)
                p.pop("width", None)
        return "tiles", p
    if re.search(r"paint|பெயிண்ட்", t):
        a = re.search(NUM + r"\s*(?:sq\.?\s*ft|sqft)", t)
        return "paint", ({"area_sqft": float(a.group(1))} if a else {})
    if re.search(r"plaster|பூச்சு|poochu", t) and re.search(r"cement|sand|how much|quantity|evlo", t):
        a = re.search(NUM + r"\s*(?:sq\.?\s*ft|sqft)", t)
        th = re.search(NUM + r"\s*mm", t)
        p = {"area_sqft": float(a.group(1))} if a else {}
        if th:
            p["thickness_mm"] = float(th.group(1))
        return "plaster", p
    if re.search(r"aac", t) and re.search(r"how many|blocks? for|count|evlo", t):
        p = {}
        if dims:
            p.update(length=float(dims.group(1)), height=float(dims.group(3)), unit=unit)
        return "aac", p
    if re.search(r"brick|செங்கல்|sengal", t) and re.search(r"how many|bricks? for|count|wall|evlo|எத்தனை", t):
        p = {}
        if dims:
            p.update(length=float(dims.group(1)), height=float(dims.group(3)), unit=unit)
        th = re.search(r"(230|115|9\"|4\.5\"|9 inch|4.5 inch)", t)
        if th:
            p["thickness_mm"] = 115 if th.group(1).startswith("115") or th.group(1).startswith("4") else 230
        return "brickwork", p
    if re.search(r"excavat|digging|pit|தோண்ட", t):
        p = {}
        if dims and dims.group(5):
            p.update(length=float(dims.group(1)), width=float(dims.group(3)), depth=float(dims.group(5)), unit=unit)
        return "excavation", p
    if re.search(r"concrete|cement|m20|m15|m25|m10|footing|slab|column|beam|கான்கிரீட்", t) and \
            re.search(r"how much|how many|quantity|bags|need|required|calculate|evlo|எவ்வளவு|for\s+\d", t):
        p = {}
        g = re.search(r"\bm\s?(7\.5|10|15|20|25)\b", t)
        if g:
            p["grade"] = "M" + g.group(1)
        v = re.search(NUM + r"\s*(?:m3|m³|cum|cubic\s*m)", t)
        if v:
            p["volume_m3"] = float(v.group(1))
        elif dims and dims.group(5):
            u3 = (dims.group(6) or dims.group(2) or "ft")
            p.update(length=float(dims.group(1)), width=float(dims.group(3)), depth=float(dims.group(5)),
                     unit="m" if u3.startswith("m") and u3 != "mm" else "ft")
            if u3 == "mm":  # slab thickness in mm
                p["depth"] = float(dims.group(5)) / (304.8 if unit == "ft" else 1000)
        n = re.search(NUM + r"\s*(?:nos|numbers|footings|columns|beams)", t)
        if n:
            p["count"] = float(n.group(1))
        return "concrete", p
    return None, {}


ROUTER_PROMPT = """You decide how a civil engineering assistant (Nexora Build, India / Tamil Nadu) handles a message.
Return JSON only: {{"tool": "...", "args": {{...}}, "search": "short English search keywords"}}

Tools:
- plan: draw / suggest / modify a house floor plan. args: {{"request_en": "the user's plan request in plain English,
  including details from earlier in the chat if this message modifies it, keeping ONLY details the user gave"}}
- estimate: cost / budget / BOQ / overall material quantity for a whole house or the plan in this chat.
  args: {{"request_en": "...", "builtup_sqft": number or null, "area_basis": "per_floor" | "total" | null,
  "floors": number of levels or null, "bedrooms": number or null, "toilets": number or null}}
- vastu: Vastu check of the plan / design. args: {{}}
- calc: one specific quantity calculation. args: {{"kind": one of {kinds}, "params": {{...}}}}
  param keys: {params}. Lengths keep the user's numbers; set "unit": "ft" or "m" as the user said.
- setback: Tamil Nadu setbacks. args: {{"plot_w_ft", "plot_d_ft", "road_width_ft", "floors"}}
- docs: answer from the project's uploaded documents (contract, specification, soil report, BOQ…). args: {{"query": "..."}}
- site: this project's site status / progress / delays today. args: {{}}
- knowledge: codes & standards, materials, site problems, construction methods, general civil questions. args: {{}}
- chat: greetings, thanks, small talk. args: {{}}

Rules: NEVER invent numbers – use null when the user did not give a value. If the message answers a question the
assistant asked (see "Waiting for"), choose that same tool. Prefer the agent's focus when unclear.
Agent: {agent}. Waiting for: {pending}. Last plan request: {last_plan}.
Recent chat:
{history}
User message: {text}"""


def llm_route(text: str, agent: str, history: str, pending: dict | None, last_plan: str, order: list[str]) -> tuple[str, dict, str, str]:
    kinds = list(calc.CALCS)
    params = "; ".join(f"{k}: {', '.join(p[0] for p in v[3])}" for k, v in calc.CALCS.items())
    pend = json.dumps({k: pending.get(k) for k in ("tool", "kind") if pending.get(k)}) if pending else "nothing"
    prompt = ROUTER_PROMPT.format(kinds=kinds, params=params, agent=AGENTS[agent][0], pending=pend,
                                  last_plan=last_plan or "none", history=history or "(none)", text=text)
    data, prov = llm.ask(prompt, want_json=True, order=order)
    tool = str(data.get("tool", "")).strip().lower()
    if tool not in TOOLS:
        raise ValueError(f"router returned {tool!r}")
    return tool, data.get("args") or {}, str(data.get("search") or ""), prov


# ------------------------------------------------------------------ answer writing
WRITER_PROMPT = """You are Nexora AI, a friendly senior civil engineer helping house builders in India (Tamil Nadu default).
Agent role: {agent_name}. {focus}
{lang}
{style}

STRICT RULES
1. Use ONLY the numbers in TOOL RESULT and SOURCES. Never invent dimensions, quantities, rates or clause numbers.
2. If TOOL RESULT lists missing details / questions, ask them clearly (numbered) and say why each is needed. Do not
   answer with assumed values.
3. Cite sources inline as [1], [2] when you use them. If the sources don't cover the question, say what is
   general good practice and suggest confirming with a qualified engineer / the local body.
4. Structural member sizes are guidance only – remind to get them confirmed by a structural engineer.
5. The app already shows cards (plan drawing, tables, forms) for the tool result – do NOT repeat whole tables;
   give a short explanation, the key numbers and practical tips. Use short paragraphs or bullets (markdown).
{project}
Recent chat:
{history}

TOOL RESULT ({tool}):
{facts}

SOURCES:
{sources}

User: {text}
Answer:"""


def _sources_block(srcs: list[dict]) -> str:
    if not srcs:
        return "(none)"
    out = []
    for s in srcs:
        where = f"{s['title']} – {s.get('ref', '')}" if s["kind"] == "kb" else f"{s['title']} (page {s.get('page') or '-'})"
        out.append(f"[{s['n']}] {where}: {s['snippet']}")
    return "\n".join(out)


def history_text(db: Session, conv: AIConversation, limit: int = 6) -> str:
    rows = (db.query(AIMessage).filter(AIMessage.conversation_id == conv.id)
            .order_by(AIMessage.id.desc()).limit(limit).all())[::-1]
    out = []
    for m in rows:
        c = re.sub(r"\s+", " ", m.content or "")[:250]
        out.append(f"{'User' if m.role == 'user' else 'Assistant'}: {c}")
    return "\n".join(out)


def project_text(p: Project | None) -> str:
    if not p:
        return "No project selected."
    unit = "m" if p.unit == "m" else "ft"
    parts = [f"Project: {p.name} ({p.code})", f"location {p.location or '-'}, {p.district or ''} {p.state}",
             f"type {p.project_type}", f"floors {p.floors}", f"spec {p.spec_level}"]
    if p.plot_width and p.plot_length:
        parts.append(f"plot {p.plot_width:g}×{p.plot_length:g} {unit}")
    if p.facing:
        parts.append(f"{p.facing} facing")
    if p.builtup_area:
        parts.append(f"built-up {p.builtup_area:g} sq ft")
    parts.append(f"progress {p.progress:g}%")
    return "Project context: " + ", ".join(parts) + "."


def last_plan_of(db: Session, conv: AIConversation) -> dict | None:
    mid = (conv.state or {}).get("last_plan_msg")
    if not mid:
        return None
    m = db.get(AIMessage, mid)
    for c in (m.cards if m else []) or []:
        if c.get("type") == "plan":
            return c.get("plan")
    return None


# ------------------------------------------------------------------ main entry
def respond(db: Session, user: User, conv: AIConversation, text: str, perms: dict | None, p: Project | None,
            form: dict | None = None, attachment: StoredFile | None = None, language: str | None = None) -> dict:
    st = dict(conv.state or {})
    settings = ai_settings(db)
    order = settings.get("provider_order") or ["gemini", "groq", "openrouter"]
    pref = {"en": "en", "ta": "ta", "ta_en": "en"}.get(settings.get("language", "ta_en"), "en")
    ln = language if language in ("en", "ta", "tanglish") else lang.detect(text, pref)
    agent = conv.agent if conv.agent in AGENTS else "general"
    pending = st.get("pending")
    hist = history_text(db, conv)
    last_plan = last_plan_of(db, conv)
    provider_used = []
    notes = []

    # 1. route
    tool, args, search = "chat", {}, text
    if form and form.get("tool") in TOOLS:
        tool, args = form["tool"], dict(form.get("args") or {})
    elif attachment is not None and attachment.original_name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) \
            and agent != "drawing" and not re.search(r"plan|drawing|layout|room|வரைபட|floor", text.lower()):
        tool = "photo"   # a site photo → AI photo check
    elif attachment is not None:
        tool = "drawing" if attachment.original_name.lower().rsplit(".", 1)[-1] in ("dxf", "png", "jpg", "jpeg", "webp", "pdf") \
            and (agent in ("drawing", "design", "vastu", "quantity") or re.search(r"plan|drawing|room|வரைபட|analy", text.lower())) \
            else "docs"
    else:
        try:
            if not any(llm.keys().values()):
                raise llm.LLMError("no keys")
            tool, args, s2, prov = llm_route(text, agent, hist, pending, st.get("last_plan_request", ""), order)
            provider_used.append(prov)
            search = s2 or text
        except Exception as e:
            log.info("router fallback: %s", e)
            tool, args = regex_route(text, agent, False, pending)
    allowed_text = text + " " + (pending or {}).get("text", "") + " " + (pending or {}).get("original", "")

    # 2. run the tool
    res: ToolResult
    try:
        if tool == "plan":
            req = args.get("request_en") if isinstance(args.get("request_en"), str) else ""
            res = tools.tool_plan(db, user, p, perms, _safe_request(req, text, pending) or text, pending, form, text,
                                  "" if req else st.get("last_plan_request", ""))
        elif tool == "estimate":
            a = _guard_params({k: args.get(k) for k in ("builtup_sqft", "floors", "bedrooms", "toilets")}, allowed_text)
            if args.get("area_basis") in ("per_floor", "total"):
                a["area_basis"] = args["area_basis"]
            req = args.get("request_en") if isinstance(args.get("request_en"), str) else ""
            res = tools.tool_estimate(db, user, p, perms, _safe_request(req, text, pending) or text, a, pending, form,
                                      last_plan, text)
        elif tool == "vastu":
            res = tools.tool_vastu(db, user, p, perms, last_plan, form)
        elif tool == "calc":
            kind = (form or {}).get("kind") or args.get("kind") or ""
            params = _guard_params(args.get("params") or {}, allowed_text)
            if not form and not params and kind:  # model gave nothing usable → try the pattern reader
                k2, p2 = calc_from_text(" " + text.lower() + " ")
                if k2 == kind:
                    params = p2
            res = tools.tool_calc(kind, params, pending, form)
        elif tool == "setback":
            a = dict((form or {}).get("answers") or {}) or _guard_params(args, allowed_text)
            if pending and pending.get("tool") == "setback":
                a = {**pending.get("args", {}), **a}
            res = tools.tool_setback(a, p)
        elif tool == "site":
            res = tools.tool_site(db, user, p, perms)
        elif tool == "photo" and attachment is not None:
            res = tools.tool_photo(db, user, p, perms, attachment, ln)
        elif tool == "drawing" and attachment is not None:
            res = tools.tool_drawing(db, user, p, perms, attachment)
        elif tool == "docs":
            res = _docs(db, p, perms, args.get("query") or search or text, attachment)
        elif tool == "chat":
            res = ToolResult("chat", facts="(conversation – no tool needed)",
                             fallback="Vanakkam! Ask me about plans, estimates, materials, site problems, Vastu or IS codes.")
        else:
            res = ToolResult("knowledge")
    except ToolDenied as e:
        res = ToolResult(tool, facts=f"ACCESS: {e}", fallback=str(e))

    # 3. sources: knowledge base (+ documents when relevant)
    srcs: list[dict] = list(res.sources)
    fixed = {"plan": ["tncdbr-setback", "nbc-rooms"], "vastu": ["vastu-basics"], "setback": ["tncdbr-setback"]}
    kb_hits: list[dict] = []
    if res.questions or tool == "chat":
        kb_hits = []
    elif tool in fixed:
        kb_hits = [e for e in tools._KB if e["id"] in fixed[tool]]
    elif tool == "calc":
        kind = next((c.get("kind") for c in res.cards if c.get("type") == "calc"), "")
        kb_hits = [e for e in tools._KB if e["id"] in CALC_KB.get(kind, [])]
    elif tool == "estimate":
        kb_hits = [e for e in tools._KB if e["id"] == "design-cost-saving"] if re.search(
            r"save|saving|reduce|cheap|budget|low cost|குறை|kammi|korai", text.lower()) else []
    elif tool in ("knowledge", "site", "drawing", "docs", "photo"):
        cat = AGENTS[agent][3] if AGENTS[agent][3] in ("code", "material", "site", "vastu", "design") else None
        kb_hits = [e for e in tools.kb_search(search or text, k=4 if tool == "knowledge" else 2, category=cat)
                   if tool == "knowledge" or e["score"] >= 4]
    for e in kb_hits:
        srcs.append({"kind": "kb", "title": e["title"], "ref": e["source"], "snippet": e["text"][:600],
                     "category": e["category"], "id": e["id"]})
    if tool == "knowledge" and p and (perms is None or perms.get("view")):
        try:
            for h in docs.search(db, p.id, search or text, k=3):
                if h["score"] >= 0.03:
                    srcs.append({"kind": "doc", "title": h["name"], "file_id": h["file_id"], "page": h["page"],
                                 "snippet": h["text"][:900]})
        except Exception as e:
            log.info("doc search skipped: %s", e)
    for i, s in enumerate(srcs, 1):
        s["n"] = i
    if tool == "knowledge" and not srcs:
        res.facts = "No matching entry in the knowledge base or project documents."
        res.fallback = ("I couldn't find this in the built-in knowledge or your project documents. "
                        "Please add more detail, or upload the document under Projects → Docs.")
    elif tool == "knowledge":
        res.facts = "Answer from the sources below."
        res.fallback = "\n\n".join(f"**{s['title']}** [{s['n']}]\n{s['snippet']}" for s in srcs[:2])

    # 4. write the answer
    style = ("Keep it short (under 120 words)." if settings.get("response_style") == "short"
             else "Be clear and complete but concise (under 260 words unless a step list needs more).")
    if res.questions:
        style = "Ask only the missing questions (numbered) in 2–5 short lines; mention what you understood."
    prompt = WRITER_PROMPT.format(
        agent_name=AGENTS[agent][0], focus=AGENT_FOCUS[agent], lang=lang.instruction(ln), style=style,
        project=project_text(p) if settings.get("use_project_context", True) else "", history=hist or "(none)",
        tool=res.tool, facts=res.facts or "(none)", sources=_sources_block(srcs), text=text)
    content = ""
    try:
        if not any(llm.keys().values()):
            raise llm.LLMError("No AI keys in .env")
        content, prov = llm.ask(prompt, want_json=False, temperature=0.3, order=order, min_chars=20)
        content = str(content).strip()
        provider_used.append(prov)
    except Exception as e:
        log.warning("AI writer failed: %s", e)
        why = str(e).replace("All AI providers failed: ", "")
        if "No AI keys" in why:
            why = "no AI keys in .env"
        elif re.search(r"\b429\b|rate|quota|RESOURCE_EXHAUSTED", why, re.I):
            why = "free AI limit reached for now – try again in a minute"
        elif re.search(r"\b40[13]\b|API key|invalid", why, re.I):
            why = "an AI key in .env is invalid – check Settings → AI Preferences"
        else:
            why = why[:160]
        notes.append(f"AI service not reachable ({why}) – showing Nexora's calculated result.")
        content = res.fallback or res.facts or "Sorry, I could not answer that right now."
    if not content:
        content = res.fallback or "Sorry, I could not answer that right now."

    # 5. conversation state
    st.update(res.state)
    if res.pending:
        st["pending"] = res.pending
    elif tool not in ("chat", "knowledge") or not pending:
        st.pop("pending", None)
    shown = [s for s in srcs if settings.get("show_sources", True)]
    return {"content": content, "cards": res.cards, "sources": shown, "tool": res.tool, "language": ln,
            "provider": provider_used[-1] if provider_used else "", "chips": res.chips, "notes": notes,
            "state": st}


def _safe_request(req: str, original: str, pending: dict | None) -> str:
    """The model's English rewrite of a plan request may only contain details the user really gave."""
    if not req:
        return ""
    said = (original + " " + (pending or {}).get("text", "") + " " + (pending or {}).get("original", "")).lower()
    if any(n not in _numbers(said) for n in _numbers(req)):
        return ""
    checks = [  # (phrase in the rewrite, words that must appear in what the user said)
        (r"\d+(?:\.\d+)?\s*(?:ft|feet|foot|m|mtr|meters?|metres?)?\s*(?:wide\s*)?road|road\s*(?:width)?\s*(?:is|of|:)?\s*\d+(?:\.\d+)?\s*(?:ft|feet|m)?",
         r"road|rd\b|street|ரோடு|சாலை|தெரு|theru|\d+\s*(?:ft|feet|')\s*(?:wide)?\s*$"),
        (r"\b(?:north|south)?-?\s*(?:east|west|north|south)[- ]?facing|\bfacing\s+(?:north|south|east|west)(?:-(?:east|west))?",
         r"east|west|north|south|kizhakku|merku|vadakku|therku|கிழக்கு|மேற்கு|வடக்கு|தெற்கு"),
        (r"\d+\s*(?:bhk|bed\s*rooms?|bedrooms?)", r"bhk|bed|room|படுக்கை|அறை|rooms?"),
        (r"\b(?:g|ground|stilt)\s*\+\s*\d|ground floor only|single floor|duplex",
         r"g\s*\+|ground|floor|maadi|மாடி|தளம்|duplex|stilt|single"),
        (r"\d+\s*(?:toilets?|bathrooms?)", r"toilet|bath|கழிவறை|குளியல்"),
    ]
    for phrase, need_words in checks:
        if re.search(phrase, req, re.I) and not re.search(need_words, said, re.I):
            req = re.sub(phrase, "", req, flags=re.I)
    return req


def _docs(db: Session, p: Project | None, perms: dict | None, query: str, attachment: StoredFile | None) -> ToolResult:
    if not p:
        q = "Choose a project first – Document Q&A searches that project's uploaded documents."
        return ToolResult("docs", facts=q, fallback=q, questions=[q])
    tools.need(perms, "view")
    info = docs.ensure_indexed(db, p.id)
    hits = docs.search(db, p.id, query, k=5, file_ids=[attachment.id] if attachment else None)
    if not hits:
        msg = ("No matching text in this project's documents." if info["indexed"] else
               "This project has no readable documents yet (PDF with text, Word, Excel, CSV or TXT). "
               "Upload them in Projects → Docs or with the attach button.")
        return ToolResult("docs", facts=msg, fallback=msg)
    srcs = [{"kind": "doc", "title": h["name"], "file_id": h["file_id"], "page": h["page"], "snippet": h["text"][:1200]}
            for h in hits]
    return ToolResult("docs", facts=f"Search in {info['indexed']} indexed document(s) for: {query}. Use the sources.",
                      sources=srcs, fallback="\n\n".join(f"**{h['name']}** (page {h['page'] or '-'})\n{h['text'][:500]}"
                                                         for h in hits[:2]))


def title_from(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return (t[:70] + "…") if len(t) > 70 else (t or "New conversation")
