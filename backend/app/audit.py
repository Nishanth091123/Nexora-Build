"""Audit trail helper – every important change is recorded (never deleted)."""
from typing import Optional

from sqlalchemy.orm import Session

from .models import AuditLog, User


def log_action(db: Session, user: Optional[User], action: str, entity: str = "", entity_id="",
               details: str = "", project_id: Optional[int] = None, commit: bool = True) -> None:
    db.add(AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "system",
        action=action, entity=entity, entity_id=str(entity_id or ""),
        details=details[:2000], project_id=project_id,
    ))
    if commit:
        db.commit()
