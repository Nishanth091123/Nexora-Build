"""AI photo check – one site photo at a time, only when the user asks.

Uses the vision models already configured (Gemini → Groq → OpenRouter). No training, no extra copies of the photo:
only the short JSON result is stored. The answer is guidance; the user must confirm on site.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from .. import llm
from ..models import AIPhotoCheck, StoredFile
from ..storage import backend_for

PROMPT = """You are a senior civil engineer reviewing ONE construction-site photo from India.
Look only at what is visible. Report quality / safety issues such as: cracks (hairline, map, diagonal, along bars),
honeycombing, exposed or rusted reinforcement, missing cover blocks, poor bar spacing or lap, formwork gaps / bulging,
segregation, dampness, efflorescence, seepage, poor curing, bad material storage (cement bags on the ground, rusting
steel), unsafe work (no helmet / harness, weak scaffolding), poor masonry joints, plaster defects.
RULES: Do not guess measurements – only give a size if a tape / scale is visible. If the photo is unclear or not a site
photo, say so. Never claim strength or grade from a photo. Be honest about confidence.
Return JSON only:
{"photo_type": "what the photo shows (e.g. RCC column, slab, brick wall, plaster, steel stack)",
 "photo_ok": true/false (clear enough to judge?),
 "overall": "one or two sentence summary",
 "findings": [{"issue": "short name", "where": "where in the photo", "severity": "low|medium|high",
               "confidence": "low|medium|high", "likely_cause": "...", "what_to_check": "...", "suggested_fix": "..."}],
 "good_points": ["things done well"],
 "cannot_judge": ["things that need a site check / test"]}
Answer language: {lang}."""

IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")


def is_image(f: StoredFile) -> bool:
    return f.original_name.lower().endswith(IMG_EXT) or (f.content_type or "").startswith("image/")


def check(db: Session, user_id: int, f: StoredFile, lang: str = "English") -> AIPhotoCheck:
    data = backend_for(f.storage_backend).read(f.storage_key)
    mime = f.content_type if (f.content_type or "").startswith("image/") else "image/jpeg"
    blob, mime = llm._shrink_image(data, mime, max_side=1600, max_bytes=1_500_000)
    res, prov = llm.ask(PROMPT.replace("{lang}", lang), blob, mime, want_json=True)
    if not isinstance(res, dict):
        raise llm.LLMError("The AI did not return a readable result")
    res.setdefault("findings", [])
    res["findings"] = [x for x in res["findings"] if isinstance(x, dict)][:10]
    res["note"] = "AI guidance from one photo – confirm on site; structural issues must be checked by an engineer."
    rec = AIPhotoCheck(file_id=f.id, project_id=f.project_id, result=res, provider=prov[:120], created_by=user_id)
    db.add(rec)
    db.commit()
    return rec


def out(rec: AIPhotoCheck) -> dict:
    return {"id": rec.id, "file_id": rec.file_id, "result": rec.result, "provider": rec.provider,
            "created_at": rec.created_at.isoformat()}
