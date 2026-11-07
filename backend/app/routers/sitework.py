"""1.19 Site work tools built from the ACTIVE drawing:
  • Site marking guide (16)            GET  /projects/{pid}/site-marking  (+ .pdf),  PUT /projects/{pid}/site-data/levels
  • Change requests / variations (17)  GET/POST /projects/{pid}/variations, POST …/impact, POST …/{no}/decision, GET …/{no}/pdf
  • Steel cutting optimiser (18)       POST /projects/{pid}/steel-cutting  (+ /pdf)
  • RWH / sump / septic (19)           GET  /projects/{pid}/services (+ .pdf), PUT /projects/{pid}/site-data/services,
                                       POST /projects/{pid}/services/approval
  • Handover pack (21)                 GET  /projects/{pid}/handover, PUT /projects/{pid}/site-data/handover, GET …/handover.pdf
Inputs live in projects.site_data (one JSON, additive). Nothing is deleted: a rejected variation stays in the list."""
from __future__ import annotations

import copy
import re
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..audit import log_action
from ..db import get_db
from ..design.edit import recompute
from ..estimate.rates_seed import DEFAULT_STATE
from ..models import BbsSchedule, Design, Project, StructuralDesign, User
from ..security import get_current_user, project_permissions, require_project
from .design import _proj, active_design
from .estimate import rates_dict, rates_for

router = APIRouter(prefix="/api", tags=["site-work"])
SECTIONS = ("levels", "services", "handover")


def _need(db: Session, user: User, pid: int, *mods: str) -> Project:
    p = require_project(db, user, pid, "view")
    perms = project_permissions(db, user, p)
    if not any(perms.get(m) for m in mods):
        raise HTTPException(403, f"You need {' / '.join(mods)} access on this project")
    return p


def _sd(p: Project) -> dict:
    return copy.deepcopy(p.site_data or {})


def _save_sd(db: Session, p: Project, sd: dict) -> None:
    p.site_data = sd
    flag_modified(p, "site_data")
    db.commit()


def _plan(db: Session, p: Project) -> tuple[Design, dict]:
    d = active_design(db, p)
    if not d:
        raise HTTPException(404, "No drawing yet – make or upload a floor plan in Design and press 'Use everywhere'.")
    return d, recompute(d.plan)


def _struct(db: Session, p: Project, d: Design) -> dict | None:
    s = (db.query(StructuralDesign).filter(StructuralDesign.project_id == p.id, StructuralDesign.design_id == d.id,
                                           StructuralDesign.is_hidden.is_(False)).order_by(StructuralDesign.id.desc()).first())
    return s.result if s else None


def _rates(db: Session, p: Project) -> dict:
    _used, _fb, rows = rates_for(db, p.state or DEFAULT_STATE)
    rd = rates_dict(rows)
    from ..market import apply_market
    apply_market(db, rd, p.id)
    return rd


def _file(data: bytes, name: str) -> Response:
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


class SectionIn(BaseModel):
    values: dict


@router.put("/projects/{project_id}/site-data/{section}")
def put_section(project_id: int, section: str, body: SectionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if section not in SECTIONS:
        raise HTTPException(404, "Unknown section")
    p = _need(db, user, project_id, "site", "design")
    sd = _sd(p)
    cur = sd.get(section) or {}
    for k, v in body.values.items():
        if v in (None, ""):
            cur.pop(k, None)  # back to the automatic value
        else:
            cur[k] = v
    sd[section] = cur
    _save_sd(db, p, sd)
    log_action(db, user, "updated", "site_data", p.id, f"{section}: {', '.join(body.values)[:150]}", project_id=p.id)
    return cur


# ================================================================ 16 site marking
@router.get("/projects/{project_id}/site-marking")
def site_marking(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "site", "design")
    from ..site import marking
    d, plan = _plan(db, p)
    return {"design": {"id": d.id, "title": d.title, "version": d.version},
            "has_structure": _struct(db, p, d) is not None,
            "guide": marking.build(plan, _sd(p).get("levels"), _struct(db, p, d))}


@router.get("/projects/{project_id}/site-marking.pdf")
def site_marking_pdf(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "site", "design")
    from ..site import marking
    d, plan = _plan(db, p)
    g = marking.build(plan, _sd(p).get("levels"), _struct(db, p, d))
    return _file(marking.pdf(plan, g, _proj(p, db)), f"{p.code}_Site_Marking_Guide.pdf")


# ================================================================ 19 services
def _services(db, p):
    from ..site import services
    _d, plan = _plan(db, p)
    sd = _sd(p)
    res = services.size(plan, sd.get("services"), _rates(db, p), p.spec_level or "standard")
    res["approval"] = sd.get("services_approval") or {"status": "pending"}
    return plan, res


@router.get("/projects/{project_id}/services")
def get_services(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "site", "design", "estimate")
    return _services(db, p)[1]


@router.get("/projects/{project_id}/services.pdf")
def services_pdf(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "site", "design", "estimate")
    from ..site import services
    plan, res = _services(db, p)
    return _file(services.pdf(plan, res, _proj(p, db), res["approval"]), f"{p.code}_Water_Services.pdf")


class ApprovalIn(BaseModel):
    status: str  # approved | pending
    by: str = ""
    note: str = ""


@router.post("/projects/{project_id}/services/approval")
def services_approval(project_id: int, body: ApprovalIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "site", "design")
    if body.status not in ("approved", "pending"):
        raise HTTPException(400, "status must be approved or pending")
    if body.status == "approved" and not body.by.strip():
        raise HTTPException(400, "Who approved it? (client name)")
    sd = _sd(p)
    sd["services_approval"] = {"status": body.status, "by": body.by.strip()[:120], "note": body.note.strip()[:300],
                               "date": date.today().isoformat(), "recorded_by": user.full_name or user.username}
    _save_sd(db, p, sd)
    log_action(db, user, "updated", "services", p.id, f"Water services {body.status} {body.by}", project_id=p.id)
    return sd["services_approval"]


# ================================================================ 18 steel cutting
class CutIn(BaseModel):
    bbs_id: int | None = None
    rows: list[dict] | None = None
    stock_mm: int = 12000
    kerf_mm: int = 5
    reuse_min_mm: int = 1000


def _cut(db, p, body: CutIn):
    from ..cutting import optimise
    title = "BBS on screen"
    rows = body.rows
    if body.bbs_id:
        b = db.get(BbsSchedule, body.bbs_id)
        if not b or b.is_hidden or b.project_id != p.id:
            raise HTTPException(404, "BBS not found")
        rows, title = (b.result or {}).get("rows", []), b.title
    if not rows:
        raise HTTPException(422, {"message": "Choose a saved BBS (or make one first)", "questions": ["Which BBS?"]})
    if not (6000 <= body.stock_mm <= 13000):
        raise HTTPException(400, "Stock bar length must be 6000–13000 mm")
    st = _rates(db, p).get("steel")
    rate = float(st[p.spec_level or "standard"]) if st else None
    return optimise(rows, body.stock_mm, max(0, body.kerf_mm), max(300, body.reuse_min_mm), rate), title


@router.post("/projects/{project_id}/steel-cutting")
def steel_cutting(project_id: int, body: CutIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "estimate", "design", "site")
    return _cut(db, p, body)[0]


@router.post("/projects/{project_id}/steel-cutting/pdf")
def steel_cutting_pdf(project_id: int, body: CutIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "estimate", "design", "site")
    from ..cutting import pdf
    res, title = _cut(db, p, body)
    return _file(pdf(res, _proj(p, db), title), f"{p.code}_Steel_Cutting_Plan.pdf")


# ================================================================ 17 change requests / variations
class Line(BaseModel):
    desc: str
    qty: float = 0
    unit: str = ""
    rate: float | None = None  # None → from the rate library (code)
    code: str = ""
    sign: int = 1  # +1 extra work, −1 omitted work


class ImpactIn(BaseModel):
    lines: list[Line] = []
    from_design_id: int | None = None  # compare two drawings (auto cost + time)
    to_design_id: int | None = None
    days: int | None = None  # manual time impact


class VariationIn(ImpactIn):
    title: str
    reason: str = ""
    requested_by: str = ""


def _impact(db, p, body: ImpactIn) -> dict:
    rates = _rates(db, p)
    spec = p.spec_level or "standard"
    lines, notes = [], []
    for ln in body.lines:
        rate = ln.rate
        unit = ln.unit
        if rate is None and ln.code:
            r = rates.get(ln.code)
            if not r:
                raise HTTPException(400, f"Rate code '{ln.code}' is not in your rate library")
            rate, unit = float(r[spec]), unit or r["unit"]
        if rate is None:
            raise HTTPException(422, {"message": "Rate needed", "questions": [f"Rate for '{ln.desc}' (or pick an item from the rate library)"]})
        sign = -1 if ln.sign < 0 else 1
        lines.append({"desc": ln.desc[:200], "qty": ln.qty, "unit": unit, "rate": rate, "code": ln.code, "sign": sign,
                      "amount": round(sign * ln.qty * rate, 2), "auto": False})
    auto_days = 0
    if body.from_design_id and body.to_design_id:
        from .design import quick_estimate
        ds = []
        for did in (body.from_design_id, body.to_design_id):
            d = db.get(Design, did)
            if not d or d.project_id != p.id or d.is_hidden:
                raise HTTPException(404, "Drawing not found")
            ds.append((d, quick_estimate(db, recompute(d.plan), spec, p.state or DEFAULT_STATE, p.structure_type or "rcc_framed")))
        (d0, a), (d1, b) = ds
        diff = b["totals"]["grand_total"] - a["totals"]["grand_total"]
        lines.append({"desc": f"Drawing change: {d0.title} v{d0.version} → {d1.title} v{d1.version} "
                              f"({a['totals']['builtup_sqft']:g} → {b['totals']['builtup_sqft']:g} sq ft)",
                      "qty": 1, "unit": "LS", "rate": round(diff, 2), "code": "", "sign": 1, "amount": round(diff, 2), "auto": True})
        auto_days = round((b["totals"].get("duration_months", 0) - a["totals"].get("duration_months", 0)) * 30)
        if auto_days == 0 and abs(diff) > 0:
            # same rounded months: share of the project time in proportion to the cost change
            auto_days = round(a["totals"].get("duration_months", 0) * 30 * diff / max(1.0, a["totals"]["grand_total"]))
        notes.append("Cost difference from the full estimate of both drawings (your rate library).")
    total = round(sum(x["amount"] for x in lines), 2)
    days = body.days if body.days is not None else auto_days
    return {"lines": lines, "total": total, "days": days, "days_source": "manual" if body.days is not None else "auto", "notes": notes}


@router.post("/projects/{project_id}/variations/impact")
def variation_impact(project_id: int, body: ImpactIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "estimate", "site", "design")
    return _impact(db, p, body)


@router.get("/projects/{project_id}/variations")
def list_variations(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "estimate", "site", "design")
    vs = _sd(p).get("variations") or []
    appr = [v for v in vs if v.get("status") == "approved"]
    return {"items": vs[::-1], "approved_total": round(sum(v["total"] for v in appr), 2),
            "approved_days": sum(v.get("days") or 0 for v in appr), "pending": sum(1 for v in vs if v.get("status") == "pending")}


@router.post("/projects/{project_id}/variations")
def add_variation(project_id: int, body: VariationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "estimate", "site", "design")
    if not body.title.strip():
        raise HTTPException(400, "Give the change a short title")
    imp = _impact(db, p, body)
    sd = _sd(p)
    vs = sd.get("variations") or []
    no = max([v["no"] for v in vs] or [0]) + 1
    v = {"no": no, "title": body.title.strip()[:150], "reason": body.reason.strip()[:500], "requested_by": body.requested_by.strip()[:120],
         "date": date.today().isoformat(), "status": "pending", **imp, "created_by": user.full_name or user.username}
    vs.append(v)
    sd["variations"] = vs
    _save_sd(db, p, sd)
    log_action(db, user, "created", "variation", p.id, f"VO-{no} {v['title']}: ₹{v['total']:,.0f}, {v['days']} days", project_id=p.id)
    return v


class DecisionIn(BaseModel):
    status: str  # approved | rejected | pending
    by: str = ""
    note: str = ""


@router.post("/projects/{project_id}/variations/{no}/decision")
def decide_variation(project_id: int, no: int, body: DecisionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "estimate", "site", "design")
    if body.status not in ("approved", "rejected", "pending"):
        raise HTTPException(400, "status must be approved, rejected or pending")
    if body.status != "pending" and not body.by.strip():
        raise HTTPException(400, "Who decided? (client name)")
    sd = _sd(p)
    v = next((x for x in sd.get("variations") or [] if x["no"] == no), None)
    if not v:
        raise HTTPException(404, "Change request not found")
    v.update({"status": body.status, "decided_by": body.by.strip()[:120], "decision_note": body.note.strip()[:300],
              "decided_on": date.today().isoformat(), "recorded_by": user.full_name or user.username})
    _save_sd(db, p, sd)
    log_action(db, user, "updated", "variation", p.id, f"VO-{no} {body.status} by {body.by}", project_id=p.id)
    return v


@router.get("/projects/{project_id}/variations/{no}/pdf")
def variation_pdf(project_id: int, no: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "estimate", "site", "design")
    v = next((x for x in _sd(p).get("variations") or [] if x["no"] == no), None)
    if not v:
        raise HTTPException(404, "Change request not found")
    from ..site.pdfdoc import Doc
    d = Doc(f"Variation / Change Request VO-{no:03d}", _proj(p, db), f"{v['title']} · raised {v['date']}")
    d.table(["", ""], [["Requested by", v.get("requested_by") or "-"], ["Reason", v.get("reason") or "-"],
                       ["Status", v["status"].title() + (f" by {v['decided_by']} on {v['decided_on']}" if v.get("decided_by") else "")]], [25, 75], zebra=False)
    d.h("Cost impact")
    d.table(["Item", "Qty", "Unit", "Rate ₹", "Amount ₹"],
            [[("(omitted) " if x["sign"] < 0 else "") + x["desc"], f"{x['qty']:g}", x["unit"], f"{x['rate']:,.2f}", f"{x['amount']:,.0f}"] for x in v["lines"]]
            + [["Net change in cost", "", "", "", f"{v['total']:,.0f}"]], [50, 10, 10, 15, 15], bold_last=True)
    d.h("Time impact")
    d.para(f"{v['days']:+d} days to the completion date ({v.get('days_source', 'manual')}).")
    for n in v.get("notes", []):
        d.para(n, True)
    d.h("Client approval")
    d.para("The change above, its cost and its effect on the completion date are accepted:")
    d.signatures(["Client", "Contractor / site engineer"])
    return _file(d.build(), f"{p.code}_VO-{no:03d}.pdf")


# ================================================================ 21 handover pack
MAINTENANCE = [
    ("Terrace waterproofing & outlets", "Clean outlets, check cracks / joints", "Before every monsoon (May–June) and after heavy rain"),
    ("Rain water harvesting well", "Remove silt, wash / replace filter media", "Every year before the monsoon"),
    ("Sump & overhead tank", "Empty, clean, disinfect (bleaching powder)", "Every 6 months"),
    ("Septic tank", "Desludge (licensed operator)", "Every 1–2 years"),
    ("Drain chambers & gully traps", "Clear, check covers", "Every 6 months"),
    ("Exterior paint", "Repaint; check for damp patches", "Every 5–6 years"),
    ("Interior paint", "Repaint", "Every 5–7 years"),
    ("Doors & windows", "Oil hinges, check locks, sealant around frames", "Every year"),
    ("Electrical", "Check earthing pit (water it), MCB / RCCB test button", "Every year"),
    ("Plumbing", "Check leaks under sinks, clean aerators, motor service", "Every year"),
    ("Anti-termite", "Inspect skirting / wood; re-treat if needed", "Every 3–5 years"),
    ("Sealant / grout in toilets", "Re-grout / re-seal joints", "Every 2–3 years"),
]


def _brands(db, p) -> list[dict]:
    from ..models import MarketBrand, MarketVariant
    out = []
    for cat, vid in (p.brand_choices or {}).items():
        v = db.get(MarketVariant, int(vid)) if vid else None
        if not v:
            continue
        b = db.get(MarketBrand, v.brand_id)
        out.append({"category": cat, "brand": b.name if b else "", "variant": v.name})
    return out


@router.get("/projects/{project_id}/handover")
def handover(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "site", "design")
    h = _sd(p).get("handover") or {}
    brands = _brands(db, p)
    w = h.get("warranties")
    if not w:  # start from the brands used – years / contact are filled in by the team
        w = [{"item": x["category"], "brand": f"{x['brand']} {x['variant']}".strip(), "years": "", "from": "", "contact": ""} for x in brands]
    return {"handover": {**h, "warranties": w}, "brands": brands, "maintenance": [{"item": a, "what": b, "when": c} for a, b, c in MAINTENANCE],
            "has_design": active_design(db, p) is not None}


@router.get("/projects/{project_id}/handover.pdf")
def handover_pdf(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "site", "design")
    info = handover(project_id, user, db)
    h = info["handover"]
    proj = _proj(p, db)
    from ..site.pdfdoc import Doc
    d = Doc("Handover Pack", proj, f"Owner: {p.client_name or '-'} · Handed over on {h.get('date') or '____________'}")
    d.h("1. Building")
    dsg = active_design(db, p)
    if dsg:
        plan = recompute(dsg.plan)
        s = plan["summary"]
        d.table(["", ""], [["As-built drawing", f"{dsg.title} v{dsg.version} (sheets attached at the end)"],
                           ["Plot", f"{plan['plot']['w']:g} × {plan['plot']['d']:g} ft, {plan['facing'].title()} facing"],
                           ["Floors / built-up", f"{len(plan['levels'])} floor(s), {s['builtup_sqft']:,.0f} sq ft"],
                           ["Rooms", f"{s['bedrooms']} bedrooms, {s['toilets']} toilets, {s['kitchens']} kitchen(s)"]], [30, 70], zebra=False)
        if h.get("as_built_notes"):
            d.para("Changes made during construction (as-built): " + h["as_built_notes"])
    d.h("2. Materials & brands used")
    if info["brands"]:
        d.table(["Material", "Brand", "Product / variant"], [[x["category"], x["brand"], x["variant"]] for x in info["brands"]], [30, 30, 40])
    else:
        d.para("No brands recorded – pick them in the Material Library for this project.", True)
    d.h("3. Warranties")
    d.table(["Item", "Brand / product", "Warranty", "From", "Service contact"],
            [[x.get("item", ""), x.get("brand", ""), f"{x['years']} yr" if x.get("years") else "____", x.get("from") or "____", x.get("contact") or "____"]
             for x in h["warranties"]] or [["-", "", "", "", ""]], [22, 30, 12, 14, 22])
    d.h("4. Water & drainage")
    try:
        _plan_, sv = _services(db, p)
        d.bullets([f"Sump {sv['sump']['litres']:,} L, overhead tank {sv['oht']['litres']:,} L",
                   f"Rain water harvesting: {sv['rwh']['wells']} well(s)"] +
                  ([f"Septic tank {sv['septic']['inner_l_m']} × {sv['septic']['inner_b_m']} m – desludge every 1–2 years"] if sv["septic"]["needed"] else []) +
                  [f"{x['item']}: {x['x']:.1f} ft from left, {x['y']:.1f} ft from front" for x in sv.get("positions", [])])
    except HTTPException:
        d.para("-")
    d.h("5. Maintenance calendar")
    d.table(["Item", "What to do", "When"], [[m["item"], m["what"], m["when"]] for m in info["maintenance"]], [28, 40, 32])
    if h.get("keys"):
        d.h("6. Keys & documents handed over")
        d.para(h["keys"])
    d.h("Handing over")
    d.signatures(["Owner (received)", "Contractor (handed over)"])
    data = d.build()
    if dsg:  # attach the drawing set
        try:
            import io as _io

            from pypdf import PdfReader, PdfWriter

            from ..design.sheets import sheet_set_pdf
            sheets = sheet_set_pdf(recompute(dsg.plan), proj, {"version": dsg.version, "date": dsg.created_at.strftime("%d-%m-%Y")})
            w = PdfWriter()
            for src in (data, sheets):
                for pg in PdfReader(_io.BytesIO(src)).pages:
                    w.add_page(pg)
            buf = _io.BytesIO()
            w.write(buf)
            data = buf.getvalue()
        except Exception:  # the pack is still useful without the sheets
            pass
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", p.code)
    return _file(data, f"{safe}_Handover_Pack.pdf")
