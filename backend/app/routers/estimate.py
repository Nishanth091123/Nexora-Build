"""Phase 2 – rate library + estimates (quick estimate, detailed BOQ, versions, Excel/PDF)."""
import logging
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
from ..security import get_current_user, has_rates_access, require_owner, require_project, require_rates
from .projects import project_out

router = APIRouter(prefix="/api", tags=["estimate"])
log = logging.getLogger("nexora.estimate")

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
    items = [rate_out(r) for r in rows]
    locked = not has_rates_access(db, user)
    if locked:  # 1.16: names/units only (estimate inputs need them) – the rupee values stay with the owner
        for it in items:
            it["basic"] = it["standard"] = it["premium"] = None
            it["note"] = ""
    return {"state": state, "rates_state": used, "using_fallback": fallback, "locked": locked, "items": items}


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
def add_rate(body: RateIn, owner: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_rates(db, owner)
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
def edit_rate(rate_id: int, body: RatePatch, owner: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_rates(db, owner)
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


def run_calc(db: Session, inputs: dict, state: str, project_id: int | None = None):
    used, fallback, rows = rates_for(db, state)
    rates = rates_dict(rows)
    from ..market import apply_market  # 1.18: brand grades (A/B/C) + this project's chosen brands
    market_notes = apply_market(db, rates, project_id)
    try:
        result = calculate(inputs, rates)
    except MissingInfo as e:
        raise HTTPException(422, {"message": "Please confirm these details", "questions": e.questions})
    except (TypeError, ValueError) as e:
        raise HTTPException(400, f"Invalid input: {e}")
    if fallback:
        result["warnings"].insert(0, f"No rates saved for {state} yet – Tamil Nadu average rates used.")
    result["warnings"].extend(market_notes)
    result["material_notes"] = market_notes
    result["rates_state"] = used
    return result, rates


# 1.8: owner's default percentages (Settings → Units & Rates → Estimate defaults)
EST_DEFAULTS = {"gst_pct": 0, "contractor_margin_pct": 0, "contingency_pct": None}


def estimate_setting_defaults(db: Session) -> dict:
    from ..models import AppSetting
    row = db.get(AppSetting, "estimate_defaults")
    v = (row.value if row else {}) or {}
    out = {}
    for k, d in EST_DEFAULTS.items():
        x = v.get(k, d)
        out[k] = None if x in (None, "") else float(x)
    if out["gst_pct"] is None:
        out["gst_pct"] = 0
    if out["contractor_margin_pct"] is None:
        out["contractor_margin_pct"] = 0
    return out


@router.get("/estimate-settings")
def get_est_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return estimate_setting_defaults(db)


class EstSettingsIn(BaseModel):
    gst_pct: float = Field(default=0, ge=0, le=28)
    contractor_margin_pct: float = Field(default=0, ge=0, le=40)
    contingency_pct: float | None = Field(default=None, ge=0, le=20)


@router.put("/estimate-settings")
def put_est_settings(body: EstSettingsIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    from ..models import AppSetting
    row = db.get(AppSetting, "estimate_defaults")
    if not row:
        row = AppSetting(key="estimate_defaults", value={})
        db.add(row)
    row.value = body.model_dump()
    db.commit()
    log_action(db, owner, "updated", "settings", "estimate_defaults", str(row.value))
    return estimate_setting_defaults(db)


# ---------------------------------------------------------------- 1.8 quick / oral estimate
class QuickIn(BaseModel):
    builtup_sqft: float = Field(gt=0, le=200000)  # total of all floors
    floors: int = Field(ge=1, le=6)
    bedrooms: int = Field(ge=0, le=60)
    toilets: int = Field(ge=0, le=60)
    structure: str = "rcc_framed"
    stilt: bool = False
    state: str = DEFAULT_STATE


@router.post("/projects/{project_id}/estimate/quick")
def quick_estimate(project_id: int, body: QuickIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Oral estimate for a first discussion: the same engine run for Basic / Standard / Premium."""
    p = require_project(db, user, project_id, "estimate")
    if body.bedrooms <= 0 and body.toilets <= 0:
        raise HTTPException(422, {"message": "Please confirm these details",
                                  "questions": ["How many bedrooms and toilets in total?"]})
    per = body.builtup_sqft / body.floors
    kitchens = max(1, body.floors - (1 if body.stilt else 0)) if body.bedrooms >= 2 * body.floors else 1
    base = {"floor_areas_sqft": [round(per, 1)] * body.floors, "stilt": body.stilt, "structure": body.structure,
            "bedrooms": body.bedrooms, "toilets": body.toilets, "kitchens": kitchens, "halls": kitchens,
            "plot_width_ft": p.plot_width * (3.28084 if p.unit == "m" else 1) if p.plot_width else None,
            "plot_length_ft": p.plot_length * (3.28084 if p.unit == "m" else 1) if p.plot_length else None,
            **estimate_setting_defaults(db)}
    out = {}
    std = None
    for spec in ("basic", "standard", "premium"):
        r, _ = run_calc(db, {**base, "spec_level": spec}, body.state, project_id)
        t = r["totals"]
        out[spec] = {"grand_total": t["grand_total"], "cost_per_sqft": t["cost_per_sqft"]}
        if spec == "standard":
            std = r
    t = std["totals"]
    return {"specs": out, "builtup_sqft": body.builtup_sqft, "floors": body.floors, "kitchens": kitchens,
            "breakdown": std["breakdown"], "rates_state": std["rates_state"],
            "quantities": {"cement_bags": t["cement_bags"], "steel_kg": t["steel_kg"], "msand_m3": t["msand_m3"],
                           "psand_m3": t["psand_m3"], "aggregate_m3": t["aggregate_m3"], "bricks": t["bricks"]},
            "inputs": {**base, "spec_level": "standard"},
            "note": (f"Oral estimate for discussion – {kitchens} kitchen(s) assumed from the bedroom count; "
                     "the detailed BOQ (Detailed Estimate) is the figure to quote.")}


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
            "approval_fees": 0, "extra_items": [], **estimate_setting_defaults(db),
        },
        "state": p.state or DEFAULT_STATE,
        "needs_confirmation": missing,
        "active_design": _active_summary(db, p),
    }


def _active_summary(db, p):
    """1.18: the project's active drawing – the Estimate page uses it instead of asking for manual sizes."""
    from .design import active_design, design_summary
    d = active_design(db, p)
    return design_summary(d) if d else None


@router.post("/projects/{project_id}/estimate/calculate")
def calc_preview(project_id: int, body: CalcIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_project(db, user, project_id, "estimate")
    result, _ = run_calc(db, body.inputs, body.state, project_id)
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
    result, rates = run_calc(db, body.inputs, body.state, project_id)
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


V18_KEYS = ("floor_boq", "area_statement", "key_quantities", "payment_schedule")


def upgrade_result(db: Session, e: Estimate) -> dict:
    """1.13: estimates saved before 1.8 have no floor-wise BOQ / area statement / payment schedule.
    They are worked out once from the SAME inputs and the SAME saved rates (totals unchanged) and kept."""
    res = e.result or {}
    if all(k in res for k in V18_KEYS):
        return res
    try:
        rates = e.rates_snapshot or rates_dict(rates_for(db, e.rate_state or DEFAULT_STATE)[2])
        fresh = calculate(e.inputs or {}, rates)
    except Exception as ex:  # an old estimate that can no longer be worked out: show what is saved
        log.info("estimate %s upgrade skipped: %s", e.id, ex)
        return res
    new = dict(res)
    g = (res.get("totals") or {}).get("grand_total") or fresh["totals"]["grand_total"]
    for k in V18_KEYS:
        new[k] = fresh[k]
    for x in new["payment_schedule"]:
        x["amount"] = round(g * x["pct"] / 100, 0)
    e.result = new  # new dict → saved
    try:
        db.commit()
    except Exception:
        db.rollback()
    return new


@router.get("/estimates/{estimate_id}")
def get_estimate(estimate_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e, _ = load_estimate(db, user, estimate_id)
    return est_summary(e) | {"result": upgrade_result(db, e), "inputs": e.inputs}


def export_payload(e: Estimate, p: Project, db: Session | None = None):
    from ..models import Organization
    org = db.get(Organization, 1) if db is not None else None
    company = {"name": (org.name if org else "") or "", "proprietor": (org.proprietor if org else "") or "",
               "phone": (org.phone if org else "") or "", "email": (org.email if org else "") or "",
               "address": (org.address if org else "") or "", "registration_no": (org.registration_no if org else "") or ""}
    return ({"name": p.name, "code": p.code, "location": p.location, "district": p.district, "state": p.state,
             "client_name": p.client_name, "floors": p.floors, "company": company,
             "plot": f"{p.plot_width:g} x {p.plot_length:g} {p.unit}" if p.plot_width and p.plot_length else ""},
            {"title": e.title, "version": e.version, "rate_state": e.rate_state,
             "result": upgrade_result(db, e) if db is not None else e.result,
             "date": e.created_at.strftime("%d-%m-%Y")})


@router.get("/estimates/{estimate_id}/excel")
def export_excel(estimate_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e, p = load_estimate(db, user, estimate_id)
    data = to_excel(*export_payload(e, p, db))
    name = f"{p.code}_BOQ_v{e.version}.xlsx"
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.get("/estimates/{estimate_id}/pdf")
def export_pdf(estimate_id: int, fmt: str = "detailed", user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """fmt: detailed (full BOQ) | bank (bank-loan estimate) | client (clean summary for the client)."""
    from ..estimate.exports import to_pdf_bank, to_pdf_client
    e, p = load_estimate(db, user, estimate_id)
    pay = export_payload(e, p, db)
    if fmt == "bank":
        data, tag = to_pdf_bank(*pay), "Bank_Loan_Estimate"
    elif fmt == "client":
        data, tag = to_pdf_client(*pay), "Client_Estimate"
    else:
        data, tag = to_pdf(*pay), "Estimate"
    name = f"{p.code}_{tag}_v{e.version}.pdf"
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


class ExportIn(BaseModel):
    inputs: dict
    state: str = DEFAULT_STATE
    title: str = "Estimate (not saved)"


@router.post("/projects/{project_id}/estimate/export")
def export_unsaved(project_id: int, body: ExportIn, kind: str = "pdf", user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """1.13: download what is on the screen now, without saving a version first.
    kind: excel | pdf | bank | client."""
    from ..estimate.exports import to_pdf_bank, to_pdf_client
    p = require_project(db, user, project_id, "estimate")
    result, _ = run_calc(db, body.inputs, body.state, project_id)
    from datetime import datetime as _dt
    tmp = Estimate(title=body.title, version=0, rate_state=result["rates_state"], result=result, created_at=_dt.now())
    proj, est = export_payload(tmp, p, db)  # tmp is never added to the database
    est["version"] = "draft"
    fn = {"excel": to_excel, "pdf": to_pdf, "bank": to_pdf_bank, "client": to_pdf_client}.get(kind)
    if not fn:
        raise HTTPException(400, "kind must be excel, pdf, bank or client")
    data = fn(proj, est)
    tag = {"excel": "BOQ", "pdf": "Estimate", "bank": "Bank_Loan_Estimate", "client": "Client_Estimate"}[kind]
    ext = "xlsx" if kind == "excel" else "pdf"
    mt = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if kind == "excel" else "application/pdf")
    name = f"{p.code}_{tag}_draft.{ext}"
    return Response(data, media_type=mt, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


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
    can_rates = has_rates_access(db, user)
    data = excel_input.template(body.inputs or {}, [rate_out(r) for r in rows if r.is_active] if can_rates else [],
                                used, p.name, can_rates)
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
        if not has_rates_access(db, user):
            out["warnings"].append("Rates in the file were ignored – Material Rates permission is needed.")
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


# ---------------------------------------------------------------- 1.8 loan / official documents checklist
LOAN_DOCS = [("estimate_report", "Estimate Report (Detailed)"), ("boq", "BOQ (Excel)"), ("architectural", "Architectural Plan"),
             ("structural", "Structural Drawings"), ("site_photos", "Site Photos"), ("approval", "Approval Documents"),
             ("loan_form", "Loan Application Copy"), ("id_proof", "Identity Proof (Client)")]


@router.get("/projects/{project_id}/loan-docs")
def loan_docs(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..models import StoredFile
    from .files import file_out
    p = require_project(db, user, project_id, "estimate")
    files = (db.query(StoredFile).filter(StoredFile.project_id == p.id, StoredFile.is_hidden.is_(False),
                                         StoredFile.category.like("loan_%")).order_by(StoredFile.created_at.desc()).all())
    items = []
    for key, label in LOAN_DOCS:
        fs = [file_out(f) for f in files if f.category == f"loan_{key}"]
        items.append({"key": key, "label": label, "status": "uploaded" if fs else "pending", "files": fs})
    return {"items": items, "done": sum(i["status"] == "uploaded" for i in items), "total": len(items)}


# ---------------------------------------------------------------- 1.16 downloads for every tab + part estimate
class TabExportIn(BaseModel):
    inputs: dict
    state: str = DEFAULT_STATE
    label: str = ""  # e.g. "v3" or "draft" – shown on the file


def _file(data: bytes, fmt: str, stem: str) -> Response:
    if fmt == "excel":
        return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(stem + '.xlsx')}"})
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(stem + '.pdf')}"})


def _proj(db: Session, p: Project) -> dict:
    from datetime import datetime as _dt
    tmp = Estimate(title="", version=0, rate_state="", result={}, created_at=_dt.now())
    proj = export_payload(tmp, p, None)[0]  # db=None: only the project/company block is used
    from ..models import Organization
    org = db.get(Organization, 1)
    proj["company"] = {"name": (org.name if org else "") or ""}
    return proj


@router.post("/projects/{project_id}/estimate/tab-export")
def tab_export(project_id: int, body: TabExportIn, tab: str = "overview", fmt: str = "pdf",
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """1.16: the download under every Estimate tab (works without saving – 'draft')."""
    from ..estimate import tabs as T
    p = require_project(db, user, project_id, "estimate")
    if fmt not in ("pdf", "excel"):
        raise HTTPException(400, "fmt must be pdf or excel")
    if tab not in T.TAB_TITLE or tab == "part":
        raise HTTPException(400, f"tab must be one of {', '.join(k for k in T.TAB_TITLE if k != 'part')}")
    result, _ = run_calc(db, body.inputs, body.state, project_id)
    extra = None
    if tab == "compare":
        extra = {"compare": {lv: run_calc(db, {**body.inputs, "spec_level": lv}, body.state, project_id)[0]
                             for lv in ("basic", "standard", "premium")}}
    secs = T.sections_for(tab, result, extra)
    if not secs:
        raise HTTPException(422, "Nothing to download in this tab yet – calculate first")
    title = f"{T.TAB_TITLE[tab]} Estimate"
    sub = " · ".join(x for x in [f"{result.get('rates_state', body.state)} rates",
                                 f"{result.get('spec_level', '').title()} spec", body.label or "draft"] if x)
    proj = _proj(db, p)
    fn = T.render_excel if fmt == "excel" else T.render_pdf
    return _file(fn(proj, title, sub, secs), fmt, T.file_stem(p.code, p.name, T.TAB_TITLE[tab], "Estimate"))


class PartIn(BaseModel):
    inputs: dict
    state: str = DEFAULT_STATE
    floor: str = "all"
    work: str = "all"
    label: str = ""


@router.post("/projects/{project_id}/estimate/part")
def part_estimate(project_id: int, body: PartIn, fmt: str = "json", user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """1.16: Part estimate – one floor and/or one work (e.g. Ground Floor + Slab): items, materials needed,
    labour and total. fmt=json shows it; pdf / excel downloads it. Works unsaved (draft)."""
    from ..estimate import tabs as T
    p = require_project(db, user, project_id, "estimate")
    result, _ = run_calc(db, body.inputs, body.state, project_id)
    try:
        part = T.part_estimate(result, body.floor, body.work)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if fmt == "json":
        return part
    if fmt not in ("pdf", "excel"):
        raise HTTPException(400, "fmt must be json, pdf or excel")
    if not part["items"]:
        raise HTTPException(422, f"No items for {part['work_label']} on {part['floor_label']}")
    secs = T.sections_for("part", result, part)
    title = f"Part Estimate – {part['floor_label']} – {part['work_label']}"
    sub = " · ".join(x for x in [f"{result.get('rates_state', body.state)} rates", body.label or "draft"] if x)
    fn = T.render_excel if fmt == "excel" else T.render_pdf
    stem = T.file_stem(p.code, p.name, "" if body.floor == "all" else body.floor,
                       part["file_label"], "Estimate")
    return _file(fn(_proj(db, p), title, sub, secs), fmt, stem)
