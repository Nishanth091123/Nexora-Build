"""1.22 "exact reader": what is WRITTEN on the drawing wins over what the lines happen to measure.

Used for vector PDF and DXF (both give texts with positions + closed regions):
  1. every size text is paired with ONE room name by position (name above, size below / beside) –
     never by "which region contains the text", which fails for open plans;
  2. a room keeps the geometry of its own closed region only when that region is a clean rectangle that
     holds this room alone and matches the written size; otherwise the room is placed at its label
     with the written size ("anchored") and neighbours are pushed apart;
  3. a room with only a written WIDTH (e.g. "STAIRCASE 3'6" WIDE") is matched to a small unlabelled
     rectangular area near its name;
  4. a check list (written size vs final size) is produced – nothing is changed silently.
Units here are drawing units (points / DXF units); k = feet per unit.
"""
from __future__ import annotations

import re

from .regions import parse_size, room_type, to_ft

WIDTH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:'|ft|’)\s*(?:-?\s*(\d+(?:\.\d+)?)\s*(?:\"|”|''|in))?\s*(?:wide|width|w\b)", re.I)


def parse_width(text: str) -> float | None:
    """'3'6" WIDE (EXT.)' → 3.5 (feet); None when no width is written."""
    m = WIDTH_RE.search((text or "").replace("’", "'").replace("”", '"'))
    if not m:
        return None
    return float(m.group(1)) + (float(m.group(2)) / 12 if m.group(2) else 0)


def _clean(texts: list[dict]) -> list[dict]:
    return [t for t in texts if len(t["text"].strip()) > 2 or parse_size(t["text"])]


def pair_sizes(labels: list[dict], texts: list[dict], ext: float) -> dict[int, dict]:
    """label index → the size / width text that belongs to it (one-to-one, nearest first, name above size)."""
    sizes = [t for t in _clean(texts) if (parse_size(t["text"]) or parse_width(t["text"])) and not room_type(t["text"])]
    # a label that carries its own size ("KITCHEN 9'3" X 10'4"") needs no partner
    own = {i for i, lb in enumerate(labels) if parse_size(lb["text"])}
    cands = []
    dxmax, dymax = ext * 0.10, ext * 0.07
    for i, lb in enumerate(labels):
        if i in own:
            continue
        for j, s in enumerate(sizes):
            dx, dy = abs(s["x"] - lb["x"]), lb["y"] - s["y"]  # dy > 0: size is below the name
            if dx > dxmax or dy > dymax or dy < -dymax * 0.6:
                continue
            cands.append((dx + (dy if dy >= 0 else -dy * 2.5) * 1.3, i, j))
    cands.sort()
    out, used = {}, set()
    for _, i, j in cands:
        if i in out or j in used:
            continue
        out[i] = sizes[j]
        used.add(j)
    return out


def _written(room: dict) -> tuple[float | None, float | None, float | None]:
    """(a, b, width) in the units of the text: a × b as written, or only a width."""
    for t in [room["label"]] + room.get("extra", []):
        ps = parse_size(t)
        if ps:
            hint = ps[2].rstrip("?") if ps[2] != "ft?" else "ft"
            return to_ft(ps[0], hint), to_ft(ps[1], hint), None
    for t in [room["label"]] + room.get("extra", []):
        w = parse_width(t)
        if w:
            return None, None, w
    return None, None, None


def estimate_scale(rooms: list[dict]) -> float | None:
    """feet per drawing unit from rooms that stand alone in a clean rectangle."""
    ratios = []
    for r in rooms:
        if r.get("shared") or not r.get("rectangular", True):
            continue
        a, b, _ = _written(r)
        if not a or r["w"] <= 0 or r["d"] <= 0:
            continue
        k1, k2 = (a / r["w"] + b / r["d"]) / 2, (b / r["w"] + a / r["d"]) / 2
        s1, s2 = abs(a / r["w"] - b / r["d"]), abs(b / r["w"] - a / r["d"])
        ratios.append((min(s1, s2) / max(k1, k2, 1e-9), k1 if s1 <= s2 else k2))
    if not ratios:
        return None
    good = sorted(v for e, v in ratios if e < 0.12) or sorted(v for _, v in ratios)
    return good[len(good) // 2]


def _treads(segs: list, width_u: float, lx: float, ly: float):
    """Stair steps drawn as many equal horizontal lines (≈ the written width) one above the other → (x, y, w, d)."""
    fam: dict[tuple[int, int], list[float]] = {}
    for x1, y1, x2, y2 in segs:
        if abs(y1 - y2) <= 0.02 * abs(x2 - x1) and abs(abs(x2 - x1) - width_u) <= 0.12 * width_u:
            fam.setdefault((round(min(x1, x2) / 2), round(max(x1, x2) / 2)), []).append(((y1 + y2) / 2, min(x1, x2), max(x1, x2)))
    best = None
    for lines in fam.values():
        ys = sorted({round(l[0], 1) for l in lines})
        if len(ys) < 4:
            continue
        x0 = sum(l[1] for l in lines) / len(lines)
        x1 = sum(l[2] for l in lines) / len(lines)
        cx, cy = (x0 + x1) / 2, (ys[0] + ys[-1]) / 2
        dist = ((cx - lx) ** 2 + (cy - ly) ** 2) ** 0.5
        if best is None or dist < best[0]:
            best = (dist, (x0, ys[0], x1 - x0, ys[-1] - ys[0]))
    return best[1] if best else None


def _stacks(regs: list[dict]) -> list[dict]:
    """Unlabelled rectangles, plus stacks of same-width rectangles on top of each other (stair treads drawn as lines)."""
    out = [{**g, "ids": [g["id"]]} for g in regs]
    cols: dict[tuple[int, int], list[dict]] = {}
    for g in regs:
        cols.setdefault((round(g["x"] / max(g["w"], 1) * 4), round(g["w"])), []).append(g)
    for lst in cols.values():
        lst.sort(key=lambda g: g["y"])
        chain = [lst[0]]
        for g in lst[1:] + [None]:
            if g is not None and abs(g["y"] - (chain[-1]["y"] + chain[-1]["d"])) <= 0.03 * max(chain[-1]["d"], 1) + 0.5 \
                    and abs(g["x"] - chain[0]["x"]) <= 0.5:
                chain.append(g)
                continue
            if len(chain) > 1:
                out.append({"id": chain[0]["id"], "ids": [c["id"] for c in chain], "x": chain[0]["x"], "y": chain[0]["y"],
                            "w": chain[0]["w"], "d": chain[-1]["y"] + chain[-1]["d"] - chain[0]["y"], "fill": 1.0})
            chain = [g] if g is not None else []
    return out


def refine(rooms: list[dict], regions: list[dict], k: float, notes: list[str], segs: list | None = None) -> bool:
    """Replace measured boxes by the written sizes (see module doc). rooms are modified in place (drawing units)."""
    if not k or k <= 0:
        return False
    outer = [r for r in regions if not r.get("outside")]
    if not outer:
        return False
    bx0, by0 = min(r["x"] for r in outer), min(r["y"] for r in outer)
    bx1, by1 = max(r["x"] + r["w"] for r in outer), max(r["y"] + r["d"] for r in outer)
    used_regions = {r["region"] for r in rooms}
    moved: list[dict] = []
    for r in rooms:
        a, b, width = _written(r)
        mw, md = r["w"] * k, r["d"] * k
        r["rigid"] = False
        if a and b:
            # written order is "horizontal × vertical" as drawn; flip if the box says otherwise
            if abs(mw - a) + abs(md - b) <= abs(mw - b) + abs(md - a):
                ww, wd = a, b
            else:
                ww, wd = b, a
            clean = (not r.get("shared") and r.get("rectangular", True)
                     and abs(mw - ww) <= max(0.75, 0.12 * ww) and abs(md - wd) <= max(0.75, 0.12 * wd))
            if clean:
                cx, cy = r["x"] + r["w"] / 2, r["y"] + r["d"] / 2
                r["rigid"] = True  # the closed region IS this room: keep its position
            else:
                sx, sy = r.get("size_xy") or (r["lx"], r["ly"])
                cx, cy = (r["lx"] + sx) / 2, (r["ly"] + sy) / 2
                # keep the room inside the area drawn for it (open plan: its part of the shared area) when it fits
                if ww / k <= r["w"] and wd / k <= r["d"]:
                    cx = min(max(cx, r["x"] + ww / k / 2), r["x"] + r["w"] - ww / k / 2)
                    cy = min(max(cy, r["y"] + wd / k / 2), r["y"] + r["d"] - wd / k / 2)
                moved.append(r)
                r["anchored"] = True
            if not clean:
                notes.append(f"{r['label'].title()}: the walls drawn for it measure about {mw:.1f}' × {md:.1f}' but "
                             f"{ww:.2f}' × {wd:.2f}' is written – the written size is used.")
            r["w"], r["d"] = ww / k, wd / k
            r["x"], r["y"] = cx - r["w"] / 2, cy - r["d"] / 2
            r["exact_size"] = True
        elif width:
            # only a width is written (external staircase): find the small unlabelled rectangle next to the name
            best = None
            tr = _treads(segs or [], width / k, r["lx"], r["ly"])
            if tr:
                best = (0.0, {"id": -1, "ids": [], "x": tr[0], "y": tr[1], "w": tr[2], "d": tr[3]})
            for g in ([] if best else _stacks([g for g in regions if g["id"] not in used_regions and not g.get("outside")
                              and g["fill"] >= 0.92])):
                gw, gd = g["w"] * k, g["d"] * k
                short, long_ = min(gw, gd), max(gw, gd)
                if abs(short - width) > max(0.6, 0.2 * width) or long_ < short * 1.2:
                    continue
                dist = ((g["x"] + g["w"] / 2 - r["lx"]) ** 2 + (g["y"] + g["d"] / 2 - r["ly"]) ** 2) ** 0.5
                if best is None or dist < best[0]:
                    best = (dist, g)
            if best:
                g = best[1]
                r["x"], r["y"], r["w"], r["d"] = g["x"], g["y"], g["w"], g["d"]
                r["rigid"] = True
                r["rectangular"] = True
                r["shared"] = False
                r["extra"] = list(r.get("extra", [])) + [f"{width:g}' wide"]
                r["width_only"] = width
                used_regions.update(g["ids"])
            else:
                notes.append(f"{r['label'].title()}: only the width ({width:g}') is written and no matching area was found – "
                             "please enter its length.")
    # push anchored rooms away from whatever they overlap (rigid rooms and already placed rooms stay)
    fixed = [r for r in rooms if r not in moved]
    for _ in range(12):
        changed = False
        for r in moved:
            for o in rooms:
                if o is r:
                    continue
                ox = min(r["x"] + r["w"], o["x"] + o["w"]) - max(r["x"], o["x"])
                oy = min(r["y"] + r["d"], o["y"] + o["d"]) - max(r["y"], o["y"])
                if ox > 0.02 * r["w"] and oy > 0.02 * r["d"]:
                    pen = k * min(ox, oy)
                    if pen < 0.05:
                        continue
                    share = 0.5 if (o in moved) else 1.0
                    if ox < oy:
                        r["x"] += (-ox if (r["x"] + r["w"] / 2) < (o["x"] + o["w"] / 2) else ox) * share
                    else:
                        r["y"] += (-oy if (r["y"] + r["d"] / 2) < (o["y"] + o["d"] / 2) else oy) * share
                    changed = True
            r["x"] = min(max(r["x"], bx0), max(bx0, bx1 - r["w"]))
            r["y"] = min(max(r["y"], by0), max(by0, by1 - r["d"]))
        if not changed:
            break
    del fixed
    return True


def overlaps(rooms: list[dict], k: float) -> list[str]:
    out = []
    for i, a in enumerate(rooms):
        for b in rooms[i + 1:]:
            ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            oy = min(a["y"] + a["d"], b["y"] + b["d"]) - max(a["y"], b["y"])
            if ox * k > 0.5 and oy * k > 0.5:
                out.append(f"{a['label'].title()} and {b['label'].title()} overlap by {ox * k:.1f}' × {oy * k:.1f}' – "
                           "check their position in the 2D editor.")
    return out
