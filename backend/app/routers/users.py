"""Owner-only user management + per-project module access."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..models import Project, ProjectAccess, User, utcnow
from ..security import (MODULES, get_current_user, hash_password, require_owner,
                        validate_password_strength)
from .auth import USERNAME_RE, clean_email, user_out, username_or_email_taken

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.role.desc(), User.created_at).all()
    counts = {s: sum(1 for u in users if u.status == s) for s in ("active", "pending", "deactivated")}
    return {"users": [user_out(u) for u in users], "counts": {"all": len(users), **counts}}


@router.get("/directory")
def directory(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Minimal list (name + title) any logged-in user can see, e.g. for team member lists."""
    users = db.query(User).filter(User.status == "active").order_by(User.full_name).all()
    return [{"id": u.id, "full_name": u.full_name, "username": u.username, "job_title": u.job_title,
             "role": u.role} for u in users]


class UserCreate(BaseModel):
    username: str
    email: str | None = None  # optional
    full_name: str
    job_title: str = ""
    phone: str = ""
    password: str
    can_create_projects: bool = False


@router.post("")
def create_user(body: UserCreate, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    if not USERNAME_RE.match(username):
        raise HTTPException(400, "Username: 3-40 characters, only a-z, 0-9, _ and .")
    validate_password_strength(body.password)
    email = clean_email(body.email)
    if username_or_email_taken(db, username, email):
        raise HTTPException(409, "Username or email already exists")
    u = User(username=username, email=email, full_name=body.full_name.strip(), job_title=body.job_title.strip(),
             phone=body.phone.strip(), password_hash=hash_password(body.password), role="user", status="active",
             can_create_projects=body.can_create_projects, password_changed_at=utcnow())
    db.add(u)
    db.commit()
    log_action(db, owner, "added", "user", u.id, f"Added user {u.username}")
    return user_out(u)


class UserUpdate(BaseModel):
    email: str | None = None  # "" clears it
    full_name: str | None = None
    job_title: str | None = None
    phone: str | None = None
    can_create_projects: bool | None = None
    status: str | None = None  # active | deactivated  (pending -> active = approve)
    new_password: str | None = None


@router.patch("/{user_id}")
def update_user(user_id: int, body: UserUpdate, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.is_protected and (body.status not in (None, "active")):
        raise HTTPException(400, "The owner account cannot be deactivated")
    changes = []
    if body.email is not None:
        new_email = clean_email(body.email)
        if new_email and new_email != u.email and db.query(User).filter(func.lower(User.email) == new_email).first():
            raise HTTPException(409, "Email already used by another user")
        if u.is_protected and not new_email:
            raise HTTPException(400, "The owner must keep an email")
        u.email = new_email
        changes.append("email")
    for f in ("full_name", "job_title", "phone"):
        v = getattr(body, f)
        if v is not None:
            setattr(u, f, v.strip())
            changes.append(f)
    if body.can_create_projects is not None and not u.is_protected:
        u.can_create_projects = body.can_create_projects
        changes.append("can_create_projects")
    action = "updated"
    if body.status is not None and body.status != u.status:
        if body.status not in ("active", "deactivated"):
            raise HTTPException(400, "status must be active or deactivated")
        action = "approved" if (u.status == "pending" and body.status == "active") else body.status
        u.status = body.status
    if body.new_password:
        validate_password_strength(body.new_password)
        u.password_hash = hash_password(body.new_password)
        u.password_changed_at = utcnow()
        changes.append("password reset")
    db.commit()
    log_action(db, owner, action, "user", u.id, f"{u.username}: {', '.join(changes) or action}")
    return user_out(u)


# ---------- project access matrix ----------

def access_out(a: ProjectAccess | None) -> dict:
    if not a:
        return {m: False for m in MODULES} | {"project_role": "none"}
    return {m: bool(getattr(a, f"can_{m}")) for m in MODULES} | {"project_role": a.project_role}


@router.get("/access/matrix")
def access_matrix(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    users = db.query(User).filter(User.role != "owner").order_by(User.full_name).all()
    projects = db.query(Project).filter(Project.status != "archived").order_by(Project.created_at).all()
    rows = db.query(ProjectAccess).all()
    by_key = {(r.user_id, r.project_id): r for r in rows}
    return {
        "modules": list(MODULES),
        "users": [{"id": u.id, "full_name": u.full_name, "username": u.username, "status": u.status} for u in users],
        "projects": [{"id": p.id, "code": p.code, "name": p.name} for p in projects],
        "access": {f"{u.id}:{p.id}": access_out(by_key.get((u.id, p.id))) for u in users for p in projects},
    }


class AccessIn(BaseModel):
    user_id: int
    project_id: int
    view: bool = True
    edit: bool = False
    design: bool = False
    estimate: bool = False
    site: bool = False
    vastu: bool = False
    ai: bool = True


@router.put("/access")
def set_access(body: AccessIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    u = db.get(User, body.user_id)
    p = db.get(Project, body.project_id)
    if not u or not p:
        raise HTTPException(404, "User or project not found")
    if u.role == "owner":
        raise HTTPException(400, "The owner always has full access")
    a = db.query(ProjectAccess).filter_by(user_id=u.id, project_id=p.id).first()
    if not a:
        a = ProjectAccess(user_id=u.id, project_id=p.id, granted_by=owner.id)
        db.add(a)
    flags = {m: getattr(body, m) for m in MODULES}
    if any(flags[m] for m in MODULES if m != "view"):
        flags["view"] = True  # any module implies view
    for m, v in flags.items():
        setattr(a, f"can_{m}", v)
    a.project_role = "editor" if any(flags[m] for m in ("edit", "design", "estimate", "site", "vastu")) \
        else ("viewer" if flags["view"] else "none")
    a.granted_by = owner.id
    db.commit()
    on = [m for m, v in flags.items() if v]
    log_action(db, owner, "access_changed", "project_access", a.id,
               f"{u.username} on {p.code}: {', '.join(on) or 'no access'}", project_id=p.id)
    return access_out(a)
