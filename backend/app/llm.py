"""LLM access with automatic fallback: Gemini → Groq → OpenRouter (free models).

Model names change over time, so each provider's model is: the .env value if set, else a known
default, else the first suitable model found in the provider's model list (cached).
Keys are read from .env and never logged or returned.
"""
from __future__ import annotations

import base64
import json
import logging
import re
import time

import httpx

from . import config

log = logging.getLogger("nexora.llm")
TIMEOUT = httpx.Timeout(90.0, connect=15.0)
_model_cache: dict[str, tuple[float, str]] = {}
NOT_CHAT = ("guard", "whisper", "tts", "embed", "playai", "orpheus", "distil", "moderation", "rerank", "compound")


class LLMError(RuntimeError):
    pass


def keys() -> dict:
    return {"gemini": config.env("GEMINI_API_KEY"), "groq": config.env("GROQ_API_KEY"),
            "openrouter": config.env("OPENROUTER_API_KEY")}


def _json_from(text: str) -> dict:
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    else:
        a, b = text.find("{"), text.rfind("}")
        if a >= 0 and b > a:
            text = text[a:b + 1]
    return json.loads(text)


# ---------------------------------------------------------------- model discovery
def _gemini_models(client: httpx.Client, key: str) -> list[str]:
    r = client.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key, "pageSize": 200})
    r.raise_for_status()
    out = []
    for m in r.json().get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            out.append(m["name"].split("/", 1)[-1])
    return out


def _pick_gemini(client, key) -> list[str]:
    pref = [config.env("GEMINI_VISION_MODEL"), "gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"]
    pref = [p for p in pref if p]
    cached = _model_cache.get("gemini")
    if cached and time.time() - cached[0] < 86400:
        return [cached[1]] + [p for p in pref if p != cached[1]]
    try:
        avail = _gemini_models(client, key)
        flash = [m for m in avail if "flash" in m and "lite" not in m and "image" not in m and "tts" not in m
                 and "thinking" not in m and "exp" not in m]
        flash.sort(key=lambda m: [int(x) if x.isdigit() else 0 for x in re.findall(r"\d+", m)], reverse=True)
        order = [p for p in pref if p in avail] + flash
        if order:
            _model_cache["gemini"] = (time.time(), order[0])
            return list(dict.fromkeys(order))[:3]
    except Exception as e:  # list call failed – try defaults anyway
        log.info("gemini model list failed: %s", e)
    return pref


def _pick_openai_like(provider: str, client, key, url, vision: bool) -> list[str]:
    env_name = {"groq": "GROQ_VISION_MODEL" if vision else "GROQ_MODEL",
                "openrouter": "OPENROUTER_VISION_MODEL" if vision else "OPENROUTER_MODEL"}[provider]
    defaults = {("groq", True): ["meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-maverick-17b-128e-instruct"],
                ("groq", False): ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "qwen/qwen3-32b",
                                  "meta-llama/llama-4-maverick-17b-128e-instruct", "llama-3.1-8b-instant"],
                ("openrouter", True): ["google/gemma-3-27b-it:free", "meta-llama/llama-4-maverick:free"],
                ("openrouter", False): ["meta-llama/llama-3.3-70b-instruct:free"]}[(provider, vision)]
    pref = [m for m in [config.env(env_name)] + defaults if m]
    ck = f"{provider}:{vision}"
    cached = _model_cache.get(ck)
    if cached and time.time() - cached[0] < 86400:
        return [cached[1]] + [p for p in pref if p != cached[1]]
    try:
        r = client.get(url, headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        data = r.json().get("data", [])
        ids = {m.get("id") for m in data}
        order = [p for p in pref if p in ids]
        if vision:
            for m in data:
                mods = (m.get("architecture") or {}).get("input_modalities") or []
                mid = m.get("id", "")
                if ("image" in mods or "vision" in mid or "llama-4" in mid) and (provider != "openrouter" or mid.endswith(":free")):
                    order.append(mid)
        else:
            for m in data:
                mid = m.get("id", "")
                if provider != "openrouter" or mid.endswith(":free"):
                    if any(w in mid for w in ("llama", "qwen", "gemma", "deepseek", "mistral", "gpt-oss")):
                        order.append(mid)
        # never use classifier / speech / embedding models for chat (e.g. llama-prompt-guard returns a score)
        order = [m for m in order if not any(w in m.lower() for w in NOT_CHAT)]
        order = list(dict.fromkeys(order))
        if order:
            _model_cache[ck] = (time.time(), order[0])
            return order[:3]
    except Exception as e:
        log.info("%s model list failed: %s", provider, e)
    return pref


# ---------------------------------------------------------------- calls
def _post(client, url, **kw):
    """POST; on a short rate-limit (HTTP 429 with a small wait) wait once and retry."""
    r = client.post(url, **kw)
    if r.status_code == 429:
        wait = 0.0
        try:
            wait = float(r.headers.get("retry-after") or 0)
        except ValueError:
            wait = 0.0
        m = re.search(r"try again in ([0-9.]+)s", r.text or "")
        if m:
            wait = max(wait, float(m.group(1)))
        if 0 < wait <= 10:
            time.sleep(wait + 0.3)
            r = client.post(url, **kw)
    return r


def _gemini(client, key, model, prompt, blob, mime, want_json, temperature=0.0) -> str:
    parts = [{"text": prompt}]
    if blob is not None:
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(blob).decode()}})
    gen = {"temperature": temperature}
    if want_json:
        gen["responseMimeType"] = "application/json"
    r = _post(client, f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    params={"key": key}, json={"contents": [{"role": "user", "parts": parts}], "generationConfig": gen})
    if r.status_code >= 400:
        raise LLMError(f"Gemini {model}: HTTP {r.status_code} {r.text[:200]}")
    cands = r.json().get("candidates") or []
    if not cands:
        raise LLMError("Gemini returned no answer (safety block or empty)")
    return "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))


def _openai_like(client, base, key, model, prompt, blob, mime, want_json, extra_headers=None, temperature=0.0) -> str:
    content: list | str
    if blob is not None:
        content = [{"type": "text", "text": prompt},
                   {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(blob).decode()}"}}]
    else:
        content = prompt
    body = {"model": model, "messages": [{"role": "user", "content": content}], "temperature": temperature}
    if want_json:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {key}", **(extra_headers or {})}
    r = _post(client, base + "/chat/completions", headers=headers, json=body)
    if r.status_code == 400 and want_json:  # some models reject response_format – retry without it
        body.pop("response_format", None)
        r = client.post(base + "/chat/completions", headers=headers, json=body)
    if r.status_code >= 400:
        raise LLMError(f"{model}: HTTP {r.status_code} {r.text[:200]}")
    return r.json()["choices"][0]["message"]["content"] or ""


def _shrink_image(blob: bytes, mime: str, max_side: int = 2000, max_bytes: int = 3_500_000) -> tuple[bytes, str]:
    """Groq / OpenRouter limit image size – resize with Pillow when available."""
    if len(blob) <= max_bytes and mime != "image/webp":
        return blob, mime
    try:
        import io

        from PIL import Image
        im = Image.open(io.BytesIO(blob))
        im = im.convert("RGB")
        im.thumbnail((max_side, max_side))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=85)
        return out.getvalue(), "image/jpeg"
    except Exception:
        return blob, mime


def ask(prompt: str, blob: bytes | None = None, mime: str = "", want_json: bool = True,
        image_fallback: tuple[bytes, str] | None = None, temperature: float = 0.0,
        order: list[str] | None = None, min_chars: int = 0, strict: bool = False) -> tuple[dict | str, str]:
    """Run the prompt through Gemini → Groq → OpenRouter (or the order given). Returns (answer, 'provider/model').
    min_chars: for text answers, a shorter (or number-only) answer counts as a failure and the next model is tried.

    blob may be an image or a PDF (PDF only works on Gemini; image_fallback is sent to the others)."""
    k = keys()
    errors: list[str] = []
    default = ["gemini", "groq", "openrouter"]
    order = [o for o in (order or default) if o in default]
    if not strict:  # strict = only the providers given (used by the key test)
        order += [o for o in default if o not in order]

    other_blob, other_mime = blob, mime
    if blob is not None and (mime == "application/pdf" or mime.startswith("audio/")):
        other_blob, other_mime = image_fallback if image_fallback else (None, "")
    if other_blob is not None:
        other_blob, other_mime = _shrink_image(other_blob, other_mime)
    vision = other_blob is not None

    def done(txt: str, tag: str):
        txt = re.sub(r"<think>.*?</think>", "", txt or "", flags=re.S).strip()  # reasoning models
        if want_json:
            return _json_from(txt), tag
        if min_chars and (len(txt) < min_chars or re.fullmatch(r"[-+0-9.eE\s]+", txt)):
            raise LLMError(f"unusable answer {txt[:40]!r}")
        return txt, tag

    with httpx.Client(timeout=TIMEOUT) as client:
        for prov in order:
            key = k.get(prov)
            if not key:
                continue
            if prov == "gemini":
                for model in _pick_gemini(client, key):
                    try:
                        return done(_gemini(client, key, model, prompt, blob, mime, want_json, temperature), f"gemini/{model}")
                    except Exception as e:
                        errors.append(f"gemini/{model}: {str(e)[:160]}")
                continue
            if blob is not None and other_blob is None:
                errors.append(f"{prov}: can't read this file type ({mime})" if mime.startswith("audio/") else
                              f"{prov}: can't read PDF files and no picture was found inside the PDF")
                continue
            base = "https://api.groq.com/openai/v1" if prov == "groq" else "https://openrouter.ai/api/v1"
            extra = {"X-Title": "Nexora Build"} if prov == "openrouter" else None
            for model in _pick_openai_like(prov, client, key, base + "/models", vision):
                try:
                    return done(_openai_like(client, base, key, model, prompt, other_blob, other_mime, want_json,
                                             extra, temperature), f"{prov}/{model}")
                except Exception as e:
                    errors.append(f"{prov}/{model}: {str(e)[:160]}")
    if not any(k.values()):
        raise LLMError("No AI keys in .env (GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY).")
    errors = [re.sub(r"(key=|Bearer\s+)[A-Za-z0-9_\-.]+", r"\1***", e) for e in errors]
    log.warning("all LLM providers failed: %s", errors)
    raise LLMError("All AI providers failed: " + " | ".join(errors[-4:]))


# ---------------------------------------------------------------- embeddings (document search)
EMBED_DIM = 768


def embed(texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> list[list[float]] | None:
    """Gemini embeddings (768 numbers per text). Returns None when no Gemini key or the call fails –
    document search then falls back to keyword search."""
    key = keys()["gemini"]
    if not key or not texts:
        return None
    models = [m for m in [config.env("GEMINI_EMBED_MODEL"), "gemini-embedding-001", "text-embedding-004"] if m]
    out: list[list[float]] = []
    with httpx.Client(timeout=TIMEOUT) as client:
        for model in dict.fromkeys(models):
            try:
                out = []
                for i in range(0, len(texts), 90):
                    batch = texts[i:i + 90]
                    reqs = [{"model": f"models/{model}", "content": {"parts": [{"text": t[:7000]}]},
                             "taskType": task, "outputDimensionality": EMBED_DIM} for t in batch]
                    r = client.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents",
                                    params={"key": key}, json={"requests": reqs})
                    if r.status_code >= 400:
                        raise LLMError(f"HTTP {r.status_code} {r.text[:160]}")
                    for e in r.json().get("embeddings", []):
                        v = e.get("values") or []
                        if len(v) != EMBED_DIM:
                            raise LLMError(f"unexpected embedding size {len(v)}")
                        n = sum(x * x for x in v) ** 0.5 or 1.0
                        out.append([x / n for x in v])
                if len(out) == len(texts):
                    return out
            except Exception as e:
                log.info("embedding with %s failed: %s", model, str(e)[:200])
    return None


# ---------------------------------------------------------------- voice → text
def transcribe(audio: bytes, mime: str, language: str = "") -> tuple[str, str]:
    """Speech to text. Groq Whisper first (Tamil / English); Gemini as fallback. Returns (text, provider)."""
    k = keys()
    errors = []
    lang = language if language in ("ta", "en") else ""
    ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/wav": "wav",
           "audio/x-wav": "wav", "audio/aac": "aac"}.get((mime or "").split(";")[0], "webm")
    with httpx.Client(timeout=TIMEOUT) as client:
        if k["groq"]:
            for model in [m for m in [config.env("GROQ_WHISPER_MODEL"), "whisper-large-v3", "whisper-large-v3-turbo"] if m]:
                try:
                    data = {"model": model, "response_format": "json", "temperature": "0",
                            "prompt": "Construction site talk in Tamil and English: cement, steel, slab, column, plan, estimate."}
                    if lang:
                        data["language"] = lang
                    r = client.post("https://api.groq.com/openai/v1/audio/transcriptions",
                                    headers={"Authorization": f"Bearer {k['groq']}"}, data=data,
                                    files={"file": (f"voice.{ext}", audio, (mime or "audio/webm").split(";")[0])})
                    if r.status_code >= 400:
                        raise LLMError(f"HTTP {r.status_code} {r.text[:160]}")
                    return (r.json().get("text") or "").strip(), f"groq/{model}"
                except Exception as e:
                    errors.append(f"groq/{model}: {str(e)[:160]}")
        if k["gemini"]:
            how = {"ta": "Write Tamil words in Tamil script.", "en": "Write in English."}.get(
                lang, "Keep Tamil words in Tamil script and English words in English, exactly as spoken.")
            try:
                txt, prov = ask(f"Transcribe this voice note exactly. {how} Return only the words spoken.",
                                audio, (mime or "audio/webm").split(";")[0], want_json=False, order=["gemini"])
                if str(prov).startswith("gemini"):
                    return str(txt).strip(), prov
            except Exception as e:
                errors.append(f"gemini: {str(e)[:160]}")
    if not k["groq"] and not k["gemini"]:
        raise LLMError("Voice needs GROQ_API_KEY (Whisper) or GEMINI_API_KEY in .env.")
    raise LLMError("Voice could not be converted: " + " | ".join(errors[-3:]))
