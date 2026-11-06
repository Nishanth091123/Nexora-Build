"""1.15 – Part 7: Material Library.
Built-in colours / materials live in the screens (frontend). Here: the owner's OWN items – any colour with a brand
shade code, or a photo of a tile / granite / stone / wood (uploaded, or taken from a web page link) that the 3D view
then lays on walls and floors."""
import re
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..models import LibraryItem, User
from ..security import get_current_user, has_rates_access, require_owner
from .files import read_and_check, store

router = APIRouter(prefix="/api/materials", tags=["materials"])

CATEGORIES = {"paint": "Paint colour", "cladding": "Cladding (stone / wood / tiles)", "flooring": "Flooring",
              "wall_tile": "Wall tiles", "roof": "Terrace / roof finish", "door": "Door", "frame": "Window frame",
              "counter": "Kitchen counter top", "plinth": "Plinth"}
FINISHES = ("matt", "satin", "gloss")
IMG_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MAX_IMG = 8 * 1024 * 1024


def item_out(i: LibraryItem) -> dict:
    return {"id": i.id, "ref": f"c:{i.id}", "category": i.category, "name": i.name, "brand": i.brand, "code": i.code,
            "color": i.color, "image_url": f"/api/files/{i.image_file_id}/download" if i.image_file_id else None,
            "tile_ft": i.tile_ft, "finish": i.finish, "rate": i.rate, "unit": i.unit, "source_url": i.source_url,
            "notes": i.notes, "created_at": i.created_at.isoformat()}


class ItemIn(BaseModel):
    category: str
    name: str = Field(min_length=1, max_length=120)
    brand: str = Field(default="", max_length=80)
    code: str = Field(default="", max_length=60)
    color: str = "#cccccc"
    tile_ft: float = Field(default=2.0, gt=0.1, le=40)
    finish: str = "matt"
    rate: float | None = Field(default=None, ge=0)
    unit: str = Field(default="", max_length=20)
    source_url: str = Field(default="", max_length=500)
    notes: str = ""


def _check(body: ItemIn) -> dict:
    if body.category not in CATEGORIES:
        raise HTTPException(400, f"category must be one of {', '.join(CATEGORIES)}")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", body.color or ""):
        raise HTTPException(400, "Colour must look like #a1b2c3")
    d = body.model_dump()
    d["finish"] = d["finish"] if d["finish"] in FINISHES else "matt"
    d["name"] = d["name"].strip()
    return d


@router.get("")
def list_items(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(LibraryItem).filter(LibraryItem.is_hidden.is_(False)).order_by(LibraryItem.category, LibraryItem.name).all()
    items = [item_out(i) for i in rows]
    if not has_rates_access(db, user):  # 1.16: rates of own items only with Material Rates permission
        for it in items:
            it["rate"] = None
    return {"items": items, "categories": CATEGORIES, "rates_locked": not has_rates_access(db, user)}


@router.post("")
def add_item(body: ItemIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    i = LibraryItem(created_by=owner.id, **_check(body))
    db.add(i)
    db.commit()
    log_action(db, owner, "created", "library_item", i.id, f"{i.name} ({i.category})")
    return item_out(i)


@router.put("/{iid}")
def edit_item(iid: int, body: ItemIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    i = db.get(LibraryItem, iid)
    if not i or i.is_hidden:
        raise HTTPException(404, "Item not found")
    for k, v in _check(body).items():
        setattr(i, k, v)
    db.commit()
    return item_out(i)


@router.post("/{iid}/image")
async def upload_image(iid: int, file: UploadFile = File(...), owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    i = db.get(LibraryItem, iid)
    if not i or i.is_hidden:
        raise HTTPException(404, "Item not found")
    name, data, ctype = await read_and_check(file)
    if ctype not in IMG_TYPES:
        raise HTTPException(415, "Use a photo: JPG, PNG or WEBP")
    f = store(db, owner, name, data, ctype, "material_lib", None)
    i.image_file_id = f.id
    db.commit()
    return item_out(i)


class UrlIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)


@router.post("/{iid}/image-from-url")
def image_from_url(iid: int, body: UrlIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    """Take the photo from a web link (e.g. a tile on a shop's website). Only a direct image link works –
    for a web page, save the picture and upload it instead."""
    i = db.get(LibraryItem, iid)
    if not i or i.is_hidden:
        raise HTTPException(404, "Item not found")
    u = urlparse(body.url.strip())
    if u.scheme not in ("http", "https") or not u.netloc or u.hostname in ("localhost", "127.0.0.1") or (u.hostname or "").startswith(("10.", "192.168.", "169.254.")):
        raise HTTPException(400, "Give a normal https:// link to a picture")
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": "NexoraBuild/1.17 (material library)"}) as c:
            r = c.get(body.url.strip())
    except Exception as e:
        raise HTTPException(400, f"Could not open the link ({type(e).__name__}). Save the picture and upload it instead.")
    ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
    if r.status_code != 200 or ctype not in IMG_TYPES:
        raise HTTPException(400, "That link is a web page, not a picture. Right-click the picture → 'Copy image address' "
                                 "and paste that, or save the picture and upload it.")
    if len(r.content) > MAX_IMG:
        raise HTTPException(413, "Picture too large (max 8 MB)")
    f = store(db, owner, f"library_{i.id}{IMG_TYPES[ctype]}", r.content, ctype, "material_lib", None)
    i.image_file_id = f.id
    i.source_url = body.url.strip()[:500]
    db.commit()
    return item_out(i)
