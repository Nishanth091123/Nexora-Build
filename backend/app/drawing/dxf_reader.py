"""Minimal ASCII DXF reader (R12 … 2018) – lines, polylines, texts, dimensions → rooms.

Reads ENTITIES (and block contents placed with INSERT, without rotation/scale beyond X/Y scale).
Binary DXF is refused with a clear message. Units come from $INSUNITS; if missing they are
suggested from the drawing size and the user confirms (never guessed silently).
"""
from __future__ import annotations

import math
import re

from .regions import find_north, find_regions, parse_size, room_type

INSUNITS = {1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}
TO_FT = {"in": 1 / 12, "ft": 1.0, "mm": 1 / 304.8, "cm": 1 / 30.48, "m": 1 / 0.3048}


class DxfError(ValueError):
    pass


def _pairs(text: str):
    lines = text.splitlines()
    for i in range(0, len(lines) - 1, 2):
        code = lines[i].strip()
        try:
            yield int(code), lines[i + 1].rstrip("\r")
        except ValueError:
            continue


def clean_mtext(s: str) -> str:
    s = re.sub(r"\\[PpNn]", " ", s)
    s = re.sub(r"\\[A-Za-z][^;\\{}]*;", "", s)
    s = re.sub(r"\\[LlOoKk]", "", s)
    s = s.replace("{", "").replace("}", "").replace("%%c", "Ø").replace("%%d", "°").replace("%%p", "±")
    s = s.replace("\\~", " ")
    return re.sub(r"\s+", " ", s).strip()


def parse(data: bytes) -> dict:
    if data[:22].startswith(b"AutoCAD Binary DXF"):
        raise DxfError("This is a binary DXF. Please save it as ASCII DXF (AutoCAD: SAVEAS → DXF, choose ASCII).")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    if "SECTION" not in text[:5000] and "ENTITIES" not in text:
        raise DxfError("This file does not look like a DXF drawing.")

    header: dict = {}
    blocks: dict[str, list] = {}
    entities: list[dict] = []
    section = None
    cur: dict | None = None
    cur_block: str | None = None
    target: list = entities
    pending_var = None
    poly: dict | None = None

    def flush():
        nonlocal cur, poly
        if cur is None:
            return
        t = cur["type"]
        if t == "VERTEX" and poly is not None:
            poly["pts"].append((cur.get(10, 0.0), cur.get(20, 0.0)))
        elif t == "POLYLINE":
            poly = {"type": "POLY", "pts": [], "closed": bool(int(cur.get(70, 0)) & 1), "layer": cur.get(8, "")}
        elif t == "SEQEND" and poly is not None:
            target.append(poly)
            poly = None
        elif t in ("LINE", "LWPOLYLINE", "TEXT", "MTEXT", "DIMENSION", "INSERT", "ATTRIB", "ARC", "CIRCLE"):
            target.append(cur)
        cur = None

    for code, val in _pairs(text):
        if code == 0:
            flush()
            if val == "SECTION":
                section = "?"
                continue
            if val == "ENDSEC":
                section = None
                continue
            if val == "BLOCK":
                cur_block = None
                cur = {"type": "BLOCKHDR"}
                continue
            if val == "ENDBLK":
                target = entities
                cur_block = None
                continue
            if section in ("ENTITIES", "BLOCKS"):
                cur = {"type": val, "pts": [], "texts": []}
            continue
        if section == "?" and code == 2:
            section = val
            if section == "BLOCKS":
                target = entities
            continue
        if section == "HEADER":
            if code == 9:
                pending_var = val
            elif pending_var:
                header.setdefault(pending_var, val)
            continue
        if cur is None:
            continue
        if cur["type"] == "BLOCKHDR":
            if code == 2:
                cur_block = val
                blocks[cur_block] = []
                target = blocks[cur_block]
                cur = None
            continue
        if cur["type"] == "LWPOLYLINE" and code in (10, 20):
            if code == 10:
                cur["pts"].append([float(val), 0.0])
            elif cur["pts"]:
                cur["pts"][-1][1] = float(val)
            continue
        if cur["type"] == "MTEXT" and code in (1, 3):
            cur["texts"].append(val)
            continue
        if code in (10, 20, 11, 21, 13, 23, 14, 24, 40, 41, 42, 43, 50, 70, 71, 72, 73):
            try:
                cur[code] = float(val)
            except ValueError:
                pass
        elif code in (1, 2, 8):
            cur[code] = val
    flush()

    # expand INSERTs (one level deep is enough for room labels / furniture)
    expanded: list[dict] = []
    for e in entities:
        if e["type"] == "INSERT" and e.get(2) in blocks:
            bx, by = e.get(10, 0.0), e.get(20, 0.0)
            sx, sy = e.get(41, 1.0) or 1.0, e.get(42, 1.0) or 1.0
            rot = math.radians(e.get(50, 0.0))
            cr, sr = math.cos(rot), math.sin(rot)

            def tf(x, y):
                x, y = x * sx, y * sy
                return bx + x * cr - y * sr, by + x * sr + y * cr
            for b in blocks[e[2]]:
                c = dict(b)
                if b["type"] in ("LINE",):
                    c[10], c[20] = tf(b.get(10, 0), b.get(20, 0))
                    c[11], c[21] = tf(b.get(11, 0), b.get(21, 0))
                elif b["type"] in ("LWPOLYLINE", "POLY"):
                    c["pts"] = [list(tf(p[0], p[1])) for p in b["pts"]]
                elif b["type"] in ("TEXT", "MTEXT", "ATTRIB"):
                    c[10], c[20] = tf(b.get(10, 0), b.get(20, 0))
                else:
                    continue
                expanded.append(c)
        else:
            expanded.append(e)

    segs: list[tuple[float, float, float, float]] = []
    texts: list[dict] = []
    dims: list[dict] = []
    for e in expanded:
        t = e["type"]
        if t == "LINE":
            segs.append((e.get(10, 0), e.get(20, 0), e.get(11, 0), e.get(21, 0)))
        elif t in ("LWPOLYLINE", "POLY"):
            pts = e["pts"]
            closed = (bool(int(e.get(70, 0)) & 1) if t == "LWPOLYLINE" else e.get("closed"))
            for a, b in zip(pts, pts[1:] + (pts[:1] if closed else [])):
                segs.append((a[0], a[1], b[0], b[1]))
        elif t in ("TEXT", "ATTRIB"):
            s = clean_mtext((e.get(1) or "").strip())
            if s:
                h = e.get(40, 0) or 0
                if (e.get(72) or e.get(73)) and 11 in e:  # aligned text: alignment point
                    tx, ty = e.get(11, 0), e.get(21, 0)
                    if int(e.get(72) or 0) == 0:
                        tx += len(s) * h * 0.45
                else:  # left-aligned: move to the middle of the text
                    tx, ty = e.get(10, 0) + len(s) * h * 0.45, e.get(20, 0) + h * 0.4
                texts.append({"text": s, "x": tx, "y": ty, "h": h})
        elif t == "MTEXT":
            s = clean_mtext("".join(e["texts"]))
            if s:
                texts.append({"text": s, "x": e.get(10, 0), "y": e.get(20, 0), "h": e.get(40, 0)})
        elif t == "DIMENSION":
            dims.append({"value": e.get(42), "text": e.get(1, "")})
    if not segs:
        raise DxfError("No lines found in the DXF (model space is empty or uses unsupported entities).")

    # units
    unit = INSUNITS.get(int(float(header.get("$INSUNITS", 0) or 0)))
    xs = [v for s in segs for v in (s[0], s[2])]
    ys = [v for s in segs for v in (s[1], s[3])]
    extent = max(max(xs) - min(xs), max(ys) - min(ys))
    questions, warnings = [], []
    suggested = unit
    if not unit:
        size_hints = [parse_size(t["text"]) for t in texts]
        hints = [h[2] for h in size_hints if h]
        if any(h == "ft" for h in hints) and extent < 400:
            suggested = "ft"
        elif extent > 3000:
            suggested = "mm"
        elif extent > 300:
            suggested = "cm"
        elif extent > 80:
            suggested = "in"
        else:
            suggested = "m" if extent < 40 and not any(h == "ft" for h in hints) else "ft"
        questions.append(f"The DXF does not say its units. It looks like {suggested} "
                         f"(drawing is {extent:,.1f} units across) – please confirm the units.")

    labels = []
    for t in texts:
        typ = room_type(t["text"])
        if typ and len(t["text"]) <= 32 and ":" not in t["text"]:
            labels.append({**t, "type": typ})
    size_texts = [t for t in texts if parse_size(t["text"]) and not room_type(t["text"])]
    rooms_raw, unplaced = find_regions(segs, labels)
    # attach separate size texts to the room whose region contains them
    for st in size_texts:
        for r in rooms_raw:
            if r["x"] <= st["x"] <= r["x"] + r["w"] and r["y"] <= st["y"] <= r["y"] + r["d"]:
                r.setdefault("extra", []).append(st["text"])
                break
    x0, y0 = min(xs), min(ys)
    ox = min([r["x"] for r in rooms_raw], default=x0)
    oy = min([r["y"] for r in rooms_raw], default=y0)
    preview = _preview(segs, ox, oy)
    return {
        "method": "dxf", "units": suggested, "units_from_file": bool(unit), "to_ft": TO_FT.get(suggested or "ft", 1.0),
        "rooms_raw": [{**r, "x": r["x"] - ox, "y": r["y"] - oy} for r in rooms_raw],
        "unplaced": [{"text": u["text"], "type": u.get("type")} for u in unplaced],
        "texts": [t["text"] for t in texts][:200], "dimensions": dims[:200],
        "titles": [{"text": t["text"], "x": t["x"] - ox, "y": t["y"] - oy} for t in texts
                   if re.search(r"floor|stilt|terrace plan|ground|first|second|plan", t["text"], re.I) and len(t["text"]) < 60],
        "preview_raw": preview, "questions": questions, "warnings": warnings, "north_deg": find_north(texts, segs),
        "stats": {"lines": len(segs), "texts": len(texts), "labels": len(labels)},
    }


def _preview(segs, ox, oy, limit: int = 6000):
    """Longest segments first, shifted so the rooms start at 0,0 (drawing units)."""
    s = sorted(segs, key=lambda q: -abs(q[2] - q[0]) - abs(q[3] - q[1]))[:limit]
    return [[a - ox, b - oy, c - ox, d - oy] for a, b, c, d in s]
