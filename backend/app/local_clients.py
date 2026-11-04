"""1.13 – Client data lives ONLY on the owner's PC.

Clients (name, phone, address, notes) and their documents (land papers, ID proof...) are kept in
    <project folder>\\local_data\\clients.db            (a small SQLite database)
    <project folder>\\local_data\\client_files\\C-001\\  (the documents themselves)
Nothing of this goes to Neon, Render or GitHub (local_data/ is in .gitignore).

The online server (Render) has no Clients module at all – the endpoints answer "PC only".
At the first local start, clients that older versions kept in the cloud are copied here, a local
backup zip is written, and only then are the cloud copies removed.
"""
import io
import json
import logging
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from . import config

log = logging.getLogger("nexora.local_clients")

# Render sets RENDER=true on its servers; NEXORA_MODE=online can force it elsewhere.
ONLINE = bool(os.getenv("RENDER")) or config.env("NEXORA_MODE").lower() == "online"
LOCAL_DIR = Path(config.env("LOCAL_DATA_DIR", str(config.PROJECT_DIR / "local_data")))
FILES_DIR = LOCAL_DIR / "client_files"
BACKUP_DIR = LOCAL_DIR / "backups"
PC_ONLY_MSG = ("Clients are kept only on your PC. Open Nexora Build on your computer (scripts\\start.bat) "
               "to see clients and their documents.")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LBase(DeclarativeBase):
    pass


class LClient(LBase):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(160), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class LClientFile(LBase):
    __tablename__ = "client_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(Integer, index=True)
    category: Mapped[str] = mapped_column(String(40), default="client_other")
    name: Mapped[str] = mapped_column(String(200))
    rel_path: Mapped[str] = mapped_column(String(400))
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


_engine = None
_Session = None


def _ensure() -> None:
    global _engine, _Session
    if _engine is not None:
        return
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{(LOCAL_DIR / 'clients.db').as_posix()}",
                            connect_args={"check_same_thread": False})
    LBase.metadata.create_all(_engine)
    _Session = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def require_local() -> None:
    if ONLINE:
        raise HTTPException(404, PC_ONLY_MSG)


def get_ldb():
    """FastAPI dependency: the PC-only clients database."""
    require_local()
    _ensure()
    s = _Session()
    try:
        yield s
    finally:
        s.close()


def session():
    _ensure()
    return _Session()


# ---------------------------------------------------------------- files on disk
def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._ -]", "_", s)[:150] or "file"


def save_file(c: LClient, name: str, data: bytes) -> str:
    folder = FILES_DIR / _safe(c.code)
    folder.mkdir(parents=True, exist_ok=True)
    stem = datetime.now().strftime("%Y%m%d_%H%M%S_") + _safe(name)
    path = folder / stem
    path.write_bytes(data)
    return path.relative_to(LOCAL_DIR).as_posix()


def file_path(f: LClientFile) -> Path:
    p = (LOCAL_DIR / f.rel_path).resolve()
    if LOCAL_DIR.resolve() not in p.parents:
        raise HTTPException(400, "Bad file path")
    return p


# ---------------------------------------------------------------- local backup
def backup_zip(reason: str, client_ids: list[int] | None = None) -> Path:
    """Zip clients.db + client documents into local_data/backups (kept on the PC)."""
    _ensure()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    out = BACKUP_DIR / f"clients_{datetime.now():%Y%m%d_%H%M%S}_{_safe(reason)}.zip"
    with session() as s:
        q = s.query(LClient)
        if client_ids:
            q = q.filter(LClient.id.in_(client_ids))
        clients = q.all()
        files = s.query(LClientFile).filter(LClientFile.client_id.in_([c.id for c in clients])).all() if clients else []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("clients.json", json.dumps({
            "made": datetime.now().isoformat(), "reason": reason,
            "clients": [{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in c.__dict__.items()
                         if not k.startswith("_")} for c in clients],
            "files": [{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in f.__dict__.items()
                       if not k.startswith("_")} for f in files]}, indent=1))
        for f in files:
            p = LOCAL_DIR / f.rel_path
            if p.exists():
                z.write(p, f.rel_path)
    # keep the newest 30
    olds = sorted(BACKUP_DIR.glob("clients_*.zip"))
    for o in olds[:-30]:
        try:
            o.unlink()
        except OSError:
            pass
    return out


# ---------------------------------------------------------------- one-time move from the cloud
def move_from_cloud(db) -> int:
    """Copy clients + client documents that older versions kept in Neon to this PC, then remove the
    cloud copies (local backup zip first). Safe to run every start: does nothing when the cloud has none."""
    if ONLINE:
        return 0
    from .models import Client, StoredFile
    from .storage import backend_for
    cloud = db.query(Client).all()
    cfiles = db.query(StoredFile).filter(StoredFile.client_id.isnot(None)).all()
    if not cloud and not cfiles:
        return 0
    _ensure()
    moved = 0
    with session() as s:
        for c in cloud:
            if s.get(LClient, c.id) is None:
                code = c.code
                if s.query(LClient).filter_by(code=code).first():
                    code = f"{code}-{c.id}"
                s.add(LClient(id=c.id, code=code, name=c.name, phone=c.phone or "", email=c.email or "",
                              address=c.address or "", location=c.location or "", notes=c.notes or "",
                              is_hidden=bool(c.is_hidden), created_by=c.created_by,
                              created_at=c.created_at or utcnow(), updated_at=c.updated_at or utcnow()))
                moved += 1
        s.commit()
        for f in cfiles:
            lc = s.get(LClient, f.client_id)
            if lc is None:
                continue
            if s.query(LClientFile).filter_by(client_id=lc.id, name=f.original_name, size_bytes=f.size_bytes or 0).first():
                continue  # copied on an earlier start
            data = backend_for(f.storage_backend).read(f.storage_key)  # raises → nothing is removed below
            rel = save_file(lc, f.original_name, data)
            s.add(LClientFile(client_id=lc.id, category=f.category or "client_other", name=f.original_name,
                              rel_path=rel, content_type=f.content_type or "application/octet-stream",
                              size_bytes=len(data), is_hidden=bool(f.is_hidden), created_at=f.created_at or utcnow()))
        s.commit()
    zp = backup_zip("moved_from_cloud")
    log.info("Clients moved to this PC: %d clients, %d documents (backup %s)", moved, len(cfiles), zp.name)
    # now remove the cloud copies (owner rule: backup first – done above, on this PC)
    from .routers.trash import _allow, _drop_file
    _allow(db)
    for f in cfiles:
        _drop_file(db, f)
    db.flush()
    for c in cloud:
        db.delete(c)
    db.commit()
    return moved + len(cfiles)


# ---------------------------------------------------------------- helpers used by the routers
def next_code(s) -> str:
    n = (s.query(func.max(LClient.id)).scalar() or 0) + 1
    code = f"C-{n:03d}"
    while s.query(LClient).filter_by(code=code).first():
        n += 1
        code = f"C-{n:03d}"
    return code


def find_or_create(s, name: str, user_id: int | None, location: str = "") -> LClient | None:
    name = (name or "").strip()
    if not name:
        return None
    c = (s.query(LClient).filter(func.lower(LClient.name) == name.lower(), LClient.is_hidden.is_(False))
         .order_by(LClient.id).first())
    if not c:
        c = LClient(code=next_code(s), name=name, location=location or "", created_by=user_id)
        s.add(c)
        s.commit()
    return c


def status() -> dict:
    return {"local": not ONLINE, "folder": str(LOCAL_DIR) if not ONLINE else "", "message": "" if not ONLINE else PC_ONLY_MSG}


def daily_backup() -> None:
    """At start-up on the PC: one local backup zip a day (only when there are clients)."""
    if ONLINE:
        return
    _ensure()
    with session() as s:
        if not s.query(LClient).count():
            return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    if not any(p.name.startswith(f"clients_{today}") for p in BACKUP_DIR.glob("clients_*.zip")):
        backup_zip("daily")
