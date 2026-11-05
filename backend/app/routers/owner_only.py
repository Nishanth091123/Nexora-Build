"""Settings → Project Access → "Owner-only modules" (moved out of the old Clients router in 1.16.1)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..models import AppSetting, User
from ..security import OWNER_ONLY_CHOICES, get_current_user, owner_only_modules, require_owner

router = APIRouter(prefix="/api", tags=["settings"])


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
