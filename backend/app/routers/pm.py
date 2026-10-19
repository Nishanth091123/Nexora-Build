"""Phase 5 – project management: schedule (Gantt + milestones + stage progress), tasks, approvals."""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..models import Approval, Project, ScheduleStage, Task, User
from ..security import get_current_user, project_permissions
from ..site import logic

router = APIRouter(prefix="/api", tags=["project-management"])


def access(db: Session, user: User, project_id: int, write: bool = False) -> Project:
    p = db.get(Project, project_id)
    if not p or p.is_hidden:
        raise HTTPException(404, "Project not found")
    perms = project_permissions(db, user, p)
    if not perms.get("view"):
        raise HTTPException(403, "You don't have access to this project")
    if write and not (perms.get("edit") or perms.get("site")):
        raise HTTPException(403, "You need Edit or Site access to change this")
    return p


def stage_out(s: ScheduleStage) -> dict:
    return {"id": s.id, "name": s.name, "stage_group": s.stage_group, "start_date": s.start_date.isoformat() if s.start_date else None,
            "end_date": s.end_date.isoformat() if s.end_date else None, "progress": s.progress, "weight": s.weight,
            "is_milestone": s.is_milestone, "sort": s.sort, "notes": s.notes,
            "actual_start": s.actual_start.isoformat() if s.actual_start else None,
            "actual_end": s.actual_end.isoformat() if s.actual_end else None,
            "status": "completed" if s.progress >= 100 else "in_progress" if s.progress > 0 else "pending"}


def stages_of(db: Session, project_id: int) -> list[ScheduleStage]:
    return (db.query(ScheduleStage).filter(ScheduleStage.project_id == project_id, ScheduleStage.is_hidden.is_(False))
            .order_by(ScheduleStage.sort, ScheduleStage.id).all())


def as_dicts(rows: list[ScheduleStage]) -> list[dict]:
    return [{"name": s.name, "stage_group": s.stage_group, "start_date": s.start_date, "end_date": s.end_date,
             "progress": s.progress, "weight": s.weight} for s in rows]


def refresh_project(db: Session, p: Project) -> None:
    """Overall progress + health follow the schedule automatically once a schedule exists."""
    rows = stages_of(db, p.id)
    if not rows:
        return
    d = as_dicts(rows)
    p.progress = logic.overall(d)
    if p.status not in ("completed", "archived", "on_hold"):
        p.health = logic.health(d, date.today())
        if p.progress >= 100:
            p.status = "completed"
    db.commit()


@router.get("/projects/{project_id}/schedule")
def get_schedule(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = access(db, user, project_id)
    rows = stages_of(db, project_id)
    d = as_dicts(rows)
    today = date.today()
    return {"stages": [stage_out(s) for s in rows], "overall": logic.overall(d), "planned": logic.planned(d, today),
            "variance_days": logic.schedule_variance_days(d, today) if rows else 0,
            "health": logic.health(d, today) if rows else p.health, "pipeline": logic.pipeline(d),
            "groups": logic.group_progress(d), "project_start": p.start_date.isoformat() if p.start_date else None,
            "project_end": p.end_date.isoformat() if p.end_date else None}


@router.post("/projects/{project_id}/schedule/template")
def make_template(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = access(db, user, project_id, write=True)
    if stages_of(db, project_id):
        raise HTTPException(400, "A schedule already exists – edit it, or hide its stages first")
    for s in logic.schedule_template(p.floors, p.start_date, p.end_date):
        db.add(ScheduleStage(project_id=project_id, **s))
    db.commit()
    refresh_project(db, p)
    log_action(db, user, "created", "schedule", p.code, f"Schedule from template ({p.floors})", project_id=p.id)
    return get_schedule(project_id, user, db)


class StageIn(BaseModel):
    name: str | None = None
    stage_group: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    progress: float | None = None
    weight: float | None = None
    is_milestone: bool | None = None
    sort: int | None = None
    notes: str | None = None


@router.post("/projects/{project_id}/schedule/stages")
def add_stage(project_id: int, body: StageIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = access(db, user, project_id, write=True)
    if not body.name:
        raise HTTPException(422, "Stage name is required")
    n = len(stages_of(db, project_id))
    s = ScheduleStage(project_id=project_id, name=body.name.strip()[:120], stage_group=body.stage_group or "finishing",
                      start_date=body.start_date, end_date=body.end_date, progress=min(100, max(0, body.progress or 0)),
                      weight=body.weight or 1, is_milestone=bool(body.is_milestone), sort=body.sort if body.sort is not None else n,
                      notes=body.notes or "")
    db.add(s)
    db.commit()
    refresh_project(db, p)
    return stage_out(s)


@router.patch("/schedule/stages/{stage_id}")
def edit_stage(stage_id: int, body: StageIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(ScheduleStage, stage_id)
    if not s:
        raise HTTPException(404, "Stage not found")
    p = access(db, user, s.project_id, write=True)
    data = body.model_dump(exclude_unset=True)
    if "progress" in data and data["progress"] is not None:
        data["progress"] = min(100.0, max(0.0, float(data["progress"])))
        if data["progress"] > 0 and not s.actual_start:
            s.actual_start = date.today()
        if data["progress"] >= 100 and not s.actual_end:
            s.actual_end = date.today()
    for k, v in data.items():
        if v is not None:
            setattr(s, k, v)
    if s.start_date and s.end_date and s.end_date < s.start_date:
        raise HTTPException(400, "End date is before start date")
    db.commit()
    refresh_project(db, p)
    if "progress" in data:
        log_action(db, user, "updated", "schedule", s.id, f"{s.name}: {s.progress:g}%", project_id=p.id)
    return stage_out(s)


@router.post("/schedule/stages/{stage_id}/hide")
def hide_stage(stage_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "owner":
        raise HTTPException(403, "Only the owner can delete – ask the owner")
    s = db.get(ScheduleStage, stage_id)
    if not s:
        raise HTTPException(404, "Stage not found")
    p = access(db, user, s.project_id, write=True)
    s.is_hidden = True
    db.commit()
    refresh_project(db, p)
    return {"ok": True}


# ---------------------------------------------------------------- tasks
def task_out(t: Task, names: dict) -> dict:
    return {"id": t.id, "title": t.title, "description": t.description, "assignee_id": t.assignee_id,
            "assignee": names.get(t.assignee_id, ""), "stage_id": t.stage_id,
            "due_date": t.due_date.isoformat() if t.due_date else None, "priority": t.priority, "status": t.status,
            "overdue": bool(t.due_date and t.status != "completed" and t.due_date < date.today()),
            "completed_at": t.completed_at.isoformat() if t.completed_at else None, "created_at": t.created_at.isoformat()}


def user_names(db: Session) -> dict:
    return {u.id: u.full_name or u.username for u in db.query(User).all()}


@router.get("/projects/{project_id}/tasks")
def list_tasks(project_id: int, status: str = "all", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    access(db, user, project_id)
    q = db.query(Task).filter(Task.project_id == project_id, Task.is_hidden.is_(False))
    if status != "all":
        q = q.filter(Task.status == status)
    names = user_names(db)
    rows = q.order_by(Task.status == "completed", Task.due_date.is_(None), Task.due_date, Task.id).all()
    return [task_out(t, names) for t in rows]


class TaskIn(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee_id: int | None = None
    stage_id: int | None = None
    due_date: date | None = None
    priority: str | None = None
    status: str | None = None


@router.post("/projects/{project_id}/tasks")
def add_task(project_id: int, body: TaskIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = access(db, user, project_id, write=True)
    if not (body.title or "").strip():
        raise HTTPException(422, "Task title is required")
    t = Task(project_id=project_id, title=body.title.strip()[:200], description=body.description or "",
             assignee_id=body.assignee_id, stage_id=body.stage_id, due_date=body.due_date,
             priority=body.priority if body.priority in ("low", "normal", "high") else "normal",
             status=body.status if body.status in ("pending", "in_progress", "completed") else "pending", created_by=user.id)
    db.add(t)
    db.commit()
    log_action(db, user, "created", "task", t.id, t.title, project_id=p.id)
    return task_out(t, user_names(db))


@router.patch("/tasks/{task_id}")
def edit_task(task_id: int, body: TaskIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    p = access(db, user, t.project_id, write=True)
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in ("pending", "in_progress", "completed"):
        raise HTTPException(422, "Bad status")
    for k, v in data.items():
        setattr(t, k, v)
    if t.status == "completed" and not t.completed_at:
        t.completed_at = datetime.now(timezone.utc)
        log_action(db, user, "completed", "task", t.id, t.title, project_id=p.id, commit=False)
    elif t.status != "completed":
        t.completed_at = None
    db.commit()
    return task_out(t, user_names(db))


@router.post("/tasks/{task_id}/hide")
def hide_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "owner":
        raise HTTPException(403, "Only the owner can delete – ask the owner")
    t = db.get(Task, task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    access(db, user, t.project_id, write=True)
    t.is_hidden = True
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- approvals
def approval_out(a: Approval, names: dict) -> dict:
    return {"id": a.id, "item_type": a.item_type, "title": a.title, "ref_id": a.ref_id, "note": a.note, "status": a.status,
            "approver_id": a.approver_id, "approver": names.get(a.approver_id, "Owner"),
            "requested_by": names.get(a.requested_by, ""), "history": a.history or [],
            "decided_at": a.decided_at.isoformat() if a.decided_at else None, "created_at": a.created_at.isoformat()}


@router.get("/projects/{project_id}/approvals")
def list_approvals(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    access(db, user, project_id)
    names = user_names(db)
    rows = (db.query(Approval).filter(Approval.project_id == project_id, Approval.is_hidden.is_(False))
            .order_by(Approval.status != "pending", Approval.id.desc()).all())
    return [approval_out(a, names) for a in rows]


class ApprovalIn(BaseModel):
    item_type: str = "drawing"
    title: str
    ref_id: int | None = None
    note: str = ""
    approver_id: int | None = None


@router.post("/projects/{project_id}/approvals")
def request_approval(project_id: int, body: ApprovalIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p or p.is_hidden:
        raise HTTPException(404, "Project not found")
    perms = project_permissions(db, user, p)
    if not any(perms.get(m) for m in ("edit", "design", "estimate", "site", "vastu")):
        raise HTTPException(403, "You need write access to request an approval")
    if not body.title.strip():
        raise HTTPException(422, "Title is required")
    now = datetime.now(timezone.utc).isoformat()
    a = Approval(project_id=project_id, item_type=body.item_type if body.item_type in ("drawing", "estimate", "design", "material", "other") else "other",
                 title=body.title.strip()[:200], ref_id=body.ref_id, note=body.note, approver_id=body.approver_id,
                 requested_by=user.id, history=[{"at": now, "by": user.full_name or user.username, "action": "requested", "comment": body.note}])
    db.add(a)
    db.commit()
    log_action(db, user, "requested approval", "approval", a.id, a.title, project_id=p.id)
    return approval_out(a, user_names(db))


class DecideIn(BaseModel):
    status: str  # approved | rejected | changes
    comment: str = ""


@router.post("/approvals/{approval_id}/decide")
def decide(approval_id: int, body: DecideIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(Approval, approval_id)
    if not a:
        raise HTTPException(404, "Approval not found")
    access(db, user, a.project_id)
    if user.role != "owner" and user.id != a.approver_id:
        raise HTTPException(403, "Only the owner or the chosen approver can decide")
    if body.status not in ("approved", "rejected", "changes"):
        raise HTTPException(422, "status must be approved, rejected or changes")
    a.status = body.status
    a.decided_at = datetime.now(timezone.utc)
    a.history = list(a.history or []) + [{"at": a.decided_at.isoformat(), "by": user.full_name or user.username,
                                          "action": body.status, "comment": body.comment}]
    db.commit()
    log_action(db, user, body.status, "approval", a.id, a.title, project_id=a.project_id)
    return approval_out(a, user_names(db))
