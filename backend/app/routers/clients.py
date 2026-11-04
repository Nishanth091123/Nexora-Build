"""1.8 – Clients & Projects (owner only). 1.13: client details + documents are kept ONLY on the PC
(see local_clients.py); the project tracker and notes stay with the project.

Clients are the owner's own business data (name, phone, address, land documents), so every endpoint here is
owner-only. Other users never see clients, client documents, the project workflow tracker or project notes.
"""
from datetime import date
from datetime import date as Date  # (field below is called "date")

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from .. import local_clients as lc
from ..models import AppSetting, Project, ProjectNote, User
from ..security import OWNER_ONLY_CHOICES, get_current_user, owner_only_modules, require_owner
from .files import read_and_check

router = APIRouter(prefix="/api", tags=["clients"])

CLIENT_DOC_CATS = {"land": "Land Documents", "site": "Site Documents", "id": "ID Proof", "other": "Others"}
# Project workflow (image: Project Progress Tracker)
WORKFLOW = [
    ("client_meeting", "Client Meeting"), ("site_survey", "Site Survey"), ("design_2d", "2D Design"),
    ("structural", "Structural Design"), ("estimation", "Estimation"), ("vastu", "Vastu Check"),
    ("approval_drawing", "Approval Drawing"), ("submission", "Submission"), ("completed", "Completed"),
]
WORKFLOW_KEYS = {k for k, _ in WORKFLOW}


# ---------------------------------------------------------------- helpers
def _real_projects(db: Session):
    """Projects that count: not hidden, not archived, not the smoke-test project."""
    return (db.query(Project).filter(Project.is_hidden.is_(False), Project.status != "archived",
                                     ~func.upper(Project.name).like("SMOKE%")))


def find_or_create_client(db: Session, name: str, user_id: int | None, location: str = ""):
    """Used by the projects router. On the PC → a local client record; online → no link (name only)."""
    if lc.ONLINE:
        return None
    with lc.session() as s:
        return lc.find_or_create(s, name, user_id, location)


def link_existing_clients(db: Session) -> int:
    """Once at start-up (PC only): move cloud clients to this PC, then link projects that only have a typed name."""
    if lc.ONLINE:
        return 0
    n = lc.move_from_cloud(db)
    rows = (db.query(Project).filter(Project.client_id.is_(None), Project.client_name != "").all())
    for p in rows:
        c = find_or_create_client(db, p.client_name, p.created_by, p.location)
        if c:
            p.client_id = c.id
    if rows:
        db.commit()
    return n + len(rows)


def doc_out(f: lc.LClientFile) -> dict:
    return {"id": f.id, "name": f.name, "category": f.category, "size_bytes": f.size_bytes,
            "content_type": f.content_type, "created_at": f.created_at.isoformat(),
            "url": f"/api/clients/files/{f.id}/download"}


def client_out(c: lc.LClient, projects: int = 0, docs: int = 0) -> dict:
    return {"id": c.id, "code": c.code, "name": c.name, "phone": c.phone, "email": c.email, "address": c.address,
            "location": c.location, "notes": c.notes, "projects": projects, "documents": docs,
            "created_at": c.created_at.isoformat(), "updated_at": c.updated_at.isoformat()}


def _client(s, cid: int) -> lc.LClient:
    c = s.get(lc.LClient, cid)
    if not c or c.is_hidden:
        raise HTTPException(404, "Client not found")
    return c


def _project(db: Session, pid: int) -> Project:
    p = db.get(Project, pid)
    if not p or p.is_hidden:
        raise HTTPException(404, "Project not found")
    return p


def workflow_out(p: Project) -> list[dict]:
    w = p.workflow or {}
    return [{"key": k, "label": l, "done": bool((w.get(k) or {}).get("done")), "date": (w.get(k) or {}).get("date") or ""}
            for k, l in WORKFLOW]


# ---------------------------------------------------------------- clients (PC only)
class ClientIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=200)
    address: str = ""
    location: str = Field(default="", max_length=160)
    notes: str = ""


class ClientPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = None
    location: str | None = Field(default=None, max_length=160)
    notes: str | None = None


@router.get("/clients/where")
def clients_where(owner: User = Depends(require_owner)):
    """Tells the screen whether clients are available here (PC) or not (online)."""
    return lc.status()


@router.get("/clients/stats")
def client_stats(owner: User = Depends(require_owner), db: Session = Depends(get_db), s=Depends(lc.get_ldb)):
    projects = _real_projects(db).all()
    submitted = sum(bool(((p.workflow or {}).get("submission") or {}).get("done"))
                    and not ((p.workflow or {}).get("completed") or {}).get("done") for p in projects)
    return {
        "clients": s.query(func.count(lc.LClient.id)).filter(lc.LClient.is_hidden.is_(False)).scalar() or 0,
        "projects": len(projects),
        "in_progress": sum(p.status == "ongoing" for p in projects),
        "completed": sum(p.status == "completed" for p in projects),
        "submitted": submitted,
        "on_hold": sum(p.status == "on_hold" for p in projects),
    }


@router.get("/clients")
def list_clients(q: str = "", owner: User = Depends(require_owner), db: Session = Depends(get_db), s=Depends(lc.get_ldb)):
    qry = s.query(lc.LClient).filter(lc.LClient.is_hidden.is_(False))
    if q.strip():
        like = f"%{q.strip()}%"
        L = lc.LClient
        qry = qry.filter(or_(L.name.ilike(like), L.phone.ilike(like), L.location.ilike(like),
                             L.code.ilike(like), L.address.ilike(like)))
    rows = qry.order_by(lc.LClient.updated_at.desc()).all()
    pc = dict(_real_projects(db).with_entities(Project.client_id, func.count(Project.id)).group_by(Project.client_id).all())
    dc = dict(s.query(lc.LClientFile.client_id, func.count(lc.LClientFile.id)).filter(lc.LClientFile.is_hidden.is_(False))
              .group_by(lc.LClientFile.client_id).all())
    return {"clients": [client_out(c, pc.get(c.id, 0), dc.get(c.id, 0)) for c in rows]}


@router.post("/clients")
def create_client(body: ClientIn, owner: User = Depends(require_owner), db: Session = Depends(get_db), s=Depends(lc.get_ldb)):
    data = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump().items()}
    if s.query(lc.LClient).filter(func.lower(lc.LClient.name) == data["name"].lower(), lc.LClient.is_hidden.is_(False),
                                  lc.LClient.phone == data["phone"]).first():
        raise HTTPException(409, "A client with this name and phone already exists")
    c = lc.LClient(code=lc.next_code(s), created_by=owner.id, **data)
    s.add(c)
    s.commit()
    log_action(db, owner, "created", "client", c.code, "(details kept on PC)")
    return client_out(c)


@router.get("/clients/bin")
def client_bin(owner: User = Depends(require_owner), s=Depends(lc.get_ldb)):
    cs = s.query(lc.LClient).filter(lc.LClient.is_hidden.is_(True)).all()
    names = {c.id: c.name for c in s.query(lc.LClient).all()}
    fs = s.query(lc.LClientFile).filter(lc.LClientFile.is_hidden.is_(True)).all()
    return {"clients": [{"id": c.id, "title": f"{c.code} · {c.name}", "deleted_at": c.deleted_at.isoformat() if c.deleted_at else None} for c in cs],
            "files": [{"id": f.id, "title": f.name, "client": names.get(f.client_id, ""),
                       "deleted_at": f.deleted_at.isoformat() if f.deleted_at else None} for f in fs],
            "backups": sorted([p.name for p in lc.BACKUP_DIR.glob("clients_*.zip")], reverse=True)[:10] if lc.BACKUP_DIR.exists() else [],
            "folder": str(lc.LOCAL_DIR)}


@router.get("/clients/{cid}")
def get_client(cid: int, owner: User = Depends(require_owner), db: Session = Depends(get_db), s=Depends(lc.get_ldb)):
    c = _client(s, cid)
    projects = (db.query(Project).filter(Project.client_id == c.id, Project.is_hidden.is_(False))
                .order_by(Project.updated_at.desc()).all())
    docs = (s.query(lc.LClientFile).filter(lc.LClientFile.client_id == c.id, lc.LClientFile.is_hidden.is_(False))
            .order_by(lc.LClientFile.created_at.desc()).all())
    return {
        "client": client_out(c, sum(p.status != "archived" and not p.name.upper().startswith("SMOKE") for p in projects), len(docs)),
        "projects": [{"id": p.id, "code": p.code, "name": p.name, "project_type": p.project_type, "floors": p.floors,
                      "plot": f"{p.plot_width:g} × {p.plot_length:g} {p.unit}" if p.plot_width and p.plot_length else "",
                      "builtup_area": p.builtup_area, "status": p.status, "location": p.location,
                      "updated_at": p.updated_at.isoformat(), "workflow": workflow_out(p)} for p in projects],
        "documents": [doc_out(f) for f in docs],
        "doc_categories": CLIENT_DOC_CATS,
        "folder": str(lc.FILES_DIR / c.code),
    }


@router.patch("/clients/{cid}")
def update_client(cid: int, body: ClientPatch, owner: User = Depends(require_owner), db: Session = Depends(get_db),
                  s=Depends(lc.get_ldb)):
    c = _client(s, cid)
    changed = []
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is None:
            continue
        v = v.strip() if isinstance(v, str) else v
        if getattr(c, k) != v:
            setattr(c, k, v)
            changed.append(k)
    s.commit()
    if "name" in changed:  # keep the name shown on projects in step
        for p in db.query(Project).filter(Project.client_id == c.id).all():
            p.client_name = c.name
        db.commit()
    if changed:
        log_action(db, owner, "updated", "client", c.code, "Changed: " + ", ".join(changed))
    return client_out(c)


@router.delete("/clients/{cid}")
def hide_client(cid: int, owner: User = Depends(require_owner), db: Session = Depends(get_db), s=Depends(lc.get_ldb)):
    """Move to the clients Recycle Bin (on this PC). Projects stay."""
    c = _client(s, cid)
    c.is_hidden, c.deleted_at = True, lc.utcnow()
    s.commit()
    log_action(db, owner, "deleted", "client", c.code, "moved to recycle bin (PC)")
    return {"ok": True}


@router.post("/clients/{cid}/files")
async def upload_client_file(cid: int, category: str = Form("land"), file: UploadFile = File(...),
                             owner: User = Depends(require_owner), db: Session = Depends(get_db), s=Depends(lc.get_ldb)):
    c = _client(s, cid)
    if category not in CLIENT_DOC_CATS:
        raise HTTPException(400, f"category must be one of {', '.join(CLIENT_DOC_CATS)}")
    name, data, ctype = await read_and_check(file)
    f = lc.LClientFile(client_id=c.id, category=f"client_{category}", name=name, rel_path=lc.save_file(c, name, data),
                       content_type=ctype or "application/octet-stream", size_bytes=len(data))
    s.add(f)
    s.commit()
    log_action(db, owner, "uploaded", "client_file", f.id, f"{c.code} (kept on PC)")
    return doc_out(f)


@router.get("/clients/files/{fid}/download")
def download_client_file(fid: int, owner: User = Depends(require_owner), s=Depends(lc.get_ldb)):
    f = s.get(lc.LClientFile, fid)
    if not f:
        raise HTTPException(404, "File not found")
    p = lc.file_path(f)
    if not p.exists():
        raise HTTPException(404, f"The file is missing from {p.parent}")
    return FileResponse(p, media_type=f.content_type, filename=f.name)


@router.delete("/clients/files/{fid}")
def hide_client_file(fid: int, owner: User = Depends(require_owner), s=Depends(lc.get_ldb)):
    f = s.get(lc.LClientFile, fid)
    if not f:
        raise HTTPException(404, "File not found")
    f.is_hidden, f.deleted_at = True, lc.utcnow()
    s.commit()
    return {"ok": True}


class BinIn(BaseModel):
    kind: str  # client | file
    id: int


@router.post("/clients/bin/restore")
def restore_from_bin(body: BinIn, owner: User = Depends(require_owner), s=Depends(lc.get_ldb)):
    m = lc.LClient if body.kind == "client" else lc.LClientFile
    o = s.get(m, body.id)
    if not o:
        raise HTTPException(404, "Not found")
    o.is_hidden, o.deleted_at = False, None
    s.commit()
    return {"ok": True}


@router.post("/clients/bin/purge")
def purge_from_bin(body: BinIn, owner: User = Depends(require_owner), db: Session = Depends(get_db), s=Depends(lc.get_ldb)):
    """Owner only: delete permanently from this PC – a backup zip is written first (local_data\\backups)."""
    if body.kind == "client":
        c = s.get(lc.LClient, body.id)
        if not c or not c.is_hidden:
            raise HTTPException(400, "Move it to the recycle bin first")
        zp = lc.backup_zip(f"before_delete_{c.code}", [c.id])
        for f in s.query(lc.LClientFile).filter_by(client_id=c.id).all():
            try:
                lc.file_path(f).unlink(missing_ok=True)
            except OSError:
                pass
            s.delete(f)
        db.query(Project).filter(Project.client_id == c.id).update({Project.client_id: None}, synchronize_session=False)
        db.commit()
        s.delete(c)
    else:
        f = s.get(lc.LClientFile, body.id)
        if not f or not f.is_hidden:
            raise HTTPException(400, "Move it to the recycle bin first")
        zp = lc.backup_zip(f"before_delete_file_{f.id}", [f.client_id])
        try:
            lc.file_path(f).unlink(missing_ok=True)
        except OSError:
            pass
        s.delete(f)
    s.commit()
    return {"ok": True, "backup": zp.name}


@router.post("/clients/backup")
def make_backup(owner: User = Depends(require_owner), s=Depends(lc.get_ldb)):
    zp = lc.backup_zip("manual")
    return FileResponse(zp, media_type="application/zip", filename=zp.name)


# ---------------------------------------------------------------- project link, workflow, notes
class LinkIn(BaseModel):
    client_id: int | None = None


@router.put("/projects/{pid}/client")
def set_project_client(pid: int, body: LinkIn, owner: User = Depends(require_owner), db: Session = Depends(get_db),
                       s=Depends(lc.get_ldb)):
    p = _project(db, pid)
    if body.client_id is None:
        p.client_id = None
    else:
        c = _client(s, body.client_id)
        p.client_id, p.client_name = c.id, c.name
    db.commit()
    log_action(db, owner, "updated", "project", p.code, f"Client: {p.client_name or '—'}", project_id=p.id)
    return {"ok": True, "client_id": p.client_id, "client_name": p.client_name}


@router.get("/projects/{pid}/workflow")
def get_workflow(pid: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    return {"stages": workflow_out(_project(db, pid))}


class StageIn(BaseModel):
    key: str
    done: bool
    date: Date | None = None


@router.put("/projects/{pid}/workflow")
def set_stage(pid: int, body: StageIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    p = _project(db, pid)
    if body.key not in WORKFLOW_KEYS:
        raise HTTPException(400, "Unknown stage")
    w = dict(p.workflow or {})
    w[body.key] = {"done": body.done, "date": (body.date or date.today()).isoformat() if body.done else ""}
    p.workflow = w  # new dict so the JSON column is saved
    db.commit()
    label = dict(WORKFLOW)[body.key]
    log_action(db, owner, "updated", "workflow", p.code, f"{label}: {'done' if body.done else 'pending'}", project_id=p.id)
    return {"stages": workflow_out(p)}


class NoteIn(BaseModel):
    activity: str = Field(min_length=2, max_length=200)
    remarks: str = ""
    note_date: date | None = None


def note_out(n: ProjectNote) -> dict:
    return {"id": n.id, "activity": n.activity, "remarks": n.remarks, "date": n.note_date.isoformat(),
            "by": n.by_name, "created_at": n.created_at.isoformat()}


@router.get("/projects/{pid}/notes")
def list_notes(pid: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    _project(db, pid)
    rows = (db.query(ProjectNote).filter(ProjectNote.project_id == pid, ProjectNote.is_hidden.is_(False))
            .order_by(ProjectNote.note_date.desc(), ProjectNote.id.desc()).all())
    return {"notes": [note_out(n) for n in rows]}


@router.post("/projects/{pid}/notes")
def add_note(pid: int, body: NoteIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    p = _project(db, pid)
    n = ProjectNote(project_id=p.id, activity=body.activity.strip(), remarks=body.remarks.strip(),
                    note_date=body.note_date or date.today(), by_name=owner.full_name or owner.username)
    db.add(n)
    db.commit()
    log_action(db, owner, "added", "note", n.id, n.activity, project_id=p.id)
    return note_out(n)


# ---------------------------------------------------------------- owner-only modules
@router.get("/owner-only")
def get_owner_only(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Everyone may read this (menus hide these modules for non-owners)."""
    return {"modules": sorted(owner_only_modules(db)), "choices": list(OWNER_ONLY_CHOICES)}


class OwnerOnlyIn(BaseModel):
    modules: list[str]


@router.put("/owner-only")
def set_owner_only(body: OwnerOnlyIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    mods = sorted({m for m in body.modules if m in OWNER_ONLY_CHOICES})
    row = db.get(AppSetting, "owner_only")
    if not row:
        row = AppSetting(key="owner_only", value={})
        db.add(row)
    row.value = {"modules": mods}
    db.commit()
    log_action(db, owner, "updated", "settings", "owner_only", ", ".join(mods) or "none")
    return {"modules": mods, "choices": list(OWNER_ONLY_CHOICES)}
