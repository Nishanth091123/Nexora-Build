"""Phase 4 – Vastu Intelligence: analyse a design, apply suggestions, saved reports + PDF."""
import copy
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..design.edit import PlanError, recompute
from ..models import AppSetting, Design, User, VastuReport
from ..security import get_current_user, require_owner
from ..vastu import engine, report
from .design import require_any

router = APIRouter(prefix="/api", tags=["vastu"])


class VastuIn(BaseModel):
    design_id: int | None = None
    plan: dict | None = None
    north_deg: float | None = None
    lang: str = "en"  # 1.16: "ta" = Tamil text


# ---------------------------------------------------------------- 1.16 site answers (per project) + owner's own rules
def site_of(db: Session, project_id: int) -> dict:
    row = db.get(AppSetting, f"vastu_site:{project_id}")
    return dict(row.value or {}) if row else {}


def rules_of(db: Session) -> dict:
    row = db.get(AppSetting, "vastu_rules")
    return dict(row.value or {}) if row else {}


def _kw(db: Session, project_id: int) -> dict:
    return {"site": site_of(db, project_id), "rules": rules_of(db)}


@router.get("/projects/{project_id}/vastu/site")
def get_site(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_any(db, user, project_id, ("vastu",))
    from ..vastu.more import SITE_FIELDS
    return {"site": site_of(db, project_id),
            "fields": [{"key": k, "question": en, "question_ta": ta, "kind": kind, "options": opts} for k, en, ta, kind, opts in SITE_FIELDS]}


@router.put("/projects/{project_id}/vastu/site")
def put_site(project_id: int, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Details that are not in the drawing (sump, borewell, gate, plot cut, T-junction …) – answered by you."""
    require_any(db, user, project_id, ("vastu",))
    from ..vastu.more import SITE_FIELDS
    allowed = {k: (kind, opts) for k, _, _, kind, opts in SITE_FIELDS}
    clean = {}
    for k, v in (body or {}).items():
        if k not in allowed or v in (None, ""):
            continue
        kind, opts = allowed[k]
        if kind == "multi":
            if isinstance(v, list):
                clean[k] = [x for x in v if x in opts]
        elif v in opts:
            clean[k] = v
    row = db.get(AppSetting, f"vastu_site:{project_id}")
    if not row:
        row = AppSetting(key=f"vastu_site:{project_id}", value={})
        db.add(row)
    row.value = clean
    db.commit()
    log_action(db, user, "updated", "vastu site", project_id, ", ".join(f"{k}={v}" for k, v in clean.items())[:500],
               project_id=project_id)
    return {"site": clean}


@router.get("/vastu/rules")
def get_rules(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Built-in rules + the owner's own preferred zones (if set)."""
    own = rules_of(db)
    return {"rules": [{"key": k, "title": t, "good": sorted(g), "ok": sorted(o), "avoid": sorted(b), "why": w,
                       "own": own.get(k)} for k, t, _, g, o, b, w in engine.RULES], "own": own}


@router.put("/vastu/rules")
def put_rules(body: dict, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    """Owner only: {rule key: {good: [zones], ok: [zones]}} – everything else becomes 'avoid'. {} = back to built-in."""
    zones = set(engine.ZONES) | {"C"}
    keys = {r[0] for r in engine.RULES}
    clean = {}
    for k, v in (body or {}).items():
        if k in keys and isinstance(v, dict):
            g = [z for z in v.get("good", []) if z in zones]
            if g:
                clean[k] = {"good": g, "ok": [z for z in v.get("ok", []) if z in zones and z not in g]}
    row = db.get(AppSetting, "vastu_rules")
    if not row:
        row = AppSetting(key="vastu_rules", value={})
        db.add(row)
    row.value = clean
    db.commit()
    log_action(db, owner, "updated", "settings", "vastu_rules", ", ".join(clean) or "built-in rules")
    return {"own": clean}


def _plan(db: Session, project_id: int, body: VastuIn) -> tuple[dict, Design | None]:
    d = None
    if body.design_id:
        d = db.get(Design, body.design_id)
        if not d or d.project_id != project_id:
            raise HTTPException(404, "Design not found")
        plan = copy.deepcopy(d.plan)
    elif body.plan:
        try:
            plan = recompute(copy.deepcopy(body.plan))
        except PlanError as e:
            raise HTTPException(422, {"message": str(e), "questions": [str(e)]})
    else:
        raise HTTPException(422, {"message": "Choose a design or upload a drawing first", "questions": []})
    if body.north_deg is not None:
        engine.set_north(plan, body.north_deg)
    elif "north_deg" not in plan:
        plan["north_deg"] = engine.north_of(plan["compass"])
    return plan, d


@router.post("/projects/{project_id}/vastu/analyse")
def analyse(project_id: int, body: VastuIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_any(db, user, project_id, ("vastu",))
    plan, _ = _plan(db, project_id, body)
    return {"plan": plan, "result": engine.analyse(plan, lang=body.lang, **_kw(db, project_id))}


@router.post("/projects/{project_id}/vastu/options")
def options(project_id: int, body: VastuIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """1.16: 2–3 improved plan options with scores, to compare side by side. Nothing is saved here."""
    require_any(db, user, project_id, ("vastu",))
    plan, _ = _plan(db, project_id, body)
    out = engine.options_for_vastu(plan, **_kw(db, project_id))
    if not out["options"]:
        out["message"] = ("No better arrangement was found for this building size and room list – the room-wise "
                          "remedies and the door pada advice are the next steps.")
    return out


@router.post("/projects/{project_id}/vastu/apply")
def apply(project_id: int, body: VastuIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Suggest an improved plan by swapping rooms. Nothing is saved until the user saves it as a design version."""
    require_any(db, user, project_id, ("vastu",))
    plan, _ = _plan(db, project_id, body)
    out = engine.best_for_vastu(plan, **_kw(db, project_id))
    if not out["changes"]:
        if out["after"].get("not_matched", 0) == 0:
            out["message"] = "This plan already follows the Vastu rules – nothing needs to change."
        else:
            out["message"] = ("This is already the best Vastu arrangement for this building size and room list. "
                              "The remaining points need a bigger change (for example fewer rooms, another floor "
                              "or a different plot) – see the room-wise suggestions.")
    return out


class SaveIn(VastuIn):
    pass


def report_out(r: VastuReport) -> dict:
    return {"id": r.id, "project_id": r.project_id, "design_id": r.design_id, "design_version": r.design_version,
            "north_deg": r.north_deg, "summary": r.summary, "created_at": r.created_at.isoformat()}


@router.post("/projects/{project_id}/vastu/reports")
def save_report(project_id: int, body: SaveIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_any(db, user, project_id, ("vastu",))
    plan, d = _plan(db, project_id, body)
    res = engine.analyse(plan, **_kw(db, project_id))
    r = VastuReport(project_id=project_id, design_id=d.id if d else None, design_version=d.version if d else 0,
                    north_deg=float(plan.get("north_deg") or 0), summary=res["summary"], result=res, plan=plan,
                    created_by=user.id)
    db.add(r)
    db.commit()
    log_action(db, user, "created", "vastu report", r.id,
               f"{res['summary']['matched']} of {res['summary']['total']} rules matched", project_id=project_id)
    return report_out(r) | {"result": res}


@router.post("/projects/{project_id}/vastu/report-pdf")
def report_pdf_now(project_id: int, body: SaveIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """1.13: the report for what is on the screen – downloaded without saving a report first."""
    p = require_any(db, user, project_id, ("vastu",))
    plan, d = _plan(db, project_id, body)
    kw = _kw(db, project_id)
    res = engine.analyse(plan, **kw)
    best = engine.options_for_vastu(plan, **kw)["options"]
    meta = {"version": d.version if d else "-", "date": datetime.now().strftime("%d %b %Y"), "code": p.code,
            "client": p.client_name or "", "location": p.location or ""}
    data = report.to_pdf(plan, res, {"name": p.name}, meta, best[0] if best else None)
    name = f"{p.code}_{p.name}_Vastu_Report.pdf".replace(" ", "_")
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.post("/projects/{project_id}/vastu/report-html")
def report_html(project_id: int, body: SaveIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """1.16: printable report in Tamil or English (the browser prints Tamil letters correctly → Save as PDF)."""
    p = require_any(db, user, project_id, ("vastu",))
    plan, d = _plan(db, project_id, body)
    kw = _kw(db, project_id)
    res = engine.analyse(plan, lang=body.lang, **kw)
    best = engine.options_for_vastu(plan, **kw)["options"]
    meta = {"version": d.version if d else "-", "date": datetime.now().strftime("%d %b %Y"), "code": p.code,
            "client": p.client_name or "", "location": p.location or ""}
    from ..vastu import report_html as RH
    return Response(RH.html(plan, res, {"name": p.name}, meta, best[0] if best else None, body.lang),
                    media_type="text/html; charset=utf-8")


@router.get("/projects/{project_id}/vastu/reports")
def list_reports(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_any(db, user, project_id, ("vastu",))
    rows = (db.query(VastuReport).filter(VastuReport.project_id == project_id, VastuReport.is_hidden.is_(False))
            .order_by(VastuReport.id.desc()).limit(50).all())
    return [report_out(r) for r in rows]


@router.get("/vastu/reports/{report_id}/pdf")
def report_pdf(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(VastuReport, report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    p = require_any(db, user, r.project_id, ("vastu",))
    data = report.to_pdf(r.plan, r.result, {"name": p.name}, {"version": r.design_version or "-",
                                                             "date": datetime.now().strftime("%d %b %Y")})
    name = f"{p.code}_Vastu_Report_{r.id}.pdf"
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
