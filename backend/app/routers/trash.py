"""Phase 6.6 – Recycle Bin (owner only).

Delete  → the item is hidden and listed in the Recycle Bin (is_hidden = true).
Restore → visible again.
Delete permanently / Empty bin → a backup is taken first, then the rows (and stored files) are removed.
Only this module can remove rows: it switches the database's delete guard off inside its own transaction.
The owner account and the audit log are never deleted.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import log_action
from ..backup import run_backup
from ..db import get_db
from ..models import (AIConversation, AIDocChunk, AIIndexedFile, AIMessage, AIPhotoCheck, Approval, Attendance,
                      BbsSchedule, Design, DrawingAnalysis, Estimate, MaterialEntry, PermitChecklist, Project,
                      ProjectAccess, QualityCheck, SafetyRecord, ScheduleStage, SiteActivity, SitePhoto, SiteReport,
                      StoredFile, Task, TrashLog, User, VastuReport, Worker)
from ..security import require_owner
from ..storage import backend_for

log = logging.getLogger("nexora.trash")
router = APIRouter(prefix="/api/trash", tags=["recycle-bin"])


def _d(v):
    return v.strftime("%d %b %Y") if v else ""


# entity → (model, label, title function)
ENTITIES = {
    "project": (Project, "Project", lambda o: f"{o.code} · {o.name}"),
    "file": (StoredFile, "Document / file", lambda o: f"{o.original_name} (v{o.version})"),
    "design": (Design, "Design", lambda o: f"{o.title} (v{o.version})"),
    "estimate": (Estimate, "Estimate", lambda o: f"{o.title} (v{o.version})"),
    "analysis": (DrawingAnalysis, "Drawing analysis", lambda o: o.file_name),
    "vastu_report": (VastuReport, "Vastu report", lambda o: f"Vastu report – design v{o.design_version}"),
    "stage": (ScheduleStage, "Schedule stage", lambda o: o.name),
    "task": (Task, "Task", lambda o: o.title),
    "approval": (Approval, "Approval", lambda o: o.title),
    "activity": (SiteActivity, "Site activity", lambda o: f"{o.title} – {_d(o.work_date)}"),
    "photo": (SitePhoto, "Site photo", lambda o: f"{o.caption or 'Photo'} – {_d(o.taken_on)}"),
    "material": (MaterialEntry, "Material entry", lambda o: f"{o.code} {o.kind} {o.qty:g} – {_d(o.entry_date)}"),
    "quality": (QualityCheck, "Quality check", lambda o: o.item),
    "safety": (SafetyRecord, "Safety / issue", lambda o: f"{o.title} – {_d(o.record_date)}"),
    "worker": (Worker, "Worker", lambda o: f"{o.name} ({o.trade})"),
    "conversation": (AIConversation, "AI conversation", lambda o: o.title),
    "bbs": (BbsSchedule, "Bar bending schedule", lambda o: o.title),
}


def _get(db: Session, entity: str, eid: int):
    if entity not in ENTITIES:
        raise HTTPException(404, "Unknown item type")
    o = db.get(ENTITIES[entity][0], eid)
    if not o:
        raise HTTPException(404, "Item not found")
    return o


def move_to_bin(db: Session, user: User, entity: str, o) -> None:
    o.is_hidden = True
    title = ENTITIES[entity][2](o)
    db.add(TrashLog(entity=entity, entity_id=o.id, project_id=o.id if entity == "project" else getattr(o, "project_id", None),
                    title=title[:300], deleted_by=user.id))
    db.commit()
    log_action(db, user, "deleted", entity, o.id, f"moved to Recycle Bin: {title}",
               project_id=o.id if entity == "project" else getattr(o, "project_id", None))


@router.post("/{entity}/{eid}")
def delete_item(entity: str, eid: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    o = _get(db, entity, eid)
    if getattr(o, "is_hidden", False):
        return {"ok": True, "already": True}
    move_to_bin(db, owner, entity, o)
    return {"ok": True}


@router.post("/{entity}/{eid}/restore")
def restore_item(entity: str, eid: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    o = _get(db, entity, eid)
    o.is_hidden = False
    for t in db.query(TrashLog).filter_by(entity=entity, entity_id=eid, state="in_bin").all():
        t.state, t.done_at = "restored", datetime.now(timezone.utc)
    db.commit()
    log_action(db, owner, "restored", entity, eid, ENTITIES[entity][2](o))
    return {"ok": True}


@router.get("")
def list_bin(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    logs = {}
    for t in db.query(TrashLog).filter_by(state="in_bin").order_by(TrashLog.id).all():
        logs[(t.entity, t.entity_id)] = t
    names = {u.id: (u.full_name or u.username) for u in db.query(User).all()}
    hidden_projects = {p.id for p in db.query(Project.id).filter(Project.is_hidden.is_(True)).all()}
    pnames = {p.id: f"{p.code} · {p.name}" for p in db.query(Project.id, Project.code, Project.name).all()}
    items = []
    for entity, (model, label, title) in ENTITIES.items():
        for o in db.query(model).filter(model.is_hidden.is_(True)).limit(2000).all():
            pid = o.id if entity == "project" else getattr(o, "project_id", None)
            if entity != "project" and pid in hidden_projects:
                continue  # shown inside its project
            t = logs.get((entity, o.id))
            items.append({"entity": entity, "label": label, "id": o.id, "title": title(o), "project_id": pid,
                          "project": pnames.get(pid, "") if entity != "project" else "",
                          "deleted_at": t.deleted_at.isoformat() if t else None,
                          "deleted_by": names.get(t.deleted_by, "") if t else ""})
    items.sort(key=lambda x: x["deleted_at"] or "", reverse=True)
    archived = [{"id": p.id, "title": f"{p.code} · {p.name}", "updated_at": p.updated_at.isoformat() if p.updated_at else None}
                for p in db.query(Project).filter(Project.status == "archived", Project.is_hidden.is_(False)).all()]
    return {"items": items, "archived_projects": archived}


# ---------------------------------------------------------------- permanent delete
def _allow(db: Session) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SET LOCAL nexora.allow_delete = 'on'"))


def _drop_file(db: Session, f: StoredFile) -> None:
    try:
        backend_for(f.storage_backend).delete(f.storage_key)
    except Exception as e:  # the row still goes; a missing object is fine
        log.info("storage delete %s: %s", f.storage_key, e)
    db.query(AIDocChunk).filter(AIDocChunk.file_id == f.id).delete(synchronize_session=False)
    db.query(AIIndexedFile).filter(AIIndexedFile.file_id == f.id).delete(synchronize_session=False)
    db.query(AIPhotoCheck).filter(AIPhotoCheck.file_id == f.id).delete(synchronize_session=False)
    db.query(SitePhoto).filter(SitePhoto.file_id == f.id).delete(synchronize_session=False)
    db.query(SiteActivity).filter(SiteActivity.photo_file_id == f.id).update({"photo_file_id": None}, synchronize_session=False)
    db.delete(f)


def _purge(db: Session, entity: str, o) -> None:
    if entity == "project":
        pid = o.id
        conv_ids = [c.id for c in db.query(AIConversation.id).filter(AIConversation.project_id == pid).all()]
        if conv_ids:
            db.query(AIMessage).filter(AIMessage.conversation_id.in_(conv_ids)).delete(synchronize_session=False)
        for f in db.query(StoredFile).filter(StoredFile.project_id == pid).all():
            _drop_file(db, f)
        db.flush()  # files rows go before the project row (foreign key)
        for m in (AIConversation, AIDocChunk, AIIndexedFile, AIPhotoCheck, Attendance, Worker, SiteReport, SiteActivity,
                  SitePhoto, MaterialEntry, QualityCheck, SafetyRecord, Task, Approval, ScheduleStage, VastuReport,
                  DrawingAnalysis, Design, Estimate, BbsSchedule, PermitChecklist, ProjectAccess):
            db.query(m).filter(m.project_id == pid).delete(synchronize_session=False)
        db.flush()
        db.delete(o)
    elif entity == "file":
        _drop_file(db, o)
    elif entity == "photo":
        f = db.get(StoredFile, o.file_id) if o.file_id else None
        db.delete(o)
        db.flush()
        if f:
            _drop_file(db, f)
    elif entity == "conversation":
        db.query(AIMessage).filter(AIMessage.conversation_id == o.id).delete(synchronize_session=False)
        db.delete(o)
    elif entity == "worker":
        db.query(Attendance).filter(Attendance.worker_id == o.id).delete(synchronize_session=False)
        db.delete(o)
    else:
        db.delete(o)


def _purge_many(db: Session, owner: User, pairs: list[tuple[str, int]]) -> int:
    rec = run_backup("predelete", owner.id)  # safety copy first – can be restored if needed
    _allow(db)
    n = 0
    titles = []
    for entity, eid in pairs:
        o = db.get(ENTITIES[entity][0], eid)
        if not o or not getattr(o, "is_hidden", False):
            continue
        titles.append(f"{ENTITIES[entity][1]}: {ENTITIES[entity][2](o)}")
        _purge(db, entity, o)
        db.flush()
        for t in db.query(TrashLog).filter_by(entity=entity, entity_id=eid, state="in_bin").all():
            t.state, t.done_at = "purged", datetime.now(timezone.utc)
        n += 1
    db.commit()
    log_action(db, owner, "deleted permanently", "recycle_bin", n,
               f"{n} item(s); backup {rec.storage_key}: " + "; ".join(titles)[:900])
    return n


@router.post("/{entity}/{eid}/purge")
async def purge_item(entity: str, eid: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    o = _get(db, entity, eid)
    if not getattr(o, "is_hidden", False):
        raise HTTPException(400, "Move it to the Recycle Bin first")
    n = await run_in_threadpool(_purge_many, db, owner, [(entity, eid)])
    return {"ok": True, "deleted": n}


@router.post("/empty")
async def empty_bin(body: dict, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    if (body or {}).get("confirm") != "DELETE":
        raise HTTPException(400, "Type DELETE to confirm")
    pairs = []
    # projects last-but-first: their children go with them
    for entity, (model, _, _) in ENTITIES.items():
        for o in db.query(model.id).filter(model.is_hidden.is_(True)).all():
            pairs.append((entity, o.id))
    pairs.sort(key=lambda x: x[0] == "project")
    n = await run_in_threadpool(_purge_many, db, owner, pairs)
    return {"ok": True, "deleted": n}
