"""Phase 6 – AI Assistant API: conversations, chat, voice, document Q&A, calculators, knowledge, material guide."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import llm
from ..ai import calc, docs, knowledge, orchestrator
from ..audit import log_action
from ..config import DEFAULT_STATE
from ..db import get_db
from ..models import AIConversation, AIMessage, Project, StoredFile, User
from ..security import get_current_user, project_permissions
from .estimate import rates_for
from .files import file_out, read_and_check, store

router = APIRouter(prefix="/api/ai", tags=["ai"])
DRAWING_EXT = (".dxf", ".png", ".jpg", ".jpeg", ".webp")


# ------------------------------------------------------------------ access
def project_ctx(db: Session, user: User, project_id: int | None) -> tuple[Project | None, dict | None]:
    if not project_id:
        return None, None
    p = db.get(Project, project_id)
    if not p or p.is_hidden:
        raise HTTPException(404, "Project not found")
    perms = project_permissions(db, user, p)
    if not perms.get("ai"):
        raise HTTPException(403, "You don't have AI Assistant access on this project – ask the owner.")
    return p, perms


def own_conv(db: Session, user: User, cid: int) -> AIConversation:
    c = db.get(AIConversation, cid)
    if not c or c.user_id != user.id or c.is_hidden:
        raise HTTPException(404, "Conversation not found")
    return c


def conv_out(c: AIConversation, last: AIMessage | None = None) -> dict:
    return {"id": c.id, "project_id": c.project_id, "title": c.title, "agent": c.agent, "is_pinned": c.is_pinned,
            "created_at": c.created_at.isoformat(), "updated_at": (c.updated_at or c.created_at).isoformat(),
            "preview": (last.content[:120] if last else ""),
            "pending": bool((c.state or {}).get("pending"))}


def msg_out(m: AIMessage, files: dict | None = None) -> dict:
    cards = [c for c in (m.cards or []) if c.get("type") not in ("chips", "notes")]
    meta = {c["type"]: c.get("items", []) for c in (m.cards or []) if c.get("type") in ("chips", "notes")}
    att = None
    if m.attachment_file_id:
        f = (files or {}).get(m.attachment_file_id)
        att = {"id": m.attachment_file_id, "name": f.original_name if f else "attachment",
               "url": f"/api/files/{m.attachment_file_id}/download"}
    return {"id": m.id, "conversation_id": m.conversation_id, "role": m.role, "content": m.content, "cards": cards,
            "sources": m.sources or [], "tool": m.tool, "provider": m.provider, "language": m.language,
            "feedback": m.feedback, "chips": meta.get("chips", []), "notes": meta.get("notes", []),
            "attachment": att, "created_at": m.created_at.isoformat()}


# ------------------------------------------------------------------ meta
@router.get("/status")
def status(test: bool = False, user: User = Depends(get_current_user)):
    """test=true: send a tiny question to each provider and report which ones answer (keys are never shown)."""
    k = llm.keys()
    out = {"providers": {name: bool(v) for name, v in k.items()}, "any": any(k.values()),
           "voice": bool(k["groq"] or k["gemini"]), "embeddings": bool(k["gemini"])}
    if test:
        res = {}
        for name in ("gemini", "groq", "openrouter"):
            if not k[name]:
                res[name] = "no key"
                continue
            try:
                txt, prov = llm.ask("Reply with the words: Nexora ready", want_json=False, order=[name], min_chars=5, strict=True)
                res[name] = f"OK ({prov})" if prov.startswith(name) else f"failed (answered by {prov})"
            except Exception as e:
                res[name] = "failed: " + str(e).replace("All AI providers failed: ", "")[:220]
        out["test"] = res
    return out


@router.get("/meta")
def meta(project_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p, _ = project_ctx(db, user, project_id) if project_id else (None, None)
    state = p.state if p and p.state else DEFAULT_STATE
    used, _, rows = rates_for(db, state)
    rates = {r.code: {"name": r.name, "unit": r.unit, "basic": r.basic, "standard": r.standard, "premium": r.premium}
             for r in rows if r.is_active}
    guide = []
    for g in knowledge.MATERIAL_GUIDE:
        guide.append({**g, "rate": rates.get(g["rate_code"]) if g.get("rate_code") else None})
    kb = [{k: e[k] for k in ("id", "category", "title", "title_ta", "source")} for e in knowledge.entries()]
    return {"agents": [{"key": k, "name": v[0], "name_ta": v[1], "desc": v[2]} for k, v in orchestrator.AGENTS.items()],
            "calculators": calc.catalog(), "material_guide": guide, "rates_state": used, "kb": kb}


@router.get("/kb")
def kb(category: str = "", q: str = "", user: User = Depends(get_current_user)):
    from ..ai.tools import kb_search
    if q.strip():
        return kb_search(q, k=8, category=category or None)
    return [e for e in knowledge.entries() if not category or e["category"] == category]


class CalcIn(BaseModel):
    kind: str
    params: dict = {}


@router.post("/calc")
def run_calc(body: CalcIn, user: User = Depends(get_current_user)):
    try:
        return calc.run(body.kind, body.params)
    except calc.CalcError as e:
        raise HTTPException(422, str(e))


# ------------------------------------------------------------------ conversations
@router.get("/conversations")
def list_conversations(project_id: int | None = None, limit: int = 30, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    q = db.query(AIConversation).filter(AIConversation.user_id == user.id, AIConversation.is_hidden.is_(False))
    if project_id:
        q = q.filter((AIConversation.project_id == project_id) | (AIConversation.project_id.is_(None)))
    rows = q.order_by(AIConversation.is_pinned.desc(), AIConversation.updated_at.desc()).limit(min(limit, 200)).all()
    ids = [c.id for c in rows]
    last_ids = dict(db.query(AIMessage.conversation_id, func.max(AIMessage.id))
                    .filter(AIMessage.conversation_id.in_(ids or [-1]), AIMessage.role == "assistant")
                    .group_by(AIMessage.conversation_id).all())
    msgs = {m.id: m for m in db.query(AIMessage).filter(AIMessage.id.in_(list(last_ids.values()) or [-1])).all()}
    return [conv_out(c, msgs.get(last_ids.get(c.id))) for c in rows]  # 3 queries instead of one per chat


class ConvIn(BaseModel):
    project_id: int | None = None
    agent: str = "general"
    title: str = ""


@router.post("/conversations")
def create_conversation(body: ConvIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project_ctx(db, user, body.project_id)
    c = AIConversation(user_id=user.id, project_id=body.project_id or None,
                       agent=body.agent if body.agent in orchestrator.AGENTS else "general",
                       title=body.title.strip()[:200] or "New conversation", state={})
    db.add(c)
    db.commit()
    return conv_out(c)


@router.get("/conversations/{cid}")
def get_conversation(cid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = own_conv(db, user, cid)
    msgs = db.query(AIMessage).filter(AIMessage.conversation_id == c.id).order_by(AIMessage.id).all()
    fids = {m.attachment_file_id for m in msgs if m.attachment_file_id}
    files = {f.id: f for f in db.query(StoredFile).filter(StoredFile.id.in_(fids)).all()} if fids else {}
    return conv_out(c) | {"messages": [msg_out(m, files) for m in msgs], "state_pending": (c.state or {}).get("pending")}


class ConvPatch(BaseModel):
    title: str | None = None
    agent: str | None = None
    is_pinned: bool | None = None


@router.patch("/conversations/{cid}")
def patch_conversation(cid: int, body: ConvPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = own_conv(db, user, cid)
    if body.title is not None and body.title.strip():
        c.title = body.title.strip()[:200]
    if body.agent in orchestrator.AGENTS:
        c.agent = body.agent
    if body.is_pinned is not None:
        c.is_pinned = body.is_pinned
    db.commit()
    return conv_out(c)


@router.post("/conversations/{cid}/hide")
def hide_conversation(cid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """'Delete' only hides – messages are kept."""
    c = own_conv(db, user, cid)
    c.is_hidden = True
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ chat
class ChatIn(BaseModel):
    conversation_id: int | None = None
    project_id: int | None = None
    agent: str = "general"
    text: str = ""
    form: dict | None = None
    attachment_file_id: int | None = None
    language: str | None = None


@router.post("/chat")
def chat(body: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    text = (body.text or "").strip()
    if not text and not body.form and not body.attachment_file_id:
        raise HTTPException(400, "Type a question first")
    if len(text) > 4000:
        raise HTTPException(400, "Message too long (max 4000 characters)")
    if body.conversation_id:
        c = own_conv(db, user, body.conversation_id)
        if body.agent in orchestrator.AGENTS and body.agent != c.agent:
            c.agent = body.agent
    else:
        project_ctx(db, user, body.project_id)
        c = AIConversation(user_id=user.id, project_id=body.project_id or None,
                           agent=body.agent if body.agent in orchestrator.AGENTS else "general",
                           title=orchestrator.title_from(text or "Attachment"), state={})
        db.add(c)
        db.commit()
    p, perms = project_ctx(db, user, c.project_id)
    att = None
    if body.attachment_file_id:
        att = db.get(StoredFile, body.attachment_file_id)
        if not att or att.is_hidden or (att.project_id and att.project_id != c.project_id) or \
                (not att.project_id and att.uploaded_by != user.id):
            raise HTTPException(404, "Attachment not found")
    shown = text or (f"[{body.form.get('label', 'Answered the form')}]" if body.form else f"Attached {att.original_name}")
    um = AIMessage(conversation_id=c.id, role="user", content=shown,
                   attachment_file_id=att.id if att else None, cards=[], sources=[])
    db.add(um)
    db.commit()
    if c.title == "New conversation" and text:
        c.title = orchestrator.title_from(text)
    out = orchestrator.respond(db, user, c, text or shown, perms, p, form=body.form, attachment=att,
                               language=body.language)
    cards = list(out["cards"])
    if out["chips"]:
        cards.append({"type": "chips", "items": out["chips"]})
    if out["notes"]:
        cards.append({"type": "notes", "items": out["notes"]})
    am = AIMessage(conversation_id=c.id, role="assistant", content=out["content"], cards=cards, sources=out["sources"],
                   tool=out["tool"], provider=out["provider"][:120], language=out["language"])
    db.add(am)
    db.flush()
    st = dict(out["state"])
    if any(cd.get("type") == "plan" for cd in out["cards"]):
        st["last_plan_msg"] = am.id
    c.state = st
    db.commit()
    files = {att.id: att} if att else {}
    return {"conversation": conv_out(c, am), "user_message": msg_out(um, files), "assistant_message": msg_out(am)}


class FeedbackIn(BaseModel):
    value: int


@router.post("/messages/{mid}/feedback")
def feedback(mid: int, body: FeedbackIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(AIMessage, mid)
    if not m:
        raise HTTPException(404, "Message not found")
    own_conv(db, user, m.conversation_id)
    m.feedback = 1 if body.value > 0 else -1 if body.value < 0 else 0
    db.commit()
    return {"ok": True, "feedback": m.feedback}


class LinkIn(BaseModel):
    design_id: int | None = None
    estimate_id: int | None = None


@router.post("/messages/{mid}/links")
def link(mid: int, body: LinkIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remember the design / estimate saved from a chat card, so it is not saved twice."""
    m = db.get(AIMessage, mid)
    if not m:
        raise HTTPException(404, "Message not found")
    own_conv(db, user, m.conversation_id)
    cards = [dict(cd) for cd in (m.cards or [])]
    for cd in cards:
        if cd.get("type") in ("plan", "estimate"):
            links = dict(cd.get("links") or {})
            if body.design_id:
                links["design_id"] = body.design_id
            if body.estimate_id:
                links["estimate_id"] = body.estimate_id
            cd["links"] = links
            break
    m.cards = cards
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ files, voice, documents
@router.post("/upload")
async def upload(project_id: int | None = Form(None), file: UploadFile = File(...),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Attach a drawing / document to the chat. Stored like any project file (never deleted)."""
    project_ctx(db, user, project_id)
    name, data, ctype = await read_and_check(file)
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    cat = "drawing" if ext in DRAWING_EXT or (ext == ".pdf" and "plan" in name.lower()) else "other"
    f = store(db, user, name, data, ctype, cat, project_id)
    log_action(db, user, "uploaded", "file", f.id, f"{name} (AI assistant)", project_id=project_id)
    return file_out(f)


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form(""), user: User = Depends(get_current_user)):
    data = await audio.read()
    if not data:
        raise HTTPException(400, "No audio received")
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "Voice note too long (max ~10 minutes)")
    from fastapi.concurrency import run_in_threadpool
    try:
        text, prov = await run_in_threadpool(llm.transcribe, data, audio.content_type or "audio/webm", language)
    except llm.LLMError as e:
        raise HTTPException(502, str(e))
    if not text:
        raise HTTPException(422, "Couldn't hear any words – please try again closer to the mic.")
    return {"text": text, "provider": prov}


@router.get("/docs")
def doc_status(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project_ctx(db, user, project_id)
    return {"files": docs.status(db, project_id), "embeddings": bool(llm.keys()["gemini"])}


@router.post("/docs/index")
def doc_index(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project_ctx(db, user, project_id)
    info = docs.ensure_indexed(db, project_id)
    return info | {"files": docs.status(db, project_id)}
