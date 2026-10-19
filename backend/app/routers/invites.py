"""Phase 6.6 – invite links. The owner creates a link with ready project access; a person opens it, registers, and
waits as 'pending' until the owner approves (Settings → Users). Links never expire; the owner can stop them."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..models import InviteLink, Organization, Project, ProjectAccess, User, utcnow
from ..security import MODULES, get_current_user, hash_password, require_owner, validate_password_strength
from .auth import USERNAME_RE, clean_email, username_or_email_taken

router = APIRouter(prefix="/api/invites", tags=["invites"])


def _clean_access(db: Session, access: dict) -> dict:
    out = {}
    for pid, flags in (access or {}).items():
        try:
            p = db.get(Project, int(pid))
        except (TypeError, ValueError):
            continue
        if not p or p.is_hidden:
            continue
        f = {m: bool((flags or {}).get(m)) for m in MODULES}
        if any(f[m] for m in MODULES if m != "view"):
            f["view"] = True
        if any(f.values()):
            out[str(p.id)] = f
    return out


def invite_out(db: Session, i: InviteLink, users: list[User] | None = None) -> dict:
    names = {p.id: f"{p.code} · {p.name}" for p in db.query(Project).filter(Project.id.in_([int(k) for k in i.access] or [-1])).all()}
    return {"id": i.id, "token": i.token, "label": i.label, "job_title": i.job_title, "is_active": i.is_active,
            "uses": i.uses, "created_at": i.created_at.isoformat(),
            "access": [{"project_id": int(k), "project": names.get(int(k), f"#{k}"), **v} for k, v in i.access.items()],
            "joined": [{"id": u.id, "full_name": u.full_name, "username": u.username, "status": u.status,
                        "created_at": u.created_at.isoformat()} for u in (users or [])]}


class InviteIn(BaseModel):
    label: str = Field("", max_length=120)
    job_title: str = Field("", max_length=80)
    access: dict = {}


@router.get("")
def list_invites(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    rows = db.query(InviteLink).order_by(InviteLink.id.desc()).all()
    users = db.query(User).filter(User.invited_via.isnot(None)).all()
    return [invite_out(db, i, [u for u in users if u.invited_via == i.id]) for i in rows]


@router.post("")
def create_invite(body: InviteIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    access = _clean_access(db, body.access)
    if not access:
        raise HTTPException(422, "Choose at least one project and what they can use")
    i = InviteLink(token=secrets.token_urlsafe(24), label=body.label.strip() or body.job_title.strip() or "Team invite",
                   job_title=body.job_title.strip(), access=access, created_by=owner.id)
    db.add(i)
    db.commit()
    log_action(db, owner, "created", "invite_link", i.id, f"{i.label}: {len(access)} project(s)")
    return invite_out(db, i)


class InvitePatch(BaseModel):
    is_active: bool | None = None
    label: str | None = None
    access: dict | None = None


@router.patch("/{invite_id}")
def edit_invite(invite_id: int, body: InvitePatch, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    i = db.get(InviteLink, invite_id)
    if not i:
        raise HTTPException(404, "Invite not found")
    if body.is_active is not None:
        i.is_active = body.is_active
    if body.label is not None and body.label.strip():
        i.label = body.label.strip()[:120]
    if body.access is not None:
        a = _clean_access(db, body.access)
        if not a:
            raise HTTPException(422, "Choose at least one project")
        i.access = a
    db.commit()
    log_action(db, owner, "stopped" if i.is_active is False else "updated", "invite_link", i.id, i.label)
    return invite_out(db, i)


# ---------------------------------------------------------------- public (no login)
def _live(db: Session, token: str) -> InviteLink:
    i = db.query(InviteLink).filter_by(token=token).first()
    if not i or not i.is_active:
        raise HTTPException(404, "This invite link is not valid any more. Ask the owner for a new link.")
    return i


@router.get("/open/{token}")
def invite_info(token: str, db: Session = Depends(get_db)):
    i = _live(db, token)
    org = db.get(Organization, 1)
    owner = db.query(User).filter(User.role == "owner").first()
    return {"label": i.label, "job_title": i.job_title, "company": org.name if org else "",
            "invited_by": owner.full_name if owner else "", "projects": len(i.access)}


class JoinIn(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    email: str | None = None
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = ""
    password: str


@router.post("/open/{token}/join")
def join(token: str, body: JoinIn, db: Session = Depends(get_db)):
    i = _live(db, token)
    username = body.username.strip().lower()
    if not USERNAME_RE.match(username):
        raise HTTPException(400, "Username: 3-40 characters, only a-z, 0-9, _ and .")
    validate_password_strength(body.password)
    email = clean_email(body.email)
    if username_or_email_taken(db, username, email):
        raise HTTPException(409, "Username or email already registered")
    u = User(username=username, email=email, full_name=body.full_name.strip(), job_title=i.job_title,
             phone=body.phone.strip(), password_hash=hash_password(body.password), role="user", status="pending",
             password_changed_at=utcnow(), invited_via=i.id)
    db.add(u)
    db.flush()
    for pid, flags in i.access.items():  # ready access – used only after the owner approves the account
        a = ProjectAccess(user_id=u.id, project_id=int(pid), granted_by=i.created_by)
        for m in MODULES:
            setattr(a, f"can_{m}", bool(flags.get(m)))
        a.project_role = "editor" if any(flags.get(m) for m in ("edit", "design", "estimate", "site", "vastu")) else "viewer"
        db.add(a)
    i.uses += 1
    db.commit()
    log_action(db, u, "registered", "user", u.id, f"Joined with invite '{i.label}' – waiting for owner approval")
    return {"ok": True, "message": "Request sent. You can log in after the owner approves your account."}


# ---------------------------------------------------------------- bell notifications
notif_router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@notif_router.get("")
def notifications(user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    from datetime import date as _date

    from ..models import Approval, Task
    items = []
    if user.role == "owner":
        invites = {i.id: i.label for i in db.query(InviteLink).all()}
        for u in db.query(User).filter(User.status == "pending").order_by(User.created_at.desc()).all():
            via = f" via invite '{invites.get(u.invited_via, '')}'" if u.invited_via else ""
            items.append({"kind": "user", "title": f"{u.full_name or u.username} wants to join{via}",
                          "link": "/settings?tab=users", "at": u.created_at.isoformat()})
    live = {p.id: p.name for p in db.query(Project).filter(Project.is_hidden.is_(False), Project.status != "archived").all()}
    q = db.query(Approval).filter(Approval.status == "pending", Approval.is_hidden.is_(False))
    for a in q.all():
        if a.project_id in live and (a.approver_id == user.id or (user.role == "owner" and not a.approver_id)):
            items.append({"kind": "approval", "title": f"Approval needed: {a.title} ({live[a.project_id]})",
                          "link": "/projects?tab=approvals", "at": a.created_at.isoformat()})
    today = _date.today()
    for t in db.query(Task).filter(Task.status != "completed", Task.is_hidden.is_(False), Task.due_date.isnot(None),
                                   Task.due_date < today).all():
        if t.project_id in live and (t.assignee_id == user.id or (user.role == "owner" and not t.assignee_id)):
            items.append({"kind": "task", "title": f"Overdue task: {t.title} ({live[t.project_id]})",
                          "link": "/projects?tab=tasks", "at": t.due_date.isoformat()})
    items.sort(key=lambda x: x["at"], reverse=True)
    return {"count": len(items), "items": items[:30]}
