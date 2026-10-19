"""Restore from a Nexora backup (gzip'd JSON written by backup.py).

Two uses:
  * In the app (owner): "Recover from backup" – adds back rows that are in the backup but missing now
    (e.g. after 'Delete permanently'). Existing rows are never changed or overwritten.
  * scripts/restore_backup.py: rebuild a NEW, EMPTY database from a backup (disaster recovery).
Stored files (drawings, photos) live in file storage, not in the backup; a recovered file row whose stored
object was deleted is reported as 'file missing'.
"""
from __future__ import annotations

import gzip
import json
from datetime import date, datetime

from sqlalchemy import Date, DateTime, select, text
from sqlalchemy.orm import Session

from .models import Base

SKIP = {"schema_migrations"}  # recreated by the app itself
LABELS = {
    "projects": "Projects", "files": "Documents / files", "designs": "Designs", "estimates": "Estimates",
    "drawing_analyses": "Drawing analyses", "vastu_reports": "Vastu reports", "schedule_stages": "Schedule stages",
    "tasks": "Tasks", "approvals": "Approvals", "site_reports": "Daily reports", "site_activities": "Site activities",
    "site_photos": "Site photos", "material_entries": "Material entries", "workers": "Workers", "attendance": "Attendance",
    "quality_checks": "Quality checks", "safety_records": "Safety / issues", "ai_conversations": "AI conversations",
    "ai_messages": "AI messages", "bbs_schedules": "BBS", "permit_checklists": "Plan approval checklists",
    "project_access": "Project access", "users": "Users", "rate_items": "Rates",
}


def load(data: bytes) -> dict:
    try:
        doc = json.loads(gzip.decompress(data).decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Not a Nexora backup file: {e}")
    if doc.get("app") != "Nexora Build" or "tables" not in doc:
        raise ValueError("Not a Nexora backup file")
    return doc


def _convert(table, row: dict) -> dict:
    out = {}
    for c in table.columns:
        if c.name not in row:
            continue
        v = row[c.name]
        if v is not None and isinstance(v, str):
            if isinstance(c.type, DateTime):
                v = datetime.fromisoformat(v)
            elif isinstance(c.type, Date):
                v = date.fromisoformat(v[:10])
        out[c.name] = v
    return out


def _pk(table):
    cols = list(table.primary_key.columns)
    return cols[0] if len(cols) == 1 else None


def diff(db: Session, doc: dict) -> list[dict]:
    """Per table: rows in the backup, and how many of them are missing in the database now."""
    out = []
    for table in Base.metadata.sorted_tables:
        rows = doc["tables"].get(table.name) or []
        pk = _pk(table)
        if table.name in SKIP or not rows or pk is None:
            continue
        have = {r[0] for r in db.execute(select(pk)).all()}
        missing = [r for r in rows if r.get(pk.name) not in have]
        sample = []
        for r in missing[:5]:
            t = r.get("name") or r.get("title") or r.get("original_name") or r.get("caption") or r.get("item") or r.get("username")
            sample.append(str(t) if t else f"#{r.get(pk.name)}")
        out.append({"table": table.name, "label": LABELS.get(table.name, table.name.replace("_", " ")),
                    "in_backup": len(rows), "missing": len(missing), "sample": sample})
    return out


def _fix_sequences(db: Session, names: list[str]) -> None:
    if db.get_bind().dialect.name != "postgresql":
        return
    for name in names:
        table = Base.metadata.tables[name]
        pk = _pk(table)
        if pk is None or not str(pk.type).upper().startswith("INTEGER"):
            continue
        db.execute(text(f"SELECT setval(pg_get_serial_sequence('{name}', '{pk.name}'), "
                        f"COALESCE((SELECT MAX({pk.name}) FROM {name}), 1))"))


def _fk_ok(db: Session, table, cache: dict):
    """Returns a checker: a row is skipped if it points to a parent row that does not exist (and is not being restored)."""
    fks = []
    for c in table.columns:
        for fk in c.foreign_keys:
            ref = fk.column
            key = (ref.table.name, ref.name)
            if key not in cache:
                cache[key] = {r[0] for r in db.execute(select(ref)).all()}
            fks.append((c.name, cache[key]))

    def ok(row: dict) -> bool:
        return all(row.get(col) is None or row.get(col) in have for col, have in fks)
    return ok


def recover_missing(db: Session, doc: dict, tables: list[str]) -> dict:
    """Insert rows that are in the backup but missing now. Never updates or deletes existing rows.
    Recovered items keep their old 'in the bin' flag, so they show in the Recycle Bin → Restore."""
    from .storage import backend_for
    wanted = set(tables)
    done, skipped, files_missing = {}, {}, 0
    cache: dict = {}
    for table in Base.metadata.sorted_tables:  # parents before children
        if table.name not in wanted or table.name in SKIP:
            continue
        pk = _pk(table)
        if pk is None:
            continue
        have = {r[0] for r in db.execute(select(pk)).all()}
        ok = _fk_ok(db, table, cache)
        n = s = 0
        for r in doc["tables"].get(table.name) or []:
            if r.get(pk.name) in have:
                continue
            if not ok(r):
                s += 1
                continue
            db.execute(table.insert().values(**_convert(table, r)))
            n += 1
            if table.name == "files" and r.get("storage_key"):
                try:
                    if not backend_for(r.get("storage_backend") or "local").exists(r["storage_key"]):
                        files_missing += 1
                except Exception:
                    files_missing += 1
        db.flush()
        done[table.name] = n
        if s:
            skipped[table.name] = s
        cache[(table.name, pk.name)] = have | {r.get(pk.name) for r in doc["tables"].get(table.name) or [] if ok(r)}
    _fix_sequences(db, list(done))
    db.commit()
    return {"restored": done, "skipped": skipped, "files_missing": files_missing}


def restore_all(db: Session, doc: dict) -> dict:
    """Fill an EMPTY database with everything in the backup (used by scripts/restore_backup.py)."""
    done = {}
    for table in Base.metadata.sorted_tables:
        if table.name in SKIP:
            continue
        rows = doc["tables"].get(table.name) or []
        for r in rows:
            db.execute(table.insert().values(**_convert(table, r)))
        done[table.name] = len(rows)
    _fix_sequences(db, [t for t, n in done.items() if n])
    db.commit()
    return done
