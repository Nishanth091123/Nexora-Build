"""1.12 – Structural design API (preliminary RCC design from a saved design)."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..design.edit import recompute
from ..models import Design, StructuralDesign, User
from ..security import get_current_user
from ..structural import engine, sheets
from .design import _proj, require_any

router = APIRouter(prefix="/api", tags=["structural"])


class CalcIn(BaseModel):
    design_id: int
    inputs: dict = {}
    title: str = ""


def _design(db: Session, pid: int, design_id: int) -> Design:
    d = db.get(Design, design_id)
    if not d or d.project_id != pid or d.is_hidden:
        raise HTTPException(404, "Design not found – save the floor plan first (Design → Save)")
    return d


def _run(plan: dict, inputs: dict) -> dict:
    try:
        return engine.design(plan, inputs)
    except engine.NeedInfo as e:
        raise HTTPException(422, {"message": "Please give these details first", "questions": e.questions})


def out(s: StructuralDesign | None, res: dict, plan: dict) -> dict:
    return {"id": s.id if s else None, "version": s.version if s else None, "title": s.title if s else "",
            "design_id": s.design_id if s else None, "result": res, "previews": sheets.previews(res, plan)}


@router.post("/projects/{project_id}/structural/calculate")
def calculate(project_id: int, body: CalcIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_any(db, user, project_id, ("design",))
    plan = recompute(_design(db, project_id, body.design_id).plan)
    return out(None, _run(plan, body.inputs), plan)


@router.post("/projects/{project_id}/structural")
def save(project_id: int, body: CalcIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_any(db, user, project_id, ("design",))
    d = _design(db, project_id, body.design_id)
    plan = recompute(d.plan)
    res = _run(plan, body.inputs)
    ver = (db.query(func.max(StructuralDesign.version)).filter(StructuralDesign.project_id == p.id).scalar() or 0) + 1
    s = StructuralDesign(project_id=p.id, design_id=d.id, version=ver, title=body.title.strip() or f"Structural v{ver} (design v{d.version})",
                         inputs=res["inputs"], result=res, created_by=user.id)
    db.add(s)
    db.commit()
    log_action(db, user, "created", "structural", f"v{ver}",
               f"{s.title}: {res['summary']['columns']} columns, {res['summary']['concrete_m3']} m3", project_id=p.id)
    return out(s, res, plan)


@router.get("/projects/{project_id}/structural")
def list_versions(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_any(db, user, project_id, ("design", "estimate"))
    rows = (db.query(StructuralDesign).filter(StructuralDesign.project_id == project_id, StructuralDesign.is_hidden.is_(False))
            .order_by(StructuralDesign.version.desc()).all())
    return [{"id": s.id, "version": s.version, "title": s.title, "design_id": s.design_id, "summary": (s.result or {}).get("summary"),
             "created_at": s.created_at.isoformat()} for s in rows]


def _load(db: Session, user: User, sid: int):
    s = db.get(StructuralDesign, sid)
    if not s or s.is_hidden:
        raise HTTPException(404, "Structural design not found")
    p = require_any(db, user, s.project_id, ("design", "estimate"))
    d = db.get(Design, s.design_id) if s.design_id else None
    if not d:
        raise HTTPException(404, "The floor plan of this structural design is missing")
    return s, p, recompute(d.plan)


@router.get("/structural/{sid}")
def get_one(sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s, _, plan = _load(db, user, sid)
    return out(s, s.result, plan)


@router.get("/structural/{sid}/pdf")
def pdf(sid: int, style: str = "paper", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s, p, plan = _load(db, user, sid)
    data = sheets.structural_pdf(s.result, plan, _proj(p, db), {"version": s.version, "date": s.created_at.strftime("%d-%m-%Y")},
                                 "cad" if style == "cad" else "paper")
    name = f"{p.code}_Structural_v{s.version}{'_CAD' if style == 'cad' else ''}.pdf"
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.get("/structural/{sid}/dxf")
def dxf(sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..design.sheets import dwgs_dxf
    s, p, plan = _load(db, user, sid)
    r = s.result
    dw = [sheets.column_layout(r, plan), sheets.foundation_plan(r, plan), sheets.footing_detail(r), sheets.column_section(r),
          sheets.beam_detail(r)] + [sheets.beam_layout(r, plan, l) for l in r["levels"]] + [sheets.slab_layout(r, plan, l) for l in r["levels"]]
    data = dwgs_dxf(dw, f"{p.name} - structural v{s.version} - PRELIMINARY")
    name = f"{p.code}_Structural_v{s.version}.dxf"
    return Response(data, media_type="application/dxf", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
