"""Phase 3 – Design Studio: prompt → requirements → TN-setback plan → edit → versions → compare → estimate."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..design import exports, parser
from ..design.edit import PlanError, compare, recompute
from ..design.geometry import estimate_inputs
from ..design.layout import LayoutError, generate
from ..design.setbacks import AREA_TYPES, SetbackError, tn_setbacks
from ..estimate.engine import MissingInfo, calculate
from ..estimate.rates_seed import DEFAULT_STATE
from ..models import Design, Project, User
from ..security import get_current_user, project_permissions
from .estimate import rates_dict, rates_for

router = APIRouter(prefix="/api", tags=["design"])


def require_any(db: Session, user: User, project_id: int, modules: tuple[str, ...]) -> Project:
    p = db.get(Project, project_id)
    if not p or p.is_hidden:
        raise HTTPException(404, "Project not found")
    perms = project_permissions(db, user, p)
    if not any(perms.get(m) for m in modules):
        raise HTTPException(403, f"You don't have '{modules[0]}' access to this project")
    return p


def project_defaults(p: Project) -> dict:
    to_ft = 3.28084 if p.unit == "m" else 1.0
    d = {}
    if p.plot_width:
        d["plot_w_ft"] = round(p.plot_width * to_ft, 2)
    if p.plot_length:
        d["plot_d_ft"] = round(p.plot_length * to_ft, 2)
    return d


# ---------------------------------------------------------------- understanding the request
class ParseIn(BaseModel):
    text: str
    defaults: dict = {}


@router.post("/projects/{project_id}/design/parse")
def parse_request(project_id: int, body: ParseIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_any(db, user, project_id, ("design",))
    defaults = project_defaults(p) | {k: v for k, v in (body.defaults or {}).items() if v not in (None, "")}
    return parser.parse(body.text, defaults)


class ReqIn(BaseModel):
    answers: dict  # structured form values (same keys as parser "partial")


@router.post("/projects/{project_id}/design/requirements")
def build_req(project_id: int, body: ReqIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Structured form → requirements (rooms per floor), after the user answered the questions."""
    require_any(db, user, project_id, ("design",))
    d = dict(body.answers)
    missing = [label for k, label in [("plot_w_ft", "Plot frontage (ft)"), ("plot_d_ft", "Plot depth (ft)"),
                                      ("facing", "Facing"), ("road_width_m", "Road width"), ("floors", "Floors")]
               if not d.get(k)]
    if d.get("bedrooms") in (None, ""):
        missing.append("Bedrooms")
    if missing:
        raise HTTPException(422, {"message": "Please confirm these details", "questions": missing})
    for k in ("plot_w_ft", "plot_d_ft", "road_width_m"):
        d[k] = float(d[k])
    for k in ("floors", "bedrooms"):
        d[k] = int(d[k])
    if d.get("toilets") not in (None, ""):
        d["toilets"] = int(d["toilets"])
    else:
        d.pop("toilets", None)
    return parser.build_requirements(d)


class SetbackIn(BaseModel):
    plot_w_ft: float
    plot_d_ft: float
    road_width_m: float
    levels: int = 1
    floor_height_ft: float = 10
    area_type: str = "other"
    corner: bool = False
    side_road_width_m: float | None = None


@router.post("/design/setbacks")
def setbacks(body: SetbackIn, user: User = Depends(get_current_user)):
    try:
        return tn_setbacks(body.plot_w_ft, body.plot_d_ft, body.road_width_m, body.levels, body.floor_height_ft,
                           body.area_type, body.corner, body.side_road_width_m)
    except SetbackError as e:
        raise HTTPException(422, {"message": str(e), "questions": [str(e)]})


@router.get("/design/area-types")
def area_types(user: User = Depends(get_current_user)):
    return AREA_TYPES


# ---------------------------------------------------------------- plan generation & editing
class GenIn(BaseModel):
    requirements: dict


@router.post("/projects/{project_id}/design/generate")
def generate_plan(project_id: int, body: GenIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_any(db, user, project_id, ("design",))
    try:
        return generate(body.requirements)
    except LayoutError as e:
        raise HTTPException(422, {"message": "The rooms do not fit this plot after setbacks",
                                  "questions": e.questions, "suggestions": e.suggestions})
    except SetbackError as e:
        raise HTTPException(422, {"message": str(e), "questions": [str(e)]})
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(400, f"Invalid requirements: {e}")


class PlanIn(BaseModel):
    plan: dict


@router.post("/projects/{project_id}/design/recompute")
def recompute_plan(project_id: int, body: PlanIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """After editing rooms: walls, doors, windows, checks and quantities are derived again."""
    require_any(db, user, project_id, ("design",))
    try:
        return recompute(body.plan)
    except PlanError as e:
        raise HTTPException(422, {"message": str(e), "questions": [str(e)]})
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(400, f"Invalid plan: {e}")


class QuickIn(BaseModel):
    plan: dict
    spec_level: str = "standard"
    state: str = DEFAULT_STATE
    structure: str = "rcc_framed"


def quick_estimate(db: Session, plan: dict, spec: str, state: str, structure: str = "rcc_framed") -> dict:
    used, fallback, rows = rates_for(db, state)
    inp = estimate_inputs(plan, {"spec_level": spec, "structure": structure})
    try:
        res = calculate(inp, rates_dict(rows))
    except MissingInfo as e:
        raise HTTPException(422, {"message": "Please confirm these details", "questions": e.questions})
    t = res["totals"]
    return {"inputs": inp, "rates_state": used, "using_fallback": fallback, "spec_level": spec,
            "totals": t, "breakdown": res["breakdown"], "floors": res.get("floors", []),
            "warnings": res.get("warnings", [])}


@router.post("/projects/{project_id}/design/quick-estimate")
def design_quick_estimate(project_id: int, body: QuickIn, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    require_any(db, user, project_id, ("design", "estimate"))
    return quick_estimate(db, body.plan, body.spec_level, body.state, body.structure)


# ---------------------------------------------------------------- versions
class SaveIn(BaseModel):
    plan: dict
    title: str = ""
    prompt: str = ""
    source: str = "ai"
    spec_level: str = "standard"
    state: str = DEFAULT_STATE
    parent_id: int | None = None


def design_summary(d: Design) -> dict:
    return {"id": d.id, "project_id": d.project_id, "version": d.version, "title": d.title, "prompt": d.prompt,
            "source": d.source, "spec_level": d.spec_level, "rate_state": d.rate_state,
            "estimate_total": d.estimate_total, "cost_per_sqft": d.cost_per_sqft, "builtup_sqft": d.builtup_sqft,
            "summary": d.summary, "parent_id": d.parent_id, "created_by": d.created_by,
            "created_at": d.created_at.isoformat()}


@router.post("/projects/{project_id}/designs")
def save_design(project_id: int, body: SaveIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_any(db, user, project_id, ("design",))
    try:
        plan = recompute(body.plan)
    except PlanError as e:
        raise HTTPException(422, {"message": str(e), "questions": [str(e)]})
    q = quick_estimate(db, plan, body.spec_level, body.state)
    ver = (db.query(func.max(Design.version)).filter(Design.project_id == p.id).scalar() or 0) + 1
    t = q["totals"]
    d = Design(project_id=p.id, version=ver, title=body.title.strip() or f"Design v{ver}", prompt=body.prompt,
               source=body.source if body.source in ("ai", "edited", "manual") else "edited", plan=plan,
               summary=plan["summary"], spec_level=q["spec_level"], rate_state=q["rates_state"],
               estimate_total=t["grand_total"], cost_per_sqft=t["cost_per_sqft"], builtup_sqft=t["builtup_sqft"],
               parent_id=body.parent_id, created_by=user.id)
    db.add(d)
    db.commit()
    log_action(db, user, "created", "design", f"v{ver}",
               f"{d.title}: {plan['summary']['builtup_sqft']:g} sq ft, Rs {t['grand_total']:,.0f}", project_id=p.id)
    return design_summary(d) | {"plan": plan, "estimate": q}


@router.get("/projects/{project_id}/designs")
def list_designs(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_any(db, user, project_id, ("design", "estimate"))
    rows = (db.query(Design).filter(Design.project_id == project_id, Design.is_hidden.is_(False))
            .order_by(Design.version.desc()).all())
    return [design_summary(d) for d in rows]


def load_design(db: Session, user: User, design_id: int, modules=("design",)) -> tuple[Design, Project]:
    d = db.get(Design, design_id)
    if not d:
        raise HTTPException(404, "Design not found")
    p = require_any(db, user, d.project_id, modules)
    return d, p


@router.get("/designs/compare")
def compare_designs(a: int, b: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    da, pa = load_design(db, user, a)
    dbb, pb = load_design(db, user, b)
    if pa.id != pb.id:
        raise HTTPException(400, "Both designs must belong to the same project")
    return compare(design_summary(da) | {"plan": da.plan}, design_summary(dbb) | {"plan": dbb.plan})


@router.get("/designs/{design_id}")
def get_design(design_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d, _ = load_design(db, user, design_id, ("design", "estimate"))
    return design_summary(d) | {"plan": d.plan}


@router.get("/designs/{design_id}/estimate-inputs")
def design_estimate_inputs(design_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Inputs for the Estimate page's '2D Drawing' method (quantities measured from this design)."""
    d, p = load_design(db, user, design_id, ("estimate", "design"))
    inp = estimate_inputs(d.plan, {"spec_level": p.spec_level or d.spec_level or "standard",
                                   "structure": p.structure_type or "rcc_framed"})
    inp["design_id"] = d.id
    return {"inputs": inp, "design": design_summary(d)}


@router.post("/designs/{design_id}/hide")
def hide_design(design_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "owner":
        raise HTTPException(403, "Only the owner can delete – ask the owner")
    d, p = load_design(db, user, design_id)
    d.is_hidden = True
    db.commit()
    log_action(db, user, "hidden", "design", f"v{d.version}", d.title, project_id=p.id)
    return {"ok": True}


def _proj(p: Project) -> dict:
    return {"name": p.name, "code": p.code, "location": p.location}


@router.get("/designs/{design_id}/pdf")
def design_pdf(design_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d, p = load_design(db, user, design_id, ("design", "estimate"))
    data = exports.to_pdf(d.plan, _proj(p), {"version": d.version})
    name = f"{p.code}_Plan_v{d.version}.pdf"
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.get("/designs/{design_id}/dxf")
def design_dxf(design_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d, p = load_design(db, user, design_id, ("design", "estimate"))
    data = exports.to_dxf(d.plan, _proj(p), {"version": d.version})
    name = f"{p.code}_Plan_v{d.version}.dxf"
    return Response(data, media_type="application/dxf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
