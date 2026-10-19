"""Phase 6.6 – BBS (bar bending schedule), plan-approval checklist and AI photo check."""
from __future__ import annotations

import io
import re
import zipfile
from datetime import date, datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import bbs, bbs_export, llm
from ..ai import photo
from ..ai.tools import kb_search
from ..audit import log_action
from ..db import get_db
from ..models import AIPhotoCheck, BbsSchedule, Estimate, PermitChecklist, Project, StoredFile, User
from ..security import get_current_user, project_permissions, require_project
from ..storage import backend_for

router = APIRouter(prefix="/api", tags=["bbs-permit-photo"])


def _proj(p: Project) -> dict:
    return {"name": p.name, "code": p.code, "location": p.location}


def _need(db: Session, user: User, project_id: int, *mods: str) -> Project:
    p = require_project(db, user, project_id, "view")
    perms = project_permissions(db, user, p)
    if not any(perms.get(m) for m in mods):
        raise HTTPException(403, f"You need {' / '.join(mods)} access on this project")
    return p


# ================================================================ BBS
class BbsIn(BaseModel):
    title: str = "BBS"
    members: list[dict] = []
    wastage_pct: float = 3.0


def _calc(body: BbsIn) -> dict:
    try:
        return bbs.schedule(body.members, max(0.0, min(body.wastage_pct, 15.0)))
    except bbs.BBSMissing as e:
        raise HTTPException(422, {"message": "Please fill these details", "questions": e.questions})


def bbs_out(b: BbsSchedule, full=True) -> dict:
    d = {"id": b.id, "project_id": b.project_id, "title": b.title, "total_kg": b.total_kg,
         "members": len(b.members or []), "created_at": b.created_at.isoformat(),
         "updated_at": (b.updated_at or b.created_at).isoformat()}
    if full:
        d.update(members=b.members, result=b.result)
    return d


@router.post("/projects/{project_id}/bbs/calculate")
def bbs_calc(project_id: int, body: BbsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need(db, user, project_id, "estimate", "design", "site")
    return _calc(body)


@router.get("/projects/{project_id}/bbs")
def bbs_list(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need(db, user, project_id, "estimate", "design", "site")
    rows = (db.query(BbsSchedule).filter(BbsSchedule.project_id == project_id, BbsSchedule.is_hidden.is_(False))
            .order_by(BbsSchedule.id.desc()).all())
    return [bbs_out(b, False) for b in rows]


@router.post("/projects/{project_id}/bbs")
def bbs_save(project_id: int, body: BbsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _need(db, user, project_id, "estimate", "design", "site")
    res = _calc(body)
    b = BbsSchedule(project_id=p.id, title=body.title.strip()[:200] or "BBS", members=body.members, result=res,
                    total_kg=res["total_kg"], created_by=user.id)
    db.add(b)
    db.commit()
    log_action(db, user, "created", "bbs", b.id, f"{b.title}: {res['total_kg']:,.0f} kg steel", project_id=p.id)
    return bbs_out(b)


def _load_bbs(db: Session, user: User, bid: int) -> tuple[BbsSchedule, Project]:
    b = db.get(BbsSchedule, bid)
    if not b or b.is_hidden:
        raise HTTPException(404, "BBS not found")
    return b, _need(db, user, b.project_id, "estimate", "design", "site")


@router.get("/bbs/{bid}")
def bbs_get(bid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b, _ = _load_bbs(db, user, bid)
    return bbs_out(b)


@router.put("/bbs/{bid}")
def bbs_update(bid: int, body: BbsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b, p = _load_bbs(db, user, bid)
    res = _calc(body)
    b.title, b.members, b.result, b.total_kg = body.title.strip()[:200] or b.title, body.members, res, res["total_kg"]
    db.commit()
    log_action(db, user, "updated", "bbs", b.id, f"{b.title}: {res['total_kg']:,.0f} kg", project_id=p.id)
    return bbs_out(b)


@router.get("/bbs/{bid}/{kind}")
def bbs_export_file(bid: int, kind: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b, p = _load_bbs(db, user, bid)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", b.title)[:40]
    if kind == "excel":
        data, mt, ext = bbs_export.to_excel(_proj(p), b.title, b.result), \
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    elif kind == "pdf":
        data, mt, ext = bbs_export.to_pdf(_proj(p), b.title, b.result), "application/pdf", "pdf"
    else:
        raise HTTPException(404, "Use excel or pdf")
    name = f"{p.code}_BBS_{safe}.{ext}"
    return Response(data, media_type=mt, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


# ================================================================ plan approval checklist
COMMON = [
    ("title_deed", "Sale deed / title document (copy)"),
    ("patta", "Patta (with Chitta / Adangal where applicable)"),
    ("ec", "Encumbrance Certificate (EC) – recent"),
    ("fmb", "FMB sketch / survey sketch"),
    ("layout", "Approved layout copy or plot regularisation order"),
    ("drawings", "Building plan: site plan, floor plans, sections, elevation – signed by a registered engineer / architect"),
    ("structural", "Structural stability certificate (where required)"),
    ("tax", "Latest property tax / vacant land tax receipt"),
    ("id", "Owner ID proof (Aadhaar / PAN) and photograph"),
    ("photos", "Site photographs (plot and road)"),
    ("affidavit", "Affidavit / undertaking forms as asked by the local body"),
    ("noc_owners", "NOC from co-owners / legal heirs (if any)"),
]
EXTRA = {
    "dtcp": [("road", "Proof of access road width"), ("portal", "Online application on the TN single-window / DTCP portal")],
    "cmda": [("portal", "Online application on the CMDA / single-window portal"), ("road", "Road width proof")],
    "corporation": [("form", "Corporation building permit application form"), ("portal", "Online application (if the corporation uses the portal)")],
    "municipality": [("form", "Municipality building permit application form")],
    "panchayat": [("form", "Village Panchayat building permission form"), ("bdo", "Forwarding through BDO / union office (where required)")],
}
AUTH_LABEL = {"dtcp": "DTCP (Town & Country Planning)", "cmda": "CMDA (Chennai Metro)", "corporation": "Corporation",
              "municipality": "Municipality", "panchayat": "Village Panchayat"}
FEES = ["Scrutiny fee", "Building licence / permit fee", "Infrastructure & amenities charges",
        "Labour welfare cess (BOCW – 1% of construction cost)", "Other charges"]
STATUSES = ("pending", "collected", "submitted", "approved", "not_needed")


def _template(authority: str, old: list | None = None) -> list[dict]:
    keep = {i["key"]: i for i in (old or [])}
    items = []
    for k, name in COMMON + EXTRA.get(authority, []):
        o = keep.get(k, {})
        items.append({"key": k, "name": name, "status": o.get("status", "pending"), "file_id": o.get("file_id"),
                      "note": o.get("note", ""), "custom": False})
    items += [i for i in (old or []) if i.get("custom")]
    return items


def _permit(db: Session, p: Project) -> PermitChecklist:
    c = db.query(PermitChecklist).filter_by(project_id=p.id).first()
    if not c:
        c = PermitChecklist(project_id=p.id, authority="dtcp", items=_template("dtcp"),
                            fees=[{"name": f, "amount": None, "paid": False, "receipt": ""} for f in FEES])
        db.add(c)
        db.commit()
    return c


def permit_out(db: Session, c: PermitChecklist) -> dict:
    ids = [i.get("file_id") for i in c.items if i.get("file_id")] + ([c.approved_file_id] if c.approved_file_id else [])
    files = {f.id: f for f in db.query(StoredFile).filter(StoredFile.id.in_(ids or [-1])).all()}
    items = [dict(i, file_name=files[i["file_id"]].original_name if i.get("file_id") in files and not files[i["file_id"]].is_hidden else None)
             for i in c.items]
    need = [i for i in items if i["status"] != "not_needed"]
    done = sum(1 for i in need if i["status"] in ("collected", "submitted", "approved"))
    est = (db.query(Estimate).filter(Estimate.project_id == c.project_id, Estimate.is_hidden.is_(False))
           .order_by(Estimate.version.desc()).first())
    return {"authority": c.authority, "authority_label": AUTH_LABEL.get(c.authority, c.authority), "authorities": AUTH_LABEL,
            "items": items, "fees": c.fees, "application_no": c.application_no, "approval_no": c.approval_no,
            "approval_date": c.approval_date.isoformat() if c.approval_date else None,
            "approved_file_id": c.approved_file_id,
            "approved_file_name": files[c.approved_file_id].original_name if c.approved_file_id in files else None,
            "notes": c.notes, "progress": round(100 * done / len(need)) if need else 0, "done": done, "total": len(need),
            "cess_hint": round(est.grand_total * 0.01) if est else None,
            "disclaimer": "Typical list – requirements differ by local body and change over time. Confirm with the "
                          "planning office / portal before applying. The app does not submit the application."}


@router.get("/projects/{project_id}/permit")
def permit_get(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_project(db, user, project_id, "view")
    return permit_out(db, _permit(db, p))


class PermitIn(BaseModel):
    authority: str | None = None
    items: list[dict] | None = None
    fees: list[dict] | None = None
    application_no: str | None = None
    approval_no: str | None = None
    approval_date: date | None = None
    approved_file_id: int | None = None
    notes: str | None = None


@router.put("/projects/{project_id}/permit")
def permit_put(project_id: int, body: PermitIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_project(db, user, project_id, "edit")
    c = _permit(db, p)
    if body.items is not None:
        clean = []
        for i in body.items:
            name = str(i.get("name") or "").strip()[:200]
            if not name:
                continue
            st = i.get("status") if i.get("status") in STATUSES else "pending"
            clean.append({"key": str(i.get("key") or f"c{len(clean)}")[:40], "name": name, "status": st,
                          "file_id": int(i["file_id"]) if i.get("file_id") else None, "note": str(i.get("note") or "")[:300],
                          "custom": bool(i.get("custom"))})
        c.items = clean
    if body.authority and body.authority in AUTH_LABEL and body.authority != c.authority:
        c.authority = body.authority
        c.items = _template(body.authority, c.items)
    if body.fees is not None:
        c.fees = [{"name": str(f.get("name") or "")[:120], "amount": float(f["amount"]) if f.get("amount") not in (None, "") else None,
                   "paid": bool(f.get("paid")), "receipt": str(f.get("receipt") or "")[:80]} for f in body.fees if f.get("name")]
    for k in ("application_no", "approval_no", "notes"):
        v = getattr(body, k)
        if v is not None:
            setattr(c, k, v.strip()[:2000])
    if body.approval_date is not None:
        c.approval_date = body.approval_date
    if body.approved_file_id is not None:
        c.approved_file_id = body.approved_file_id or None
    db.commit()
    log_action(db, user, "updated", "plan_approval", p.id, f"{AUTH_LABEL.get(c.authority)} checklist", project_id=p.id)
    return permit_out(db, c)


def _summary_pdf(p: Project, d: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    buf = io.BytesIO()
    st = getSampleStyleSheet()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Plan approval documents")
    el = [Paragraph("<b>Plan approval – document pack</b>", st["Title"]),
          Paragraph(f"{p.name} ({p.code}) · {p.location or ''} · {d['authority_label']} · {datetime.now():%d %b %Y}", st["BodyText"]),
          Spacer(1, 8)]
    rows = [["#", "Document", "Status", "File in pack"]]
    for n, i in enumerate(d["items"], 1):
        rows.append([n, Paragraph(i["name"], st["BodyText"]), i["status"].replace("_", " "), i.get("file_name") or "—"])
    t = Table(rows, colWidths=[20, 280, 70, 140])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el += [t, Spacer(1, 8), Paragraph("<b>Fees</b>", st["Heading3"])]
    fr = [["Fee", "Amount (Rs)", "Paid", "Receipt"]] + [[f["name"], f"{f['amount']:,.0f}" if f.get("amount") else "—",
                                                         "Yes" if f.get("paid") else "No", f.get("receipt") or ""] for f in d["fees"]]
    ft = Table(fr, colWidths=[260, 90, 50, 110])
    ft.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    el += [ft, Spacer(1, 8), Paragraph(d["disclaimer"], st["BodyText"])]
    doc.build(el)
    return buf.getvalue()


@router.get("/projects/{project_id}/permit/pack.zip")
def permit_pack(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_project(db, user, project_id, "view")
    d = permit_out(db, _permit(db, p))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("00_Summary.pdf", _summary_pdf(p, d))
        for n, i in enumerate(d["items"], 1):
            if not i.get("file_id") or not i.get("file_name"):
                continue
            f = db.get(StoredFile, i["file_id"])
            if not f or f.is_hidden:
                continue
            ext = f.original_name.rsplit(".", 1)[-1] if "." in f.original_name else "bin"
            short = re.sub(r"[^A-Za-z0-9]+", "_", i["name"])[:40].strip("_")
            z.writestr(f"{n:02d}_{short}.{ext}", backend_for(f.storage_backend).read(f.storage_key))
    name = f"{p.code}_Plan_Approval_Pack.zip"
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


# ================================================================ AI photo check
class PhotoIn(BaseModel):
    file_id: int
    force: bool = False
    language: str = "English"


def _photo_file(db: Session, user: User, file_id: int) -> StoredFile:
    f = db.get(StoredFile, file_id)
    if not f or f.is_hidden:
        raise HTTPException(404, "Photo not found")
    if f.project_id:
        _need(db, user, f.project_id, "site", "ai")
    elif f.uploaded_by != user.id and user.role != "owner":
        raise HTTPException(403, "Not allowed")
    if not photo.is_image(f):
        raise HTTPException(415, "AI photo check works on JPG / PNG / WEBP photos")
    return f


def photo_payload(rec: AIPhotoCheck) -> dict:
    o = photo.out(rec)
    q = " ".join(f"{x.get('issue', '')} {x.get('likely_cause', '')}" for x in rec.result.get("findings", []))
    o["sources"] = [{"id": e["id"], "title": e["title"], "ref": e["source"], "snippet": e["text"][:500]}
                    for e in kb_search(q or rec.result.get("photo_type", ""), k=3, category="site")] if q.strip() else []
    return o


@router.get("/ai/photo-check/{file_id}")
def photo_get(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _photo_file(db, user, file_id)
    rec = db.query(AIPhotoCheck).filter_by(file_id=file_id).order_by(AIPhotoCheck.id.desc()).first()
    return photo_payload(rec) if rec else None


@router.post("/ai/photo-check")
async def photo_run(body: PhotoIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = _photo_file(db, user, body.file_id)
    if not body.force:
        rec = db.query(AIPhotoCheck).filter_by(file_id=f.id).order_by(AIPhotoCheck.id.desc()).first()
        if rec:
            return photo_payload(rec)
    lang = {"ta": "Tamil", "tanglish": "Tanglish (Tamil in English letters)"}.get(body.language, "English")
    try:
        rec = await run_in_threadpool(photo.check, db, user.id, f, lang)
    except llm.LLMError as e:
        raise HTTPException(502, f"AI photo check not available now: {str(e)[:300]}")
    log_action(db, user, "ai_photo_check", "file", f.id, f"{len(rec.result.get('findings', []))} finding(s)",
               project_id=f.project_id)
    return photo_payload(rec)

