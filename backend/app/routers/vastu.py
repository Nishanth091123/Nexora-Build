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
from ..models import Design, User, VastuReport
from ..security import get_current_user
from ..vastu import engine, report
from .design import require_any

router = APIRouter(prefix="/api", tags=["vastu"])


class VastuIn(BaseModel):
    design_id: int | None = None
    plan: dict | None = None
    north_deg: float | None = None


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
    return {"plan": plan, "result": engine.analyse(plan)}


@router.post("/projects/{project_id}/vastu/apply")
def apply(project_id: int, body: VastuIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Suggest an improved plan by swapping rooms. Nothing is saved until the user saves it as a design version."""
    require_any(db, user, project_id, ("vastu",))
    plan, _ = _plan(db, project_id, body)
    out = engine.improve(plan)
    if not out["changes"]:
        out["message"] = ("No safe room swap improves this plan automatically – follow the room-wise suggestions "
                          "in the 2D editor (sizes or doors would break otherwise).")
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
    res = engine.analyse(plan)
    r = VastuReport(project_id=project_id, design_id=d.id if d else None, design_version=d.version if d else 0,
                    north_deg=float(plan.get("north_deg") or 0), summary=res["summary"], result=res, plan=plan,
                    created_by=user.id)
    db.add(r)
    db.commit()
    log_action(db, user, "created", "vastu report", r.id,
               f"{res['summary']['matched']} of {res['summary']['total']} rules matched", project_id=project_id)
    return report_out(r) | {"result": res}


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
