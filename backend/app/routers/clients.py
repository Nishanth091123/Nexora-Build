"""1.8 – Clients & Projects (owner only).
1.14: client documents (patta, sale deed, Aadhaar…) are NOT uploaded or stored by the app – the owner keeps them
in his own laptop folder. The app keeps only a checklist per client: which documents are needed, received or pending.

Clients are the owner's own business data (name, phone, address, land documents), so every endpoint here is
owner-only. Other users never see clients, client documents, the project workflow tracker or project notes.
"""
from datetime import date
from datetime import date as Date  # (field below is called "date")

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..models import AppSetting, Client, Project, ProjectNote, User
from ..security import OWNER_ONLY_CHOICES, get_current_user, owner_only_modules, require_owner

router = APIRouter(prefix="/api", tags=["clients"])

# typical documents collected from a client (the owner can add / remove items per client)
DOC_TEMPLATE = [
    ("patta", "Patta (Chitta / Adangal)"), ("sale_deed", "Sale deed / title deed"), ("parent_doc", "Parent documents (link deeds)"),
    ("ec", "Encumbrance Certificate (EC)"), ("fmb", "FMB / survey sketch"), ("layout", "Approved layout copy / plot regularisation"),
    ("tax", "Property tax / vacant land tax receipt"), ("aadhaar", "Aadhaar card (owner)"), ("pan", "PAN card (owner)"),
    ("photo", "Owner photograph"), ("site_photos", "Site photographs"),
]
DOC_STATUS = ("pending", "received", "not_needed")


def doc_list(c: Client) -> list[dict]:
    have = {i.get("key"): i for i in (c.doc_checklist or []) if isinstance(i, dict)}
    out = []
    for k, name in DOC_TEMPLATE:
        o = have.get(k, {})
        out.append({"key": k, "name": o.get("name") or name, "status": o.get("status", "pending"),
                    "date": o.get("date", ""), "note": o.get("note", ""), "custom": False})
    out += [dict(i, custom=True) for i in (c.doc_checklist or []) if isinstance(i, dict) and i.get("custom")]
    return out


def doc_counts(c: Client) -> tuple[int, int]:
    items = [i for i in doc_list(c) if i["status"] != "not_needed"]
    return sum(i["status"] == "received" for i in items), len(items)
# Project workflow (image: Project Progress Tracker)
WORKFLOW = [
    ("client_meeting", "Client Meeting"), ("site_survey", "Site Survey"), ("design_2d", "2D Design"),
    ("structural", "Structural Design"), ("estimation", "Estimation"), ("vastu", "Vastu Check"),
    ("approval_drawing", "Approval Drawing"), ("submission", "Submission"), ("completed", "Completed"),
]
WORKFLOW_KEYS = {k for k, _ in WORKFLOW}


# ---------------------------------------------------------------- helpers
def next_client_code(db: Session) -> str:
    n = (db.query(func.max(Client.id)).scalar() or 0) + 1
    code = f"C-{n:03d}"
    while db.query(Client).filter_by(code=code).first():
        n += 1
        code = f"C-{n:03d}"
    return code


def find_or_create_client(db: Session, name: str, user_id: int | None, location: str = "") -> Client | None:
    name = (name or "").strip()
    if not name:
        return None
    c = (db.query(Client).filter(func.lower(Client.name) == name.lower(), Client.is_hidden.is_(False))
         .order_by(Client.id).first())
    if not c:
        c = Client(code=next_client_code(db), name=name, location=location or "", created_by=user_id)
        db.add(c)
        db.flush()
    return c


def link_existing_clients(db: Session) -> int:
    """Once at start-up: projects that only have a typed client name get a Client record (idempotent).
    1.14: first, client records that 1.13 kept on the PC come back into the app (documents stay on the PC)."""
    from ..local_clients import move_back
    try:
        move_back(db)
    except Exception as e:  # never block the start
        db.rollback()
        log_msg = f"client records not moved back yet: {e}"
        import logging
        logging.getLogger("nexora.clients").warning(log_msg)
    rows = (db.query(Project).filter(Project.client_id.is_(None), Project.client_name != "").all())
    for p in rows:
        c = find_or_create_client(db, p.client_name, p.created_by, p.location)
        if c:
            p.client_id = c.id
    if rows:
        db.commit()
    return len(rows)


def _real_projects(db: Session):
    """Projects that count: not hidden, not archived, not the smoke-test project."""
    return db.query(Project).filter(Project.is_hidden.is_(False), Project.status != "archived",
                                    ~func.upper(Project.name).like("SMOKE%"))


def client_out(c: Client, projects: int = 0) -> dict:
    """1.15: no documents at all in the app (files and checklist both removed at Nishanth's request)."""
    return {"id": c.id, "code": c.code, "name": c.name, "phone": c.phone, "email": c.email, "address": c.address,
            "location": c.location, "notes": c.notes, "projects": projects,
            "created_at": c.created_at.isoformat(), "updated_at": c.updated_at.isoformat()}


def _client(db: Session, cid: int) -> Client:
    c = db.get(Client, cid)
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


# ---------------------------------------------------------------- clients
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


@router.get("/clients/stats")
def client_stats(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    projects = _real_projects(db).all()
    submitted = sum(bool(((p.workflow or {}).get("submission") or {}).get("done"))
                    and not ((p.workflow or {}).get("completed") or {}).get("done") for p in projects)
    return {
        "clients": db.query(func.count(Client.id)).filter(Client.is_hidden.is_(False)).scalar() or 0,
        "projects": len(projects),
        "in_progress": sum(p.status == "ongoing" for p in projects),
        "completed": sum(p.status == "completed" for p in projects),
        "submitted": submitted,
        "on_hold": sum(p.status == "on_hold" for p in projects),
    }


@router.get("/clients")
def list_clients(q: str = "", owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    qry = db.query(Client).filter(Client.is_hidden.is_(False))
    if q.strip():
        like = f"%{q.strip()}%"
        qry = qry.filter(or_(Client.name.ilike(like), Client.phone.ilike(like), Client.location.ilike(like),
                             Client.code.ilike(like), Client.address.ilike(like)))
    rows = qry.order_by(Client.updated_at.desc()).all()
    pc = dict(_real_projects(db).with_entities(Project.client_id, func.count(Project.id)).group_by(Project.client_id).all())
    return {"clients": [client_out(c, pc.get(c.id, 0)) for c in rows]}


@router.post("/clients")
def create_client(body: ClientIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    data = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump().items()}
    if db.query(Client).filter(func.lower(Client.name) == data["name"].lower(), Client.is_hidden.is_(False),
                               Client.phone == data["phone"]).first():
        raise HTTPException(409, "A client with this name and phone already exists")
    c = Client(code=next_client_code(db), created_by=owner.id, **data)
    db.add(c)
    db.commit()
    log_action(db, owner, "created", "client", c.code, c.name)
    return client_out(c)


@router.get("/clients/{cid}")
def get_client(cid: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    c = _client(db, cid)
    projects = (db.query(Project).filter(Project.client_id == c.id, Project.is_hidden.is_(False))
                .order_by(Project.updated_at.desc()).all())
    return {
        "client": client_out(c, sum(p.status != "archived" and not p.name.upper().startswith("SMOKE") for p in projects)),
        "projects": [{"id": p.id, "code": p.code, "name": p.name, "project_type": p.project_type, "floors": p.floors,
                      "plot": f"{p.plot_width:g} × {p.plot_length:g} {p.unit}" if p.plot_width and p.plot_length else "",
                      "builtup_area": p.builtup_area, "status": p.status, "location": p.location,
                      "updated_at": p.updated_at.isoformat(), "workflow": workflow_out(p)} for p in projects],
    }


@router.patch("/clients/{cid}")
def update_client(cid: int, body: ClientPatch, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    c = _client(db, cid)
    changed = []
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is None:
            continue
        v = v.strip() if isinstance(v, str) else v
        if getattr(c, k) != v:
            setattr(c, k, v)
            changed.append(k)
    if "name" in changed:  # keep the name shown on projects in step
        for p in db.query(Project).filter(Project.client_id == c.id).all():
            p.client_name = c.name
    db.commit()
    if changed:
        log_action(db, owner, "updated", "client", c.code, "Changed: " + ", ".join(changed))
    return client_out(c)


# ---------------------------------------------------------------- project link, workflow, notes
class LinkIn(BaseModel):
    client_id: int | None = None


@router.put("/projects/{pid}/client")
def set_project_client(pid: int, body: LinkIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    p = _project(db, pid)
    if body.client_id is None:
        p.client_id = None
    else:
        c = _client(db, body.client_id)
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
