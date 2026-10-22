"""Full-database JSON backups (stored in file storage, recorded in backup_records).

A backup is a single gzip'd JSON file containing every row of every table.
Automatic backups run in a background thread every AUTO_BACKUP_HOURS.
"""
import gzip
import io
import json
import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from .db import SessionLocal
from .models import AppSetting, Base, BackupRecord
from .storage import storage

log = logging.getLogger("nexora.backup")


def _jsonable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


_lock = threading.Lock()
_state = {"running": False, "kind": "", "started": None, "error": ""}


def backup_running() -> dict:
    return dict(_state)


def run_backup(kind: str = "auto", user_id: int | None = None) -> BackupRecord:
    """Stream every table into a gzip'd JSON file (low memory, works for large databases). One backup at a time."""
    with _lock:
        _state.update(running=True, kind=kind, started=datetime.now(timezone.utc).isoformat(), error="")
        try:
            return _run(kind, user_id)
        except Exception as e:
            _state["error"] = str(e)[:300]
            raise
        finally:
            _state["running"] = False


def _run(kind: str, user_id: int | None) -> BackupRecord:
    buf = io.BytesIO()
    counts = {}
    with SessionLocal() as db:
        with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6) as gz:
            head = {"app": "Nexora Build", "created_at": datetime.now(timezone.utc).isoformat(), "kind": kind}
            gz.write(json.dumps(head, ensure_ascii=False)[:-1].encode("utf-8") + b', "tables": {')
            tables = [t for t in Base.metadata.sorted_tables if t.name != "stored_blobs"]  # file contents: not in backups
            for ti, table in enumerate(tables):
                gz.write((", " if ti else "").encode() + json.dumps(table.name).encode() + b": [")
                n = 0
                res = db.execute(select(table).execution_options(yield_per=500))
                for r in res.mappings():
                    gz.write((b", " if n else b"") + json.dumps({k: _jsonable(v) for k, v in r.items()},
                                                               ensure_ascii=False).encode("utf-8"))
                    n += 1
                gz.write(b"]")
                counts[table.name] = n
            gz.write(b"}}")
        data = buf.getvalue()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        key = f"backups/nexora_{kind}_{stamp}.json.gz"
        storage.save(key, data, "application/gzip")
        rec = BackupRecord(kind=kind, storage_key=key, size_bytes=len(data), tables=counts, created_by=user_id)
        db.add(rec)
        db.commit()
        log.info("Backup saved: %s (%d bytes)", key, len(data))
        _trim(db)
        return rec


def _trim(db, keep: int = 20) -> None:
    """Backups are kept inside the database now – keep the newest 20 files (the list itself stays)."""
    if storage.name != "db":
        return
    try:
        for old in db.query(BackupRecord).order_by(BackupRecord.created_at.desc()).offset(keep).all():
            storage.delete(old.storage_key)
    except Exception as e:
        log.info("old backup cleanup skipped: %s", e)


def start_backup_thread(kind: str, user_id: int | None, after=None) -> bool:
    """Run a backup in the background. Returns False if one is already running."""
    if _state["running"]:
        return False

    def work():
        try:
            rec = run_backup(kind, user_id)
            if after:
                after(rec)
        except Exception as e:
            log.warning("Backup failed: %s", e)
    threading.Thread(target=work, name="nexora-backup", daemon=True).start()
    return True


def _auto_loop():
    time.sleep(30)  # let the app start first
    while True:
        try:
            with SessionLocal() as db:
                s = db.get(AppSetting, "backups")
                cfg = (s.value if s else {}) or {}
                hours = max(1, int(cfg.get("frequency_hours", 24)))
                if cfg.get("automatic", True):
                    last = (db.query(BackupRecord).filter_by(kind="auto")
                            .order_by(BackupRecord.created_at.desc()).first())
                    due = (not last) or (datetime.now(timezone.utc) - last.created_at > timedelta(hours=hours))
                    if due:
                        run_backup("auto")
        except Exception as e:  # never crash the app because of a backup
            log.warning("Automatic backup failed: %s", e)
        time.sleep(1800)  # check every 30 minutes


def start_auto_backups() -> None:
    threading.Thread(target=_auto_loop, name="nexora-auto-backup", daemon=True).start()
