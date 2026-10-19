import re
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import config
from ..audit import log_action
from ..db import get_db
from ..models import StoredFile, User
from ..security import get_current_user, require_project
from ..storage import backend_for, storage

router = APIRouter(prefix="/api/files", tags=["files"])

ALLOWED = {
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".dxf": "image/vnd.dxf", ".xlsx":
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".glb": "model/gltf-binary", ".txt": "text/plain",
}
CATEGORIES = {"drawing", "report", "photo", "contract", "other"}
DWG_MESSAGE = ("DWG files can't be read directly. Please convert to DXF (AutoCAD 2018 DXF, ASCII) or a vector PDF: "
               "in AutoCAD use SAVEAS → 'AutoCAD 2018 DXF', or use the free ODA File Converter "
               "(DWG → DXF 2018). Then upload the DXF/PDF here. | "
               "DWG file-ஐ நேரடியாக படிக்க முடியாது. DXF 2018 அல்லது vector PDF-ஆ convert பண்ணி upload பண்ணுங்க.")
MAGIC = {".pdf": [b"%PDF"], ".png": [b"\x89PNG"], ".jpg": [b"\xff\xd8"], ".jpeg": [b"\xff\xd8"]}


def file_out(f: StoredFile) -> dict:
    return {"id": f.id, "project_id": f.project_id, "category": f.category, "name": f.original_name,
            "content_type": f.content_type, "size_bytes": f.size_bytes, "version": f.version,
            "uploaded_by": f.uploaded_by, "created_at": f.created_at.isoformat(),
            "url": f"/api/files/{f.id}/download"}


def safe_name(name: str) -> str:
    name = name.replace("\\", "/").split("/")[-1]
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:150] or "file"


async def read_and_check(upload: UploadFile) -> tuple[str, bytes, str]:
    name = safe_name(upload.filename or "file")
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if ext == ".dwg":
        raise HTTPException(415, DWG_MESSAGE)
    if ext not in ALLOWED:
        raise HTTPException(415, f"File type {ext or '(none)'} not supported. Allowed: "
                                 + ", ".join(sorted(ALLOWED)))
    data = await upload.read()
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {config.MAX_UPLOAD_MB} MB)")
    if not data:
        raise HTTPException(400, "Empty file")
    if ext in MAGIC and not any(data.startswith(m) for m in MAGIC[ext]):
        raise HTTPException(400, f"This file does not look like a real {ext} file")
    return name, data, ALLOWED[ext]


def store(db: Session, user: User, name: str, data: bytes, ctype: str, category: str,
          project_id: int | None) -> StoredFile:
    folder = f"projects/{project_id}" if project_id else "org"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    key = f"{folder}/{category}/{stamp}_{uuid.uuid4().hex[:10]}_{name}"
    storage.save(key, data, ctype)
    prev = (db.query(StoredFile).filter_by(project_id=project_id, original_name=name, category=category)
            .order_by(StoredFile.version.desc()).first())
    f = StoredFile(project_id=project_id, category=category, original_name=name, storage_key=key,
                   storage_backend=storage.name, content_type=ctype, size_bytes=len(data),
                   version=(prev.version + 1) if prev else 1, uploaded_by=user.id)
    db.add(f)
    db.commit()
    return f


@router.post("/project/{project_id}")
async def upload_project_file(project_id: int, category: str = Form("other"), file: UploadFile = File(...),
                              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if category not in CATEGORIES:
        raise HTTPException(400, f"category must be one of {', '.join(sorted(CATEGORIES))}")
    require_project(db, user, project_id, "edit")
    name, data, ctype = await read_and_check(file)
    f = store(db, user, name, data, ctype, category, project_id)
    log_action(db, user, "uploaded", "file", f.id, f"{name} (v{f.version}, {category})", project_id=project_id)
    return file_out(f)


@router.get("/project/{project_id}")
def list_project_files(project_id: int, category: str = "", user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    require_project(db, user, project_id, "view")
    q = db.query(StoredFile).filter(StoredFile.project_id == project_id, StoredFile.is_hidden.is_(False))
    if category:
        q = q.filter(StoredFile.category == category)
    return [file_out(f) for f in q.order_by(StoredFile.created_at.desc()).all()]


@router.get("/{file_id}/download")
def download(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = db.get(StoredFile, file_id)
    if not f:
        raise HTTPException(404, "File not found")
    if f.project_id:
        require_project(db, user, f.project_id, "view")
    elif f.category not in ("logo",) and user.role != "owner":
        raise HTTPException(403, "Not allowed")
    be = backend_for(f.storage_backend)
    headers = {"Content-Disposition": f"inline; filename*=UTF-8''{quote(f.original_name)}"}
    return StreamingResponse(be.stream(f.storage_key), media_type=f.content_type, headers=headers)


@router.post("/{file_id}/hide")
def hide_file(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """'Delete' from the user's view. The file and record are kept for history/restore."""
    if user.role != "owner":
        raise HTTPException(403, "Only the owner can delete – ask the owner")
    f = db.get(StoredFile, file_id)
    if not f:
        raise HTTPException(404, "File not found")
    if f.project_id:
        require_project(db, user, f.project_id, "edit")
    elif user.role != "owner":
        raise HTTPException(403, "Not allowed")
    f.is_hidden = True
    db.commit()
    log_action(db, user, "hidden", "file", f.id, f.original_name, project_id=f.project_id)
    return {"ok": True}
