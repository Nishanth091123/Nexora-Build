"""1.27.5 – owner's seal & signature for the letterhead PDFs.

The box on every PDF stays blank and labelled "Seal & Signature" until the OWNER uploads his own signature and switches
the stamp on. The stamp is: PROPRIETOR / (signature) / PRAGANYA CONSTRUCTION.
"""
from __future__ import annotations

import base64
import io

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import letterhead
from ..audit import log_action
from ..db import get_db
from ..models import AppSetting, User
from ..security import require_owner

router = APIRouter(prefix="/api", tags=["branding"])
KEY = "branding"


def load(db: Session) -> None:
    """Called at start-up and after every change: pushes the saved stamp into the letterhead module."""
    row = db.get(AppSetting, KEY)
    v = (row.value if row else None) or {}
    sig = base64.b64decode(v["sig"]) if v.get("sig") else None
    letterhead.configure(bool(v.get("on")), sig)


def _clean_signature(raw: bytes) -> bytes:
    """Photo of a signature on paper (white OR grey, uneven light) → transparent PNG, ≤ 600 px wide, dark-blue ink."""
    from PIL import Image, ImageChops, ImageFilter, ImageOps
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    if im.width > 900:
        im = im.resize((900, max(1, round(im.height * 900 / im.width))))
    gray = ImageOps.autocontrast(im.convert("L"), cutoff=0)
    # local paper brightness: shrink, take the brightest nearby pixels, blur, grow back (ink is thinner than the filter)
    sw, sh = max(8, gray.width // 6), max(8, gray.height // 6)
    bg = gray.resize((sw, sh), Image.BILINEAR).filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(3)).resize(gray.size, Image.BILINEAR)
    diff = ImageChops.subtract(bg, gray)                          # how much darker than the paper around it
    alpha = diff.point(lambda v: 0 if v < 18 else min(255, (v - 18) * 6))
    mx, my = int(alpha.width * 0.05), int(alpha.height * 0.05)      # photo edges are shadowy – never ink
    alpha.paste(0, (0, 0, alpha.width, my)); alpha.paste(0, (0, alpha.height - my, alpha.width, alpha.height))
    alpha.paste(0, (0, 0, mx, alpha.height)); alpha.paste(0, (alpha.width - mx, 0, alpha.width, alpha.height))
    bbox = alpha.point(lambda v: 255 if v > 90 else 0).getbbox()
    ink = Image.new("RGBA", gray.size, (24, 36, 110, 255))        # one dark-blue ink colour
    ink.putalpha(alpha)
    if bbox:
        pad = 6
        ink = ink.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(ink.width, bbox[2] + pad), min(ink.height, bbox[3] + pad)))
    if ink.width > 600:
        ink = ink.resize((600, max(1, round(ink.height * 600 / ink.width))), Image.LANCZOS)
    out = io.BytesIO()
    ink.save(out, "PNG")
    return out.getvalue()


def _svg(sig_b64: str | None) -> str:
    img = (f'<image href="data:image/png;base64,{sig_b64}" x="14" y="34" width="172" height="44" preserveAspectRatio="xMidYMid meet"/>'
           if sig_b64 else "")
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100" width="260">'
            '<rect x="2" y="2" width="196" height="96" rx="8" fill="#fff" stroke="#1E3A8A" stroke-width="2.4"/>'
            '<rect x="7" y="7" width="186" height="86" rx="5" fill="none" stroke="#1E3A8A" stroke-width="0.8"/>'
            '<text x="100" y="26" text-anchor="middle" font-family="Helvetica,Arial" font-weight="700" font-size="12" fill="#1E3A8A">PROPRIETOR</text>'
            f'{img}'
            '<text x="100" y="88" text-anchor="middle" font-family="Helvetica,Arial" font-weight="700" font-size="12" fill="#1E3A8A">PRAGANYA CONSTRUCTION</text></svg>')


def _state(db: Session) -> dict:
    row = db.get(AppSetting, KEY)
    v = (row.value if row else None) or {}
    return {"on": bool(v.get("on")), "has_signature": bool(v.get("sig")), "preview": _svg(v.get("sig"))}


@router.get("/branding")
def get_branding(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    return _state(db)


class SigIn(BaseModel):
    image: str   # base64 (or a data URL) of the signature photo


@router.put("/branding/signature")
def put_signature(body: SigIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    data = body.image.split(",", 1)[1] if body.image.startswith("data:") else body.image
    try:
        raw = base64.b64decode(data, validate=False)
    except Exception:
        raise HTTPException(422, "The image could not be read.")
    if len(raw) > 4_000_000:
        raise HTTPException(422, "Image too big – use a photo under 4 MB.")
    try:
        png = _clean_signature(raw)
    except Exception:
        raise HTTPException(422, "That file is not a readable image (use JPG or PNG).")
    row = db.get(AppSetting, KEY)
    if not row:
        row = AppSetting(key=KEY, value={})
        db.add(row)
    row.value = {**(row.value or {}), "sig": base64.b64encode(png).decode()}
    db.commit()
    load(db)
    log_action(db, owner, "updated", "settings", KEY, "signature image uploaded")
    return _state(db)


class OnIn(BaseModel):
    on: bool


@router.put("/branding/enabled")
def put_enabled(body: OnIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    row = db.get(AppSetting, KEY)
    if not row:
        row = AppSetting(key=KEY, value={})
        db.add(row)
    row.value = {**(row.value or {}), "on": bool(body.on)}
    db.commit()
    load(db)
    log_action(db, owner, "updated", "settings", KEY, f"seal & signature on PDFs {'ON' if body.on else 'OFF'}")
    return _state(db)


@router.delete("/branding/signature")
def delete_signature(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    row = db.get(AppSetting, KEY)
    if row:
        v = dict(row.value or {})
        v.pop("sig", None)
        row.value = v
        db.commit()
    load(db)
    log_action(db, owner, "updated", "settings", KEY, "signature image removed")
    return _state(db)
