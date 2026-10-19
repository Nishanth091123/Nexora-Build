from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from .. import config
from ..audit import log_action
from ..backup import backup_running, start_backup_thread
from ..db import SessionLocal, get_db
from ..models import AuditLog, BackupRecord, Project, StoredFile, User
from ..security import require_owner
from ..storage import backend_for, storage

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit")
def audit_logs(page: int = Query(1, ge=1), per_page: int = Query(25, ge=5, le=200), q: str = "",
               owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    qry = db.query(AuditLog)
    if q.strip():
        like = f"%{q.strip()}%"
        qry = qry.filter((AuditLog.username.ilike(like)) | (AuditLog.action.ilike(like))
                         | (AuditLog.details.ilike(like)) | (AuditLog.entity.ilike(like)))
    total = qry.count()
    rows = qry.order_by(AuditLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {"total": total, "page": page, "per_page": per_page,
            "items": [{"id": a.id, "username": a.username, "action": a.action, "entity": a.entity,
                       "entity_id": a.entity_id, "project_id": a.project_id, "details": a.details,
                       "created_at": a.created_at.isoformat()} for a in rows]}


def backup_out(b: BackupRecord) -> dict:
    return {"id": b.id, "kind": b.kind, "size_bytes": b.size_bytes, "tables": b.tables,
            "created_at": b.created_at.isoformat(), "file": b.storage_key.split("/")[-1]}


@router.get("/backups")
def list_backups(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    rows = db.query(BackupRecord).order_by(BackupRecord.created_at.desc()).limit(60).all()
    files_bytes = db.query(func.coalesce(func.sum(StoredFile.size_bytes), 0)).scalar() or 0
    backup_bytes = db.query(func.coalesce(func.sum(BackupRecord.size_bytes), 0)).scalar() or 0
    return {"backups": [backup_out(b) for b in rows], "storage_backend": storage.name, "running": backup_running(),
            "files_bytes": int(files_bytes), "backups_bytes": int(backup_bytes)}


@router.post("/backups")
def backup_now(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    """Starts the backup in the background (large databases take a while) – the list shows it when ready."""
    def done(rec):
        with SessionLocal() as s2:
            log_action(s2, owner, "backup", "backup", rec.id, rec.storage_key)
    started = start_backup_thread("manual", owner.id, done)
    return {"started": started, "running": True,
            "message": "Backup started – it appears in the list in a minute." if started else "A backup is already running."}


@router.get("/backups/{backup_id}/download")
def download_backup(backup_id: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    b = db.get(BackupRecord, backup_id)
    if not b:
        raise HTTPException(404, "Backup not found")
    name = b.storage_key.split("/")[-1]
    return StreamingResponse(storage.stream(b.storage_key), media_type="application/gzip",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _load_backup(db: Session, backup_id: int):
    from .. import restore
    b = db.get(BackupRecord, backup_id)
    if not b:
        raise HTTPException(404, "Backup not found")
    data = None
    for name in (storage.name, "local"):  # backups made before moving to R2 stay on the local disk
        try:
            data = backend_for(name).read(b.storage_key)
            break
        except Exception:
            continue
    if data is None:
        raise HTTPException(404, "The backup file is missing from storage")
    try:
        return b, restore.load(data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/backups/{backup_id}/compare")
def compare_backup(backup_id: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    """What is in this backup but missing now (e.g. after 'Delete permanently')."""
    from .. import restore
    b, doc = _load_backup(db, backup_id)
    tables = restore.diff(db, doc)
    return {"backup": backup_out(b), "tables": tables, "missing_total": sum(t["missing"] for t in tables)}


@router.post("/backups/{backup_id}/recover")
def recover_backup(backup_id: int, tables: list[str] = Body(..., embed=True),
                   owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    """Adds back the missing rows of the chosen tables. Existing data is never changed."""
    from .. import restore
    b, doc = _load_backup(db, backup_id)
    try:
        r = restore.recover_missing(db, doc, tables)
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Could not recover: {str(e)[:200]}")
    n = sum(r["restored"].values())
    log_action(db, owner, "recovered", "backup", b.id, f"{n} row(s) from {b.storage_key}: "
               + ", ".join(f"{k} {v}" for k, v in r["restored"].items() if v))
    return {**r, "total": n}


@router.get("/system")
def system_status(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    db_version = db.execute(text("SELECT version()")).scalar() if db.bind.dialect.name == "postgresql" else "sqlite"
    return {
        "app": config.APP_NAME, "version": config.APP_VERSION,
        "database": (db_version or "").split(" on ")[0],
        "storage_backend": storage.name,
        "counts": {
            "users": db.query(func.count(User.id)).scalar(),
            "projects": db.query(func.count(Project.id)).scalar(),
            "files": db.query(func.count(StoredFile.id)).scalar(),
            "audit_logs": db.query(func.count(AuditLog.id)).scalar(),
            "backups": db.query(func.count(BackupRecord.id)).scalar(),
        },
        "llm_keys": {"gemini": bool(config.env("GEMINI_API_KEY")), "groq": bool(config.env("GROQ_API_KEY")),
                     "openrouter": bool(config.env("OPENROUTER_API_KEY"))},
    }
