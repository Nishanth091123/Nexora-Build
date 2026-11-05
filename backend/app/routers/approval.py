"""1.14 – Part 6: building approval – site & owner details, rule check, approval drawing (PDF / DXF),
fee calculator (rates are the owner's own – never guessed) and the approval stages.
The document checklist stays in /api/projects/{id}/permit (extras.py); this adds to the same record."""
from datetime import date
from datetime import date as Date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..approval import sheet as ap
from ..audit import log_action
from ..db import get_db
from ..design.edit import PlanError, recompute
from ..models import AppSetting, Estimate, User
from ..security import get_current_user, require_owner, require_project
from .design import _proj
from .extras import AUTH_LABEL, _permit

router = APIRouter(prefix="/api", tags=["approval"])

INFO_KEYS = {"owner_title", "owner_name", "co_owner", "owner_address", "door_no", "survey_no", "subdivision", "plot_no",
             "layout_name", "layout_approval_no", "patta_no", "village", "taluk", "district", "ward", "road_name",
             "landmark", "authority_place", "engineer_name", "engineer_reg_no", "allowed_fsi", "allowed_coverage_pct",
             "sheet_size", "rwh", "septic", "sump", "extra_note"}
STAGES = [("drawing_ready", "Approval drawing ready"), ("docs_collected", "Documents collected"),
          ("applied", "Application submitted (online / office)"), ("inspection", "Site inspection done"),
          ("demand", "Fee demand received"), ("fee_paid", "Fees paid"), ("approved", "Approval / permit received")]
STAGE_KEYS = {k for k, _ in STAGES}
FEE_BASIS = {"per_m2_builtup": "₹ per m² of built-up area", "per_m2_plot": "₹ per m² of plot area",
             "pct_cost": "% of construction cost (latest estimate)", "fixed": "fixed amount (₹)"}
DEFAULT_FEE_HEADS = [("Scrutiny fee", "per_m2_builtup"), ("Building licence / permit fee", "per_m2_builtup"),
                     ("Infrastructure & amenities charges", "per_m2_builtup"), ("Labour welfare cess (BOCW)", "pct_cost"),
                     ("Other charges", "fixed")]


def _clean_info(d: dict) -> dict:
    out = {}
    for k, v in (d or {}).items():
        if k not in INFO_KEYS:
            continue
        if k in ("rwh", "septic", "sump"):
            out[k] = bool(v)
        elif k in ("allowed_fsi", "allowed_coverage_pct"):
            try:
                out[k] = float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                out[k] = None
        else:
            out[k] = str(v or "").strip()[:200]
    return out


def fee_rates(db: Session) -> dict:
    row = db.get(AppSetting, "approval_fee_rates")
    return dict(row.value) if row and isinstance(row.value, dict) else {}


def rates_for(db: Session, authority: str) -> list[dict]:
    have = fee_rates(db).get(authority)
    if have:
        return have
    return [{"name": n, "basis": b, "rate": None} for n, b in DEFAULT_FEE_HEADS]


def calc_fees(rows: list[dict], builtup_m2: float, plot_m2: float, cost: float | None) -> tuple[list[dict], float]:
    out, total = [], 0.0
    for r in rows:
        rate = r.get("rate")
        base = {"per_m2_builtup": builtup_m2, "per_m2_plot": plot_m2, "pct_cost": (cost or 0) / 100, "fixed": 1}.get(r.get("basis"), 0)
        amt = None
        if rate not in (None, ""):
            if r.get("basis") == "pct_cost" and not cost:
                amt = None
            else:
                amt = round(float(rate) * base, 0)
                total += amt
        out.append({**r, "amount": amt, "basis_label": FEE_BASIS.get(r.get("basis"), "")})
    return out, round(total, 0)


def workflow_out(c) -> list[dict]:
    w = c.workflow or {}
    out = []
    for k, label in STAGES:
        s = w.get(k) or {}
        ref = s.get("ref", "")
        if k == "applied" and not ref:
            ref = c.application_no or ""
        if k == "approved" and not ref:
            ref = c.approval_no or ""
        out.append({"key": k, "label": label, "done": bool(s.get("done")), "date": s.get("date", ""), "ref": ref})
    return out


def approval_out(db: Session, c) -> dict:
    return {"site_info": {"rwh": True, "sheet_size": "A1", **(c.site_info or {})}, "authority": c.authority,
            "authorities": AUTH_LABEL, "stages": workflow_out(c), "fee_rates": rates_for(db, c.authority),
            "fee_basis": FEE_BASIS, "required": [{"key": k, "label": l} for k, l in ap.REQUIRED]}


@router.get("/projects/{project_id}/approval")
def get_approval(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_project(db, user, project_id, "approval")
    return approval_out(db, _permit(db, p))


class ApprovalIn(BaseModel):
    site_info: dict | None = None
    authority: str | None = None


@router.put("/projects/{project_id}/approval")
def put_approval(project_id: int, body: ApprovalIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_project(db, user, project_id, "approval")
    c = _permit(db, p)
    if body.site_info is not None:
        c.site_info = {**(c.site_info or {}), **_clean_info(body.site_info)}
    if body.authority and body.authority in AUTH_LABEL and body.authority != c.authority:
        from .extras import _template
        c.authority = body.authority
        c.items = _template(body.authority, c.items)
    db.commit()
    log_action(db, user, "updated", "approval", p.code, "Approval details saved", project_id=p.id)
    return approval_out(db, c)


class StageIn(BaseModel):
    key: str
    done: bool
    date: Date | None = None
    ref: str = ""


@router.put("/projects/{project_id}/approval/stage")
def set_stage(project_id: int, body: StageIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_project(db, user, project_id, "approval")
    if body.key not in STAGE_KEYS:
        raise HTTPException(400, "Unknown stage")
    c = _permit(db, p)
    w = dict(c.workflow or {})
    d = (body.date or date.today()) if body.done else None
    w[body.key] = {"done": body.done, "date": d.isoformat() if d else "", "ref": body.ref.strip()[:80]}
    c.workflow = w
    if body.key == "applied" and body.ref.strip():
        c.application_no = body.ref.strip()[:80]
    if body.key == "approved":
        if body.ref.strip():
            c.approval_no = body.ref.strip()[:80]
        c.approval_date = d
    # keep the project tracker (Clients page) in step
    pw = dict(p.workflow or {})
    link = {"drawing_ready": "approval_drawing", "applied": "submission"}
    if body.key in link:
        pw[link[body.key]] = {"done": body.done, "date": d.isoformat() if d else ""}
        p.workflow = pw
    db.commit()
    label = dict(STAGES)[body.key]
    log_action(db, user, "updated", "approval", p.code, f"{label}: {'done' if body.done else 'pending'}", project_id=p.id)
    return {"stages": workflow_out(c)}


class CheckIn(BaseModel):
    plan: dict
    site_info: dict | None = None


def _plan_info(db: Session, p, c, body: CheckIn) -> tuple[dict, dict]:
    try:
        plan = recompute(body.plan)
    except PlanError as e:
        raise HTTPException(422, {"message": str(e), "questions": [str(e)]})
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(400, f"Invalid plan: {e}")
    info = {"rwh": True, **(c.site_info or {}), **_clean_info(body.site_info or {}), "authority": c.authority}
    return plan, info


@router.post("/projects/{project_id}/approval/check")
def check(project_id: int, body: CheckIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Rule check (required vs provided) + fee calculation for the plan on the screen."""
    p = require_project(db, user, project_id, "approval")
    c = _permit(db, p)
    plan, info = _plan_info(db, p, c, body)
    res = ap.compliance(plan, info)
    est = (db.query(Estimate).filter(Estimate.project_id == p.id, Estimate.is_hidden.is_(False))
           .order_by(Estimate.version.desc()).first())
    cost = float(est.grand_total) if est and est.grand_total else None
    fees, total = calc_fees(rates_for(db, c.authority), res["area"]["total_builtup_m2"], res["area"]["plot_m2"], cost)
    return {**res, "fees": fees, "fee_total": total, "estimate_total": cost,
            "estimate_label": f"latest saved estimate v{est.version}" if est else "no saved estimate yet"}


@router.post("/projects/{project_id}/approval/sheet")
def sheet(project_id: int, body: CheckIn, kind: str = "pdf", style: str = "paper", size: str = "",
          version: str = "draft", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The approval drawing (one sheet) for the plan on the screen – PDF (A1 / A2 / A3, paper or CAD colours) or DXF."""
    p = require_project(db, user, project_id, "approval")
    c = _permit(db, p)
    plan, info = _plan_info(db, p, c, body)
    size = size if size in ap.SIZES else (info.get("sheet_size") if info.get("sheet_size") in ap.SIZES else "A1")
    meta = {"version": version or "draft", "date": date.today().strftime("%d-%m-%Y")}
    try:
        if kind == "dxf":
            data, mt, ext = ap.approval_dxf(plan, info, _proj(p, db)), "application/dxf", "dxf"
        else:
            data, mt, ext = ap.approval_pdf(plan, _proj(p, db), info, meta, "cad" if style == "cad" else "paper", size), "application/pdf", "pdf"
    except ap.NeedInfo as e:
        raise HTTPException(422, {"message": "Please fill these details for the approval drawing", "questions": e.questions})
    name = f"{p.code}_Approval_Drawing_{size if ext == 'pdf' else ''}{'_CAD' if style == 'cad' and ext == 'pdf' else ''}.{ext}".replace("_.", ".")
    return Response(data, media_type=mt, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


class FeeRatesIn(BaseModel):
    authority: str
    rows: list[dict]


@router.put("/approval/fee-rates")
def put_fee_rates(body: FeeRatesIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    """The owner's own fee rates per authority (from the local body's current order) – the app never assumes a rate."""
    if body.authority not in AUTH_LABEL:
        raise HTTPException(400, "Unknown authority")
    rows = []
    for r in body.rows[:20]:
        name = str(r.get("name") or "").strip()[:120]
        basis = r.get("basis") if r.get("basis") in FEE_BASIS else "fixed"
        try:
            rate = float(r["rate"]) if r.get("rate") not in (None, "") else None
        except (TypeError, ValueError):
            rate = None
        if name:
            rows.append({"name": name, "basis": basis, "rate": rate})
    row = db.get(AppSetting, "approval_fee_rates")
    if not row:
        row = AppSetting(key="approval_fee_rates", value={})
        db.add(row)
    row.value = {**(row.value or {}), body.authority: rows}
    db.commit()
    log_action(db, owner, "updated", "settings", "approval_fee_rates", AUTH_LABEL[body.authority])
    return {"authority": body.authority, "rows": rows}
