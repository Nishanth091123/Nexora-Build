"""1.26 – Interior package + Electrical / Plumbing drawings from the project's active drawing.

GET  /api/projects/{pid}/interior            items, rates (suggested defaults, editable), totals
PUT  /api/projects/{pid}/interior            save edited rates / quantities / on-off (projects.site_data["interior"])
GET  /api/projects/{pid}/interior/pdf|excel
GET  /api/projects/{pid}/mep                 electrical + plumbing numbers and suggestions (JSON)
GET  /api/projects/{pid}/mep/pdf?kind=both|electrical|plumbing     and  /mep/dxf
"""
from __future__ import annotations

import copy
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..audit import log_action
from ..db import get_db
from ..design import interior as I
from ..design import mep as M
from ..models import User
from ..security import get_current_user
from .design import active_design, require_any

router = APIRouter(prefix="/api", tags=["fitout"])
MODS = ("design", "estimate", "view")


def _ctx(db: Session, user: User, pid: int):
    p = require_any(db, user, pid, MODS)
    d = active_design(db, p)
    if not d or not d.plan:
        raise HTTPException(422, {"message": "Save or upload a drawing first – the interior and the electrical / plumbing "
                                             "drawings are made from the project's active drawing.", "questions": []})
    proj = {"name": p.name, "code": p.code}
    return p, copy.deepcopy(d.plan), proj


def _saved(p) -> dict:
    return copy.deepcopy((p.site_data or {}).get("interior") or {})


@router.get("/projects/{pid}/interior")
def get_interior(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p, plan, _ = _ctx(db, user, pid)
    return I.compute(plan, _saved(p)) | {"saved": _saved(p)}


class InteriorIn(BaseModel):
    rates: dict[str, float | None] = {}
    qty: dict[str, float | None] = {}
    on: list[str] = []          # optional items switched ON
    off: list[str] = []         # standard items switched OFF
    loose_rates: dict[str, float | None] = {}


@router.put("/projects/{pid}/interior")
def save_interior(pid: int, body: InteriorIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p, plan, _ = _ctx(db, user, pid)
    bad = [k for k in body.rates if k not in I.RATES]
    if bad:
        raise HTTPException(400, f"Unknown rate: {', '.join(bad)}")
    for v in list(body.rates.values()) + list(body.qty.values()) + list(body.loose_rates.values()):
        if v is not None and (v < 0 or v > 1e8):
            raise HTTPException(400, "Rates and quantities must be positive numbers")
    sd = copy.deepcopy(p.site_data or {})
    sd["interior"] = {"rates": {k: v for k, v in body.rates.items() if v is not None}, "qty": {k: v for k, v in body.qty.items() if v is not None},
                      "on": body.on, "off": body.off, "loose_rates": {k: v for k, v in body.loose_rates.items() if v is not None}}
    p.site_data = sd
    flag_modified(p, "site_data")
    db.commit()
    log_action(db, user, "updated", "interior", p.id, "interior rates / quantities", project_id=p.id)
    return I.compute(plan, sd["interior"]) | {"saved": sd["interior"]}


def _file(data: bytes, mt: str, name: str):
    return Response(data, media_type=mt, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.get("/projects/{pid}/interior/pdf")
def interior_pdf(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p, plan, proj = _ctx(db, user, pid)
    return _file(I.to_pdf(plan, proj, I.compute(plan, _saved(p))), "application/pdf", f"{p.code}_Interior_Estimate.pdf")


@router.get("/projects/{pid}/interior/excel")
def interior_excel(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p, plan, proj = _ctx(db, user, pid)
    return _file(I.to_excel(plan, proj, I.compute(plan, _saved(p))),
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{p.code}_Interior_Estimate.xlsx")


@router.get("/projects/{pid}/mep")
def mep_json(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p, plan, _ = _ctx(db, user, pid)
    e, pl = M.electrical(plan), M.plumbing(plan)
    strip = lambda d: {k: v for k, v in d.items() if k != "floors"} | {  # noqa: E731
        "floors": [{k: v for k, v in f.items() if k not in ("rooms", "pipes", "fixtures", "stacks")} for f in d["floors"]]}
    return {"electrical": strip(e) | {"notes": M.electrical_notes(e, plan)}, "plumbing": strip(pl) | {"notes": M.plumbing_notes(pl, plan)}}


@router.get("/projects/{pid}/mep/pdf")
def mep_pdf(pid: int, kind: str = "both", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if kind not in ("both", "electrical", "plumbing"):
        raise HTTPException(400, "kind must be both, electrical or plumbing")
    p, plan, proj = _ctx(db, user, pid)
    tag = {"both": "Electrical_Plumbing", "electrical": "Electrical", "plumbing": "Plumbing"}[kind]
    return _file(M.to_pdf(plan, proj, kind), "application/pdf", f"{p.code}_{tag}_Layout.pdf")


@router.get("/projects/{pid}/mep/dxf")
def mep_dxf(pid: int, kind: str = "both", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if kind not in ("both", "electrical", "plumbing"):
        raise HTTPException(400, "kind must be both, electrical or plumbing")
    p, plan, proj = _ctx(db, user, pid)
    tag = {"both": "Electrical_Plumbing", "electrical": "Electrical", "plumbing": "Plumbing"}[kind]
    return _file(M.to_dxf(plan, proj, kind), "application/dxf", f"{p.code}_{tag}_Layout.dxf")
