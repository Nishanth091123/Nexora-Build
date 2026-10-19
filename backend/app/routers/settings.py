from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..models import AppSetting, Organization, User
from ..security import get_current_user, require_owner
from ..seed import DEFAULT_SETTINGS
from .files import read_and_check, store

router = APIRouter(prefix="/api/settings", tags=["settings"])

IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


@router.get("")
def get_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = {}
    for key, defaults in DEFAULT_SETTINGS.items():
        row = db.get(AppSetting, key)
        out[key] = {**defaults, **((row.value if row else {}) or {})}
    if user.role != "owner":
        out.pop("backups", None)
    return out


@router.put("/section/{section}")
def update_settings(section: str, body: dict, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    if section not in DEFAULT_SETTINGS:
        raise HTTPException(404, f"Unknown settings section '{section}'")
    allowed = DEFAULT_SETTINGS[section]
    unknown = [k for k in body if k not in allowed]
    if unknown:
        raise HTTPException(400, f"Unknown keys for {section}: {', '.join(unknown)}")
    for k, v in body.items():  # keep the same value type as the default
        d = allowed[k]
        if isinstance(d, bool) and not isinstance(v, bool):
            raise HTTPException(400, f"{k} must be true/false")
        if isinstance(d, int) and not isinstance(d, bool) and not isinstance(v, int):
            raise HTTPException(400, f"{k} must be a number")
    if section == "security" and "session_timeout_minutes" in body:
        if not 15 <= body["session_timeout_minutes"] <= 10080:
            raise HTTPException(400, "Session timeout must be between 15 minutes and 7 days")
    row = db.get(AppSetting, section)
    if not row:
        row = AppSetting(key=section, value={})
        db.add(row)
    row.value = {**allowed, **(row.value or {}), **body}
    db.commit()
    log_action(db, owner, "updated", "settings", section, ", ".join(f"{k}={v}" for k, v in body.items()))
    return row.value


# ---------- company information ----------

class CompanyIn(BaseModel):
    name: str | None = None
    registration_no: str | None = None
    address: str | None = None
    industry: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None


def company_out(o: Organization) -> dict:
    return {"name": o.name, "registration_no": o.registration_no, "address": o.address, "industry": o.industry,
            "phone": o.phone, "email": o.email, "website": o.website,
            "logo_url": f"/api/files/{o.logo_file_id}/download" if o.logo_file_id else None}


@router.get("/company")
def get_company(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return company_out(db.get(Organization, 1) or Organization(id=1))


@router.put("/company")
def update_company(body: CompanyIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    o = db.get(Organization, 1)
    if not o:
        o = Organization(id=1)
        db.add(o)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(o, k, v.strip())
    db.commit()
    log_action(db, owner, "updated", "company", 1, o.name)
    return company_out(o)


@router.post("/company/logo")
async def upload_logo(file: UploadFile = File(...), owner: User = Depends(require_owner),
                      db: Session = Depends(get_db)):
    name, data, ctype = await read_and_check(file)
    if ctype not in IMAGE_TYPES:
        raise HTTPException(415, "Logo must be PNG, JPG or WEBP")
    f = store(db, owner, name, data, ctype, "logo", None)
    o = db.get(Organization, 1)
    o.logo_file_id = f.id
    db.commit()
    log_action(db, owner, "updated", "company_logo", f.id, name)
    return company_out(o)
