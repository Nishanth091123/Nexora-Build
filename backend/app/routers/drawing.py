"""Phase 4 – drawing upload analysis: DXF / vector PDF / image (AI vision) → confirmed rooms → design."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit import log_action
from ..db import get_db
from ..drawing import convert, dxf_reader, pdf_reader, vision
from ..estimate.rates_seed import DEFAULT_STATE
from ..llm import LLMError
from ..models import Design, DrawingAnalysis, StoredFile, User
from ..security import get_current_user
from ..storage import backend_for
from .design import design_summary, quick_estimate, require_any
from .files import read_and_check, store

router = APIRouter(prefix="/api", tags=["drawing"])
MODS = ("design", "vastu", "estimate")


def analysis_out(a: DrawingAnalysis, full: bool = True) -> dict:
    d = {"id": a.id, "project_id": a.project_id, "file_id": a.file_id, "file_name": a.file_name, "method": a.method,
         "model": a.model, "status": a.status, "design_id": a.design_id, "created_at": a.created_at.isoformat(),
         "rooms": len((a.result or {}).get("rooms", []))}
    if full:
        ext = a.extraction or {}
        d["result"] = a.result
        d["questions"] = ext.get("questions", [])
        d["warnings"] = ext.get("warnings", [])
        d["info"] = {k: ext.get(k) for k in ("units", "units_from_file", "scale_source", "stats", "info", "texts", "reason")}
    return d


def run_analysis(f: StoredFile, data: bytes, page: int = 0) -> tuple[str, str, dict, dict]:
    """Returns (method, model, extraction, result)."""
    name = f.original_name.lower()
    if name.endswith(".dxf"):
        try:
            ext = dxf_reader.parse(data)
        except dxf_reader.DxfError as e:
            raise HTTPException(422, {"message": str(e), "questions": [str(e)]})
        res = convert.rooms_from_raw(ext)
        if not res["rooms"]:
            ext["questions"].append("No room names were found inside closed areas. Check that the room labels are TEXT / "
                                    "MTEXT (not exploded) and the walls are lines / polylines.")
        return "dxf", "", ext, res
    if name.endswith(".pdf"):
        try:
            ext = pdf_reader.parse(data, page)
        except pdf_reader.PdfError as e:
            raise HTTPException(422, {"message": str(e), "questions": [str(e)]})
        if ext.get("vector_ok"):
            res = convert.rooms_from_raw(ext)
            if len([r for r in res["rooms"] if r["placed"]]) >= 2:
                return "pdf", "", ext, res
        info = ext.get("info", {})
        try:
            v = vision.read_plan(data, "application/pdf", (info.get("page_w", 842), info.get("page_h", 595)),
                                 image_fallback=pdf_reader.largest_image(data, page))
        except LLMError as e:
            raise HTTPException(422, {"message": "This PDF has no readable lines / text and the AI reader failed.",
                                      "questions": [str(e)[:300], "Upload a DXF (best) or a clear JPG/PNG of the plan."]})
        res = convert.rooms_from_vision(v["data"], v["img_w"], v["img_h"])
        ext2 = {"method": "pdf-vision", "questions": [], "warnings": [], "info": info, "vision": v["data"],
                "reason": ext.get("reason", "")}
        return "pdf-vision", v["model"], ext2, res
    if any(name.endswith(e) for e in (".png", ".jpg", ".jpeg", ".webp")):
        try:
            v = vision.read_plan(data, f.content_type)
        except LLMError as e:
            raise HTTPException(422, {"message": "The AI reader could not read this picture.",
                                      "questions": [str(e)[:300], "Try a clearer, straight photo / scan, or upload DXF."]})
        res = convert.rooms_from_vision(v["data"], v["img_w"], v["img_h"])
        return "image-vision", v["model"], {"method": "image-vision", "questions": [], "warnings": [],
                                            "vision": v["data"], "img": [v["img_w"], v["img_h"]]}, res
    raise HTTPException(415, "Only DXF, PDF, PNG, JPG drawings can be analysed. (DWG: save as DXF 2018 first.)")


def _finish(db: Session, user: User, f: StoredFile, page: int) -> dict:
    data = backend_for(f.storage_backend).read(f.storage_key)
    method, model, ext, res = run_analysis(f, data, page)
    qs = list(ext.get("questions", []))
    if not any(r["placed"] for r in res["rooms"]):
        qs.append("No room could be placed automatically – add / place the rooms in the table or the 2D editor.")
    if any(r.get("confidence", 1) < 0.6 for r in res["rooms"]):
        qs.append("Rows marked in amber were read with low confidence – please check their names and sizes.")
    qs.append("Confirm the north direction (north arrow) and which side the road is on.")
    ext["questions"] = qs
    a = DrawingAnalysis(project_id=f.project_id, file_id=f.id, file_name=f.original_name, method=method, model=model,
                        extraction=ext, result=res, created_by=user.id)
    db.add(a)
    db.commit()
    log_action(db, user, "analysed", "drawing", a.id, f"{f.original_name}: {len(res['rooms'])} rooms ({method})",
               project_id=f.project_id)
    return analysis_out(a)


@router.post("/projects/{project_id}/drawings/upload")
async def upload_and_analyse(project_id: int, file: UploadFile = File(...), page: int = Form(0),
                             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_any(db, user, project_id, MODS)
    name, data, ctype = await read_and_check(file)
    if not any(name.lower().endswith(e) for e in (".dxf", ".pdf", ".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(415, "Drawings must be DXF, PDF, PNG or JPG. (DWG: save as DXF 2018 first.)")
    f = store(db, user, name, data, ctype, "drawing", project_id)
    log_action(db, user, "uploaded", "file", f.id, f"{name} (v{f.version}, drawing)", project_id=project_id)
    return await run_in_threadpool(_finish, db, user, f, page)


@router.post("/files/{file_id}/analyse")
def analyse_existing(file_id: int, page: int = 0, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = db.get(StoredFile, file_id)
    if not f or not f.project_id:
        raise HTTPException(404, "File not found")
    require_any(db, user, f.project_id, MODS)
    return _finish(db, user, f, page)


@router.get("/projects/{project_id}/analyses")
def list_analyses(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_any(db, user, project_id, MODS)
    rows = (db.query(DrawingAnalysis).filter(DrawingAnalysis.project_id == project_id, DrawingAnalysis.is_hidden.is_(False))
            .order_by(DrawingAnalysis.id.desc()).limit(50).all())
    return [analysis_out(a, full=False) for a in rows]


def load(db: Session, user: User, aid: int) -> DrawingAnalysis:
    a = db.get(DrawingAnalysis, aid)
    if not a:
        raise HTTPException(404, "Analysis not found")
    require_any(db, user, a.project_id, MODS)
    return a


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return analysis_out(load(db, user, analysis_id))


class RescaleIn(BaseModel):
    units: str | None = None             # DXF: mm / cm / m / ft / in
    building_width_ft: float | None = None  # PDF / any: known overall width of the first floor drawing


@router.post("/analyses/{analysis_id}/rescale")
def rescale(analysis_id: int, body: RescaleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = load(db, user, analysis_id)
    ext = a.extraction or {}
    if a.method not in ("dxf", "pdf"):
        raise HTTPException(400, "Re-scaling works for DXF / vector PDF. For pictures, edit the sizes in the table.")
    scale = None
    if body.building_width_ft:
        raw = [r for r in ext.get("rooms_raw", [])]
        if not raw:
            raise HTTPException(400, "No rooms to measure")
        res0 = convert.rooms_from_raw(ext, scale=1.0)
        g0 = [r for r in res0["rooms"] if r["placed"] and r.get("group", 0) == 0]
        width_units = (max(r["x"] + r["w"] for r in g0) - min(r["x"] for r in g0)) if g0 else 0
        if width_units <= 0:
            raise HTTPException(400, "Could not measure the drawing width")
        scale = body.building_width_ft / width_units
    if body.units and body.units not in ("mm", "cm", "m", "ft", "in"):
        raise HTTPException(400, "units must be mm, cm, m, ft or in")
    res = convert.rooms_from_raw(ext, units=body.units, scale=scale)
    a.result = res
    if body.units:
        a.extraction = {**ext, "units": body.units, "units_from_file": True,
                        "questions": [q for q in ext.get("questions", []) if "units" not in q]}
    if scale:
        a.extraction = {**(a.extraction or ext), "scale_ft_per_unit": scale, "scale_source": "your known width",
                        "questions": [q for q in (a.extraction or ext).get("questions", []) if "scale" not in q]}
    db.commit()
    return analysis_out(a)


class ConfirmIn(BaseModel):
    levels: list[dict]        # [{"name": "Ground Floor", "rooms": [...]}]
    opts: dict = {}           # north_deg, road_side, plot_w_ft, plot_d_ft, road_width_m, front_gap_ft, left_gap_ft, floor_height_ft
    title: str = ""
    append_to_design_id: int | None = None
    state: str = DEFAULT_STATE


def _plan_from(body: ConfirmIn) -> dict:
    if body.opts.get("north_deg") in (None, ""):
        raise HTTPException(422, {"message": "Please confirm the north direction", "questions": ["North direction"]})
    try:
        return convert.build_plan(body.levels, body.opts)
    except ValueError as e:
        raise HTTPException(422, {"message": str(e), "questions": [str(e)]})


@router.post("/analyses/{analysis_id}/preview")
def preview(analysis_id: int, body: ConfirmIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    load(db, user, analysis_id)
    return _plan_from(body)


@router.post("/analyses/{analysis_id}/confirm")
def confirm(analysis_id: int, body: ConfirmIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = load(db, user, analysis_id)
    require_any(db, user, a.project_id, ("design", "vastu"))
    plan = _plan_from(body)
    parent = None
    if body.append_to_design_id:
        parent = db.get(Design, body.append_to_design_id)
        if not parent or parent.project_id != a.project_id:
            raise HTTPException(404, "Design to add the floor to was not found")
        import copy
        base = copy.deepcopy(parent.plan)
        for lv in plan["levels"]:
            one = {**plan, "levels": [lv]}
            base = convert.append_level(base, one)
        plan = base
    q = quick_estimate(db, plan, "standard", body.state)
    ver = (db.query(func.max(Design.version)).filter(Design.project_id == a.project_id).scalar() or 0) + 1
    t = q["totals"]
    d = Design(project_id=a.project_id, version=ver, title=body.title.strip() or f"From drawing {a.file_name}"[:160],
               prompt=f"Uploaded drawing: {a.file_name}", source="upload", plan=plan, summary=plan["summary"],
               spec_level="standard", rate_state=q["rates_state"], estimate_total=t["grand_total"],
               cost_per_sqft=t["cost_per_sqft"], builtup_sqft=t["builtup_sqft"],
               parent_id=parent.id if parent else None, created_by=user.id)
    db.add(d)
    db.commit()
    a.status = "confirmed"
    a.design_id = d.id
    db.commit()
    log_action(db, user, "confirmed", "drawing", a.id, f"{a.file_name} → design v{ver}", project_id=a.project_id)
    return design_summary(d) | {"plan": plan, "estimate": q}


@router.post("/analyses/{analysis_id}/hide")
def hide_analysis(analysis_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "owner":
        raise HTTPException(403, "Only the owner can delete – ask the owner")
    a = load(db, user, analysis_id)
    a.is_hidden = True
    db.commit()
    return {"ok": True}
