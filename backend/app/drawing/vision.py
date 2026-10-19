"""Read a floor-plan picture (JPG / PNG / scanned PDF) with an AI vision model.

The model is told to copy ONLY what is written on the drawing; anything it can't read is left empty
and the user confirms every room in the table before it is used.
"""
from __future__ import annotations

import struct

from .. import llm

PROMPT = """You are reading an architectural FLOOR PLAN drawing (house plan) for a civil engineer.
Return ONLY JSON in exactly this shape:
{"units": "ft" | "m" | "mm",
 "north_arrow_deg": number or null,   // clockwise angle of the north arrow from the top of the image; null if no arrow
 "plot": {"w": number, "d": number} or null,   // only if a plot / site size is written
 "floors": ["Ground Floor", ...],              // floor titles you can see, in order (one entry if only one plan)
 "rooms": [
   {"name": "Bedroom", "floor": 0,             // index into floors
    "w": number or null, "d": number or null,  // ONLY sizes WRITTEN on the drawing for this room (e.g. 12'0"x10'0" -> 12, 10)
    "dims_text": "12'0\\" x 10'0\\"" or null,  // the exact text you read
    "bbox": [x0, y0, x1, y1],                  // the room's box on the image, fractions 0..1, origin top-left
    "confidence": 0..1}
 ],
 "notes": ["anything unclear"]}
Rules:
- NEVER invent a size. If a room has no written size, use null for w and d.
- Feet-inches like 12'6" become 12.5 (feet). Metric like 3.60 x 3.00 -> units "m".
- Include every labelled space: bedrooms, toilets, kitchen, hall/living, dining, pooja, staircase, parking, sit-out,
  utility, store, balcony, passage. Keep the label text as written (e.g. "M.Bed", "Toilet", "Car Parking").
- bbox must be tight around the room's walls."""


def image_size(blob: bytes) -> tuple[int, int]:
    try:
        import io

        from PIL import Image
        with Image.open(io.BytesIO(blob)) as im:
            return im.size
    except Exception:
        pass
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", blob[16:24])
        return w, h
    if blob[:2] == b"\xff\xd8":  # JPEG: scan for SOF marker
        i = 2
        while i < len(blob) - 9:
            if blob[i] != 0xFF:
                i += 1
                continue
            marker = blob[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", blob[i + 5:i + 9])
                return w, h
            seg = struct.unpack(">H", blob[i + 2:i + 4])[0]
            i += 2 + seg
    return 1000, 1000


def read_plan(blob: bytes, mime: str, page_size: tuple[float, float] | None = None,
              image_fallback: tuple[bytes, str] | None = None) -> dict:
    """Returns {"data": vision JSON, "model": "provider/model", "img_w", "img_h"}."""
    data, model = llm.ask(PROMPT, blob, mime, want_json=True, image_fallback=image_fallback)
    if not isinstance(data, dict):
        raise llm.LLMError("The AI answer was not in the expected format.")
    if mime == "application/pdf":
        if model.startswith("gemini") or not image_fallback:
            w, h = page_size or (842, 595)
        else:
            w, h = image_size(image_fallback[0])
    else:
        w, h = image_size(blob)
    return {"data": data, "model": model, "img_w": float(w), "img_h": float(h)}
