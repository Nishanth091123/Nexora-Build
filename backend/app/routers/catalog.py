"""1.27 – Design catalog: elevation styles (1,600) and interior designs (636) with pictures.

GET  /api/projects/{pid}/catalog/elevation?family=&palette=&top=&clad=&win=&page=&size=   styles drawn on THIS project's proportions
GET  /api/projects/{pid}/catalog/elevation/{id}/svg                                      one large picture
POST /api/projects/{pid}/catalog/elevation/{id}/apply                                    writes the style into the drawing (new saved version)
GET  /api/projects/{pid}/catalog/interior?type=&scheme=&tier=&sub=&page=&size=           interior designs (wardrobe, TV unit, kitchen, pooja, ceiling)
GET  /api/projects/{pid}/catalog/interior/{id}/svg
PUT  /api/projects/{pid}/catalog/interior/picks                                          {"picks": {"<roomid>|<key>": "I0001" | null}}
GET  /api/catalog/facets
"""
from __future__ import annotations

import copy

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..audit import log_action
from ..db import get_db
from ..design import catalog as C
from ..models import Design, User
from ..security import get_current_user
from .design import SaveIn, active_design, require_any, save_design

router = APIRouter(prefix="/api", tags=["catalog"])
MODS = ("design", "estimate", "view")


def _plan(db: Session, user: User, pid: int, need: tuple = MODS):
    p = require_any(db, user, pid, need)
    d = active_design(db, p)
    return p, d


def _shape(plan: dict | None) -> tuple[float, int]:
    if not plan:
        return 30.0, 2
    b = plan.get("building") or {}
    return float(b.get("w") or 30), max(1, len(plan.get("levels") or [1, 2]))


def _has_stair(plan: dict | None) -> bool:
    return bool(plan) and any(r.get("type") == "stair" for lv in plan.get("levels", []) for r in lv.get("rooms", []))


@router.get("/catalog/facets")
def facets(user: User = Depends(get_current_user)):
    return {"elevation": C.elevation_facets(), "interior": C.interior_facets()}


@router.get("/projects/{pid}/catalog/elevation")
def elevation(pid: int, family: str = "", palette: str = "", top: str = "", clad: str = "", win: str = "", page: int = 1, size: int = 24,
              fit: bool = True, feature: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p, d = _plan(db, user, pid)
    bw, n = _shape(d.plan if d else None)
    grp = ("G" if n == 1 else "G+") if (fit and d) else ""   # 1.27.4: only styles made for this many floors (switchable)
    res = C.elevation_list(family, palette, top, clad, win, page, size, grp, feature)
    stair = _has_stair(d.plan if d else None)
    for it in res["items"]:
        it["svg"] = C.draw_elevation(it, bw, n, 0.5, stair).svg(360)
    cur = (d.plan or {}).get("elev") if d else None
    return res | {"current": cur, "has_drawing": bool(d), "floors": n, "width_ft": bw, "fit": bool(grp), "group": grp or None}


@router.get("/projects/{pid}/catalog/elevation/{eid}/svg")
def elevation_svg(pid: int, eid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p, d = _plan(db, user, pid)
    e = C.elevation_get(eid)
    if not e:
        raise HTTPException(404, "Unknown elevation style")
    bw, n = _shape(d.plan if d else None)
    return {"svg": C.draw_elevation(e, bw, n, 0.5, _has_stair(d.plan if d else None)).svg(900), "item": e, "prompt": C.elevation_prompt(e)}


@router.post("/projects/{pid}/catalog/elevation/{eid}/apply")
def elevation_apply(pid: int, eid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = require_any(db, user, pid, ("design",))
    d = active_design(db, p)
    if not d or not d.plan:
        raise HTTPException(422, {"message": "Save or upload a drawing first – the elevation style is applied to the active drawing.", "questions": []})
    plan = copy.deepcopy(d.plan)
    try:
        res = C.elevation_apply(plan, eid)
    except ValueError as e:
        raise HTTPException(404, str(e))
    out = save_design(pid, SaveIn(plan=plan, title=f"{d.title} + {res['elevation']['family'].title()} elevation", prompt=d.prompt or "",
                                  source="edited", spec_level=d.spec_level or "standard", parent_id=d.id), user, db)
    log_action(db, user, "updated", "elevation", p.id, f"elevation style {eid} applied ({res['elevation']['name']})", project_id=p.id)
    return {"design_id": out.get("id"), "version": out.get("version"), "elevation": res["elevation"], "notes": res["notes"]}


@router.get("/projects/{pid}/catalog/interior")
def interior(pid: int, type: str = "", scheme: str = "", tier: str = "", sub: str = "", page: int = 1, size: int = 24,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p, d = _plan(db, user, pid)
    res = C.interior_list(type, scheme, tier, sub, page, size)
    for it in res["items"]:
        it["svg"] = C.draw_interior(it).svg(360)
    rooms = []
    if d and d.plan:
        for li, lv in enumerate(d.plan["levels"]):
            for r in lv["rooms"]:
                for t, kinds in C.ROOM_FOR.items():
                    if r["type"] in kinds:
                        rooms.append({"id": f"{li}:{r['id']}", "name": r["name"], "floor": lv["name"], "type": t, "room_type": r["type"]})
    picks = ((p.site_data or {}).get("interior") or {}).get("picks") or {}
    return res | {"rooms": rooms, "picks": picks, "has_drawing": bool(d)}


@router.get("/projects/{pid}/catalog/interior/{did}/svg")
def interior_svg(pid: int, did: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _plan(db, user, pid)
    x = C.interior_get(did)
    if not x:
        raise HTTPException(404, "Unknown design")
    return {"svg": C.draw_interior(x).svg(800), "item": x, "prompt": C.interior_prompt(x)}


class PicksIn(BaseModel):
    picks: dict[str, str | None] = {}


@router.put("/projects/{pid}/catalog/interior/picks")
def save_picks(pid: int, body: PicksIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p, d = _plan(db, user, pid, ("design", "estimate"))
    if not d:
        raise HTTPException(422, {"message": "Save or upload a drawing first.", "questions": []})
    ids = {f"{li}:{r['id']}" for li, lv in enumerate(d.plan["levels"]) for r in lv["rooms"]}
    sd = copy.deepcopy(p.site_data or {})
    it = dict(sd.get("interior") or {})
    cur = dict(it.get("picks") or {})
    for k, v in body.picks.items():
        rid, _, key = k.partition("|")
        if rid not in ids or key not in C.TYPES:
            raise HTTPException(400, f"Unknown room / item: {k}")
        if v is None:
            cur.pop(k, None)
            continue
        x = C.interior_get(v)
        if not x or x["type"] != key:
            raise HTTPException(400, f"Design {v} does not fit {key}")
        cur[k] = v
    it["picks"] = cur
    sd["interior"] = it
    p.site_data = sd
    flag_modified(p, "site_data")
    db.commit()
    log_action(db, user, "updated", "interior", p.id, "interior design picks", project_id=p.id)
    return {"picks": cur}
