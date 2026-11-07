"""1.20 AI Render endpoint: POST /api/projects/{pid}/ai-render  (picture of the 3D view → photo-like concept render)."""
from __future__ import annotations

import base64
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..ai import render as R
from ..audit import log_action
from ..db import get_db
from ..models import User
from ..security import get_current_user, project_permissions, require_project

router = APIRouter(prefix="/api", tags=["ai-render"])
_last: dict[int, float] = {}


class RenderIn(BaseModel):
    image: str  # PNG / JPEG, base64 or data URL
    kind: str = "exterior"  # exterior | interior
    style: str = "modern"
    light: str = "day"
    extra: str = ""
    strength: float = 0.5  # 0.2 keeps my design … 0.85 more creative
    seed: int | None = None


@router.get("/ai-render/status")
def status(user: User = Depends(get_current_user)):
    return R.configured()


@router.post("/projects/{project_id}/ai-render")
def ai_render(project_id: int, body: RenderIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_project(db, user, project_id, "view")
    perms = project_permissions(db, user, p)
    if not (perms.get("design") or perms.get("ai")):
        raise HTTPException(403, "You need Design or AI access on this project")
    now = time.time()
    if now - _last.get(user.id, 0) < 8:
        raise HTTPException(429, "One render at a time – wait a few seconds.")
    _last[user.id] = now
    data = body.image.split(",", 1)[1] if body.image.startswith("data:") else body.image
    try:
        img = base64.b64decode(data, validate=False)
    except Exception:
        raise HTTPException(400, "Picture could not be read")
    if body.kind not in ("exterior", "interior"):
        raise HTTPException(400, "kind must be exterior or interior")
    try:
        out = R.render(img, body.kind, body.style, body.light, body.extra, body.strength, body.seed)
    except R.RenderError as e:
        _last.pop(user.id, None)
        raise HTTPException(e.status, str(e))
    log_action(db, user, "created", "ai_render", p.id, f"AI render ({body.kind}, {body.style}) via {out['provider']}", project_id=p.id)
    out["label"] = "AI concept render – not to scale"
    return out
