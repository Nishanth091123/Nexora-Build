"""1.18 – Material Library (market brands): category → brand → variant → owner's rate.

Everyone with access sees the names; rupee rates only with Material Rates permission (same rule as the Rate Library).
The owner adds / edits brands and variants, tags brands A / B / C and imports shade / product lists from Excel / CSV.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..market import link, project_choices, tier_rates
from ..market_seed import CAT, CATEGORIES
from ..models import MarketBrand, MarketVariant, Project, User
from ..security import get_current_user, has_rates_access, require_owner, require_project, require_rates

router = APIRouter(prefix="/api", tags=["material-library"])


def brand_out(b: MarketBrand) -> dict:
    return {"id": b.id, "category": b.category, "name": b.name, "tier": b.tier or "", "is_default": b.is_default, "notes": b.notes}


def variant_out(v: MarketVariant, show_rate: bool) -> dict:
    code, factor = link(v)
    return {"id": v.id, "brand_id": v.brand_id, "category": v.category, "name": v.name, "code": v.code, "spec": v.spec or {},
            "color": v.color or "", "unit": v.unit, "rate": v.rate if show_rate else None,
            "gst_pct": v.gst_pct if show_rate else None, "rate_date": v.rate_date.isoformat() if v.rate_date and show_rate else None,
            "rate_code": code}


@router.get("/market")
def library(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    show = has_rates_access(db, user)
    brands = db.query(MarketBrand).filter(MarketBrand.is_hidden.is_(False)).order_by(MarketBrand.category, MarketBrand.name).all()
    ids = {b.id for b in brands}
    variants = [v for v in db.query(MarketVariant).filter(MarketVariant.is_hidden.is_(False)).order_by(MarketVariant.id).all()
                if v.brand_id in ids]
    tiers = tier_rates(db) if show else {}
    return {
        "categories": [{"key": k, "name": n, "stage": st, "unit": u, "rate_code": rc} for k, n, st, u, rc, _f in CATEGORIES],
        "brands": [brand_out(b) for b in brands],
        "variants": [variant_out(v, show) for v in variants],
        "tiers": tiers, "rates_locked": not show, "can_edit": user.role == "owner",
    }


class BrandIn(BaseModel):
    category: str
    name: str = Field(min_length=1, max_length=80)
    tier: str = ""
    is_default: bool = False
    notes: str = ""


def _brand_check(body: BrandIn) -> dict:
    if body.category not in CAT:
        raise HTTPException(400, "Unknown material category")
    d = body.model_dump()
    d["tier"] = d["tier"].upper()[:1] if d["tier"] and d["tier"].upper()[:1] in "ABC" else ""
    d["name"] = d["name"].strip()
    return d


def _one_default(db: Session, b: MarketBrand) -> None:
    if b.is_default:
        for o in db.query(MarketBrand).filter(MarketBrand.category == b.category, MarketBrand.id != b.id, MarketBrand.is_default.is_(True)).all():
            o.is_default = False


@router.post("/market/brands")
def add_brand(body: BrandIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    d = _brand_check(body)
    if db.query(MarketBrand).filter(MarketBrand.category == d["category"], MarketBrand.name.ilike(d["name"]), MarketBrand.is_hidden.is_(False)).first():
        raise HTTPException(409, f"{d['name']} is already in {CAT[d['category']][1]}")
    b = MarketBrand(created_by=owner.id, **d)
    db.add(b)
    db.flush()
    _one_default(db, b)
    db.commit()
    log_action(db, owner, "created", "market_brand", b.id, f"{b.name} ({b.category})")
    return brand_out(b)


@router.put("/market/brands/{bid}")
def edit_brand(bid: int, body: BrandIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    b = db.get(MarketBrand, bid)
    if not b or b.is_hidden:
        raise HTTPException(404, "Brand not found")
    d = _brand_check(body)
    for k in ("name", "tier", "is_default", "notes"):
        setattr(b, k, d[k])
    _one_default(db, b)
    db.commit()
    return brand_out(b)


class VariantIn(BaseModel):
    brand_id: int
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(default="", max_length=60)
    spec: dict = {}
    color: str = ""
    unit: str = Field(default="", max_length=20)
    rate: float | None = Field(default=None, ge=0)
    gst_pct: float | None = Field(default=None, ge=0, le=28)


def _variant_fields(body: VariantIn) -> dict:
    d = body.model_dump()
    if d["color"] and not re.fullmatch(r"#[0-9a-fA-F]{6}", d["color"]):
        raise HTTPException(400, "Colour must look like #a1b2c3")
    d["name"] = d["name"].strip()
    d["code"] = d["code"].strip()
    return d


@router.post("/market/variants")
def add_variant(body: VariantIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    b = db.get(MarketBrand, body.brand_id)
    if not b or b.is_hidden:
        raise HTTPException(404, "Brand not found")
    d = _variant_fields(body)
    v = MarketVariant(category=b.category, created_by=owner.id, rate_date=date.today() if d["rate"] is not None else None, **d)
    if not v.unit:
        v.unit = CAT[b.category][3]
    db.add(v)
    db.commit()
    log_action(db, owner, "created", "market_variant", v.id, f"{b.name} · {v.name}")
    return variant_out(v, True)


@router.put("/market/variants/{vid}")
def edit_variant(vid: int, body: VariantIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Owner edits everything; a user with Material Rates permission may change only the rate / GST."""
    v = db.get(MarketVariant, vid)
    if not v or v.is_hidden:
        raise HTTPException(404, "Item not found")
    d = _variant_fields(body)
    if user.role != "owner":
        require_rates(db, user)
        d = {"rate": d["rate"], "gst_pct": d["gst_pct"]}
    else:
        d.pop("brand_id", None)
    if "rate" in d and d["rate"] != v.rate:
        v.rate_date = date.today() if d["rate"] is not None else None
    for k, val in d.items():
        setattr(v, k, val)
    db.commit()
    return variant_out(v, True)


class RateIn(BaseModel):
    rate: float | None = Field(default=None, ge=0)
    gst_pct: float | None = Field(default=None, ge=0, le=28)


@router.put("/market/variants/{vid}/rate")
def set_rate(vid: int, body: RateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_rates(db, user)
    v = db.get(MarketVariant, vid)
    if not v or v.is_hidden:
        raise HTTPException(404, "Item not found")
    if body.rate != v.rate:
        v.rate_date = date.today() if body.rate is not None else None
    v.rate = body.rate
    if body.gst_pct is not None:
        v.gst_pct = body.gst_pct
    db.commit()
    return variant_out(v, True)


# ---------------------------------------------------------------- import / template
TEMPLATE_HEAD = ["category", "brand", "name", "code", "colour", "unit", "rate", "gst_pct"]


@router.get("/market/template.csv")
def template(user: User = Depends(get_current_user)):
    rows = [TEMPLATE_HEAD,
            ["paint_interior", "Asian Paints", "Shade name as on the shade card", "0951", "#efe3cf", "litre", "", "18"],
            ["floor_tiles", "Kajaria", "600x600 GVT – design name", "K-1234", "#d8d2c6", "sq ft", "", "18"],
            ["cement", "Ramco", "PPC", "", "", "bag", "", "28"]]
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    cats = "; ".join(f"{k} = {n}" for k, n, *_ in CATEGORIES)
    buf.write(f"# category keys: {cats}\n")
    return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="Material_Library_Import_Template.csv"'})


def _rows_from_upload(name: str, data: bytes) -> list[dict]:
    if name.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(data), read_only=True, data_only=True).active
        it = ws.iter_rows(values_only=True)
        head = [str(h or "").strip().lower() for h in next(it, [])]
        return [{head[i]: ("" if c is None else str(c)).strip() for i, c in enumerate(r) if i < len(head)} for r in it]
    text = data.decode("utf-8-sig", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    rd = csv.DictReader(lines)
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in rd]


@router.post("/market/import")
async def import_list(file: UploadFile = File(...), owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 5 MB)")
    try:
        rows = _rows_from_upload(file.filename or "", data)
    except Exception as e:
        raise HTTPException(400, f"Could not read the file: {e}")
    alias = {n.lower(): k for k, n, *_ in CATEGORIES}
    added_b = added_v = updated = 0
    skipped: list[str] = []
    for i, r in enumerate(rows, start=2):
        cat = (r.get("category") or "").strip()
        cat = cat if cat in CAT else alias.get(cat.lower(), "")
        brand, name = r.get("brand", ""), r.get("name", "") or r.get("shade", "") or r.get("product", "")
        if not cat or not brand or not name:
            if any(r.values()):
                skipped.append(f"row {i}: category / brand / name missing")
            continue
        b = db.query(MarketBrand).filter(MarketBrand.category == cat, MarketBrand.name.ilike(brand), MarketBrand.is_hidden.is_(False)).first()
        if not b:
            b = MarketBrand(category=cat, name=brand[:80], created_by=owner.id)
            db.add(b)
            db.flush()
            added_b += 1
        code = (r.get("code") or "")[:60]
        col = r.get("colour") or r.get("color") or ""
        if col and not col.startswith("#"):
            col = "#" + col
        if col and not re.fullmatch(r"#[0-9a-fA-F]{6}", col):
            skipped.append(f"row {i}: colour '{col}' ignored (use #a1b2c3)")
            col = ""
        rate = r.get("rate") or ""
        try:
            rate_v = float(rate.replace(",", "")) if rate else None
        except ValueError:
            rate_v = None
            skipped.append(f"row {i}: rate '{rate}' is not a number")
        gst = r.get("gst_pct") or r.get("gst") or ""
        try:
            gst_v = float(gst) if gst else None
        except ValueError:
            gst_v = None
        q = db.query(MarketVariant).filter(MarketVariant.brand_id == b.id, MarketVariant.is_hidden.is_(False))
        v = q.filter(MarketVariant.code == code).first() if code else q.filter(MarketVariant.name.ilike(name)).first()
        if v:
            v.name = name[:120]
            if col:
                v.color = col
            if rate_v is not None and rate_v != v.rate:
                v.rate, v.rate_date = rate_v, date.today()
            if gst_v is not None:
                v.gst_pct = gst_v
            if r.get("unit"):
                v.unit = r["unit"][:20]
            updated += 1
        else:
            db.add(MarketVariant(brand_id=b.id, category=cat, name=name[:120], code=code, color=col, unit=(r.get("unit") or CAT[cat][3])[:20],
                                 rate=rate_v, gst_pct=gst_v, rate_date=date.today() if rate_v is not None else None, created_by=owner.id))
            added_v += 1
    db.commit()
    log_action(db, owner, "imported", "market_variant", None, f"{added_v} new, {updated} updated, {added_b} new brands")
    return {"added_brands": added_b, "added": added_v, "updated": updated, "skipped": skipped[:30]}


# ---------------------------------------------------------------- project brand choices
@router.get("/projects/{project_id}/brand-choices")
def get_choices(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_project(db, user, project_id, "view")
    out = project_choices(db, project_id) if has_rates_access(db, user) else {}
    return {"choices": p.brand_choices or {}, "applied": out}


class ChoiceIn(BaseModel):
    category: str
    variant_id: int | None = None


@router.put("/projects/{project_id}/brand-choices")
def set_choice(project_id: int, body: ChoiceIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """One choice per estimate item: e.g. cement, M-sand and P-sand, main door and toilet door can each have their own.
    The key is the estimate rate code the variant feeds (or its category when it feeds none)."""
    p = require_project(db, user, project_id, "estimate")
    ch = dict(p.brand_choices or {})
    if body.variant_id:
        v = db.get(MarketVariant, body.variant_id)
        if not v or v.is_hidden:
            raise HTTPException(404, "Item not found")
        key = link(v)[0] or v.category
        ch[key] = v.id
    else:
        ch.pop(body.category[:40], None)
    p.brand_choices = ch
    db.commit()
    return {"choices": ch}
