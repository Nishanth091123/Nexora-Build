import re

from email_validator import EmailNotValidError, validate_email

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..models import AppSetting, User, utcnow
from ..security import (create_token, get_current_user, hash_password, session_minutes,
                        validate_password_strength, verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(u: User) -> dict:
    return {
        "id": u.id, "username": u.username, "email": u.email, "full_name": u.full_name,
        "job_title": u.job_title, "phone": u.phone, "role": u.role, "status": u.status,
        "is_protected": u.is_protected, "can_create_projects": u.can_create_projects or u.role == "owner",
        "language": u.language,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


class LoginIn(BaseModel):
    login: str  # username or email
    password: str


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    key = body.login.strip().lower()
    u = db.query(User).filter(or_(func.lower(User.username) == key, func.lower(User.email) == key)).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Wrong username/email or password")
    if u.status == "pending":
        raise HTTPException(403, "Your account is waiting for the owner's approval")
    if u.status != "active":
        raise HTTPException(403, "Your account is deactivated. Contact the owner.")
    u.last_login_at = utcnow()
    db.commit()
    log_action(db, u, "login", "user", u.id)
    minutes = session_minutes(db)
    return {"token": create_token(u, minutes), "expires_in_minutes": minutes, "user": user_out(u)}


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    email: str | None = None  # optional
    full_name: str = Field(min_length=2, max_length=120)
    job_title: str = ""
    phone: str = ""
    password: str


USERNAME_RE = re.compile(r"^[a-z0-9_.]{3,40}$")


def clean_email(v: str | None) -> str | None:
    """Email is optional. Empty -> None; otherwise must be a valid address."""
    v = (v or "").strip().lower()
    if not v:
        return None
    try:
        return validate_email(v, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        raise HTTPException(400, f"'{v}' is not a valid email (leave it empty if not available)")


def username_or_email_taken(db: Session, username: str, email: str | None) -> bool:
    conds = [func.lower(User.username) == username]
    if email:
        conds.append(func.lower(User.email) == email)
    return db.query(User).filter(or_(*conds)).first() is not None


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    s = db.get(AppSetting, "general")
    if s and not (s.value or {}).get("allow_self_registration", True):
        raise HTTPException(403, "Self registration is turned off. Ask the owner to add you.")
    username = body.username.strip().lower()
    if not USERNAME_RE.match(username):
        raise HTTPException(400, "Username: 3-40 characters, only a-z, 0-9, _ and .")
    validate_password_strength(body.password)
    email = clean_email(body.email)
    if username_or_email_taken(db, username, email):
        raise HTTPException(409, "Username or email already registered")
    u = User(username=username, email=email, full_name=body.full_name.strip(), job_title=body.job_title.strip(),
             phone=body.phone.strip(), password_hash=hash_password(body.password), role="user", status="pending",
             password_changed_at=utcnow())
    db.add(u)
    db.commit()
    log_action(db, u, "registered", "user", u.id, "Waiting for owner approval")
    return {"ok": True, "message": "Registered. The owner must approve your account before you can log in."}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


class MeUpdate(BaseModel):
    full_name: str | None = None
    job_title: str | None = None
    phone: str | None = None
    language: str | None = None


@router.patch("/me")
def update_me(body: MeUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.language is not None:
        if body.language not in ("en", "ta"):
            raise HTTPException(400, "language must be 'en' or 'ta'")
        user.language = body.language
    for f in ("full_name", "job_title", "phone"):
        v = getattr(body, f)
        if v is not None:
            setattr(user, f, v.strip())
    db.commit()
    return user_out(user)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
def change_password(body: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is wrong")
    validate_password_strength(body.new_password)
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = utcnow()
    db.commit()
    log_action(db, user, "password_changed", "user", user.id)
    return {"ok": True, "token": create_token(user, session_minutes(db))}
