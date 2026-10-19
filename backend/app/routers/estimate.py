"""Phase 2 – rate library + estimates (quick estimate, detailed BOQ, versions, Excel/PDF)."""
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..estimate.engine import MissingInfo, calculate, levels_from_floors
from ..estimate.exports import to_excel, to_pdf
from ..estimate.rates_seed import DEFAULT_STATE
from ..models import Estimate, Project, RateItem, User
from ..security import get_current_user, require_owner, require_project
from .projects import project_out

router = APIRouter(prefix="/api", tags=["estimate"])

KINDS = {"material", "labour", "equipment", "extra"}


def rate_out(r: RateItem) -> dict:
    return {"id": r.id, "state": r.state, "code": r.code, "kind": r.kind, "category": r.category, "name": r.name,
            "unit": r.unit, "basic": r.basic, "standard": r.standard, "premium": r.premium, "note": r.note,
            "is_custom": r.is_custom, "is_active": r.is_active,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None}


def rates_for(db: Session, state: str) -> tuple[str, bool, list[RateItem]]:
    """Rates of a state; falls back to Tamil Nadu if that state has none yet."""
    rows = db.query(RateItem).filter(RateItem.state == state).order_by(RateItem.kind, RateItem.category, RateItem.id).all()
    if rows:
        return state, False, rows
    rows = db.query(RateItem).filter(RateItem.state == DEFAULT_STATE).order_by(RateItem.kind, RateItem.category, RateItem.id).all()
    return DEFAULT_STATE, state != DEFAULT_STATE, rows


def rates_dict(rows: list[RateItem]) -> dict[str, dict]:
    return {r.code: {"name": r.name, "unit": r.unit, "kind": r.kind, "basic": r.basic, "standard": r.standard,
                     "premium": r.premium} for r in rows if r.is_active}


# ---------------------------------------------------------------- rate library
@router.get("/rates")
def get_rates(state: str = DEFAULT_STATE, include_hidden: bool = False, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    used, fallback, rows = rates_for(db, state)
    if not include_hidden:
        rows = [r for r in rows if r.is_active]
    return {"state": state, "rates_state": used, "using_fallback": fallback, "items": [rate_out(r) for r in rows]}


@router.get("/rates/states")
def rate_states(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(RateItem.state, func.count(RateItem.id)).group_by(RateItem.state).all()
    return [{"state": s, "items": n} for s, n in rows]


class CopyIn(BaseModel):
    from_state: str = DEFAULT_STATE
    to_state: str


@router.post("/rates/copy")
def copy_rates(body: CopyIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    if db.query(RateItem).filter(RateItem.state == body.to_state).first():
        raise HTTPException(409, f"{body.to_state} already has its own rates")
    src = db.query(RateItem).filter(RateItem.state == body.from_state).all()
    if not src:
        raise HTTPException(404, f"No rates found for {body.from_state}")
    for r in src:
        db.add(RateItem(state=body.to_state, code=r.code, kind=r.kind, category=r.category, name=r.name, unit=r.unit,
                        basic=r.basic, standard=r.standard, premium=r.premium,
                        note=(r.note + " " if r.note else "") + f"(copied from {body.from_state} – update for {body.to_state})",
                        is_custom=r.is_custom, is_active=r.is_active, updated_by=owner.id))
    db.commit()
    log_action(db, owner, "created", "rates", body.to_state, f"Copied {len(src)} rates from {body.from_state}")
    return {"ok": True, "copied": len(src)}


class RateIn(BaseModel):
    state: str = DEFAULT_STATE
    kind: str
    category: str = "Custom"
    name: str = Field(min_length=2, max_length=160)
    unit: str = Field(min_length=1, max_length=20)
    basic: float = Field(ge=0)
    standard: float = Field(ge=0)
    premium: float = Field(ge=0)
    note: str = ""


@router.post("/rates")
def add_rate(body: RateIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    if body.kind not in KINDS:
        raise HTTPException(400, f"kind must be one of {', '.join(sorted(KINDS))}")
    if body.state != DEFAULT_STATE and not db.query(RateItem).filter(RateItem.state == body.state).first():
        raise HTTPException(400, f"Create rates for {body.state} first (copy from Tamil Nadu)")
    slug = re.sub(r"[^a-z0-9]+", "_", body.name.lower()).strip("_")[:30] or "item"
    code, n = f"custom_{slug}", 1
    while db.query(RateItem).filter_by(state=body.state, code=code).first():
        n += 1
        code = f"custom_{slug}_{n}"
    r = RateItem(state=body.state, code=code, kind=body.kind, category=body.category.strip() or "Custom",
                 name=body.name.strip(), unit=body.unit.strip(), basic=body.basic, standard=body.standard,
                 premium=body.premium, note=body.note.strip(), is_custom=True, updated_by=owner.id)
    db.add(r)
    db.commit()
    log_action(db, owner, "added", "rate", r.code, f"{r.state}: {r.name}")
    return rate_out(r)


class RatePatch(BaseModel):
    name: str | None = None
    unit: str | None = None
    category: str | None = None
    basic: float | None = Field(default=None, ge=0)
    standard: float | None = Field(default=None, ge=0)
    premium: float | None = Field(default=None, ge=0)
    note: str | None = None
    is_active: bool | None = None


@router.patch("/rates/{rate_id}")
def edit_rate(rate_id: int, body: RatePatch, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    r = db.get(RateItem, rate_id)
    if not r:
        raise HTTPException(404, "Rate not found")
    data = body.model_dump(exclude_unset=True)
    if not r.is_custom and ("unit" in data) and data["unit"] != r.unit:
        raise HTTPException(400, "Unit of a built-in rate cannot change (the estimator depends on it)")
    if r.kind == "labour" and any(k in data for k in ("basic", "standard", "premium")):
        # a day wage is the same for every spec level
        v = data.get("standard", data.get("basic", data.get("premium")))
        data["basic"] = data["standard"] = data["premium"] = v
    old = {k: getattr(r, k) for k in data}
    for k, v in data.items():
        setattr(r, k, v.strip() if isinstance(v, str) else v)
    r.updated_by = owner.id
    db.commit()
    log_action(db, owner, "updated", "rate", r.code, f"{r.state}: {r.name} " +
               ", ".join(f"{k} {old[k]}→{data[k]}" for k in data))
    return rate_out(r)


# ---------------------------------------------------------------- estimates
class CalcIn(BaseModel):
    inputs: dict
    state: str = DEFAULT_STATE


def run_calc(db: Session, inputs: dict, state: str):
    used, fallback, rows = rates_for(db, state)
    rates = rates_dict(rows)
    try:
        result = calculate(inputs, rates)
    except MissingInfo as e:
        raise HTTPException(422, {"message": "Please confirm these details", "questions": e.questions})
    except (TypeError, ValueError) as e:
        raise HTTPException(400, f"Invalid input: {e}")
    if fallback:
        result["warnings"].insert(0, f"No rates saved for {state} yet – Tamil Nadu average rates used.")
    result["rates_state"] = used
    return result, rates


@router.get("/projects/{project_id}/estimate-defaults")
def estimate_defaults(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_project(db, user, project_id, "estimate")
    levels, stilt = levels_from_floors(p.floors)
    per_floor = p.builtup_area  # project "built-up area" is used as a per-floor suggestion only
    to_ft = 3.28084 if p.unit == "m" else 1.0
    missing = []
    if not per_floor:
        missing.append("Built-up area of each floor (sq ft)")
    missing.append("Number of bedrooms and toilets")
    return {
        "project": project_out(p),
        "inputs": {
            "floor_areas_sqft": [per_floor or 0] * levels, "stilt": stilt, "floor_height_ft": 10,
            "structure": p.structure_type or "rcc_framed", "spec_level": p.spec_level or "standard",
            "masonry": "brick", "bedrooms": 0, "halls": 1, "kitchens": 1, "toilets": 0,
            "plot_width_ft": round(p.plot_width * to_ft, 2) if p.plot_width else None,
            "plot_length_ft": round(p.plot_length * to_ft, 2) if p.plot_length else None,
            "staircase": True, "compound_wall": False, "gate": False, "sump_litres": 0,
            "septic_tank": False, "oh_tank_litres": None, "rwh": True, "parking_area_sqft": 0,
            "approval_fees": 0, "contractor_margin_pct": 0, "gst_pct": 0, "extra_items": [],
        },
        "state": p.state or DEFAULT_STATE,
        "needs_confirmation": missing,
    }


@router.post("/projects/{project_id}/estimate/calculate")
def calc_preview(project_id: int, body: CalcIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_project(db, user, project_id, "estimate")
    result, _ = run_calc(db, body.inputs, body.state)
    return result


class SaveIn(CalcIn):
    title: str = ""


def est_summary(e: Estimate) -> dict:
    return {"id": e.id, "project_id": e.project_id, "version": e.version, "title": e.title,
            "rate_state": e.rate_state, "spec_level": e.spec_level, "grand_total": e.grand_total,
            "cost_per_sqft": e.cost_per_sqft, "builtup_sqft": e.builtup_sqft, "created_by": e.created_by,
            "created_at": e.created_at.isoformat()}


@router.post("/projects/{project_id}/estimates")
def save_estimate(project_id: int, body: SaveIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_project(db, user, project_id, "estimate")
    result, rates = run_calc(db, body.inputs, body.state)
    ver = (db.query(func.max(Estimate.version)).filter(Estimate.project_id == p.id).scalar() or 0) + 1
    t = result["totals"]
    e = Estimate(project_id=p.id, version=ver, title=body.title.strip() or f"Estimate v{ver}",
                 rate_state=result["rates_state"], spec_level=result["spec_level"], inputs=body.inputs,
                 result=result, rates_snapshot=rates, grand_total=t["grand_total"],
                 cost_per_sqft=t["cost_per_sqft"], builtup_sqft=t["builtup_sqft"], created_by=user.id)
    db.add(e)
    db.commit()
    log_action(db, user, "created", "estimate", f"v{ver}",
               f"{e.title}: Rs {t['grand_total']:,.0f} ({result['spec_level']})", project_id=p.id)
    return est_summary(e) | {"result": result, "inputs": e.inputs}


@router.get("/projects/{project_id}/estimates")
def list_estimates(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_project(db, user, project_id, "estimate")
    rows = (db.query(Estimate).filter(Estimate.project_id == project_id, Estimate.is_hidden.is_(False))
            .order_by(Estimate.version.desc()).all())
    return [est_summary(e) for e in rows]


def load_estimate(db: Session, user: User, estimate_id: int) -> tuple[Estimate, Project]:
    e = db.get(Estimate, estimate_id)
    if not e:
        raise HTTPException(404, "Estimate not found")
    p = require_project(db, user, e.project_id, "estimate")
    return e, p


@router.get("/estimates/{estimate_id}")
def get_estimate(estimate_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e, _ = load_estimate(db, user, estimate_id)
    return est_summary(e) | {"result": e.result, "inputs": e.inputs}


def export_payload(e: Estimate, p: Project):
    return ({"name": p.name, "code": p.code, "location": p.location, "district": p.district, "state": p.state},
            {"title": e.title, "version": e.version, "rate_state": e.rate_state, "result": e.result})


@router.get("/estimates/{estimate_id}/excel")
def export_excel(estimate_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e, p = load_estimate(db, user, estimate_id)
    data = to_excel(*export_payload(e, p))
    name = f"{p.code}_BOQ_v{e.version}.xlsx"
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.get("/estimates/{estimate_id}/pdf")
def export_pdf(estimate_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e, p = load_estimate(db, user, estimate_id)
    data = to_pdf(*export_payload(e, p))
    name = f"{p.code}_Estimate_v{e.version}.pdf"
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.post("/estimates/{estimate_id}/hide")
def hide_estimate(estimate_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "owner":
        raise HTTPException(403, "Only the owner can delete – ask the owner")
    e, p = load_estimate(db, user, estimate_id)
    e.is_hidden = True
    db.commit()
    log_action(db, user, "hidden", "estimate", f"v{e.version}", e.title, project_id=p.id)
    return {"ok": True}


# ---------------------------------------------------------------- Excel input method (template → fill → upload)
class TemplateIn(BaseModel):
    inputs: dict = {}
    state: str = DEFAULT_STATE


@router.post("/projects/{project_id}/estimate/excel-template")
def excel_template(project_id: int, body: TemplateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..estimate import excel_input
    p = require_project(db, user, project_id, "estimate")
    used, _, rows = rates_for(db, body.state)
    data = excel_input.template(body.inputs or {}, [rate_out(r) for r in rows if r.is_active], used, p.name,
                                user.role == "owner")
    name = f"{p.code}_Estimate_Inputs.xlsx"
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.post("/projects/{project_id}/estimate/excel-import")
async def excel_import(project_id: int, file: UploadFile = File(...), state: str = Form(DEFAULT_STATE),
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Read the filled template. Inputs come back to the screen (nothing is saved until you press Save).
    Rates: only the owner's changed values are written to the rate library (changes are logged)."""
    from ..estimate import excel_input
    require_project(db, user, project_id, "estimate")
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(415, "Please upload the .xlsx template (Excel 2007 or newer)")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 10 MB)")
    used, _, rows = rates_for(db, state)
    by_code = {r.code: r for r in rows}
    try:
        out = excel_input.parse(data, set(by_code))
    except excel_input.ExcelInputError as e:
        raise HTTPException(422, {"message": str(e), "questions": [str(e)]})
    changed = []
    if out["rates"]:
        if user.role != "owner":
            out["warnings"].append("Rates in the file were ignored – only the owner can change the rate library.")
        else:
            for code, vals in out["rates"].items():
                r = by_code[code]
                diff = {k: v for k, v in vals.items() if abs((getattr(r, k) or 0) - v) > 1e-9}
                if diff:
                    old = {k: getattr(r, k) for k in diff}
                    for k, v in diff.items():
                        setattr(r, k, v)
                    changed.append(f"{code}: {old} → {diff}")
            if changed:
                db.commit()
                log_action(db, user, "updated", "rates", used, f"Excel import: {len(changed)} rate(s) changed – "
                           + "; ".join(changed)[:900], project_id=project_id)
    inputs = dict(out["inputs"])
    if out["extra_items"]:
        inputs["extra_items"] = out["extra_items"]
    return {"inputs": inputs, "rates_changed": len(changed), "rates_state": used, "warnings": out["warnings"]}
