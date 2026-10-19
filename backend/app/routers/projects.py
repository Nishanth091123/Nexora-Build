from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..models import AuditLog, Project, ProjectAccess, StoredFile, User
from ..security import (get_current_user, project_permissions, require_project,
                        visible_project_ids)

router = APIRouter(prefix="/api/projects", tags=["projects"])

PROJECT_TYPES = {"residential", "commercial", "industrial", "warehouse", "road", "villa", "infrastructure", "other"}
COVER_BY_TYPE = {
    "residential": "/images/proj_residential.jpg", "commercial": "/images/proj_commercial.jpg",
    "industrial": "/images/proj_warehouse.jpg", "warehouse": "/images/proj_warehouse.jpg",
    "road": "/images/proj_road.jpg", "infrastructure": "/images/proj_road.jpg",
    "villa": "/images/proj_villa.jpg", "other": "/images/proj_residential.jpg",
}
FACINGS = {"", "east", "west", "north", "south", "north-east", "north-west", "south-east", "south-west"}


def project_out(p: Project, perms: dict | None = None) -> dict:
    d = {c.name: getattr(p, c.name) for c in Project.__table__.columns}
    for k in ("start_date", "end_date", "created_at", "updated_at"):
        d[k] = d[k].isoformat() if d[k] else None
    d["cover_image"] = p.cover_image or COVER_BY_TYPE.get(p.project_type, COVER_BY_TYPE["other"])
    if perms is not None:
        d["permissions"] = perms
    return d


class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    project_type: str = "residential"
    client_name: str = ""
    location: str = ""
    district: str = ""
    state: str = "Tamil Nadu"
    plot_width: float | None = Field(default=None, gt=0)
    plot_length: float | None = Field(default=None, gt=0)
    unit: str = "ft"
    facing: str = ""
    road_width: float | None = Field(default=None, gt=0)
    floors: str = "G"
    builtup_area: float | None = Field(default=None, gt=0)
    structure_type: str = "rcc_framed"
    spec_level: str = "standard"
    start_date: date | None = None
    end_date: date | None = None
    status: str = "ongoing"
    health: str = "on_track"
    notes: str = ""


class ProjectPatch(BaseModel):
    name: str | None = None
    project_type: str | None = None
    client_name: str | None = None
    location: str | None = None
    district: str | None = None
    state: str | None = None
    plot_width: float | None = None
    plot_length: float | None = None
    unit: str | None = None
    facing: str | None = None
    road_width: float | None = None
    floors: str | None = None
    builtup_area: float | None = None
    structure_type: str | None = None
    spec_level: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    health: str | None = None
    progress: float | None = Field(default=None, ge=0, le=100)
    notes: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


def validate_fields(data: dict) -> None:
    checks = {
        "project_type": PROJECT_TYPES, "unit": {"ft", "m"}, "facing": FACINGS,
        "structure_type": {"rcc_framed", "load_bearing"}, "spec_level": {"basic", "standard", "premium"},
        "status": {"ongoing", "on_hold", "completed", "archived"}, "health": {"on_track", "delayed"},
    }
    for field, allowed in checks.items():
        if field in data and data[field] is not None and data[field] not in allowed:
            raise HTTPException(400, f"Invalid {field}: {data[field]}. Allowed: {', '.join(sorted(allowed))}")
    if data.get("start_date") and data.get("end_date") and data["end_date"] < data["start_date"]:
        raise HTTPException(400, "End date cannot be before start date")


def next_code(db: Session) -> str:
    n = (db.query(func.max(Project.id)).scalar() or 0) + 1
    code = f"PRJ-{n:04d}"
    while db.query(Project).filter_by(code=code).first():
        n += 1
        code = f"PRJ-{n:04d}"
    return code


@router.get("")
def list_projects(status: str = Query("all"), q: str = "", sort: str = "updated",
                  include_archived: bool = False, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    qry = db.query(Project).filter(Project.is_hidden.is_(False))
    ids = visible_project_ids(db, user)
    if ids is not None:
        qry = qry.filter(Project.id.in_(ids or [-1]))
    if not include_archived:
        qry = qry.filter(Project.status != "archived")
    all_rows = qry.all()
    counts = {
        "all": len(all_rows),
        "ongoing": sum(p.status == "ongoing" for p in all_rows),
        "completed": sum(p.status == "completed" for p in all_rows),
        "on_hold": sum(p.status == "on_hold" for p in all_rows),
        "on_track": sum(p.status == "ongoing" and p.health == "on_track" for p in all_rows),
        "delayed": sum(p.status == "ongoing" and p.health == "delayed" for p in all_rows),
    }
    if status != "all":
        qry = qry.filter(Project.status == status)
    if q.strip():
        like = f"%{q.strip()}%"
        qry = qry.filter(or_(Project.name.ilike(like), Project.location.ilike(like),
                             Project.code.ilike(like), Project.client_name.ilike(like)))
    order = {"updated": Project.updated_at.desc(), "name": Project.name.asc(),
             "start": Project.start_date.asc(), "created": Project.created_at.desc()}.get(sort, Project.updated_at.desc())
    rows = qry.order_by(order).all()
    team_total = db.query(func.count(User.id)).filter(User.status == "active").scalar() or 0
    return {"projects": [project_out(p, project_permissions(db, user, p)) for p in rows],
            "counts": counts, "team_members": team_total}


@router.post("")
def create_project(body: ProjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "owner" and not user.can_create_projects:
        raise HTTPException(403, "The owner has not allowed you to create projects")
    data = body.model_dump()
    validate_fields(data)
    # Built-up area is never guessed from plot size (setbacks apply – Design Studio, Phase 3).
    p =Project(code=next_code(db), created_by=user.id, **data)
    db.add(p)
    db.flush()
    if user.role != "owner":  # creator gets full access to own project
        db.add(ProjectAccess(user_id=user.id, project_id=p.id, can_view=True, can_edit=True, can_design=True,
                             can_estimate=True, can_site=True, can_vastu=True, can_ai=True,
                             project_role="editor", granted_by=user.id))
    db.commit()
    log_action(db, user, "created", "project", p.code, p.name, project_id=p.id)
    return project_out(p, project_permissions(db, user, p))


@router.get("/{project_id}")
def get_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_project(db, user, project_id, "view")
    perms = project_permissions(db, user, p)
    owner = db.query(User).filter(User.role == "owner").first()
    team = []
    if owner:
        team.append({"id": owner.id, "full_name": owner.full_name, "job_title": owner.job_title,
                     "project_role": "owner"})
    for a in db.query(ProjectAccess).filter_by(project_id=p.id).all():
        if a.user and a.user.status == "active" and a.project_role != "none":
            team.append({"id": a.user.id, "full_name": a.user.full_name, "job_title": a.user.job_title,
                         "project_role": a.project_role})
    doc_counts = dict(db.query(StoredFile.category, func.count(StoredFile.id))
                      .filter(StoredFile.project_id == p.id, StoredFile.is_hidden.is_(False))
                      .group_by(StoredFile.category).all())
    activity = (db.query(AuditLog).filter(AuditLog.project_id == p.id)
                .order_by(AuditLog.created_at.desc()).limit(10).all())
    return {
        "project": project_out(p, perms),
        "team": team,
        "document_counts": doc_counts,
        "activity": [{"id": a.id, "username": a.username, "action": a.action, "entity": a.entity,
                      "details": a.details, "created_at": a.created_at.isoformat()} for a in activity],
    }


@router.patch("/{project_id}")
def update_project(project_id: int, body: ProjectPatch, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    p = require_project(db, user, project_id, "edit")
    data = body.model_dump(exclude_unset=True)
    if data.get("status") == "archived" and user.role != "owner":
        raise HTTPException(403, "Only the owner can archive projects")
    merged = {"start_date": p.start_date, "end_date": p.end_date, **data}
    validate_fields(merged)
    changed = []
    for k, v in data.items():
        if getattr(p, k) != v:
            setattr(p, k, v)
            changed.append(k)
    db.commit()
    if changed:
        log_action(db, user, "archived" if data.get("status") == "archived" else "updated", "project", p.code,
                   "Changed: " + ", ".join(changed), project_id=p.id)
    return project_out(p, project_permissions(db, user, p))
