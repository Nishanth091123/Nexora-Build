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
    fw = bool(d.get("floor_specs"))  # 1.19 floor-by-floor request: floors / bedrooms come from the floor table
    missing = [label for k, label in [("plot_w_ft", "Plot frontage (ft)"), ("plot_d_ft", "Plot depth (ft)"),
                                      ("facing", "Facing"), ("road_width_m", "Road width"), ("floors", "Floors")]
               if not d.get(k) and not (fw and k == "floors")]
    if d.get("bedrooms") in (None, "") and not fw:
        missing.append("Bedrooms")
    if missing:
        raise HTTPException(422, {"message": "Please confirm these details", "questions": missing})
    for k in ("plot_w_ft", "plot_d_ft", "road_width_m"):
        d[k] = float(d[k])
    for k in ("floors", "bedrooms"):
        if d.get(k) not in (None, ""):
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
        plot_q = any(w in " ".join(e.questions).lower() for w in ("diagonal", "side", "corner", "plot", "measurement"))
        raise HTTPException(422, {"message": "Please complete the plot measurements" if plot_q and not e.suggestions
                                  else "The rooms do not fit this plot after setbacks",
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
        rd = rates_dict(rows)
        from ..market import apply_market  # 1.18 brand grades from the Material Library
        apply_market(db, rd)
        res = calculate(inp, rd)
    except MissingInfo as e:
        raise HTTPException(422, {"message": "Please confirm these details", "questions": e.questions})
    t = res["totals"]
    return {"inputs": inp, "rates_state": used, "using_fallback": fallback, "spec_level": spec,
            "totals": t, "breakdown": res["breakdown"], "floors": res.get("floors", []),
            "warnings": res.get("warnings", [])}


class StairIn(BaseModel):
    plan: dict
    opts: dict = {}


@router.post("/projects/{project_id}/design/stair")
def stair_design(project_id: int, body: StairIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """1.18: staircase geometry + checks + waist-slab design + BBS for the plan (opts = what the user changed)."""
    require_any(db, user, project_id, ("design", "estimate"))
    from ..design.stair import design as stair_design_fn
    try:
        return stair_design_fn(body.plan, body.opts)
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as e:
        raise HTTPException(400, f"Staircase could not be worked out: {e}")


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
    p.active_design_id = d.id  # 1.18: a newly saved design is what every module uses from now on
    db.commit()
    log_action(db, user, "created", "design", f"v{ver}",
               f"{d.title}: {plan['summary']['builtup_sqft']:g} sq ft, Rs {t['grand_total']:,.0f}", project_id=p.id)
    return design_summary(d) | {"plan": plan, "estimate": q}


@router.get("/projects/{project_id}/designs")
def list_designs(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_any(db, user, project_id, ("design", "estimate", "vastu"))
    rows = (db.query(Design).filter(Design.project_id == project_id, Design.is_hidden.is_(False))
            .order_by(Design.version.desc()).all())
    act = active_design(db, p)
    return [design_summary(d) | {"active": bool(act and d.id == act.id)} for d in rows]


def active_design(db: Session, p: Project) -> Design | None:
    """1.18: the project's active drawing – the one the owner marked, else the newest saved / uploaded version."""
    if p.active_design_id:
        d = db.get(Design, p.active_design_id)
        if d and not d.is_hidden and d.project_id == p.id:
            return d
    return (db.query(Design).filter(Design.project_id == p.id, Design.is_hidden.is_(False))
            .order_by(Design.version.desc()).first())


@router.get("/projects/{project_id}/active-design")
def get_active_design(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_any(db, user, project_id, ("design", "estimate", "vastu", "view"))
    d = active_design(db, p)
    return {"design": design_summary(d) | {"active": True} if d else None}


class ActiveIn(BaseModel):
    design_id: int


@router.put("/projects/{project_id}/active-design")
def set_active_design(project_id: int, body: ActiveIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_any(db, user, project_id, ("design",))
    d = db.get(Design, body.design_id)
    if not d or d.project_id != p.id or d.is_hidden:
        raise HTTPException(404, "Design not found")
    p.active_design_id = d.id
    db.commit()
    log_action(db, user, "updated", "design", f"v{d.version}", f"Active drawing for all modules: {d.title}", project_id=p.id)
    return {"design": design_summary(d) | {"active": True}}


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


def _proj(p: Project, db: Session | None = None) -> dict:
    out = {"name": p.name, "code": p.code, "location": p.location, "district": p.district,
           "client_name": p.client_name, "company": {}}
    if db is not None:
        from ..models import Organization
        o = db.get(Organization, 1)
        if o:
            out["company"] = {"name": o.name or "", "proprietor": o.proprietor or "", "phone": o.phone or "",
                              "address": o.address or "", "registration_no": o.registration_no or ""}
    return out


# ---------------------------------------------------------------- 1.10 drawing sheets
@router.post("/projects/{project_id}/design/sheets-preview")
def sheets_preview(project_id: int, body: PlanIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Door & window schedule, area details and SVG previews (site plan, floor plans, front elevation, section)."""
    from ..design import sheets
    require_any(db, user, project_id, ("design", "estimate"))
    try:
        plan = recompute(body.plan)
    except PlanError as e:
        raise HTTPException(422, {"message": str(e), "questions": [str(e)]})
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(400, f"Invalid plan: {e}")
    return sheets.sheet_previews(plan) | {"warnings": plan.get("warnings", [])}


class ExportIn(BaseModel):
    plan: dict
    version: str | int | None = None


@router.post("/projects/{project_id}/design/export")
def export_current(project_id: int, body: ExportIn, kind: str = "sheets_pdf", style: str = "paper", page: str = "",
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """1.13: download what is on the screen now (saved or not).
    kind: sheets_pdf (whole A3 set, or one sheet with page=site / plan_0 / elevation / section / schedule / title)
          | sheets_dxf | plan_pdf | plan_dxf."""
    from datetime import date as _date

    from ..design import sheets
    p = require_any(db, user, project_id, ("design", "estimate"))
    try:
        plan = recompute(body.plan)
    except PlanError as e:
        raise HTTPException(422, {"message": str(e), "questions": [str(e)]})
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(400, f"Invalid plan: {e}")
    ver = body.version if body.version not in (None, "") else "draft"
    meta = {"version": ver, "date": _date.today().strftime("%d-%m-%Y")}
    tag = f"v{ver}" if ver != "draft" else "draft"
    st = "cad" if style == "cad" else "paper"
    if kind == "sheets_pdf":
        data = sheets.sheet_set_pdf(plan, _proj(p, db), meta, style=st)
        label = "Drawing_Set"
        if page:
            pages = sheets.sheet_pages(plan)
            if page not in pages:
                raise HTTPException(400, f"page must be one of {', '.join(pages)}")
            data = sheets.pdf_pages(data, [pages[page]])
            label = {"title": "Title_Sheet", "site": "Site_Plan", "elevation": "Front_Elevation", "section": "Section",
                     "schedule": "Door_Window_Schedule", "roof": "Roof_Plan", "truss": "Truss_Detail",
                     "stair": "Staircase_Detail"}.get(page) or \
                (plan["levels"][int(page.split("_")[1])]["name"].replace(" ", "_") + "_Plan")
        mt, ext = "application/pdf", "pdf"
        name = f"{p.code}_{label}_{tag}{'_CAD' if st == 'cad' else ''}.{ext}"
    elif kind == "sheets_dxf":
        data, mt, name = sheets.sheets_dxf(plan, _proj(p, db), meta), "application/dxf", f"{p.code}_Drawing_Set_{tag}.dxf"
    elif kind == "plan_pdf":
        data, mt, name = exports.to_pdf(plan, _proj(p, db), meta), "application/pdf", f"{p.code}_Plan_{tag}.pdf"
    elif kind == "plan_dxf":
        data, mt, name = exports.to_dxf(plan, _proj(p), meta), "application/dxf", f"{p.code}_Plan_{tag}.dxf"
    else:
        raise HTTPException(400, "kind must be sheets_pdf, sheets_dxf, plan_pdf or plan_dxf")
    return Response(data, media_type=mt, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.get("/designs/{design_id}/sheets.pdf")
def design_sheets_pdf(design_id: int, style: str = "paper", user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    from ..design import sheets
    d, p = load_design(db, user, design_id, ("design", "estimate"))
    plan = recompute(d.plan)
    data = sheets.sheet_set_pdf(plan, _proj(p, db), {"version": d.version, "date": d.created_at.strftime("%d-%m-%Y")},
                                style="cad" if style == "cad" else "paper")
    name = f"{p.code}_Drawing_Set_v{d.version}{'_CAD' if style == 'cad' else ''}.pdf"
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.get("/designs/{design_id}/sheets.dxf")
def design_sheets_dxf(design_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..design import sheets
    d, p = load_design(db, user, design_id, ("design", "estimate"))
    plan = recompute(d.plan)
    data = sheets.sheets_dxf(plan, _proj(p, db), {"version": d.version})
    name = f"{p.code}_Drawing_Set_v{d.version}.dxf"
    return Response(data, media_type="application/dxf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.get("/designs/{design_id}/pdf")
def design_pdf(design_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d, p = load_design(db, user, design_id, ("design", "estimate"))
    data = exports.to_pdf(d.plan, _proj(p, db), {"version": d.version})
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


# ---------------------------------------------------------------- 1.10.1 one PDF for the whole project
@router.get("/projects/{project_id}/project-pdf")
def project_pdf(project_id: int, estimate: str = "detailed", design_id: int | None = None, estimate_id: int | None = None,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Drawing set (A3) + estimate (detailed / bank / client) of the latest saved versions, merged into ONE PDF."""
    import io as _io

    from pypdf import PdfReader, PdfWriter

    from ..design import sheets
    from ..estimate.exports import to_pdf as est_pdf, to_pdf_bank, to_pdf_client
    from ..models import Estimate
    from .estimate import export_payload
    p = require_any(db, user, project_id, ("design", "estimate"))
    perms = project_permissions(db, user, p)
    parts = []
    d = None
    if perms.get("design") or perms.get("estimate"):
        q = db.query(Design).filter(Design.project_id == p.id, Design.is_hidden.is_(False))
        d = q.filter(Design.id == design_id).first() if design_id else q.order_by(Design.version.desc()).first()
        if d:
            plan = recompute(d.plan)
            parts.append(sheets.sheet_set_pdf(plan, _proj(p, db), {"version": d.version, "date": d.created_at.strftime("%d-%m-%Y")}))
    if perms.get("design") and d:
        from ..models import StructuralDesign
        from ..structural import sheets as ssheets
        sd = (db.query(StructuralDesign).filter(StructuralDesign.project_id == p.id, StructuralDesign.design_id == d.id,
                                                StructuralDesign.is_hidden.is_(False)).order_by(StructuralDesign.version.desc()).first())
        if sd:
            parts.append(ssheets.structural_pdf(sd.result, plan, _proj(p, db), {"version": sd.version, "date": sd.created_at.strftime("%d-%m-%Y")}))
    if perms.get("estimate"):
        q = db.query(Estimate).filter(Estimate.project_id == p.id, Estimate.is_hidden.is_(False))
        e = q.filter(Estimate.id == estimate_id).first() if estimate_id else q.order_by(Estimate.version.desc()).first()
        if e:
            fn = {"bank": to_pdf_bank, "client": to_pdf_client}.get(estimate, est_pdf)
            parts.append(fn(*export_payload(e, p, db)))
    if not parts:
        raise HTTPException(404, "Save a design or an estimate for this project first.")
    w = PdfWriter()
    for b in parts:
        for page in PdfReader(_io.BytesIO(b)).pages:
            w.add_page(page)
    buf = _io.BytesIO()
    w.write(buf)
    name = f"{p.code}_Project_{'Drawings_and_' if len(parts) > 1 else ''}Estimate.pdf"
    return Response(buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
