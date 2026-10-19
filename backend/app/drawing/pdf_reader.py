"""Vector-PDF reader (pypdf): line work + text positions → rooms (same region method as DXF).

Scale (PDF points → feet) is taken from, in order:
  1. a scale note on the sheet such as "SCALE 1:100" (paper size in points is exact),
  2. room sizes written on the drawing ("12'0\" x 10'0\"") compared with the measured boxes,
  3. otherwise the user is asked for one known length (never guessed).
Scanned PDFs (pictures only, no text / lines) are sent to AI vision instead.
"""
from __future__ import annotations

import io
import re

from .regions import find_north, find_regions, parse_size, room_type, to_ft

PT_MM = 25.4 / 72


class PdfError(ValueError):
    pass


def _mul(a, b):
    """3x3 affine as (a,b,c,d,e,f) – PDF order. returns a·b."""
    return (a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3], a[2] * b[0] + a[3] * b[2],
            a[2] * b[1] + a[3] * b[3], a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5])


def _pt(m, x, y):
    return x * m[0] + y * m[2] + m[4], x * m[1] + y * m[3] + m[5]


def _segments(pdf, contents, resources, ctm, out, depth=0):
    from pypdf.generic import ContentStream
    if contents is None or depth > 4:
        return
    try:
        ops = ContentStream(contents, pdf).operations
    except Exception:
        return
    stack = []
    m = ctm
    path: list = []
    cur = start = (0.0, 0.0)
    for operands, op in ops:
        o = op.decode("latin-1") if isinstance(op, bytes) else str(op)
        try:
            if o == "q":
                stack.append(m)
            elif o == "Q":
                m = stack.pop() if stack else ctm
            elif o == "cm":
                m = _mul(tuple(float(v) for v in operands), m)
            elif o == "m":
                cur = start = (float(operands[0]), float(operands[1]))
            elif o == "l":
                p = (float(operands[0]), float(operands[1]))
                path.append((cur, p))
                cur = p
            elif o in ("c", "v", "y"):
                p = (float(operands[-2]), float(operands[-1]))
                cur = p  # curves (door swings) are not walls – skipped
            elif o == "h":
                path.append((cur, start))
                cur = start
            elif o == "re":
                x, y, w, h = (float(v) for v in operands)
                pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
                for a, b in zip(pts, pts[1:] + pts[:1]):
                    path.append((a, b))
            elif o in ("S", "s", "f", "F", "f*", "B", "B*", "b", "b*"):
                for a, b in path:
                    x1, y1 = _pt(m, *a)
                    x2, y2 = _pt(m, *b)
                    out.append((x1, y1, x2, y2))
                path = []
            elif o == "n":
                path = []
            elif o == "Do" and resources is not None:
                name = operands[0]
                xo = resources.get("/XObject")
                if xo is not None:
                    xo = xo.get_object()
                    form = xo.get(name)
                    if form is not None:
                        form = form.get_object()
                        if form.get("/Subtype") == "/Form":
                            fm = tuple(float(v) for v in form.get("/Matrix", [1, 0, 0, 1, 0, 0]))
                            _segments(pdf, form, form.get("/Resources", resources), _mul(fm, m), out, depth + 1)
        except (ValueError, IndexError, TypeError):
            continue
        if len(out) > 60000:
            return


def parse(data: bytes, page_no: int = 0) -> dict:
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover
        raise PdfError("PDF reading needs the 'pypdf' package – run scripts\\update.bat") from e
    try:
        pdf = PdfReader(io.BytesIO(data))
    except Exception as e:
        raise PdfError(f"Could not open the PDF: {e}")
    if pdf.is_encrypted:
        try:
            pdf.decrypt("")
        except Exception:
            raise PdfError("This PDF is password protected – please upload an unprotected copy.")
    if page_no >= len(pdf.pages):
        page_no = 0
    page = pdf.pages[page_no]
    texts: list[dict] = []

    def visit(text, cm, tm, font, size):
        s = (text or "").strip()
        if not s:
            return
        cmf = tuple(float(v) for v in cm)
        x, y = _pt(cmf, float(tm[4]), float(tm[5]))
        sc = (abs(float(tm[0])) or 1.0) * (abs(cmf[0]) or 1.0)
        w = len(s) * float(size or 8) * 0.5 * sc
        h = float(size or 8) * sc
        texts.append({"text": s, "x": x + w / 2, "y": y + h * 0.35})
    try:
        page.extract_text(visitor_text=visit)
    except Exception:
        pass
    segs: list = []
    _segments(pdf, page.get_contents(), page.get("/Resources"), (1, 0, 0, 1, 0, 0), segs)
    n_images = 0
    try:
        n_images = len(page.images)
    except Exception:
        pass
    labels = [{**t, "type": room_type(t["text"])} for t in texts if len(t["text"]) <= 32 and ":" not in t["text"]
              and room_type(t["text"])]
    info = {"pages": len(pdf.pages), "page": page_no, "lines": len(segs), "texts": len(texts), "labels": len(labels),
            "images": n_images, "page_w": float(page.mediabox.width), "page_h": float(page.mediabox.height)}
    if len(labels) < 2 or len(segs) < 8:
        return {"method": "pdf", "vector_ok": False, "info": info,
                "reason": "No readable room names / lines in this PDF (scanned or text drawn as lines)."}
    rooms_raw, unplaced = find_regions(segs, labels)
    if segs:  # labels outside all line work are legends / schedules, not rooms
        sx0 = min(min(q[0], q[2]) for q in segs); sx1 = max(max(q[0], q[2]) for q in segs)
        sy0 = min(min(q[1], q[3]) for q in segs); sy1 = max(max(q[1], q[3]) for q in segs)
        unplaced = [u for u in unplaced if sx0 <= u["x"] <= sx1 and sy0 <= u["y"] <= sy1]
    # separate size texts
    for st in texts:
        if parse_size(st["text"]) and not room_type(st["text"]):
            for r in rooms_raw:
                if r["x"] <= st["x"] <= r["x"] + r["w"] and r["y"] <= st["y"] <= r["y"] + r["d"]:
                    r.setdefault("extra", []).append(st["text"])
                    break
    # ---- scale
    questions, scale, scale_src = [], None, ""
    for t in texts:
        mm = re.search(r"1\s*:\s*(\d{2,4})", t["text"])
        if mm and "scale" in " ".join(x["text"].lower() for x in texts):
            ratio = float(mm.group(1))
            scale = PT_MM * ratio / 304.8
            scale_src = f"scale note 1:{int(ratio)}"
            break
    if not scale:
        ratios = []
        for r in rooms_raw:
            for t in [r["label"]] + r.get("extra", []):
                ps = parse_size(t)
                if ps and r["w"] > 0 and r["d"] > 0:
                    hint = ps[2].rstrip("?") if ps[2] != "ft?" else "ft"
                    a, b = to_ft(ps[0], hint), to_ft(ps[1], hint)
                    k1 = (a / r["w"] + b / r["d"]) / 2
                    k2 = (b / r["w"] + a / r["d"]) / 2
                    s1 = abs(a / r["w"] - b / r["d"])
                    s2 = abs(b / r["w"] - a / r["d"])
                    ratios.append(k1 if s1 <= s2 else k2)
                    break
        if ratios:
            ratios.sort()
            scale = ratios[len(ratios) // 2]
            scale_src = f"room sizes written on the drawing ({len(ratios)} rooms)"
    if not scale:
        questions.append("The drawing scale is unknown – enter one known length (e.g. the overall building width in feet).")
    ox = min([r["x"] for r in rooms_raw], default=0)
    oy = min([r["y"] for r in rooms_raw], default=0)
    titles = [{"text": t["text"], "x": t["x"] - ox, "y": t["y"] - oy} for t in texts
              if re.search(r"floor|stilt|ground|first|second", t["text"], re.I) and len(t["text"]) < 60]
    preview = sorted(segs, key=lambda q: -abs(q[2] - q[0]) - abs(q[3] - q[1]))[:6000]
    return {
        "method": "pdf", "vector_ok": True, "info": info, "units": "pt", "units_from_file": False,
        "to_ft": scale or 1.0, "scale_ft_per_unit": scale, "scale_source": scale_src,
        "rooms_raw": [{**r, "x": r["x"] - ox, "y": r["y"] - oy} for r in rooms_raw],
        "unplaced": [{"text": u["text"], "type": u.get("type")} for u in unplaced],
        "texts": [t["text"] for t in texts][:200], "titles": titles,
        "preview_raw": [[a - ox, b - oy, c - ox, d - oy] for a, b, c, d in preview],
        "questions": questions, "warnings": [], "north_deg": find_north(texts, segs),
        "stats": {"lines": len(segs), "texts": len(texts), "labels": len(labels)},
    }


def largest_image(data: bytes, page_no: int = 0) -> tuple[bytes, str] | None:
    """Embedded picture of a scanned PDF page (for AI vision providers that can't read PDFs)."""
    try:
        from pypdf import PdfReader
        page = PdfReader(io.BytesIO(data)).pages[page_no]
        best = None
        for img in page.images:
            if best is None or len(img.data) > len(best.data):
                best = img
        if best is None:
            return None
        name = best.name.lower()
        mime = "image/png" if name.endswith(".png") else "image/jpeg"
        return best.data, mime
    except Exception:
        return None
