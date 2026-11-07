"""1.20 AI Render – turns a picture of OUR 3D model into a photo-like concept render, keeping its shape.

Free services only, tried in this order:
  1. Cloudflare Workers AI (free daily allowance) – FLUX.2 [klein] picture editing (then dreamshaper / SD img2img); the 3D picture is the base, so
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
# best first; all share the same free daily allowance. FLUX.2 [klein] edits the picture (keeps the building),
# dreamshaper / SD 1.5 are image-to-image with a "strength". Models an account may not use (code 5018) are skipped.
CF_MODELS = ["@cf/black-forest-labs/flux-2-klein-9b", "@cf/black-forest-labs/flux-2-klein-4b",
             "@cf/lykon/dreamshaper-8-lcm", "@cf/runwayml/stable-diffusion-v1-5-img2img"]
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


def _fit(img: bytes, max_side: int) -> tuple[bytes, int, int]:
    """PNG no bigger than max_side (FLUX.2 takes input pictures below 512 px); sizes rounded to 8."""
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(img)).convert("RGB")
    k = min(1.0, max_side / max(im.size))
    w, h = max(64, int(im.width * k) // 8 * 8), max(64, int(im.height * k) // 8 * 8)
    im = im.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue(), w, h


def _cf_error(r) -> tuple[int, str]:
    try:
        e = (r.json().get("errors") or [{}])[0]
        return int(e.get("code") or 0), str(e.get("message") or "")[:200]
    except Exception:
        return 0, r.text[:200]


def _cloudflare(img: bytes, prompt: str, strength: float, seed: int | None) -> tuple[bytes, str]:
    acc, tok = config.env("CLOUDFLARE_ACCOUNT_ID"), config.env("CLOUDFLARE_AI_TOKEN")
    small, w, h = _fit(img, 504)
    k = 1024 / max(w, h)
    ow, oh = int(w * k) // 8 * 8, int(h * k) // 8 * 8  # output about 1024 px on the long side
    keep = max(0.0, min(1.0, (0.85 - strength) / 0.6))  # 1 = keep my design exactly
    edit = ("Turn this 3D model render into a photorealistic architectural photograph. "
            + ("Keep exactly the same building: same shape, number of floors, walls, windows, doors, balconies, colours "
               "and the same camera angle. Only make the materials, lighting, sky and garden look real. " if keep >= 0.5 else
               "Keep the same building shape, floors and camera angle; you may refine materials, details and landscaping. ")
            + prompt)
    last = ""
    with httpx.Client(timeout=httpx.Timeout(150.0, connect=15.0)) as c:
        for model in CF_MODELS:
            url = f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{model}"
            if "flux-2" in model:
                data = {"prompt": edit[:2000], "width": str(ow), "height": str(oh)}
                if seed is not None:
                    data["seed"] = str(int(seed))
                r = c.post(url, headers={"Authorization": f"Bearer {tok}"}, data=data,
                           files={"input_image_0": ("view.png", small, "image/png")})
            else:
                body = {"prompt": prompt, "negative_prompt": NEG, "image_b64": base64.b64encode(small).decode(),
                        "strength": max(0.2, min(0.85, strength)), "num_steps": 20, "guidance": 7.5, "width": w, "height": h}
                if seed is not None:
                    body["seed"] = int(seed)
                r = c.post(url, headers={"Authorization": f"Bearer {tok}"}, json=body)
            ct = r.headers.get("content-type", "")
            if r.status_code == 200 and ct.startswith("image/"):
                return r.content, model
            if r.status_code == 200 and "json" in ct:  # FLUX answers {"result": {"image": base64}}
                res = (r.json() or {}).get("result") or {}
                if isinstance(res, dict) and res.get("image"):
                    return base64.b64decode(res["image"]), model
                last = f"{model}: empty answer"
                continue
            code, msg = _cf_error(r)
            low = msg.lower()
            if r.status_code == 429 or code in (4006, 3036) or "allocation" in low or "neurons" in low:
                raise RenderError("Today's free Cloudflare AI allowance is used up. It resets every day (00:00 UTC = "
                                  "5:30 am India) – try again then.", 429)
            if r.status_code == 401 or code in (10000, 9109):
                raise RenderError(f"Cloudflare refused the token ({code} {msg}) – check CLOUDFLARE_ACCOUNT_ID / "
                                  f"CLOUDFLARE_AI_TOKEN in .env and on Render.", 400)
            last = f"{model.split('/')[-1]}: {r.status_code} {code} {msg}"  # e.g. 5018 not allowed → next model
            log.warning("cloudflare render: %s", last)
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
                last = f"{m}: HTTP {r.status_code}"
    raise RenderError("Gemini: no free image quota for this key.", 502)


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
    if cfg["gemini"] and not (cfg["cloudflare"] and errors and "used up" in errors[0]):
        try:
            out, model = _gemini(img, prompt)
            return {"image_b64": base64.b64encode(out).decode(), "provider": "Google Gemini (free quota)", "model": model, "prompt": prompt}
        except RenderError as e:
            if not cfg["cloudflare"]:
                errors.append(str(e))
        except httpx.HTTPError as e:
            if not cfg["cloudflare"]:
                errors.append(f"Gemini not reachable: {e}")
    status = 429 if any("used up" in x or "quota" in x for x in errors) else 502
    raise RenderError(" | ".join(errors), status)
