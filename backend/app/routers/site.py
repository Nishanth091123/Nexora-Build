"""Phase 5 – Site Management: daily work (DPR + activities), photos, materials, manpower, quality, safety,
overview dashboard and reports. Everything is kept (hide instead of delete)."""
from datetime import date, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..estimate.rates_seed import DEFAULT_STATE
from ..models import (Attendance, Estimate, MaterialEntry, Project, QualityCheck, RateItem, SafetyRecord, SiteActivity,
                      SitePhoto, SiteReport, StoredFile, User, Worker)
from ..security import get_current_user, project_permissions
from ..site import logic, reports
from .files import read_and_check, store
from .pm import as_dicts, refresh_project, stage_out, stages_of

router = APIRouter(prefix="/api", tags=["site"])


def site(db: Session, user: User, project_id: int, write: bool = False) -> Project:
    p = db.get(Project, project_id)
    if not p or p.is_hidden:
        raise HTTPException(404, "Project not found")
    perms = project_permissions(db, user, p)
    if not perms.get("site"):
        raise HTTPException(403, "You don't have Site access for this project")
    return p


def iso(d):
    return d.isoformat() if d else None


def photo_url(fid):
    return f"/api/files/{fid}/download" if fid else None


# ---------------------------------------------------------------- daily report (DPR) + activities
class ReportIn(BaseModel):
    report_date: date
    weather: str = ""
    work_done: str = ""
    next_plan: str = ""
    remarks: str = ""


def report_out(r: SiteReport | None, d: date) -> dict:
    if not r:
        return {"report_date": d.isoformat(), "weather": "", "work_done": "", "next_plan": "", "remarks": "", "saved": False}
    return {"id": r.id, "report_date": r.report_date.isoformat(), "weather": r.weather, "work_done": r.work_done,
            "next_plan": r.next_plan, "remarks": r.remarks, "saved": True, "updated_at": iso(r.updated_at)}


@router.get("/projects/{project_id}/site/report")
def get_report(project_id: int, day: date | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    site(db, user, project_id)
    d = day or date.today()
    r = db.query(SiteReport).filter_by(project_id=project_id, report_date=d).first()
    return report_out(r, d)


@router.put("/projects/{project_id}/site/report")
def save_report(project_id: int, body: ReportIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = site(db, user, project_id, True)
    r = db.query(SiteReport).filter_by(project_id=project_id, report_date=body.report_date).first()
    if not r:
        r = SiteReport(project_id=project_id, report_date=body.report_date, created_by=user.id)
        db.add(r)
    for k in ("weather", "work_done", "next_plan", "remarks"):
        setattr(r, k, getattr(body, k))
    db.commit()
    log_action(db, user, "saved", "daily report", r.id, f"DPR {body.report_date:%d %b %Y}", project_id=p.id)
    return report_out(r, body.report_date)


def act_out(a: SiteActivity, stages: dict) -> dict:
    return {"id": a.id, "work_date": a.work_date.isoformat(), "title": a.title, "location": a.location,
            "stage_id": a.stage_id, "stage": stages.get(a.stage_id, ""), "status": a.status, "progress": a.progress,
            "photo_url": photo_url(a.photo_file_id), "photo_file_id": a.photo_file_id, "notes": a.notes,
            "created_at": iso(a.created_at)}


def stage_names(db, pid):
    return {s.id: s.name for s in stages_of(db, pid)}


@router.get("/projects/{project_id}/site/activities")
def list_activities(project_id: int, day: date | None = None, days: int = 1, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    site(db, user, project_id)
    d = day or date.today()
    q = db.query(SiteActivity).filter(SiteActivity.project_id == project_id, SiteActivity.is_hidden.is_(False),
                                      SiteActivity.work_date <= d, SiteActivity.work_date > d - timedelta(days=max(1, days)))
    names = stage_names(db, project_id)
    return [act_out(a, names) for a in q.order_by(SiteActivity.work_date.desc(), SiteActivity.id).all()]


class ActivityIn(BaseModel):
    work_date: date | None = None
    title: str | None = None
    location: str | None = None
    stage_id: int | None = None
    status: str | None = None
    progress: float | None = None
    photo_file_id: int | None = None
    notes: str | None = None
    stage_progress: float | None = None  # also update the schedule stage's progress


def _apply_stage_progress(db, user, p, stage_id, value):
    if stage_id and value is not None:
        from ..models import ScheduleStage
        s = db.get(ScheduleStage, stage_id)
        if s and s.project_id == p.id:
            v = min(100.0, max(0.0, float(value)))
            s.progress = v
            if v > 0 and not s.actual_start:
                s.actual_start = date.today()
            if v >= 100 and not s.actual_end:
                s.actual_end = date.today()
            db.commit()
            refresh_project(db, p)


@router.post("/projects/{project_id}/site/activities")
def add_activity(project_id: int, body: ActivityIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = site(db, user, project_id, True)
    if not (body.title or "").strip():
        raise HTTPException(422, "Activity name is required")
    a = SiteActivity(project_id=project_id, work_date=body.work_date or date.today(), title=body.title.strip()[:200],
                     location=body.location or "", stage_id=body.stage_id,
                     status=body.status if body.status in ("pending", "in_progress", "completed") else "pending",
                     progress=min(100, max(0, body.progress or 0)), photo_file_id=body.photo_file_id, notes=body.notes or "",
                     created_by=user.id)
    if a.status == "completed":
        a.progress = 100
    db.add(a)
    db.commit()
    _apply_stage_progress(db, user, p, a.stage_id, body.stage_progress)
    log_action(db, user, "added", "site activity", a.id, f"{a.title} ({a.status})", project_id=p.id)
    return act_out(a, stage_names(db, project_id))


@router.patch("/site/activities/{activity_id}")
def edit_activity(activity_id: int, body: ActivityIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(SiteActivity, activity_id)
    if not a:
        raise HTTPException(404, "Activity not found")
    p = site(db, user, a.project_id, True)
    data = body.model_dump(exclude_unset=True)
    sp = data.pop("stage_progress", None)
    for k, v in data.items():
        if v is not None:
            setattr(a, k, v)
    if a.status == "completed":
        a.progress = 100
    db.commit()
    _apply_stage_progress(db, user, p, a.stage_id, sp)
    return act_out(a, stage_names(db, a.project_id))


@router.post("/site/activities/{activity_id}/hide")
def hide_activity(activity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "owner":
        raise HTTPException(403, "Only the owner can delete – ask the owner")
    a = db.get(SiteActivity, activity_id)
    if not a:
        raise HTTPException(404, "Activity not found")
    site(db, user, a.project_id, True)
    a.is_hidden = True
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- photos
def photo_out(ph: SitePhoto) -> dict:
    return {"id": ph.id, "file_id": ph.file_id, "url": photo_url(ph.file_id), "caption": ph.caption,
            "taken_on": ph.taken_on.isoformat(), "location": ph.location, "latitude": ph.latitude,
            "longitude": ph.longitude, "activity_id": ph.activity_id}


@router.post("/projects/{project_id}/site/photos")
async def upload_photo(project_id: int, file: UploadFile = File(...), caption: str = Form(""), taken_on: str = Form(""),
                       location: str = Form(""), latitude: str = Form(""), longitude: str = Form(""),
                       activity_id: str = Form(""), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = site(db, user, project_id, True)
    name, data, ctype = await read_and_check(file)
    if not ctype.startswith("image/"):
        raise HTTPException(415, "Site photos must be JPG / PNG / WEBP")
    f = store(db, user, name, data, ctype, "photo", project_id)

    def fnum(v):
        try:
            return float(v) if v not in ("", None) else None
        except ValueError:
            return None
    try:
        d = date.fromisoformat(taken_on) if taken_on else date.today()
    except ValueError:
        d = date.today()
    ph = SitePhoto(project_id=project_id, file_id=f.id, caption=caption[:200] or name, taken_on=d, location=location[:120],
                   latitude=fnum(latitude), longitude=fnum(longitude),
                   activity_id=int(activity_id) if activity_id.isdigit() else None, created_by=user.id)
    db.add(ph)
    db.commit()
    if ph.activity_id:
        a = db.get(SiteActivity, ph.activity_id)
        if a and a.project_id == project_id and not a.photo_file_id:
            a.photo_file_id = f.id
            db.commit()
    log_action(db, user, "uploaded", "site photo", ph.id, ph.caption, project_id=p.id)
    return photo_out(ph)


@router.get("/projects/{project_id}/site/photos")
def list_photos(project_id: int, limit: int = 60, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    site(db, user, project_id)
    rows = (db.query(SitePhoto).filter(SitePhoto.project_id == project_id, SitePhoto.is_hidden.is_(False))
            .order_by(SitePhoto.taken_on.desc(), SitePhoto.id.desc()).limit(min(500, limit)).all())
    return [photo_out(x) for x in rows]


@router.post("/site/photos/{photo_id}/hide")
def hide_photo(photo_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "owner":
        raise HTTPException(403, "Only the owner can delete – ask the owner")
    ph = db.get(SitePhoto, photo_id)
    if not ph:
        raise HTTPException(404, "Photo not found")
    site(db, user, ph.project_id, True)
    ph.is_hidden = True
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- materials
def planned_materials(db: Session, project_id: int) -> tuple[dict, dict | None]:
    e = (db.query(Estimate).filter(Estimate.project_id == project_id, Estimate.is_hidden.is_(False))
         .order_by(Estimate.version.desc()).first())
    if not e:
        return {}, None
    out = {}
    for m in (e.result or {}).get("materials", []):
        out[m.get("code") or m["name"]] = {"code": m.get("code"), "name": m["name"], "unit": m["unit"], "planned": m["qty"],
                                           "amount": m.get("amount", 0)}
    return out, {"id": e.id, "version": e.version, "title": e.title}


def material_summary(db: Session, project_id: int, upto: date | None = None) -> dict:
    planned, est = planned_materials(db, project_id)
    q = db.query(MaterialEntry).filter(MaterialEntry.project_id == project_id, MaterialEntry.is_hidden.is_(False))
    if upto:
        q = q.filter(MaterialEntry.entry_date <= upto)
    rows: dict = {}
    for code, m in planned.items():
        rows[code] = {**m, "received": 0.0, "used": 0.0}
    for e in q.all():
        key = e.code or e.name
        r = rows.setdefault(key, {"code": e.code, "name": e.name, "unit": e.unit, "planned": 0.0, "amount": 0,
                                  "received": 0.0, "used": 0.0})
        r[e.kind if e.kind in ("received", "used") else "received"] += e.qty
    items = []
    for r in rows.values():
        r["stock"] = round(r["received"] - r["used"], 2)
        r["pct"] = round(r["received"] / r["planned"] * 100, 1) if r["planned"] else None
        items.append(r)
    items.sort(key=lambda r: (-(r.get("amount") or 0), r["name"]))
    tot_planned_amt = sum(r.get("amount") or 0 for r in items if r["planned"])
    weighted = (sum((r.get("amount") or 0) * min(1.0, r["received"] / r["planned"]) for r in items if r["planned"])
                / tot_planned_amt * 100) if tot_planned_amt else None
    return {"items": items, "estimate": est, "received_pct": round(weighted, 1) if weighted is not None else None}


@router.get("/projects/{project_id}/site/materials")
def materials(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = site(db, user, project_id)
    s = material_summary(db, project_id)
    entries = (db.query(MaterialEntry).filter(MaterialEntry.project_id == project_id, MaterialEntry.is_hidden.is_(False))
               .order_by(MaterialEntry.entry_date.desc(), MaterialEntry.id.desc()).limit(200).all())
    state = p.state or DEFAULT_STATE
    lib = db.query(RateItem).filter(RateItem.state == state, RateItem.kind == "material", RateItem.is_active.is_(True)).all() or \
        db.query(RateItem).filter(RateItem.state == DEFAULT_STATE, RateItem.kind == "material", RateItem.is_active.is_(True)).all()
    return {**s, "entries": [{"id": e.id, "entry_date": e.entry_date.isoformat(), "code": e.code, "name": e.name, "unit": e.unit,
                              "kind": e.kind, "qty": e.qty, "rate": e.rate, "supplier": e.supplier, "bill_no": e.bill_no,
                              "notes": e.notes} for e in entries],
            "library": [{"code": r.code, "name": r.name, "unit": r.unit, "rate": r.standard} for r in lib]}


class MaterialIn(BaseModel):
    entry_date: date | None = None
    code: str = ""
    name: str = ""
    unit: str = ""
    kind: str = "received"
    qty: float
    rate: float | None = None
    supplier: str = ""
    bill_no: str = ""
    notes: str = ""


@router.post("/projects/{project_id}/site/materials")
def add_material(project_id: int, body: MaterialIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = site(db, user, project_id, True)
    if body.qty <= 0:
        raise HTTPException(422, "Quantity must be more than 0")
    name, unit = body.name, body.unit
    if body.code and (not name or not unit):
        r = db.query(RateItem).filter(RateItem.code == body.code).first()
        if r:
            name, unit = name or r.name, unit or r.unit
    if not name:
        raise HTTPException(422, "Material name is required")
    e = MaterialEntry(project_id=project_id, entry_date=body.entry_date or date.today(), code=body.code, name=name[:120],
                      unit=unit[:20], kind=body.kind if body.kind in ("received", "used") else "received", qty=body.qty,
                      rate=body.rate, supplier=body.supplier[:120], bill_no=body.bill_no[:60], notes=body.notes, created_by=user.id)
    db.add(e)
    db.commit()
    log_action(db, user, e.kind, "material", e.id, f"{e.name}: {e.qty:g} {e.unit}", project_id=p.id)
    return {"id": e.id}


@router.post("/site/materials/{entry_id}/hide")
def hide_material(entry_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "owner":
        raise HTTPException(403, "Only the owner can delete – ask the owner")
    e = db.get(MaterialEntry, entry_id)
    if not e:
        raise HTTPException(404, "Entry not found")
    site(db, user, e.project_id, True)
    e.is_hidden = True
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- manpower
def trade_rates(db: Session, state: str) -> dict:
    rows = db.query(RateItem).filter(RateItem.state == state, RateItem.kind == "labour").all() or \
        db.query(RateItem).filter(RateItem.state == DEFAULT_STATE, RateItem.kind == "labour").all()
    return {r.code: {"name": r.name, "wage": r.standard} for r in rows}


def worker_out(w: Worker, trades: dict) -> dict:
    t = trades.get(w.trade, {})
    return {"id": w.id, "name": w.name, "trade": w.trade, "trade_name": t.get("name", w.trade), "phone": w.phone,
            "day_wage": w.day_wage if w.day_wage is not None else t.get("wage"), "contractor": w.contractor,
            "is_active": w.is_active}


@router.get("/projects/{project_id}/site/workers")
def list_workers(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = site(db, user, project_id)
    trades = trade_rates(db, p.state or DEFAULT_STATE)
    rows = db.query(Worker).filter(Worker.project_id == project_id, Worker.is_hidden.is_(False)).order_by(Worker.is_active.desc(), Worker.trade, Worker.name).all()
    return {"workers": [worker_out(w, trades) for w in rows], "trades": [{"code": k, **v} for k, v in trades.items()]}


class WorkerIn(BaseModel):
    name: str | None = None
    trade: str | None = None
    phone: str | None = None
    day_wage: float | None = None
    contractor: str | None = None
    is_active: bool | None = None


@router.post("/projects/{project_id}/site/workers")
def add_worker(project_id: int, body: WorkerIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = site(db, user, project_id, True)
    if not (body.name or "").strip():
        raise HTTPException(422, "Worker name is required")
    w = Worker(project_id=project_id, name=body.name.strip()[:120], trade=body.trade or "mason", phone=body.phone or "",
               day_wage=body.day_wage, contractor=body.contractor or "")
    db.add(w)
    db.commit()
    return worker_out(w, trade_rates(db, p.state or DEFAULT_STATE))


@router.patch("/site/workers/{worker_id}")
def edit_worker(worker_id: int, body: WorkerIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    w = db.get(Worker, worker_id)
    if not w:
        raise HTTPException(404, "Worker not found")
    p = site(db, user, w.project_id, True)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(w, k, v)
    db.commit()
    return worker_out(w, trade_rates(db, p.state or DEFAULT_STATE))


@router.get("/projects/{project_id}/site/attendance")
def get_attendance(project_id: int, day: date | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = site(db, user, project_id)
    d = day or date.today()
    trades = trade_rates(db, p.state or DEFAULT_STATE)
    marks = {a.worker_id: a for a in db.query(Attendance).filter_by(project_id=project_id, work_date=d).all()}
    out = []
    for w in db.query(Worker).filter(Worker.project_id == project_id, Worker.is_hidden.is_(False)).order_by(Worker.trade, Worker.name).all():
        a = marks.get(w.id)
        if not w.is_active and not a:
            continue
        wo = worker_out(w, trades)
        out.append({**wo, "status": a.status if a else None, "ot_hours": a.ot_hours if a else 0,
                    "wage": a.wage if a and a.wage is not None else wo["day_wage"]})
    return {"date": d.isoformat(), "rows": out, "summary": attendance_summary(db, project_id, d, trades)}


def attendance_summary(db: Session, project_id: int, d: date, trades: dict) -> dict:
    rows = (db.query(Attendance, Worker).join(Worker, Worker.id == Attendance.worker_id)
            .filter(Attendance.project_id == project_id, Attendance.work_date == d).all())
    by_trade: dict = {}
    present, cost = 0.0, 0.0
    for a, w in rows:
        f = {"present": 1.0, "half": 0.5}.get(a.status, 0.0)
        if not f:
            continue
        present += f
        wage = a.wage if a.wage is not None else (w.day_wage if w.day_wage is not None else trades.get(w.trade, {}).get("wage", 0))
        cost += f * (wage or 0) + (a.ot_hours or 0) * (wage or 0) / 8
        t = by_trade.setdefault(w.trade, {"trade": w.trade, "name": trades.get(w.trade, {}).get("name", w.trade), "count": 0.0})
        t["count"] += f
    return {"present": present, "wages": round(cost), "by_trade": sorted(by_trade.values(), key=lambda x: -x["count"])}


class AttendanceIn(BaseModel):
    work_date: date
    entries: list[dict]  # {worker_id, status, ot_hours?, wage?}


@router.post("/projects/{project_id}/site/attendance")
def save_attendance(project_id: int, body: AttendanceIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = site(db, user, project_id, True)
    valid = {w.id for w in db.query(Worker).filter(Worker.project_id == project_id, Worker.is_hidden.is_(False)).all()}
    n = 0
    for e in body.entries:
        wid = int(e.get("worker_id") or 0)
        if wid not in valid:
            continue
        st = e.get("status")
        if st not in ("present", "half", "absent"):
            continue
        a = db.query(Attendance).filter_by(worker_id=wid, work_date=body.work_date).first()
        if not a:
            a = Attendance(project_id=project_id, worker_id=wid, work_date=body.work_date, created_by=user.id)
            db.add(a)
        a.status = st
        a.ot_hours = float(e.get("ot_hours") or 0)
        if e.get("wage") not in (None, ""):
            a.wage = float(e["wage"])
        n += 1
    db.commit()
    log_action(db, user, "saved", "attendance", body.work_date.isoformat(), f"{n} workers", project_id=p.id)
    return get_attendance(project_id, body.work_date, user, db)


# ---------------------------------------------------------------- quality
def qc_out(q: QualityCheck, names: dict) -> dict:
    return {"id": q.id, "stage": q.stage, "item": q.item, "standard": q.standard, "status": q.status, "remarks": q.remarks,
            "checked_on": iso(q.checked_on), "checked_by": names.get(q.checked_by, ""), "photo_url": photo_url(q.photo_file_id)}


@router.get("/projects/{project_id}/site/quality")
def list_quality(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    site(db, user, project_id)
    rows = db.query(QualityCheck).filter(QualityCheck.project_id == project_id, QualityCheck.is_hidden.is_(False)).all()
    if not rows and not db.query(QualityCheck.id).filter(QualityCheck.project_id == project_id).first():  # first visit: standard checklist (stored, so it is never lost)
        for i, (stg, item, std) in enumerate(logic.QC_TEMPLATE):
            db.add(QualityCheck(project_id=project_id, stage=stg, item=item, standard=std, sort=i))
        db.commit()
        rows = db.query(QualityCheck).filter(QualityCheck.project_id == project_id, QualityCheck.is_hidden.is_(False)).all()
    names = {u.id: u.full_name or u.username for u in db.query(User).all()}
    rows.sort(key=lambda q: (q.sort, q.id))
    return [qc_out(q, names) for q in rows]


class QualityIn(BaseModel):
    stage: str | None = None
    item: str | None = None
    standard: str | None = None
    status: str | None = None
    remarks: str | None = None
    photo_file_id: int | None = None


@router.post("/projects/{project_id}/site/quality")
def add_quality(project_id: int, body: QualityIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    site(db, user, project_id, True)
    if not (body.item or "").strip():
        raise HTTPException(422, "Check item is required")
    n = db.query(func.count(QualityCheck.id)).filter(QualityCheck.project_id == project_id).scalar() or 0
    q = QualityCheck(project_id=project_id, stage=body.stage or "structure", item=body.item.strip()[:160],
                     standard=body.standard or "", sort=n + 100)
    db.add(q)
    db.commit()
    return qc_out(q, {})


@router.patch("/site/quality/{qc_id}")
def edit_quality(qc_id: int, body: QualityIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.get(QualityCheck, qc_id)
    if not q:
        raise HTTPException(404, "Check not found")
    p = site(db, user, q.project_id, True)
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in ("pending", "checked", "failed"):
        raise HTTPException(422, "status must be pending, checked or failed")
    for k, v in data.items():
        if v is not None:
            setattr(q, k, v)
    if "status" in data:
        q.checked_on = date.today() if q.status != "pending" else None
        q.checked_by = user.id if q.status != "pending" else None
        log_action(db, user, q.status, "quality check", q.id, q.item, project_id=p.id, commit=False)
    db.commit()
    names = {u.id: u.full_name or u.username for u in db.query(User).all()}
    return qc_out(q, names)


# ---------------------------------------------------------------- safety & issues
def safety_out(s: SafetyRecord) -> dict:
    return {"id": s.id, "record_date": s.record_date.isoformat(), "kind": s.kind, "title": s.title, "details": s.details,
            "severity": s.severity, "status": s.status, "action": s.action, "delay_days": s.delay_days,
            "closed_on": iso(s.closed_on)}


@router.get("/projects/{project_id}/site/safety")
def list_safety(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    site(db, user, project_id)
    rows = (db.query(SafetyRecord).filter(SafetyRecord.project_id == project_id, SafetyRecord.is_hidden.is_(False))
            .order_by(SafetyRecord.status.desc(), SafetyRecord.record_date.desc(), SafetyRecord.id.desc()).limit(300).all())
    return [safety_out(s) for s in rows]


class SafetyIn(BaseModel):
    record_date: date | None = None
    kind: str | None = None
    title: str | None = None
    details: str | None = None
    severity: str | None = None
    status: str | None = None
    action: str | None = None
    delay_days: float | None = None


KINDS = ("toolbox", "ppe", "inspection", "near_miss", "incident", "issue", "delay")


@router.post("/projects/{project_id}/site/safety")
def add_safety(project_id: int, body: SafetyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = site(db, user, project_id, True)
    if not (body.title or "").strip():
        raise HTTPException(422, "Title is required")
    kind = body.kind if body.kind in KINDS else "issue"
    closed_kinds = ("toolbox", "ppe", "inspection")
    s = SafetyRecord(project_id=project_id, record_date=body.record_date or date.today(), kind=kind, title=body.title.strip()[:200],
                     details=body.details or "", severity=body.severity if body.severity in ("low", "medium", "high") else "low",
                     status=body.status if body.status in ("open", "closed") else ("closed" if kind in closed_kinds else "open"),
                     action=body.action or "", delay_days=body.delay_days or 0, created_by=user.id)
    db.add(s)
    db.commit()
    log_action(db, user, "recorded", kind.replace("_", " "), s.id, s.title, project_id=p.id)
    return safety_out(s)


@router.patch("/site/safety/{record_id}")
def edit_safety(record_id: int, body: SafetyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(SafetyRecord, record_id)
    if not s:
        raise HTTPException(404, "Record not found")
    site(db, user, s.project_id, True)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(s, k, v)
    if s.status == "closed" and not s.closed_on:
        s.closed_on = date.today()
    db.commit()
    return safety_out(s)


# ---------------------------------------------------------------- overview
@router.get("/projects/{project_id}/site/overview")
def overview(project_id: int, day: date | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = site(db, user, project_id)
    d = day or date.today()
    srows = stages_of(db, project_id)
    sd = as_dicts(srows)
    names = {s.id: s.name for s in srows}
    acts = (db.query(SiteActivity).filter(SiteActivity.project_id == project_id, SiteActivity.is_hidden.is_(False),
                                          SiteActivity.work_date == d).order_by(SiteActivity.id).all())
    recent = (db.query(SiteActivity).filter(SiteActivity.project_id == project_id, SiteActivity.is_hidden.is_(False),
                                            SiteActivity.work_date <= d)
              .order_by(SiteActivity.work_date.desc(), SiteActivity.id.desc()).limit(20).all())
    current = next((a for a in recent if a.status != "completed" and a.photo_file_id), None) or \
        next((a for a in recent if a.photo_file_id), None) or (recent[0] if recent else None)
    photos = (db.query(SitePhoto).filter(SitePhoto.project_id == project_id, SitePhoto.is_hidden.is_(False),
                                         SitePhoto.taken_on <= d)
              .order_by(SitePhoto.taken_on.desc(), SitePhoto.id.desc()).limit(6).all())
    mats = material_summary(db, project_id, d)
    trades = trade_rates(db, p.state or DEFAULT_STATE)
    att = attendance_summary(db, project_id, d, trades)
    present = (db.query(Attendance, Worker).join(Worker, Worker.id == Attendance.worker_id)
               .filter(Attendance.project_id == project_id, Attendance.work_date == d, Attendance.status != "absent").all())
    qc = db.query(QualityCheck).filter(QualityCheck.project_id == project_id, QualityCheck.is_hidden.is_(False)).all()
    qc.sort(key=lambda q: (q.sort, q.id))
    cur_groups = {s.stage_group for s in srows if 0 < s.progress < 100} or {"foundation", "structure"}
    qc_now = [q for q in qc if q.stage in cur_groups] or qc
    safety = db.query(SafetyRecord).filter(SafetyRecord.project_id == project_id, SafetyRecord.is_hidden.is_(False),
                                           SafetyRecord.status == "open").all()
    issues = [s for s in safety if s.kind in ("issue", "delay")]
    cement = next((m for m in mats["items"] if m.get("code") == "cement"), None)
    ins = logic.insights(sd, d, cement["used"] if cement else 0, cement["planned"] if cement else 0,
                         sum(1 for q in qc_now if q.status == "pending"), sum(1 for q in qc if q.status == "failed"),
                         len(issues), len(safety) - len(issues))
    return {
        "date": d.isoformat(),
        "project": {"id": p.id, "name": p.name, "location": p.location, "district": p.district, "state": p.state,
                    "latitude": p.latitude, "longitude": p.longitude, "start_date": iso(p.start_date), "end_date": iso(p.end_date),
                    "health": p.health, "progress": p.progress},
        "progress": {"overall": logic.overall(sd) if srows else p.progress, "planned": logic.planned(sd, d) if srows else None,
                     "variance_days": logic.schedule_variance_days(sd, d) if srows else 0,
                     "health": logic.health(sd, d) if srows else p.health, "pipeline": logic.pipeline(sd), "has_schedule": bool(srows)},
        "cards": {"activities": len(acts), "activities_done": sum(1 for a in acts if a.status == "completed"),
                  "workers": att["present"], "wages": att["wages"], "material_pct": mats["received_pct"],
                  "issues": len(issues)},
        "current": act_out(current, names) if current else None,
        "activities": [act_out(a, names) for a in acts],
        "photos": [photo_out(x) for x in photos],
        "materials": [m for m in mats["items"] if m["planned"]][:5] or mats["items"][:5],
        "manpower": {"by_trade": att["by_trade"], "present": [{"name": w.name, "trade": w.trade,
                     "trade_name": trades.get(w.trade, {}).get("name", w.trade), "status": a.status} for a, w in present]},
        "quality": [qc_out(q, {}) for q in qc_now[:6]],
        "gantt": [stage_out(s) for s in srows],
        "insights": ins,
        "estimate": mats["estimate"],
    }


# ---------------------------------------------------------------- reports
@router.get("/projects/{project_id}/site/dpr.pdf")
def dpr_pdf(project_id: int, day: date | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = site(db, user, project_id)
    d = day or date.today()
    data = reports.dpr_pdf(db, p, d)
    name = f"{p.code}_DPR_{d:%Y-%m-%d}.pdf"
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.get("/projects/{project_id}/site/report.xlsx")
def period_excel(project_id: int, start: date | None = None, end: date | None = None, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    p = site(db, user, project_id)
    e = end or date.today()
    s = start or (e - timedelta(days=29))
    if s > e:
        raise HTTPException(400, "Start date is after end date")
    data = reports.period_excel(db, p, s, e)
    name = f"{p.code}_Site_Report_{s:%Y%m%d}-{e:%Y%m%d}.xlsx"
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


class LocationIn(BaseModel):
    latitude: float
    longitude: float


@router.put("/projects/{project_id}/site/location")
def set_location(project_id: int, body: LocationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = site(db, user, project_id, True)
    if not (-90 <= body.latitude <= 90 and -180 <= body.longitude <= 180):
        raise HTTPException(422, "Invalid coordinates")
    p.latitude, p.longitude = body.latitude, body.longitude
    db.commit()
    log_action(db, user, "updated", "project", p.code, "Site location set", project_id=p.id)
    return {"latitude": p.latitude, "longitude": p.longitude}


# ---------------------------------------------------------------- Home: site weather card (Phase 7.2)
import re as _re  # noqa: E402

CONCRETE_WORDS = _re.compile(r"cast|concret|pcc|rcc|slab|column|beam|footing|lintel|plinth|roof|pour|chajja|sunshade|staircase waist", _re.I)


@router.get("/projects/{project_id}/weather-context")
def weather_context(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """What the Home weather card needs besides the forecast: site location, current stages, concrete still curing.
    The forecast itself is fetched by the browser (free Open-Meteo, no key)."""
    p = db.get(Project, project_id)
    if not p or p.is_hidden:
        raise HTTPException(404, "Project not found")
    perms = project_permissions(db, user, p)
    if not perms.get("view"):
        raise HTTPException(403, "No access to this project")
    today = date.today()
    out = {"project": {"id": p.id, "name": p.name, "code": p.code, "location": p.location, "district": p.district,
                       "state": p.state, "latitude": p.latitude, "longitude": p.longitude},
           "stages": [], "curing": [], "can_set_location": bool(perms.get("site"))}
    srows = [s for s in stages_of(db, project_id) if not s.is_milestone]
    names = {s.id: s.name for s in srows}
    current = [s for s in srows if 0 < (s.progress or 0) < 100] or \
        [s for s in srows if (s.progress or 0) < 100 and s.start_date and s.start_date <= today + timedelta(days=7)]
    current.sort(key=lambda s: (s.start_date or today))
    out["stages"] = [{"name": s.name, "group": s.stage_group, "progress": round(s.progress or 0),
                      "start": iso(s.start_date), "end": iso(s.end_date)} for s in current[:3]]
    if perms.get("site"):
        acts = (db.query(SiteActivity).filter(SiteActivity.project_id == project_id, SiteActivity.is_hidden.is_(False),
                                              SiteActivity.work_date >= today - timedelta(days=13),
                                              SiteActivity.work_date <= today, SiteActivity.status != "pending")
                .order_by(SiteActivity.work_date.desc(), SiteActivity.id.desc()).all())
        seen = set()
        for a in acts:
            label = f"{a.title} {names.get(a.stage_id, '')}"
            if not CONCRETE_WORDS.search(label):
                continue
            key = (a.title.strip().lower(), (a.location or "").strip().lower())
            if key in seen:
                continue
            seen.add(key)
            out["curing"].append({"title": a.title, "location": a.location or "", "cast_on": iso(a.work_date),
                                  "day": (today - a.work_date).days + 1})
        out["curing"] = out["curing"][:4]
    return out
