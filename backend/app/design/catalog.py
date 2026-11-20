"""1.27 – Design catalog: elevation styles (1,600 combinations) and interior designs (wardrobe, TV unit, modular kitchen,
pooja unit, false ceiling – 660 combinations), each with a drawn picture made by Nexora itself (original, no copied photos).

Elevation pictures are drawn on the proportions of the project's own drawing (width, number of floors).
Choosing an elevation writes the colours + a small "elev" record into the plan, so the 2D front elevation, the 3D model and the
PDFs all follow it. Choosing an interior design stores a pick per room; the interior estimate then uses the design's price tier
(economy -> low, standard -> default, premium -> high of the searched rate) and its layout for the quantity.
A picture can be turned into a photo-like image with the existing free AI render (Design -> 3D uses the same service).
"""
from __future__ import annotations

import itertools
import math
import random

# ---------------------------------------------------------------- tiny drawing scene (one picture -> SVG or PDF)
class Scene:
    def __init__(self, w: float, h: float, bg: str | None = "#f8fafc"):
        self.w, self.h, self.bg, self.items = w, h, bg, []

    def rect(self, x, y, w, h, fill=None, stroke=None, sw=0.07, op=1.0):
        self.items.append(("r", x, y, w, h, fill, stroke, sw, op))

    def line(self, x1, y1, x2, y2, stroke="#334155", sw=0.06):
        self.items.append(("l", x1, y1, x2, y2, stroke, sw))

    def circle(self, cx, cy, r, fill=None, stroke=None, sw=0.06, op=1.0):
        self.items.append(("c", cx, cy, r, fill, stroke, sw, op))

    def poly(self, pts, fill=None, stroke=None, sw=0.06, op=1.0):
        self.items.append(("p", pts, fill, stroke, sw, op))

    def text(self, x, y, s, size=0.9, fill="#334155", anchor="middle"):
        self.items.append(("t", x, y, s, size, fill, anchor))

    # ---- SVG
    def svg(self, px: int = 360) -> str:
        k = px / self.w
        H = self.h * k
        Y = lambda y: round((self.h - y) * k, 2)  # noqa: E731
        X = lambda x: round(x * k, 2)             # noqa: E731
        o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {px} {round(H, 1)}" width="{px}" height="{round(H, 1)}" '
             f'font-family="Helvetica,Arial,sans-serif">']
        if self.bg:
            o.append(f'<rect width="{px}" height="{round(H, 1)}" fill="{self.bg}"/>')
        for it in self.items:
            t = it[0]
            if t == "r":
                _, x, y, w, h, fill, stroke, sw, op = it
                o.append(f'<rect x="{X(x)}" y="{Y(y + h)}" width="{round(w * k, 2)}" height="{round(h * k, 2)}" fill="{fill or "none"}" '
                         f'{f"stroke={chr(34)}{stroke}{chr(34)} stroke-width={chr(34)}{round(sw * k, 2)}{chr(34)}" if stroke else ""}'
                         f'{f" opacity={chr(34)}{op}{chr(34)}" if op != 1 else ""}/>')
            elif t == "l":
                _, x1, y1, x2, y2, stroke, sw = it
                o.append(f'<line x1="{X(x1)}" y1="{Y(y1)}" x2="{X(x2)}" y2="{Y(y2)}" stroke="{stroke}" stroke-width="{round(sw * k, 2)}"/>')
            elif t == "c":
                _, cx, cy, r, fill, stroke, sw, op = it
                o.append(f'<circle cx="{X(cx)}" cy="{Y(cy)}" r="{round(r * k, 2)}" fill="{fill or "none"}" '
                         f'{f"stroke={chr(34)}{stroke}{chr(34)} stroke-width={chr(34)}{round(sw * k, 2)}{chr(34)}" if stroke else ""}'
                         f'{f" opacity={chr(34)}{op}{chr(34)}" if op != 1 else ""}/>')
            elif t == "p":
                _, pts, fill, stroke, sw, op = it
                o.append(f'<polygon points="{" ".join(f"{X(a)},{Y(b)}" for a, b in pts)}" fill="{fill or "none"}" '
                         f'{f"stroke={chr(34)}{stroke}{chr(34)} stroke-width={chr(34)}{round(sw * k, 2)}{chr(34)}" if stroke else ""}'
                         f'{f" opacity={chr(34)}{op}{chr(34)}" if op != 1 else ""}/>')
            else:
                _, x, y, s, size, fill, anchor = it
                a = {"middle": "middle", "start": "start", "end": "end"}[anchor]
                s = str(s).replace("&", "&amp;").replace("<", "&lt;")
                o.append(f'<text x="{X(x)}" y="{Y(y)}" font-size="{round(size * k, 2)}" fill="{fill}" text-anchor="{a}">{s}</text>')
        o.append("</svg>")
        return "".join(o)

    # ---- reportlab (fit inside the box, bottom-left x, y)
    def pdf(self, c, x: float, y: float, w: float, h: float):
        from reportlab.lib import colors
        k = min(w / self.w, h / self.h)
        ox, oy = x + (w - self.w * k) / 2, y + (h - self.h * k) / 2
        HX = colors.HexColor
        if self.bg:
            c.setFillColor(HX(self.bg))
            c.rect(ox, oy, self.w * k, self.h * k, fill=1, stroke=0)
        for it in self.items:
            t = it[0]
            if t in ("r", "c", "p"):
                fill, stroke, sw, op = (it[5], it[6], it[7], it[8]) if t == "r" else (it[4], it[5], it[6], it[7]) if t == "c" else (it[2], it[3], it[4], it[5])
                c.saveState()
                c.setFillAlpha(op)
                if fill:
                    c.setFillColor(HX(fill))
                if stroke:
                    c.setStrokeColor(HX(stroke))
                    c.setLineWidth(max(0.3, sw * k))
                if t == "r":
                    c.rect(ox + it[1] * k, oy + it[2] * k, it[3] * k, it[4] * k, fill=1 if fill else 0, stroke=1 if stroke else 0)
                elif t == "c":
                    c.circle(ox + it[1] * k, oy + it[2] * k, it[3] * k, fill=1 if fill else 0, stroke=1 if stroke else 0)
                else:
                    p = c.beginPath()
                    pts = it[1]
                    p.moveTo(ox + pts[0][0] * k, oy + pts[0][1] * k)
                    for a, b in pts[1:]:
                        p.lineTo(ox + a * k, oy + b * k)
                    p.close()
                    c.drawPath(p, fill=1 if fill else 0, stroke=1 if stroke else 0)
                c.restoreState()
            elif t == "l":
                c.setStrokeColor(HX(it[5]))
                c.setLineWidth(max(0.3, it[6] * k))
                c.line(ox + it[1] * k, oy + it[2] * k, ox + it[3] * k, oy + it[4] * k)
            else:
                c.setFillColor(HX(it[5]))
                c.setFont("Helvetica", max(4, it[4] * k))
                s = str(it[3])
                if it[6] == "middle":
                    c.drawCentredString(ox + it[1] * k, oy + it[2] * k, s)
                elif it[6] == "end":
                    c.drawRightString(ox + it[1] * k, oy + it[2] * k, s)
                else:
                    c.drawString(ox + it[1] * k, oy + it[2] * k, s)


# ================================================================ ELEVATION
# name: (outer wall, trim / bands, door, plinth, roof, accent)
PALETTES = {
    "classic_white": ("Classic white", "#F5F5F4", "#A8A29E", "#92400E", "#78716C", "#B91C1C", "#9CA3AF"),
    "warm_beige": ("Warm beige", "#E7D8C0", "#FAF5EB", "#7C4A21", "#8B7355", "#9A3412", "#B08968"),
    "grey_modern": ("Grey modern", "#CBD5E1", "#F1F5F9", "#334155", "#475569", "#334155", "#64748B"),
    "terracotta": ("Terracotta", "#D9845B", "#FDEBD8", "#5C3317", "#7C4A21", "#9A3412", "#B45309"),
    "olive_green": ("Olive green", "#B7C298", "#F3F4E8", "#4D3B1F", "#5F6B3A", "#365314", "#78903B"),
    "pastel_blue": ("Pastel blue", "#BFD8EA", "#F8FAFC", "#7C4A21", "#64748B", "#1E3A8A", "#3B82F6"),
    "sand_yellow": ("Sand yellow", "#F2DC9B", "#FFFBEB", "#7C4A21", "#A16207", "#92400E", "#D97706"),
    "charcoal": ("Charcoal contrast", "#E5E7EB", "#374151", "#1F2937", "#374151", "#111827", "#1F2937"),
    "brick_red": ("Brick red", "#C6694B", "#F5E6D3", "#4A2511", "#6B3A1F", "#7F1D1D", "#9A3412"),
    "ivory_gold": ("Ivory & gold", "#F8F1DC", "#C9A24A", "#5B3A12", "#8A7A52", "#7C2D12", "#C9A24A"),
}
TOPS = {"plain": "Plain parapet", "stepped": "Stepped parapet", "jali": "Jali parapet", "glass": "Glass railing parapet", "pergola": "Pergola top"}
CLADS = {"none": "Plain walls", "stone": "Stone feature wall", "wood": "Wood-texture feature wall", "brick": "Brick-tile feature wall"}
WINS = {"plain": "Plain windows", "frame": "Framed windows", "arch": "Arched windows", "louver": "Louvre windows"}
CANOPY = {"none": "No canopy", "slab": "Door canopy slab"}
FAM_TITLE = {"basic": "Basic", "modern": "Modern", "contemporary": "Contemporary", "traditional": "Traditional", "luxury": "Luxury"}


def family(top: str, clad: str, win: str, canopy: str) -> str:
    if win == "arch" or clad == "brick":
        return "traditional"
    if clad == "stone" and (top in ("stepped", "glass") or canopy == "slab"):
        return "luxury"
    if top in ("pergola", "glass") or clad == "wood":
        return "contemporary"
    if top in ("stepped", "jali") or win in ("frame", "louver") or canopy == "slab":
        return "modern"
    return "basic"


def _elev_all() -> list[dict]:
    rows = []
    for i, (t, c_, w, k, pal) in enumerate(itertools.product(TOPS, CLADS, WINS, CANOPY, PALETTES)):
        fam = family(t, c_, w, k)
        rows.append({"top": t, "clad": c_, "win": w, "canopy": k, "palette": pal, "family": fam,
                     "name": f"{FAM_TITLE[fam]} - {PALETTES[pal][0]} - {TOPS[t].lower()}, {CLADS[c_].lower()}, {WINS[w].lower()}"})
    random.Random(27).shuffle(rows)
    for i, r in enumerate(rows, 1):
        r["id"] = f"E{i:04d}"
    return rows


_ELEV = _elev_all()
_ELEV_BY_ID = {r["id"]: r for r in _ELEV}


def elevation_facets() -> dict:
    return {"families": [{"id": k, "label": v} for k, v in FAM_TITLE.items()],
            "palettes": [{"id": k, "label": v[0], "ext": v[1], "trim": v[2], "door": v[3]} for k, v in PALETTES.items()],
            "tops": [{"id": k, "label": v} for k, v in TOPS.items()], "claddings": [{"id": k, "label": v} for k, v in CLADS.items()],
            "windows": [{"id": k, "label": v} for k, v in WINS.items()], "total": len(_ELEV)}


def elevation_list(family_: str = "", palette: str = "", top: str = "", clad: str = "", win: str = "", page: int = 1, size: int = 24) -> dict:
    rows = [r for r in _ELEV if (not family_ or r["family"] == family_) and (not palette or r["palette"] == palette)
            and (not top or r["top"] == top) and (not clad or r["clad"] == clad) and (not win or r["win"] == win)]
    size = max(6, min(60, size))
    page = max(1, page)
    return {"total": len(rows), "page": page, "size": size, "items": rows[(page - 1) * size: page * size]}


def elevation_get(eid: str) -> dict | None:
    return _ELEV_BY_ID.get(eid)


def _stone_lines(S, x, y, w, h, kind):
    if kind == "wood":
        xx = x + 0.5
        while xx < x + w:
            S.line(xx, y, xx, y + h, "#7c2d12", 0.05)
            xx += 0.5
        return
    gap = 1.0 if kind == "stone" else 0.5
    jw = 1.8 if kind == "stone" else 1.1
    yy, row = y + gap, 0
    while yy < y + h:
        S.line(x, yy, x + w, yy, "#475569" if kind == "stone" else "#7f1d1d", 0.04)
        xx = x + (jw / 2 if row % 2 else jw)
        while xx < x + w:
            S.line(xx, yy - gap, xx, yy, "#475569" if kind == "stone" else "#7f1d1d", 0.04)
            xx += jw
        yy += gap
        row += 1


def draw_elevation(p: dict, bw: float = 30.0, n: int = 2, door_at: float = 0.5) -> Scene:
    """One elevation picture on the project's proportions (bw = building width in ft, n = floors)."""
    pal = PALETTES[p["palette"]]
    ext, trim, door, plinth, roof_c, accent = pal[1], pal[2], pal[3], pal[4], pal[5], pal[6]
    bw = max(16.0, min(60.0, float(bw)))
    n = max(1, min(4, int(n)))
    FH, SL, PL, X0, G = 10.0, 0.7, 1.5, 8.0, 1.0
    roof = G + PL + n * (FH + SL)
    S = Scene(bw + 16, roof + 14, "#E0F2FE")
    S.rect(0, 0, S.w, G, "#A8A29E")
    S.rect(0, G, S.w, 0.15, "#78716C")
    S.rect(X0, G, bw, PL, plinth, "#44403c", 0.05)
    k = max(2, round(bw / 8))
    slot = bw / k
    ds = min(k - 1, max(0, int(door_at * k)))
    band_w = 4.5
    band_x = X0 + bw - band_w - 0.3 if ds < k / 2 else X0 + 0.3
    z_top = roof
    for i in range(n):
        z0 = G + PL + i * (FH + SL)
        S.rect(X0, z0, bw, FH, ext, "#44403c", 0.05)
        S.rect(X0 - 0.4, z0 + FH, bw + 0.8, SL, trim, "#44403c", 0.04)
        for j in range(k):
            cx = X0 + (j + 0.5) * slot
            if p["clad"] != "none" and band_x - 1.6 < cx < band_x + band_w + 1.6:
                continue
            if i == 0 and j == ds:
                dw = 3.6
                S.rect(cx - dw / 2 - 0.25, z0, dw + 0.5, 7.4, trim, "#44403c", 0.04)
                S.rect(cx - dw / 2, z0, dw, 7.0, door, "#292524", 0.05)
                S.line(cx, z0, cx, z0 + 7.0, "#1c1917", 0.05)
                for q in (0.28, 0.6):
                    S.rect(cx - dw / 2 + 0.25, z0 + 7.0 * q, dw / 2 - 0.5, 1.7, None, "#1c1917", 0.04)
                    S.rect(cx + 0.25, z0 + 7.0 * q, dw / 2 - 0.5, 1.7, None, "#1c1917", 0.04)
                S.circle(cx - 0.35, z0 + 3.4, 0.14, "#fde68a")
                S.circle(cx + 0.35, z0 + 3.4, 0.14, "#fde68a")
                if p["canopy"] == "slab":
                    S.rect(cx - dw / 2 - 1.6, z0 + 7.9, dw + 3.2, 0.55, trim, "#44403c", 0.05)
                continue
            ww = min(4.5, slot * 0.55)
            wh = 4.5
            sz = z0 + 3.0
            wx = cx - ww / 2
            if p["win"] == "frame":
                S.rect(wx - 0.4, sz - 0.4, ww + 0.8, wh + 0.8, trim, "#44403c", 0.04)
            if p["win"] == "arch":
                S.rect(wx, sz, ww, wh - ww / 2, "#BAE6FD", "#1c1917", 0.05)
                pts = [(cx + math.cos(math.radians(a)) * ww / 2, sz + wh - ww / 2 + math.sin(math.radians(a)) * ww / 2) for a in range(0, 181, 12)]
                S.poly(pts, "#BAE6FD", "#1c1917", 0.05)
                S.line(cx, sz, cx, sz + wh, "#1c1917", 0.05)
            else:
                S.rect(wx, sz, ww, wh, "#BAE6FD", "#1c1917", 0.05)
                S.line(cx, sz, cx, sz + wh, "#1c1917", 0.05)
            if p["win"] == "louver":
                yy = sz + 0.5
                while yy < sz + wh:
                    S.line(wx, yy, wx + ww, yy, "#334155", 0.05)
                    yy += 0.5
            S.rect(wx - 0.3, sz - 0.28, ww + 0.6, 0.28, trim, "#44403c", 0.03)
            if p["win"] in ("plain", "louver"):
                S.rect(wx - 0.6, sz + wh + 0.25, ww + 1.2, 0.25, trim, "#44403c", 0.03)
    if p["clad"] != "none":
        cc = {"stone": "#9CA3AF", "wood": "#B4783C", "brick": "#B4532A"}[p["clad"]]
        S.rect(band_x, G + PL, band_w, roof - G - PL, cc, "#44403c", 0.05)
        _stone_lines(S, band_x, G + PL, band_w, roof - G - PL, p["clad"])
    # top treatment
    pr = 3.0
    if p["top"] == "jali":
        S.rect(X0, roof, bw, 1.0, ext, "#44403c", 0.05)
        S.rect(X0, roof + 1.0, bw, 2.0, "#E7E5E4", "#44403c", 0.05)
        xx = X0 + 0.5
        while xx < X0 + bw - 0.3:
            S.rect(xx, roof + 1.2, 0.3, 1.6, "#94A3B8")
            xx += 0.8
    elif p["top"] == "glass":
        S.rect(X0, roof, bw, 1.2, ext, "#44403c", 0.05)
        S.rect(X0, roof + 1.2, bw, 2.4, "#7DD3FC", "#334155", 0.05, 0.55)
        xx = X0
        while xx <= X0 + bw + 0.01:
            S.line(xx, roof + 1.2, xx, roof + 3.6, "#334155", 0.05)
            xx += bw / max(4, round(bw / 5))
        S.line(X0, roof + 3.6, X0 + bw, roof + 3.6, "#334155", 0.12)
    else:
        S.rect(X0, roof, bw, pr, ext, "#44403c", 0.05)
    if p["top"] == "stepped":
        S.rect(X0, roof + pr, bw * 0.4, 2.6, ext, "#44403c", 0.05)
        S.rect(X0 - 0.3, roof + pr + 2.6, bw * 0.4 + 0.6, 0.4, trim, "#44403c", 0.04)
    if p["top"] != "glass":
        S.rect(X0 - 0.3, roof + (pr if p["top"] != "jali" else 3.0), bw + 0.6, 0.4, trim, "#44403c", 0.04)
    if p["top"] == "pergola":
        pw = bw * 0.45
        for xx in (X0 + 0.3, X0 + pw - 0.6):
            S.rect(xx, roof + pr, 0.35, 8.0, "#7C2D12")
        S.rect(X0, roof + pr + 7.6, pw, 0.5, "#92400E", "#44403c", 0.04)
        xx = X0 + 0.4
        while xx < X0 + pw:
            S.rect(xx, roof + pr + 8.1, 0.3, 0.5, "#B45309")
            xx += 0.9
    elif n > 1:
        S.rect(X0 + bw - 9, roof + pr, 7, 7.5, ext, "#44403c", 0.05)
        S.rect(X0 + bw - 9.5, roof + pr + 7.5, 8, 0.5, trim, "#44403c", 0.04)
    # trees
    for tx in (3.2, S.w - 3.2):
        S.rect(tx - 0.2, G, 0.4, 3.5, "#78350F")
        S.circle(tx, G + 5.2, 2.4, "#4D7C0F", None, op=0.9)
    S.text(S.w / 2, 0.15, "Front elevation (road side) - style picture, not to scale", 0.75, "#44403c")
    return S


def elevation_apply(plan: dict, eid: str) -> dict:
    """Write the chosen elevation into the plan: finishes (colours + 3D style) and the 'elev' record. Returns notes."""
    e = _ELEV_BY_ID.get(eid)
    if not e:
        raise ValueError("Unknown elevation style")
    pal = PALETTES[e["palette"]]
    fin = dict(plan.get("finishes") or {})
    fin.update({"ext": pal[1], "frame": pal[2], "door": pal[3], "plinth": pal[4], "roof": pal[5], "style": e["family"]})
    plan["finishes"] = fin
    plan["elev"] = {k: e[k] for k in ("id", "top", "clad", "win", "canopy", "palette", "family", "name")}
    notes = []
    if e["clad"] != "none":
        h = sum(10.7 for _ in plan["levels"])
        notes.append(f"{CLADS[e['clad']]}: about {4.5 * h:.0f} sq ft of cladding (4.5 ft wide x {h:.0f} ft high) - add its rate to the estimate extras.")
    if e["top"] == "pergola":
        notes.append("Pergola top: about 0.45 of the width, 8 ft high on the terrace - needs a structural check of the terrace slab.")
    return {"elevation": plan["elev"], "notes": notes}


def clean_elev(v) -> dict | None:
    """Used by the plan checker: keep only known values."""
    if not isinstance(v, dict):
        return None
    ok = (v.get("top") in TOPS and v.get("clad") in CLADS and v.get("win") in WINS and v.get("canopy") in CANOPY and v.get("palette") in PALETTES)
    if not ok:
        return None
    fam = family(v["top"], v["clad"], v["win"], v["canopy"])
    return {"id": str(v.get("id", ""))[:6], "top": v["top"], "clad": v["clad"], "win": v["win"], "canopy": v["canopy"],
            "palette": v["palette"], "family": fam, "name": str(v.get("name", ""))[:140]}


# ================================================================ INTERIOR DESIGNS
SCHEMES = {  # name: (body, accent, handle)
    "walnut": ("Walnut", "#7B4B2A", "#D9B382", "#F5D0A0"),
    "oak": ("Natural oak", "#C79B63", "#8A6A3E", "#5B4326"),
    "white": ("White gloss", "#F3F4F6", "#CBD5E1", "#64748B"),
    "grey": ("Slate grey", "#6B7280", "#D1D5DB", "#F3F4F6"),
    "navy": ("Navy blue", "#1E3A8A", "#E5E7EB", "#FDE68A"),
    "sage": ("Sage green", "#8FA98A", "#F5F1E6", "#5B4326"),
}
TIER = {"economy": 0, "standard": 1, "premium": 2}
WARD_DOOR = {"hinged": "Hinged shutters", "sliding": "Sliding doors", "walkin": "Walk-in (open L)", "loft": "Hinged with loft"}
WARD_FIN = {"laminate": ("Laminate", "economy"), "acrylic": ("Acrylic gloss", "standard"), "glass": ("Back-painted glass", "premium"),
            "fluted": ("Fluted / reeded", "premium")}
TV_STYLE = {"floating": "Floating unit", "fullwall": "Full-wall unit", "niche": "Unit with niches", "panel": "Panel with ledge"}
TV_PANEL = {"plain": ("Plain panel", "economy"), "fluted": ("Fluted panel", "standard"), "stone": ("Stone / marble look", "premium")}
KIT_LAYOUT = {"straight": "Straight", "l": "L-shaped", "u": "U-shaped", "parallel": "Parallel", "island": "Island"}
KIT_FIN = {"laminate": ("Laminate", "economy"), "acrylic": ("Acrylic gloss", "standard"), "pu": ("Matte PU", "premium")}
KIT_TOP = {"granite": "Granite counter", "quartz": "Quartz counter"}
POOJA = {"niche": "Wall niche", "arch": "Arch mandir", "jali": "Jali panel mandir", "glass": "Glass-door cabinet"}
POOJA_FIN = {"wood": ("Teak / wood", "standard"), "white": ("White with brass", "standard"), "marble": ("Marble backed", "premium")}
CEIL = {"flat": "Flat gypsum", "cove": "Cove / peripheral", "coffer": "Coffered grid", "strip": "Wooden strip ceiling"}
CEIL_LIGHT = {"warm": ("Warm cove light", "standard"), "cool": ("Cool-white cove light", "standard"), "spot": ("Spot lights only", "economy")}

TYPES = {"wardrobe": "Wardrobe", "tv_unit": "TV unit", "kitchen": "Modular kitchen", "pooja": "Pooja unit", "ceiling": "False ceiling"}
PRICE_KEY = {"wardrobe": "wardrobe", "tv_unit": "tv_unit", "kitchen": "kitchen_cabinet"}   # priced by the interior estimate
ROOM_FOR = {"wardrobe": ("bedroom",), "tv_unit": ("hall", "lounge"), "kitchen": ("kitchen",), "pooja": ("pooja", "hall", "dining"),
            "ceiling": ("hall", "lounge", "bedroom", "dining")}


def _interior_all() -> list[dict]:
    rows = []
    for d_, f, loft, sc in itertools.product(WARD_DOOR, WARD_FIN, (0, 1), SCHEMES):
        if d_ == "loft" and loft == 0:
            continue
        rows.append({"type": "wardrobe", "door": d_, "fin": f, "loft": loft or (1 if d_ == "loft" else 0), "scheme": sc, "tier": WARD_FIN[f][1],
                     "name": f"{SCHEMES[sc][0]} {WARD_FIN[f][0].lower()} wardrobe - {WARD_DOOR[d_].lower()}{', with loft' if (loft or d_ == 'loft') else ''}"})
    for s_, pn, bl, sc in itertools.product(TV_STYLE, TV_PANEL, (0, 1), SCHEMES):
        rows.append({"type": "tv_unit", "style": s_, "panel": pn, "light": bl, "scheme": sc, "tier": TV_PANEL[pn][1],
                     "name": f"{SCHEMES[sc][0]} {TV_STYLE[s_].lower()} - {TV_PANEL[pn][0].lower()}{', back-lit' if bl else ''}"})
    for ly, f, tp, sc in itertools.product(KIT_LAYOUT, KIT_FIN, KIT_TOP, SCHEMES):
        rows.append({"type": "kitchen", "layout": ly, "fin": f, "top": tp, "scheme": sc, "tier": KIT_FIN[f][1] if tp == "granite" else
                     ("premium" if KIT_FIN[f][1] != "economy" else "standard"),
                     "name": f"{KIT_LAYOUT[ly]} kitchen - {SCHEMES[sc][0].lower()} {KIT_FIN[f][0].lower()}, {KIT_TOP[tp].lower()}"})
    for st, f, sc in itertools.product(POOJA, POOJA_FIN, SCHEMES):
        rows.append({"type": "pooja", "style": st, "fin": f, "scheme": sc, "tier": POOJA_FIN[f][1],
                     "name": f"{POOJA[st]} - {POOJA_FIN[f][0].lower()}, {SCHEMES[sc][0].lower()}"})
    for cs, lt, sc in itertools.product(CEIL, CEIL_LIGHT, SCHEMES):
        rows.append({"type": "ceiling", "style": cs, "light": lt, "scheme": sc, "tier": CEIL_LIGHT[lt][1],
                     "name": f"{CEIL[cs]} ceiling - {CEIL_LIGHT[lt][0].lower()}, {SCHEMES[sc][0].lower()} accent"})
    random.Random(28).shuffle(rows)
    for i, r in enumerate(rows, 1):
        r["id"] = f"I{i:04d}"
    return rows


_INT = _interior_all()
_INT_BY_ID = {r["id"]: r for r in _INT}


def interior_get(did: str) -> dict | None:
    return _INT_BY_ID.get(did)


def interior_facets() -> dict:
    return {"types": [{"id": k, "label": v} for k, v in TYPES.items()],
            "schemes": [{"id": k, "label": v[0], "color": v[1]} for k, v in SCHEMES.items()],
            "tiers": ["economy", "standard", "premium"], "total": len(_INT),
            "counts": {t: sum(1 for r in _INT if r["type"] == t) for t in TYPES}}


def interior_list(type_: str = "", scheme: str = "", tier: str = "", sub: str = "", page: int = 1, size: int = 24) -> dict:
    def sub_ok(r):
        return not sub or sub in (r.get("door"), r.get("style"), r.get("layout"), r.get("fin"))
    rows = [r for r in _INT if (not type_ or r["type"] == type_) and (not scheme or r["scheme"] == scheme) and (not tier or r["tier"] == tier) and sub_ok(r)]
    size = max(6, min(60, size))
    page = max(1, page)
    return {"total": len(rows), "page": page, "size": size, "items": rows[(page - 1) * size: page * size]}


def _lam(S, x, y, w, h, body, fin, scheme):
    """A shutter / panel surface in the chosen finish."""
    if fin == "glass":
        S.rect(x, y, w, h, "#1F2937", "#0F172A", 0.05)
        S.poly([(x + w * 0.15, y), (x + w * 0.45, y), (x + w * 0.7, y + h), (x + w * 0.4, y + h)], "#FFFFFF", None, op=0.12)
        return
    S.rect(x, y, w, h, body, "#44403c", 0.05)
    if fin == "fluted":
        xx = x + 0.12
        while xx < x + w - 0.05:
            S.line(xx, y + 0.05, xx, y + h - 0.05, "#00000033" if False else "#3f3f46", 0.025)
            xx += 0.18
    elif fin == "acrylic":
        S.line(x + w * 0.12, y + h * 0.95, x + w * 0.12, y + h * 0.55, "#FFFFFF", 0.09)
    elif fin == "laminate" and scheme in ("walnut", "oak"):
        yy = y + 0.4
        while yy < y + h:
            S.line(x + 0.05, yy, x + w - 0.05, yy + 0.08, "#00000022" if False else "#6b4423", 0.02)
            yy += 0.55


def draw_interior(d: dict) -> Scene:
    sc = SCHEMES[d["scheme"]]
    body, acc, hnd = sc[1], sc[2], sc[3]
    t = d["type"]
    if t == "wardrobe":
        W_, H_ = 7.0, 7.0
        loft = d["loft"]
        S = Scene(W_ + 3, H_ + (1.8 if loft else 0) + 2.4, "#F1F5F9")
        x0, y0 = 1.5, 1.0
        S.rect(0, 0, S.w, 1.0, "#CBD5E1")
        S.rect(x0 - 0.2, y0, W_ + 0.4, H_ + (1.8 if loft else 0), "#E7E5E4", "#44403c", 0.05)
        if d["door"] == "walkin":
            S.rect(x0, y0, W_, H_, "#FAFAF9", "#44403c", 0.05)
            for yy in (2.0, 3.5, 5.0, 6.4):
                S.rect(x0 + 0.1, y0 + yy, 2.2, 0.12, acc, "#44403c", 0.03)
                S.rect(x0 + W_ - 2.3, y0 + yy, 2.2, 0.12, acc, "#44403c", 0.03)
            S.line(x0 + 2.4, y0 + 5.8, x0 + 4.6, y0 + 5.8, "#78716C", 0.08)
            for xx in (2.9, 3.5, 4.1):
                S.line(x0 + xx, y0 + 5.8, x0 + xx, y0 + 4.4, "#78716C", 0.05)
            _lam(S, x0 + 2.4, y0, 2.3, H_ * 0.62, body, d["fin"], d["scheme"])
            S.text(x0 + W_ / 2, y0 + H_ + 0.15, "open walk-in (L) layout", 0.5, "#57534E")
        else:
            nd = 3 if d["door"] in ("hinged", "loft") else 2
            dw = W_ / nd
            for i in range(nd):
                xs = x0 + i * dw + (0.0 if d["door"] != "sliding" else (-0.0 if i == 0 else -0.25))
                _lam(S, xs + 0.03, y0 + 0.03, dw - 0.06 + (0.25 if d["door"] == "sliding" and i == 0 else 0), H_ - 0.06, body, d["fin"], d["scheme"])
                if d["door"] != "sliding":
                    hx = xs + (dw - 0.3 if i % 2 == 0 else 0.3)
                    S.rect(hx - 0.04, y0 + H_ * 0.45, 0.08, 1.1, hnd, None)
                else:
                    S.rect(xs + (dw - 0.45 if i == 0 else 0.25), y0 + H_ * 0.45, 0.07, 1.2, hnd, None)
            if d["door"] == "sliding":
                S.line(x0, y0 + H_ + 0.04, x0 + W_, y0 + H_ + 0.04, "#1c1917", 0.08)
            if loft:
                for i in range(nd + 1):
                    pass
                for i in range(nd):
                    _lam(S, x0 + i * dw + 0.03, y0 + H_ + 0.05, dw - 0.06, 1.7, body, d["fin"], d["scheme"])
                    S.rect(x0 + i * dw + dw / 2 - 0.3, y0 + H_ + 0.75, 0.6, 0.07, hnd, None)
        S.text(S.w / 2, 0.3, f"Wardrobe - {WARD_DOOR[d['door']].lower()}", 0.6, "#334155")
    elif t == "tv_unit":
        full = d["style"] == "fullwall"
        S = Scene(11, 9.4, "#F1F5F9")
        S.rect(0, 0, 11, 1.0, "#CBD5E1")
        wall = {"plain": acc, "fluted": body, "stone": "#CBD5E1"}[d["panel"]]
        x0, w_ = (1.0, 9.0) if full else (2.0, 7.0)
        H_ = 8.0 if full else 6.4
        S.rect(x0, 1.0, w_, H_, wall, "#44403c", 0.05)
        if d["panel"] == "fluted":
            xx = x0 + 0.15
            while xx < x0 + w_:
                S.line(xx, 1.1, xx, 1.0 + H_ - 0.1, "#3f3f46", 0.025)
                xx += 0.2
        if d["panel"] == "stone":
            for yy in range(1, int(H_)):
                S.line(x0, 1.0 + yy, x0 + w_, 1.0 + yy + 0.2, "#94A3B8", 0.03)
        if d["light"]:
            S.rect(x0 - 0.08, 1.0, 0.1, H_, "#FDE68A", None, op=0.9)
            S.rect(x0 + w_ - 0.02, 1.0, 0.1, H_, "#FDE68A", None, op=0.9)
            S.rect(x0, 1.0 + H_ - 0.05, w_, 0.1, "#FDE68A", None, op=0.9)
        tvw = 4.4 if not full else 5.0
        S.rect(x0 + w_ / 2 - tvw / 2, 3.5, tvw, tvw * 0.56, "#0F172A", "#000000", 0.05)
        S.poly([(x0 + w_ / 2 - tvw / 2 + 0.4, 3.5), (x0 + w_ / 2 - tvw / 2 + 1.6, 3.5), (x0 + w_ / 2 - tvw / 2 + 2.4, 3.5 + tvw * 0.56),
                (x0 + w_ / 2 - tvw / 2 + 1.2, 3.5 + tvw * 0.56)], "#FFFFFF", None, op=0.1)
        cab_h = 1.4
        cy = 1.9 if d["style"] in ("floating", "panel") else 1.0
        cw = w_ - 0.6 if d["style"] != "niche" else w_ * 0.5
        cx = x0 + (w_ - cw) / 2
        _lam(S, cx, cy, cw, cab_h, body, "acrylic" if d["panel"] != "fluted" else "laminate", d["scheme"])
        for i in range(1, 4 if cw > 4 else 2):
            S.line(cx + i * cw / (4 if cw > 4 else 2), cy, cx + i * cw / (4 if cw > 4 else 2), cy + cab_h, "#44403c", 0.04)
        if d["style"] == "niche":
            for side in (x0 + 0.3, x0 + w_ - 0.3 - w_ * 0.18):
                for k in range(3):
                    S.rect(side, 3.0 + k * 1.6, w_ * 0.18, 1.2, "#FAFAF9", "#44403c", 0.04)
        if d["style"] in ("floating", "panel"):
            S.rect(cx + 0.3, 1.6, cw - 0.6, 0.18, "#78716C", None)
        if d["style"] == "panel":
            S.rect(x0 - 0.3, 3.3, w_ + 0.6, 0.15, body, "#44403c", 0.04)
        S.text(5.5, 0.35, f"TV unit - {TV_STYLE[d['style']].lower()}", 0.6, "#334155")
    elif t == "kitchen":
        S = Scene(15, 9.6, "#F1F5F9")
        S.text(3.4, 9.0, "Plan", 0.6, "#475569")
        S.rect(0.6, 0.8, 6.0, 7.6, "#FFFFFF", "#44403c", 0.1)
        cab = body
        D = 1.9
        ly = d["layout"]
        runs = {"straight": [(0.6, 6.5, 6.0, D)], "l": [(0.6, 6.5, 6.0, D), (0.6, 0.8, D, 5.7)],
                "u": [(0.6, 6.5, 6.0, D), (0.6, 0.8, D, 5.7), (4.7, 0.8, D, 5.7)], "parallel": [(0.6, 6.5, 6.0, D), (0.6, 0.8, 6.0, D)],
                "island": [(0.6, 6.5, 6.0, D), (0.6, 0.8, D, 5.7)]}[ly]
        for (x, y, w, h) in runs:
            S.rect(x, y, w, h, cab, "#44403c", 0.06)
        if ly == "island":
            S.rect(2.9, 2.6, 3.0, 1.8, acc, "#44403c", 0.06)
            S.text(4.4, 3.4, "island", 0.5, "#44403c")
        S.circle(2.6, 7.45, 0.55, "#CBD5E1", "#44403c", 0.05)
        S.text(2.6, 7.35, "sink", 0.38, "#44403c")
        for hx, hy in ((4.4, 7.7), (5.2, 7.7), (4.4, 7.1), (5.2, 7.1)):
            S.circle(hx, hy, 0.22, "#1F2937")
        S.rect(1.4, 6.8, 0.5, 0.5, "#E5E7EB", "#44403c", 0.04)
        S.text(3.4, 0.25, KIT_LAYOUT[ly] + " layout", 0.5, "#475569")
        # elevation
        S.text(11.0, 9.0, "Elevation", 0.6, "#475569")
        S.rect(7.4, 1.0, 7.0, 0.35, "#44403c")
        S.rect(7.4, 1.35, 7.0, 2.6, cab, "#44403c", 0.05)
        S.rect(7.3, 3.95, 7.2, 0.22, acc if d["top"] == "quartz" else "#1F2937", "#44403c", 0.04)
        S.rect(7.4, 6.2, 7.0, 2.2, cab, "#44403c", 0.05)
        for i in range(1, 7):
            S.line(7.4 + i, 1.35, 7.4 + i, 3.95, "#44403c", 0.04)
            S.line(7.4 + i, 6.2, 7.4 + i, 8.4, "#44403c", 0.04)
            S.rect(7.4 + i - 0.2, 3.2, 0.12, 0.5, hnd)
        S.rect(10.3, 4.5, 1.6, 0.18, "#94A3B8")
        S.poly([(10.3, 4.2), (11.9, 4.2), (11.5, 6.2), (10.7, 6.2)], "#94A3B8", "#44403c", 0.04)
        S.text(10.9, 0.3, f"{KIT_FIN[d['fin']][0]}, {KIT_TOP[d['top']].lower()}", 0.5, "#475569")
    elif t == "pooja":
        S = Scene(9, 10.4, "#F1F5F9")
        S.rect(0, 0, 9, 1.0, "#CBD5E1")
        S.rect(1.6, 1.0, 5.8, 8.0, "#FAFAF9", "#44403c", 0.05)
        base = {"wood": "#8B5A2B", "white": "#F5F5F4", "marble": "#E5E7EB"}[d["fin"]]
        S.rect(2.0, 1.0, 5.0, 2.2, body, "#44403c", 0.05)
        S.line(4.5, 1.0, 4.5, 3.2, "#44403c", 0.05)
        S.rect(4.3, 2.0, 0.08, 0.5, hnd)
        S.rect(4.6, 2.0, 0.08, 0.5, hnd)
        if d["style"] == "arch":
            S.rect(2.3, 3.2, 4.4, 3.2, base, "#44403c", 0.05)
            S.poly([(2.3 + 2.2 + math.cos(math.radians(a)) * 2.2, 6.4 + math.sin(math.radians(a)) * 1.8) for a in range(0, 181, 10)], base, "#44403c", 0.05)
        elif d["style"] == "jali":
            S.rect(2.3, 3.2, 4.4, 4.8, base, "#44403c", 0.05)
            for xx in range(0, 11):
                for yy in range(0, 10):
                    S.circle(2.5 + xx * 0.4, 3.4 + yy * 0.46, 0.1, body)
        elif d["style"] == "glass":
            S.rect(2.3, 3.2, 4.4, 4.8, "#7DD3FC", "#44403c", 0.05, 0.45)
            S.line(4.5, 3.2, 4.5, 8.0, "#44403c", 0.05)
            S.rect(4.2, 5.4, 0.08, 0.6, hnd)
        else:
            S.rect(2.3, 3.2, 4.4, 4.8, base, "#44403c", 0.05)
        S.circle(4.5, 4.8, 0.5, "#FBBF24")
        S.poly([(4.1, 3.3), (4.9, 3.3), (4.5, 4.2)], "#F59E0B")
        S.rect(2.2, 8.0, 4.6, 0.4, body, "#44403c", 0.05)
        S.text(4.5, 0.3, f"{POOJA[d['style']]}", 0.6, "#334155")
    else:  # ceiling – seen from below
        S = Scene(11, 9.0, "#F1F5F9")
        S.rect(0.5, 1.0, 10, 7.4, "#FFFFFF", "#44403c", 0.1)
        glow = {"warm": "#FDE68A", "cool": "#E0F2FE", "spot": "#FFFFFF"}[d["light"]]
        st = d["style"]
        if st == "flat":
            S.rect(1.2, 1.7, 8.6, 6.0, "#F8FAFC", "#CBD5E1", 0.05)
        elif st == "cove":
            S.rect(1.0, 1.5, 9.0, 6.4, acc, "#44403c", 0.05)
            S.rect(1.6, 2.1, 7.8, 5.2, glow, "#44403c", 0.04, 0.9)
            S.rect(2.4, 2.9, 6.2, 3.6, "#FFFFFF", "#CBD5E1", 0.04)
        elif st == "coffer":
            S.rect(1.0, 1.5, 9.0, 6.4, "#FFFFFF", "#44403c", 0.05)
            for i in range(4):
                for j in range(3):
                    S.rect(1.3 + i * 2.2, 1.8 + j * 2.0, 2.0, 1.8, acc, "#44403c", 0.04)
                    S.rect(1.5 + i * 2.2, 2.0 + j * 2.0, 1.6, 1.4, glow, None, op=0.55)
        else:
            S.rect(1.0, 1.5, 9.0, 6.4, "#FFFFFF", "#44403c", 0.05)
            xx = 1.1
            while xx < 9.9:
                S.rect(xx, 1.6, 0.35, 6.2, body, "#44403c", 0.03)
                xx += 0.6
            S.rect(1.0, 4.4, 9.0, 0.18, glow, None, op=0.9)
        pts = [(3.0, 3.4), (5.5, 3.4), (8.0, 3.4), (3.0, 5.7), (5.5, 5.7), (8.0, 5.7)] if d["light"] != "spot" else \
              [(2.2 + 1.5 * i, 2.8 + 1.2 * j) for i in range(5) for j in range(4)]
        for x, y in pts:
            S.circle(x, y, 0.22, "#FEF08A", "#92400E", 0.04)
        S.circle(5.5, 4.55, 0.4, "#FBBF24", "#92400E", 0.05) if st != "strip" else None
        S.text(5.5, 0.35, f"{CEIL[st]} - seen from below", 0.6, "#334155")
    return S


def interior_prompt(d: dict) -> str:
    sc = SCHEMES[d["scheme"]][0].lower()
    t = d["type"]
    if t == "wardrobe":
        return (f"photo of a modern bedroom wardrobe, {WARD_DOOR[d['door']].lower()}, {WARD_FIN[d['fin']][0].lower()} finish, {sc} colour"
                f"{', with loft storage' if d['loft'] else ''}, Indian apartment interior, soft daylight")
    if t == "tv_unit":
        return (f"photo of a living room {TV_STYLE[d['style']].lower()}, {TV_PANEL[d['panel']][0].lower()} wall, {sc} colour"
                f"{', warm LED back-light' if d['light'] else ''}, flat-screen TV on the wall, modern Indian home")
    if t == "kitchen":
        return (f"photo of a {KIT_LAYOUT[d['layout']].lower()} modular kitchen, {KIT_FIN[d['fin']][0].lower()} cabinets in {sc}, "
                f"{KIT_TOP[d['top']].lower()}, chimney and hob, Indian home, bright")
    if t == "pooja":
        return f"photo of a {POOJA[d['style']].lower()} pooja unit, {POOJA_FIN[d['fin']][0].lower()}, {sc} accents, brass lamp, Indian home"
    return (f"photo of a living room {CEIL[d['style']].lower()} false ceiling with {CEIL_LIGHT[d['light']][0].lower()}, "
            f"{sc} accent, modern Indian home interior")


def elevation_prompt(e: dict) -> str:
    pal = PALETTES[e["palette"]][0].lower()
    return (f"photo of a {e['family']} Indian house front elevation, {pal} colour scheme, {TOPS[e['top']].lower()}, "
            f"{CLADS[e['clad']].lower()}, {WINS[e['win']].lower()}{', door canopy' if e['canopy'] == 'slab' else ''}, daylight, clear sky")


# ---- how a pick changes the quantity of the interior estimate
def qty_for(d: dict, base_qty: float, room: dict) -> tuple[float, str]:
    t = d["type"]
    if t == "kitchen":
        w, dd = room["w"], room["d"]
        run = {"straight": max(6.0, max(w, dd) - 1.5), "l": max(6.0, w + dd - 3.5), "u": max(8.0, w + 2 * dd - 5.0),
               "parallel": max(8.0, 2 * w - 3.0), "island": max(8.0, w + dd - 3.5) + 5.0}[d["layout"]]
        return round(run * 4.5, 1), f"{KIT_LAYOUT[d['layout']].lower()} layout: {run:g} ft running x 4.5 ft"
    if t == "wardrobe":
        mult = {"hinged": 1.0, "sliding": 1.0, "walkin": 1.6, "loft": 1.0}[d["door"]] * (8.8 / 7.0 if d["loft"] else 1.0)
        return round(base_qty * mult, 1), f"{WARD_DOOR[d['door']].lower()}{' + loft' if d['loft'] else ''}"
    if t == "tv_unit":
        return round(base_qty * (8.0 / 6.0 if d["style"] == "fullwall" else 1.0), 1), TV_STYLE[d["style"]].lower()
    return base_qty, ""
