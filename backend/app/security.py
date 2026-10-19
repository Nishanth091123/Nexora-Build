"""Passwords, JWT tokens and permission checks."""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import config
from .db import get_db
from .models import AppSetting, Project, ProjectAccess, User

MODULES = ("view", "edit", "design", "estimate", "site", "vastu", "ai")

bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8")[:72], bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8")[:72], hashed.encode())
    except ValueError:
        return False


def validate_password_strength(pw: str) -> None:
    if len(pw) < 8 or not any(c.isdigit() for c in pw) or not any(c.isalpha() for c in pw):
        raise HTTPException(400, "Password must be at least 8 characters with letters and numbers")


def session_minutes(db: Session) -> int:
    s = db.get(AppSetting, "security")
    try:
        return max(15, int((s.value or {}).get("session_timeout_minutes", 480))) if s else 480
    except (TypeError, ValueError):
        return 480


def create_token(user: User, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "role": user.role, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    try:
        data = jwt.decode(creds.credentials, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired – please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    user = db.get(User, int(data["sub"]))
    if not user or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not active")
    iat = data.get("iat")
    if user.password_changed_at and iat and user.password_changed_at.timestamp() > float(iat) + 1:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password changed – please log in again")
    return user


def require_owner(user: User = Depends(get_current_user)) -> User:
    if user.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner can do this")
    return user


def project_permissions(db: Session, user: User, project: Project) -> dict:
    """Return {module: bool} for this user on this project."""
    if user.role == "owner":
        return {m: True for m in MODULES}
    acc = db.query(ProjectAccess).filter_by(user_id=user.id, project_id=project.id).first()
    if not acc:
        return {m: False for m in MODULES}
    perms = {m: bool(getattr(acc, f"can_{m}")) for m in MODULES}
    if any(perms.values()):
        perms["view"] = True
    return perms


def require_project(db: Session, user: User, project_id: int, module: str = "view") -> Project:
    project = db.get(Project, project_id)
    if not project or project.is_hidden:
        raise HTTPException(404, "Project not found")
    if not project_permissions(db, user, project).get(module):
        raise HTTPException(403, f"You don't have '{module}' access to this project")
    return project


def visible_project_ids(db: Session, user: User) -> Optional[list[int]]:
    """None means 'all projects' (owner)."""
    if user.role == "owner":
        return None
    rows = db.query(ProjectAccess).filter_by(user_id=user.id).all()
    return [r.project_id for r in rows if any(getattr(r, f"can_{m}") for m in MODULES)]
