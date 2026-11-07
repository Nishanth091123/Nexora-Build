"""1.20 AI Render – turns a picture of OUR 3D model into a photo-like concept render, keeping its shape.

Free services only, tried in this order:
  1. Cloudflare Workers AI (free daily allowance) – image-to-image Stable Diffusion; the 3D picture is the base, so
     walls, floors, windows and the outline stay where the drawing has them. Needs CLOUDFLARE_ACCOUNT_ID and
     CLOUDFLARE_AI_TOKEN in .env (and on Render).
  2. Gemini image model with the GEMINI_API_KEY you already have – only if Google gives free image quota to that key.
Nothing is paid for. When the free allowance is used up the user is told so; no fake picture is ever made.
Every render is marked "AI concept render – not to scale" by the app."""
from __future__ import annotations

import base64
import logging

import httpx

from .. import config

log = logging.getLogger("nexora.render")
CF_MODELS = ["@cf/runwayml/stable-diffusion-v1-5-img2img", "@cf/lykon/dreamshaper-8-lcm"]
NEG = ("cartoon, sketch, drawing, toy, plastic, blurry, low quality, distorted, deformed building, extra floors, "
       "warped lines, text, watermark, logo, people, car crash, oversaturated")

STYLE_WORDS = {
    "luxury": "luxury modern Indian house, smooth white and beige putty walls, white curved frame band, white CNC jaali "
              "screens, frameless glass balcony railings with steel top rail, warm wooden ceiling panels with downlights, "
              "grey stacked stone cladding, black window frames, flower planters",
    "modern": "modern Indian house, beige putty walls, grey stacked stone cladding, wooden cladding, black aluminium "
              "windows, deep white roof overhang with wooden soffit and downlights, glass railings",
    "contemporary": "contemporary Indian house, two-tone white and grey walls, grey tiles, wooden vertical fins, "
                    "terrace pergola, dark grey window frames",
    "traditional": "traditional Tamil Nadu house, red clay tiled sloping roof, thinnai sit-out, round white pillars, "
                   "arched windows, cream lime-plaster walls, wooden doors",
    "basic": "simple Indian residential house, plastered painted walls, concrete roof",
}
LIGHT_WORDS = {"day": "bright daylight, clear blue sky, soft shadows",
               "dusk": "golden hour evening, warm interior lights glowing, soft sunset sky",
               "night": "night scene, warm wall lights and downlights glowing, deep blue sky"}


class RenderError(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


def configured() -> dict:
    return {"cloudflare": bool(config.env("CLOUDFLARE_ACCOUNT_ID") and config.env("CLOUDFLARE_AI_TOKEN")),
            "gemini": bool(config.env("GEMINI_API_KEY"))}


def prompt_for(kind: str, style: str, light: str, extra: str) -> str:
    if kind == "interior":
        base = ("photorealistic interior render of an Indian home, realistic materials, vitrified tile floor, painted "
                "walls, false ceiling with warm cove lights, natural light from windows, wooden furniture, plants")
    else:
        base = "photorealistic architectural exterior render, " + STYLE_WORDS.get(style, STYLE_WORDS["modern"]) + \
               ", landscaped front garden with flowers, paver driveway, compound wall"
    words = [base, LIGHT_WORDS.get(light, LIGHT_WORDS["day"]), "sharp focus, realistic textures, professional architectural visualisation, 8k"]
    if extra.strip():
        words.insert(1, extra.strip()[:300])
    return ", ".join(words)


def _cloudflare(img: bytes, prompt: str, strength: float, seed: int | None) -> tuple[bytes, str]:
    acc, tok = config.env("CLOUDFLARE_ACCOUNT_ID"), config.env("CLOUDFLARE_AI_TOKEN")
    body = {"prompt": prompt, "negative_prompt": NEG, "image_b64": base64.b64encode(img).decode(),
            "strength": max(0.2, min(0.85, strength)), "num_steps": 20, "guidance": 7.5}
    if seed is not None:
        body["seed"] = int(seed)
    last = ""
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as c:
        for model in CF_MODELS:
            r = c.post(f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{model}",
                       headers={"Authorization": f"Bearer {tok}"}, json=body)
            ct = r.headers.get("content-type", "")
            if r.status_code == 200 and ct.startswith("image/"):
                return r.content, model
            if r.status_code == 200 and "json" in ct:  # some models answer {"result": {"image": base64}}
                res = (r.json() or {}).get("result") or {}
                if isinstance(res, dict) and res.get("image"):
                    return base64.b64decode(res["image"]), model
            if r.status_code == 429:
                raise RenderError("Today's free Cloudflare AI allowance is used up. It resets every day (00:00 UTC = "
                                  "5:30 am India) – try again then.", 429)
            if r.status_code in (401, 403):
                raise RenderError("Cloudflare refused the token – check CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_AI_TOKEN "
                                  "(Workers AI token) in .env and on Render.", 400)
            last = f"{model}: HTTP {r.status_code} {r.text[:200]}"
            log.warning("cloudflare render failed %s", last)
    raise RenderError(f"Cloudflare AI could not make the render ({last}).", 502)


def _gemini(img: bytes, prompt: str) -> tuple[bytes, str]:
    key = config.env("GEMINI_API_KEY")
    models = [m for m in [config.env("GEMINI_IMAGE_MODEL"), "gemini-2.5-flash-image", "gemini-2.0-flash-preview-image-generation"] if m]
    instr = ("Turn this 3D model picture into a photorealistic architectural render. Keep exactly the same building "
             "shape, number of floors, windows, doors and camera angle; only make materials, light, sky and garden "
             "realistic. " + prompt)
    last = ""
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as c:
        for m in models:
            r = c.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", params={"key": key},
                       json={"contents": [{"parts": [{"text": instr}, {"inline_data": {"mime_type": "image/png",
                                                                                          "data": base64.b64encode(img).decode()}}]}],
                             "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}})
            if r.status_code == 200:
                for cand in (r.json().get("candidates") or []):
                    for part in ((cand.get("content") or {}).get("parts") or []):
                        d = part.get("inlineData") or part.get("inline_data")
                        if d and d.get("data"):
                            return base64.b64decode(d["data"]), m
                last = f"{m}: no picture in the answer"
            else:
                last = f"{m}: HTTP {r.status_code} {r.text[:160]}"
    raise RenderError(f"Gemini has no free image quota for this key ({last[:220]}).", 429 if "429" in last else 502)


def render(img: bytes, kind: str, style: str, light: str, extra: str, strength: float, seed: int | None = None) -> dict:
    if len(img) > 6 * 1024 * 1024:
        raise RenderError("Picture too big (max 6 MB).")
    cfg = configured()
    if not cfg["cloudflare"] and not cfg["gemini"]:
        raise RenderError("AI Render is not set up: add CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_AI_TOKEN (free Cloudflare "
                          "Workers AI) to .env and on Render.", 400)
    prompt = prompt_for(kind, style, light, extra)
    errors = []
    if cfg["cloudflare"]:
        try:
            out, model = _cloudflare(img, prompt, strength, seed)
            return {"image_b64": base64.b64encode(out).decode(), "provider": "Cloudflare Workers AI (free)", "model": model, "prompt": prompt}
        except RenderError as e:
            errors.append(str(e))
            if e.status == 400 and not cfg["gemini"]:
                raise
        except httpx.HTTPError as e:
            errors.append(f"Cloudflare not reachable: {e}")
    if cfg["gemini"]:
        try:
            out, model = _gemini(img, prompt)
            return {"image_b64": base64.b64encode(out).decode(), "provider": "Google Gemini (free quota)", "model": model, "prompt": prompt}
        except RenderError as e:
            errors.append(str(e))
        except httpx.HTTPError as e:
            errors.append(f"Gemini not reachable: {e}")
    status = 429 if any("used up" in x or "quota" in x for x in errors) else 502
    raise RenderError(" | ".join(errors), status)
