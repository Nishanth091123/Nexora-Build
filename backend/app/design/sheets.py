"""1.10 – Drawing sheets from a design: door & window schedule, area details, front elevation, section A-A,
site plan and floor plans, drawn once as simple primitives and rendered to SVG (screen), PDF (A3 sheet set with
title block) and DXF.

Units: feet. Plan y = 0 is the road side (front). Elevation/section drawings use x = horizontal, z = height.
Heights used: plinth 1.5 ft, slab 5" (125 mm), parapet 3 ft, staircase headroom 8 ft, window sill 3 ft.
Everything is a concept drawing for discussion / submission preparation – it is not a structural drawing.
"""
from __future__ import annotations

import io
import math

FT_M = 0.3048
PLINTH = 1.5
SLAB = 125 / 304.8
PARAPET = 3.0
HEADROOM = 8.0
SILL = {"window": 3.0, "vent": 5.5}

# ---------------------------------------------------------------- door & window schedule
DEFAULT_SPECS = {
    "main_door": {"label": "Main door", "material": "Teak wood frame & shutter"},
    "door": {"label": "Room door", "material": "Wood frame, flush shutter"},
    "toilet_door": {"label": "Toilet door", "material": "PVC / FRP shutter"},
    "pooja_door": {"label": "Pooja door", "material": "Teak wood, carved"},
    "opening": {"label": "Opening (no shutter)", "material": "Plastered jamb"},
    "window": {"label": "Window", "material": "UPVC / aluminium sliding with MS grill"},
    "vent": {"label": "Ventilator", "material": "UPVC louvre / glass"},
}
ORDER = ["main_door", "door", "pooja_door", "toilet_door", "opening", "window", "vent"]
PREFIX = {"main_door": "D", "door": "D", "pooja_door": "D", "toilet_door": "D", "opening": "O", "window": "W", "vent": "V"}


def ft_in(v: float) -> str:
    v = round(v * 12) / 12
    f = int(v)
    i = round((v - f) * 12)
    if i == 12:
        f, i = f + 1, 0
    return f"{f}'-{i}\""


def schedule(plan: dict) -> list[dict]:
    """Group every opening by (type, width, height) → marks D1, D2…, W1…, V1…; writes the mark on each opening."""
    groups: dict[tuple, dict] = {}
    for li, lv in enumerate(plan["levels"]):
        for o in lv.get("openings", []):
            k = (o["type"], round(o["w"], 2), round(o["h"], 2))
            g = groups.setdefault(k, {"type": o["type"], "w": o["w"], "h": o["h"], "per_level": {}, "rooms": set()})
            g["per_level"][lv["name"]] = g["per_level"].get(lv["name"], 0) + 1
            room = next((r for r in lv["rooms"] if r["id"] == o["room"]), None)
            if room:
                g["rooms"].add(room["name"])
    specs = plan.get("opening_specs") or {}
    out, counters = [], {}
    for k in sorted(groups, key=lambda k: (ORDER.index(k[0]) if k[0] in ORDER else 99, -k[1], -k[2])):
        g = groups[k]
        p = PREFIX.get(g["type"], "X")
        counters[p] = counters.get(p, 0) + 1
        mark = f"{p}{counters[p]}"
        d = DEFAULT_SPECS.get(g["type"], {"label": g["type"], "material": ""})
        s = specs.get(g["type"]) or {}
        out.append({"mark": mark, "type": g["type"], "label": d["label"], "w_ft": g["w"], "h_ft": g["h"],
                    "size": f"{ft_in(g['w'])} x {ft_in(g['h'])}", "sill_ft": SILL.get(g["type"], 0.0),
                    "material": s.get("material") or d["material"], "per_level": g["per_level"],
                    "count": sum(g["per_level"].values()), "rooms": ", ".join(sorted(g["rooms"]))[:120]})
        for lv in plan["levels"]:
            for o in lv.get("openings", []):
                if (o["type"], round(o["w"], 2), round(o["h"], 2)) == k:
                    o["mark"] = mark
    return out


def apply_specs(plan: dict) -> list[str]:
    """Owner-edited sizes per opening type (Door & Window schedule) → resize the openings in place, centred on
    the same wall, never wider than the wall of the room. Returns warnings."""
    specs = plan.get("opening_specs") or {}
    warns = []
    for lv in plan["levels"]:
        rooms = {r["id"]: r for r in lv["rooms"]}
        for o in lv.get("openings", []):
            s = specs.get(o["type"]) or {}
            w, h = s.get("w_ft"), s.get("h_ft")
            if h:
                o["h"] = float(h)
            if not w:
                continue
            w = float(w)
            r = rooms.get(o["room"])
            horiz = o["y1"] == o["y2"]
            side = (r["w"] if horiz else r["d"]) if r else w
            if w > side - 0.5:
                warns.append(f"{lv['name']}: {o['type'].replace('_', ' ')} {w:g} ft is wider than the {r['name'] if r else 'room'} wall – kept {max(1.5, side - 0.5):g} ft.")
                w = max(1.5, side - 0.5)
            if horiz:
                c = (o["x1"] + o["x2"]) / 2
                o["x1"], o["x2"] = round(c - w / 2, 2), round(c + w / 2, 2)
            else:
                c = (o["y1"] + o["y2"]) / 2
                o["y1"], o["y2"] = round(c - w / 2, 2), round(c + w / 2, 2)
            o["w"] = round(w, 2)
    return warns


# ---------------------------------------------------------------- area details
def area_details(plan: dict) -> dict:
    plot = plan["plot"]
    from .plot import plot_area_sqft  # 1.18 irregular plots: real area
    plot_sqft = plot_area_sqft(plot)
    rows = []
    for lv in plan["levels"]:
        s = lv["summary"]
        rows.append({"floor": lv["name"], "builtup_sqft": s["builtup_sqft"], "carpet_sqft": s["carpet_sqft"],
                     "balcony_sqft": s.get("balcony_sqft", 0), "terrace_sqft": s.get("terrace_sqft", 0),
                     "use": "Parking" if lv.get("stilt") else "Residential"})
    total = sum(r["builtup_sqft"] for r in rows)
    ground = rows[0]["builtup_sqft"] if rows else 0
    sb = plan.get("setbacks") or {}
    return {
        "rows": rows, "plot_sqft": round(plot_sqft, 1), "plot_m2": round(plot_sqft * FT_M ** 2, 2),
        "total_builtup_sqft": round(total, 1), "total_builtup_m2": round(total * FT_M ** 2, 2),
        "fsi": round(total / plot_sqft, 2) if plot_sqft else 0,
        "coverage_pct": round(100 * ground / plot_sqft, 1) if plot_sqft else 0,
        "open_space_sqft": round(plot_sqft - ground, 1), "open_space_pct": round(100 * (plot_sqft - ground) / plot_sqft, 1) if plot_sqft else 0,
        "height_ft": round(building_height(plan), 1), "height_m": round(building_height(plan) * FT_M, 2),
        "roof_sheets": _sheet_rows(plan),
        "setbacks_m": sb.get("m", {}), "setbacks_ft": sb.get("ft", {}),
        "note": "FSI = total built-up / plot area; coverage = ground floor built-up / plot area. "
                "Check the permitted values for the local body (DTCP / CMDA / Corporation / Panchayat).",
    }


def _sheet_rows(plan: dict) -> list[dict]:
    from .roof import PLACES, describe, geom
    out = []
    for s in plan.get("roof_sheets") or []:
        g = geom(plan, s)
        out.append({"place": PLACES[s["place"]], "level": plan["levels"][s["level"]]["name"], "type": describe(s),
                    "covered_sqft": round(s["w"] * s["d"], 1), "roof_sqft": round(g["slope_area"], 1),
                    "ridge_ft": round(g["ridge_z"], 1)})
    return out


def building_height(plan: dict) -> float:
    H = float(plan.get("floor_height_ft") or 10)
    n = len(plan["levels"])
    stair = any(r["type"] == "stair" for lv in plan["levels"] for r in lv["rooms"]) and n > 1
    from .roof import full_roof, top_height
    base = PLINTH + n * H + (0 if full_roof(plan) else PARAPET + (HEADROOM - PARAPET if stair else 0))
    return max(base, top_height(plan))  # 1.17: a sheet roof ridge can be the highest point


# ---------------------------------------------------------------- primitive drawings
# ---------------------------------------------------------------- drafting pens (CAD-style plot styles)
# layer → (colour, line weight in mm on paper, dash). Like an office CAD plot: cut walls heavy black,
# outlines medium, openings / dimensions / furniture / hatch thin and in their own colours.
WEIGHT = {"WALL": 0.5, "OUTLINE": 0.35, "SLAB": 0.35, "GROUND": 0.7, "WINDOW": 0.25, "DOOR": 0.25, "SWING": 0.13,
          "FURNITURE": 0.13, "STAIR": 0.18, "HATCH": 0.09, "WALLHATCH": 0.09, "DIM": 0.18, "TEXT": 0.25, "ROOMTEXT": 0.25,
          "MARK": 0.18, "CENTRE": 0.13, "PLOT": 0.5, "SETBACK": 0.18, "BUILDING": 0.35, "ROAD": 0.25, "COLUMN": 0.35,
          "FOOTING": 0.35, "PCC": 0.25, "PARAPET": 0.35, "SUNSHADE": 0.25, "SHADOW": 0.0, "MASK": 0.0,
          "BEAM": 0.35, "REBAR": 0.35, "STIRRUP": 0.18, "GRID": 0.13, "SLABEDGE": 0.25,
          "SHEET": 0.35, "TRUSS": 0.25}
DASH = {"SWING": (1.2, 0.8), "CENTRE": (6, 1.5, 1, 1.5), "PLOT": (6, 2), "SETBACK": (3, 1.5), "GRID": (6, 1.5, 1, 1.5),
        "BEAM": None}
# colour per layer – "paper" = coloured lines on white (PDF / print); "cad" = AutoCAD screen (black background)
PALETTE = {
    "paper": {"WALL": "#c2410c", "WALLHATCH": "#fdba74", "OUTLINE": "#c2410c", "SLAB": "#4b5563", "GROUND": "#166534",
              "WINDOW": "#0891b2", "DOOR": "#7e22ce", "SWING": "#7e22ce", "FURNITURE": "#64748b", "STAIR": "#0f766e",
              "HATCH": "#9ca3af", "DIM": "#15803d", "TEXT": "#111827", "ROOMTEXT": "#1d4ed8", "MARK": "#dc2626",
              "CENTRE": "#dc2626", "PLOT": "#111827", "SETBACK": "#ea580c", "BUILDING": "#c2410c", "ROAD": "#475569",
              "COLUMN": "#b91c1c", "FOOTING": "#92400e", "PCC": "#6b7280", "PARAPET": "#c2410c", "SUNSHADE": "#4b5563",
              "SHADOW": "#d4d4d8", "BEAM": "#2563eb", "REBAR": "#dc2626", "STIRRUP": "#16a34a", "GRID": "#dc2626",
              "SLABEDGE": "#2563eb", "MASK": "#ffffff", "BG": "#ffffff", "SHEET": "#0369a1", "TRUSS": "#9a3412"},
    "cad": {"WALL": "#ffff00", "WALLHATCH": "#6b6b00", "OUTLINE": "#ffff00", "SLAB": "#c0c0c0", "GROUND": "#00ff00",
            "WINDOW": "#00ffff", "DOOR": "#ff66ff", "SWING": "#ff66ff", "FURNITURE": "#9a9a9a", "STAIR": "#66ffcc",
            "HATCH": "#7a7a7a", "DIM": "#00ff00", "TEXT": "#ffffff", "ROOMTEXT": "#7fbfff", "MARK": "#ff5050",
            "CENTRE": "#ff5050", "PLOT": "#ffffff", "SETBACK": "#ffa040", "BUILDING": "#ffff00", "ROAD": "#a0a0a0",
            "COLUMN": "#ff5050", "FOOTING": "#ffa040", "PCC": "#a0a0a0", "PARAPET": "#ffff00", "SUNSHADE": "#c0c0c0",
            "SHADOW": "#000000", "BEAM": "#4da6ff", "REBAR": "#ff5050", "STIRRUP": "#00ff00", "GRID": "#ff5050",
            "SLABEDGE": "#4da6ff", "MASK": "#000000", "BG": "#000000", "SHEET": "#00bfff", "TRUSS": "#ff8000"},
}
DXF_COLOR = {"WALL": 2, "WALLHATCH": 8, "OUTLINE": 2, "SLAB": 9, "GROUND": 3, "WINDOW": 4, "DOOR": 6, "SWING": 6,
             "FURNITURE": 8, "STAIR": 4, "HATCH": 9, "DIM": 3, "TEXT": 7, "ROOMTEXT": 5, "MARK": 1, "CENTRE": 1,
             "PLOT": 7, "SETBACK": 30, "BUILDING": 2, "ROAD": 8, "COLUMN": 1, "FOOTING": 30, "PCC": 8, "PARAPET": 2,
             "SUNSHADE": 9, "SHADOW": 9, "TITLE": 7, "BEAM": 5, "REBAR": 1, "STIRRUP": 3, "GRID": 1, "SLABEDGE": 5,
             "SHEET": 140, "TRUSS": 30}


def pen(layer: str, style: str = "paper"):
    pal = PALETTE.get(style, PALETTE["paper"])
    return pal.get(layer, pal["TEXT"]), WEIGHT.get(layer, 0.25), DASH.get(layer)


class Dwg:
    """lines / rects / arcs / texts in feet. 'layer' picks the pen; 'fill' is a hex colour or None."""

    def __init__(self, title: str):
        self.title = title
        self.items: list[dict] = []

    def line(self, x1, y1, x2, y2, layer="OUTLINE", w=None):
        self.items.append({"t": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "layer": layer})

    def rect(self, x, y, w, h, layer="OUTLINE", fill=None, lw=1):
        self.items.append({"t": "rect", "x": x, "y": y, "w": w, "h": h, "layer": layer, "fill": fill, "lw": lw})

    def arc(self, cx, cy, r, a0, a1, layer="SWING"):
        self.items.append({"t": "arc", "cx": cx, "cy": cy, "r": r, "a0": a0, "a1": a1, "layer": layer})

    def text(self, x, y, s, h=0.9, anchor="middle", layer="TEXT", bold=False, mask=False):
        """mask=True puts a white box behind the text (like a drafted label over hatch / furniture)."""
        if mask:
            L = len(str(s)) * h * 0.58 + 0.3
            a = {"start": 0, "middle": -L / 2, "end": -L}[anchor]
            self.items.append({"t": "rect", "x": x + a - 0.15, "y": y - 0.25 * h, "w": L, "h": h * 1.25,
                               "layer": "MASK", "fill": "#ffffff", "lw": 0})
        self.items.append({"t": "text", "x": x, "y": y, "s": str(s), "h": h, "anchor": anchor, "layer": layer, "bold": bold})

    def hatch(self, x, y, w, h, gap=0.6, layer="HATCH", angle=45):
        """45° hatch lines clipped to a rectangle (earth / concrete / brick poché)."""
        if w <= 0 or h <= 0:
            return
        k = 1 if angle == 45 else -1
        t = -h
        while t < w:
            # line x = x + t + s, y = y + s (k = 1)  for s in [0, h], clipped to [x, x+w]
            s0, s1 = max(0.0, -t), min(h, w - t)
            if s1 > s0:
                if k == 1:
                    self.line(x + t + s0, y + s0, x + t + s1, y + s1, layer)
                else:
                    self.line(x + w - (t + s0), y + s0, x + w - (t + s1), y + s1, layer)
            t += gap

    def dim_h(self, x1, x2, y, label=None, off=0.0, ext_from=None):
        """Architectural dimension: line, 45° ticks, extension lines, text above."""
        self.line(x1 - 0.4, y, x2 + 0.4, y, "DIM")
        for x in (x1, x2):
            self.line(x - 0.3, y - 0.3, x + 0.3, y + 0.3, "DIM")
            if ext_from is not None:
                self.line(x, ext_from, x, y + 0.4 if y > ext_from else y - 0.4, "DIM")
        self.text((x1 + x2) / 2, y + 0.3 + off, label or ft_in(abs(x2 - x1)), 0.7, layer="DIM")

    def dim_v(self, x, y1, y2, label=None, ext_from=None):
        self.line(x, y1 - 0.4, x, y2 + 0.4, "DIM")
        for y in (y1, y2):
            self.line(x - 0.3, y - 0.3, x + 0.3, y + 0.3, "DIM")
            if ext_from is not None:
                self.line(ext_from, y, x - 0.4 if x < ext_from else x + 0.4, y, "DIM")
        self.text(x - 0.4, (y1 + y2) / 2, label or ft_in(abs(y2 - y1)), 0.7, anchor="end", layer="DIM")

    def level(self, x, z, label):
        """Level marker ▽ with value."""
        self.line(x - 0.6, z + 0.9, x + 0.6, z + 0.9, "DIM")
        self.line(x - 0.6, z + 0.9, x, z, "DIM")
        self.line(x + 0.6, z + 0.9, x, z, "DIM")
        self.line(x + 0.6, z + 0.9, x + 7.5, z + 0.9, "DIM")
        self.text(x + 1.0, z + 1.2, label, 0.65, anchor="start", layer="DIM")

    def bounds(self):
        xs, ys = [], []
        for it in self.items:
            if it["t"] == "line":
                xs += [it["x1"], it["x2"]]
                ys += [it["y1"], it["y2"]]
            elif it["t"] == "rect":
                xs += [it["x"], it["x"] + it["w"]]
                ys += [it["y"], it["y"] + it["h"]]
            elif it["t"] == "arc":
                xs += [it["cx"] - it["r"], it["cx"] + it["r"]]
                ys += [it["cy"] - it["r"], it["cy"] + it["r"]]
            else:
                L = len(it["s"]) * it["h"] * 0.55
                a = {"start": 0, "middle": -L / 2, "end": -L}[it["anchor"]]
                xs += [it["x"] + a, it["x"] + a + L]
                ys += [it["y"], it["y"] + it["h"]]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 1, 1)


THK = {"ext": 0.755, "int230": 0.755, "int115": 0.377, "parapet": 0.5}


def _furniture(d: Dwg, r: dict):
    """Simple furniture symbols so the plan reads like a hand-prepared drawing (not to scale of real items)."""
    x, y, w, h, t = r["x"], r["y"], r["w"], r["d"], r["type"]
    F = "FURNITURE"
    if t == "bedroom" and w >= 8 and h >= 8:
        bw, bl = min(5.0, w - 3), min(6.5, h - 2.5)
        bx, by = x + (w - bw) / 2, y + h - bl - 0.6
        d.rect(bx, by, bw, bl, F)
        d.rect(bx + 0.3, by + bl - 1.4, bw / 2 - 0.45, 1.0, F)
        d.rect(bx + bw / 2 + 0.15, by + bl - 1.4, bw / 2 - 0.45, 1.0, F)
        d.line(bx, by + bl * 0.55, bx + bw, by + bl * 0.55, F)
        if w >= 10:
            d.rect(x + 0.6, y + 0.6, 2.0, 4.0, F)  # wardrobe
            d.line(x + 0.6, y + 2.6, x + 2.6, y + 2.6, F)
    elif t in ("hall", "lounge") and w >= 8 and h >= 8:
        sx, sy = x + 0.8, y + 0.8
        d.rect(sx, sy, 2.3, min(7.0, h - 2.5), F)  # sofa
        d.rect(sx + 0.3, sy + 0.3, 1.7, min(7.0, h - 2.5) - 0.6, F)
        d.rect(x + 4.0, y + h / 2 - 1.0, 2.5, 2.0, F)  # centre table
        d.rect(x + w - 1.5, y + h / 2 - 2.0, 0.9, 4.0, F)  # TV unit
    elif t == "dining" and w >= 7 and h >= 7:
        cx, cy = x + w / 2, y + h / 2
        d.rect(cx - 2.0, cy - 1.25, 4.0, 2.5, F)
        for dx in (-1.2, 0.6):
            d.rect(cx + dx, cy + 1.45, 0.9, 0.9, F)
            d.rect(cx + dx, cy - 2.35, 0.9, 0.9, F)
    elif t == "kitchen":
        d.rect(x + 0.3, y + 0.3, 2.0, h - 0.6, F)  # L-counter
        d.rect(x + 2.3, y + h - 2.3, max(1.0, w - 2.6), 2.0, F)
        d.rect(x + 0.6, y + h / 2 - 0.9, 1.4, 1.8, F)  # sink
        d.arc(x + 1.3, y + h / 2, 0.55, 0, 360, F)
        d.arc(x + 3.2, y + h - 1.3, 0.45, 0, 360, F)  # hob
        d.arc(x + 4.4, y + h - 1.3, 0.45, 0, 360, F)
    elif t in ("toilet", "common_toilet") and w >= 3.5 and h >= 4:
        wx, wy = x + w - 2.0, y + h - 2.6
        d.rect(wx, wy + 1.6, 1.4, 0.7, F)  # WC cistern
        d.arc(wx + 0.7, wy + 0.95, 0.7, 0, 360, F)
        d.rect(x + 0.4, y + h - 1.6, 1.6, 1.2, F)  # wash basin
        d.arc(x + 1.2, y + h - 1.0, 0.4, 0, 360, F)
    elif t == "parking" and w >= 9 and h >= 14:
        cw, cl = 6.0, 13.5
        cx, cy = x + (w - cw) / 2, y + (h - cl) / 2
        d.rect(cx, cy, cw, cl, F)
        d.rect(cx + 0.6, cy + 3.0, cw - 1.2, 3.0, F)
        d.rect(cx + 0.6, cy + 8.0, cw - 1.2, 2.5, F)
        d.text(cx + cw / 2, cy + cl / 2 - 0.3, "CAR", 0.6, layer="FURNITURE")
    elif t == "pooja" and w >= 3:
        d.rect(x + w / 2 - 0.9, y + h - 1.4, 1.8, 1.0, F)


def wall_body(lv: dict, kinds=("ext", "int230", "int115")) -> tuple[list[tuple], list[tuple]]:
    """Union of all wall rectangles minus the door / window gaps (axis-aligned, exact by coordinate compression).
    Returns (outline segments [(x1, y1, x2, y2)], filled strips [(x0, y0, x1, y1)] for the hatch)."""
    rects, cuts = [], []
    for w in lv.get("walls", []):
        if w["kind"] not in kinds:
            continue
        t = THK.get(w["kind"], 0.5) / 2
        if w["y1"] == w["y2"]:
            rects.append((min(w["x1"], w["x2"]) - (t if w["kind"] != "int115" else 0), w["y1"] - t,
                          max(w["x1"], w["x2"]) + (t if w["kind"] != "int115" else 0), w["y1"] + t))
        else:
            rects.append((w["x1"] - t, min(w["y1"], w["y2"]), w["x1"] + t, max(w["y1"], w["y2"])))
    for o in lv.get("openings", []):
        x0, x1 = min(o["x1"], o["x2"]), max(o["x1"], o["x2"])
        y0, y1 = min(o["y1"], o["y2"]), max(o["y1"], o["y2"])
        if o["y1"] == o["y2"]:
            cuts.append((x0, o["y1"] - 0.6, x1, o["y1"] + 0.6))
        else:
            cuts.append((o["x1"] - 0.6, y0, o["x1"] + 0.6, y1))
    if not rects:
        return [], []
    xs = sorted({round(v, 4) for r in rects + cuts for v in (r[0], r[2])})
    ys = sorted({round(v, 4) for r in rects + cuts for v in (r[1], r[3])})
    nx, ny = len(xs) - 1, len(ys) - 1

    def inside(rs, cx, cy):
        return any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in rs)
    fill = [[False] * ny for _ in range(nx)]
    for i in range(nx):
        cx = (xs[i] + xs[i + 1]) / 2
        for j in range(ny):
            cy = (ys[j] + ys[j + 1]) / 2
            fill[i][j] = inside(rects, cx, cy) and not inside(cuts, cx, cy)
    F = lambda i, j: 0 <= i < nx and 0 <= j < ny and fill[i][j]
    segs = []
    for j in range(ny + 1):  # horizontal boundary edges, merged along x
        run = None
        for i in range(nx):
            edge = F(i, j - 1) != F(i, j)
            if edge and run is None:
                run = xs[i]
            if (not edge or i == nx - 1) and run is not None:
                end = xs[i + 1] if edge else xs[i]
                segs.append((run, ys[j], end, ys[j]))
                run = None
    for i in range(nx + 1):  # vertical boundary edges, merged along y
        run = None
        for j in range(ny):
            edge = F(i - 1, j) != F(i, j)
            if edge and run is None:
                run = ys[j]
            if (not edge or j == ny - 1) and run is not None:
                end = ys[j + 1] if edge else ys[j]
                segs.append((xs[i], run, xs[i], end))
                run = None
    strips = []
    for j in range(ny):  # filled runs per row → hatch strips
        run = None
        for i in range(nx + 1):
            f = F(i, j)
            if f and run is None:
                run = xs[i]
            if not f and run is not None:
                strips.append((run, ys[j], xs[i], ys[j + 1]))
                run = None
    return segs, strips


def floor_plan(plan: dict, li: int) -> Dwg:
    lv = plan["levels"][li]
    d = Dwg(f"{lv['name']} Plan")
    ops = lv.get("openings", [])
    for r in lv["rooms"]:
        if r["type"] in ("terrace", "balcony", "sitout"):
            d.hatch(r["x"], r["y"], r["w"], r["d"], 1.2)
        elif r["type"] in ("toilet", "common_toilet"):  # floor tile grid (2' x 2')
            k = 2.0
            xx = r["x"] + k
            while xx < r["x"] + r["w"] - 0.01:
                d.line(xx, r["y"], xx, r["y"] + r["d"], "HATCH")
                xx += k
            yy = r["y"] + k
            while yy < r["y"] + r["d"] - 0.01:
                d.line(r["x"], yy, r["x"] + r["w"], yy, "HATCH")
                yy += k
        _furniture(d, r)
        if r["type"] == "stair":
            treads = max(4, int(r["d"] / 0.9))
            step = r["d"] / treads
            mid = r["x"] + r["w"] / 2
            for k in range(1, treads):
                d.line(r["x"] + 0.4, r["y"] + k * step, mid - 0.15, r["y"] + k * step, "STAIR")
                d.line(mid + 0.15, r["y"] + k * step, r["x"] + r["w"] - 0.4, r["y"] + k * step, "STAIR")
            d.line(mid - 0.15, r["y"] + 0.4, mid - 0.15, r["y"] + r["d"] - 0.4, "STAIR")
            d.line(mid + 0.15, r["y"] + 0.4, mid + 0.15, r["y"] + r["d"] - 0.4, "STAIR")
            ax = r["x"] + r["w"] / 4
            d.line(ax, r["y"] + 1.0, ax, r["y"] + r["d"] - 1.5, "STAIR")
            d.line(ax, r["y"] + r["d"] - 1.5, ax - 0.4, r["y"] + r["d"] - 2.3, "STAIR")
            d.line(ax, r["y"] + r["d"] - 1.5, ax + 0.4, r["y"] + r["d"] - 2.3, "STAIR")
            d.text(ax, r["y"] + 0.4, "UP", 0.55, layer="STAIR")
    # walls: CAD style – coloured outline of the wall body (cut at doors / windows) + light hatch inside
    segs, strips = wall_body(lv)
    for x0_, y0_, x1_, y1_ in strips:
        d.hatch(x0_, y0_, x1_ - x0_, y1_ - y0_, 0.45, layer="WALLHATCH")
    for x1_, y1_, x2_, y2_ in segs:
        d.line(x1_, y1_, x2_, y2_, "WALL")
    for w in lv.get("walls", []):  # open-terrace parapets: thin double line
        if w["kind"] == "parapet":
            t = THK["parapet"] / 2
            if w["y1"] == w["y2"]:
                d.line(min(w["x1"], w["x2"]), w["y1"] - t, max(w["x1"], w["x2"]), w["y1"] - t, "PARAPET")
                d.line(min(w["x1"], w["x2"]), w["y1"] + t, max(w["x1"], w["x2"]), w["y1"] + t, "PARAPET")
            else:
                d.line(w["x1"] - t, min(w["y1"], w["y2"]), w["x1"] - t, max(w["y1"], w["y2"]), "PARAPET")
                d.line(w["x1"] + t, min(w["y1"], w["y2"]), w["x1"] + t, max(w["y1"], w["y2"]), "PARAPET")
    rooms = {r["id"]: r for r in lv["rooms"]}
    for o in ops:
        win = o["type"] in ("window", "vent")
        horiz = o["y1"] == o["y2"]
        t = 0.78
        x0, x1 = min(o["x1"], o["x2"]), max(o["x1"], o["x2"])
        y0, y1 = min(o["y1"], o["y2"]), max(o["y1"], o["y2"])
        if win:  # three-line window symbol
            for f in (-t / 2, 0, t / 2):
                if horiz:
                    d.line(x0, o["y1"] + f, x1, o["y1"] + f, "WINDOW")
                else:
                    d.line(o["x1"] + f, y0, o["x1"] + f, y1, "WINDOW")
            for e in ((x0, x1) if horiz else (y0, y1)):
                if horiz:
                    d.line(e, o["y1"] - t / 2, e, o["y1"] + t / 2, "WINDOW")
                else:
                    d.line(o["x1"] - t / 2, e, o["x1"] + t / 2, e, "WINDOW")
        elif o["type"] != "opening":  # door leaf + 90° swing into the room
            r = rooms.get(o["room"])
            W = o["w"]
            if horiz:
                into = 1 if r and r["y"] + r["d"] / 2 > o["y1"] else -1
                hx, hy = x0, o["y1"]
                d.line(hx, hy, hx, hy + into * W, "DOOR")
                d.arc(hx, hy, W, 0 if into > 0 else 270, 90 if into > 0 else 360)
            else:
                into = 1 if r and r["x"] + r["w"] / 2 > o["x1"] else -1
                hx, hy = o["x1"], y0
                d.line(hx, hy, hx + into * W, hy, "DOOR")
                d.arc(hx, hy, W, 0 if into > 0 else 90, 90 if into > 0 else 180)
        if o.get("mark"):
            if horiz:
                tx, ty = (x0 + x1) / 2, o["y1"] + (-1.5 if (rooms.get(o["room"]) or {"y": 0, "d": 0})["y"] + 0.01 > o["y1"] - 0.01 else 0.9)
            else:
                tx, ty = o["x1"] + (1.2 if (rooms.get(o["room"]) or {"x": 0})["x"] >= o["x1"] - 0.01 else -1.2), (y0 + y1) / 2
            d.text(tx, ty, o["mark"], 0.6, layer="MARK")
    for r in lv["rooms"]:
        cx, cy = r["x"] + r["w"] / 2, r["y"] + r["d"] / 2
        m = min(r["w"], r["d"])
        fs = 0.8 if m >= 7 else 0.6 if m >= 5.5 else 0.45
        if r["type"] in ("bedroom",):
            cy = r["y"] + 1.8  # keep the label clear of the bed
        if r["type"] == "stair":
            cx = r["x"] + r["w"] * 0.72
        d.text(cx, cy + 0.15, r["name"].upper(), fs, layer="ROOMTEXT", bold=True, mask=True)
        d.text(cx, cy - fs - 0.05, f"{ft_in(r['w'])} X {ft_in(r['d'])}", fs * 0.85, layer="ROOMTEXT", mask=True)
    # chain dimensions (room by room) + overall, on the top and the left
    xs_all = [r["x"] for r in lv["rooms"]] + [r["x"] + r["w"] for r in lv["rooms"]]
    ys_all = [r["y"] for r in lv["rooms"]] + [r["y"] + r["d"] for r in lv["rooms"]]
    x0, x1, y0, y1 = min(xs_all), max(xs_all), min(ys_all), max(ys_all)
    top = sorted({round(v, 2) for r in lv["rooms"] if abs(r["y"] + r["d"] - y1) < 0.05 for v in (r["x"], r["x"] + r["w"])})
    left = sorted({round(v, 2) for r in lv["rooms"] if abs(r["x"] - x0) < 0.05 for v in (r["y"], r["y"] + r["d"])})
    for a, b in zip(top, top[1:]):
        d.dim_h(a, b, y1 + 2.0, ext_from=y1 + 0.5)
    d.dim_h(x0, x1, y1 + 4.0, ext_from=y1 + 0.5)
    for a, b in zip(left, left[1:]):
        d.dim_v(x0 - 2.0, a, b, ext_from=x0 - 0.5)
    d.dim_v(x0 - 4.5, y0, y1, ext_from=x0 - 0.5)
    d.text((x0 + x1) / 2, y0 - 3.2, "FRONT  (ROAD SIDE)", 0.75, layer="TEXT", bold=True)
    d.line((x0 + x1) / 2 - 2.5, y0 - 2.0, (x0 + x1) / 2 + 2.5, y0 - 2.0, "TEXT")
    _north(d, plan, x1 + 4.5, y1 - 2.5)
    return d


def site_plan(plan: dict) -> Dwg:
    plot, b, sb = plan["plot"], plan["building"], plan.get("setbacks") or {}
    d = Dwg("Site Plan")
    from .plot import draw_plot
    poly = draw_plot(d, plot)  # 1.18 irregular plot
    if not poly:
        d.rect(0, 0, plot["w"], plot["d"], "PLOT")
    lv0 = plan["levels"][0]
    xs = [r["x"] for r in lv0["rooms"]] + [r["x"] + r["w"] for r in lv0["rooms"]]
    ys = [r["y"] for r in lv0["rooms"]] + [r["y"] + r["d"] for r in lv0["rooms"]]
    bx0, bx1, by0, by1 = b["x"] + min(xs), b["x"] + max(xs), b["y"] + min(ys), b["y"] + max(ys)
    d.rect(b["x"], b["y"], b["w"], b["d"], "SETBACK")  # buildable line
    d.rect(bx0 + 0.6, by0 - 0.6, bx1 - bx0, by1 - by0, "SHADOW", "#e4e4e7", 0)  # shadow
    d.rect(bx0, by0, bx1 - bx0, by1 - by0, "BUILDING", "#ffffff")
    d.hatch(bx0, by0, bx1 - bx0, by1 - by0, 1.0)
    d.rect(bx0 + (bx1 - bx0) / 2 - 7, (by0 + by1) / 2 - 2.2, 14, 3.6, "BUILDING", "#ffffff")
    d.text((bx0 + bx1) / 2, (by0 + by1) / 2, "PROPOSED BUILDING", 0.9, layer="ROOMTEXT", bold=True)
    d.text((bx0 + bx1) / 2, (by0 + by1) / 2 - 1.5, f"{len(plan['levels'])} floor(s)", 0.7, layer="ROOMTEXT")
    d.rect(-3, -8, plot["w"] + 6, 5, "ROAD", "#f1f5f9")
    d.line(-3, -5.5, plot["w"] + 3, -5.5, "CENTRE")
    road = (plan.get("requirements") or {}).get("road_width_m") or sb.get("road_width_m")
    d.text(plot["w"] / 2, -7.4, f"ROAD{f'  ({road:g} m WIDE)' if isinstance(road, (int, float)) else ''}", 0.8, bold=True)
    ft = sb.get("ft") or {}
    if poly:
        _north(d, plan, plot["w"] + 7, plot["d"] - 3)
        return d
    if by0 > 0.1:
        d.dim_v(-1.5, 0, by0, f"FRONT {ft.get('front', by0):g}'")
    if plot["d"] - by1 > 0.1:
        d.dim_v(-1.5, by1, plot["d"], f"REAR {ft.get('rear', plot['d'] - by1):g}'")
    if bx0 > 0.1:
        d.dim_h(0, bx0, plot["d"] + 1.5, f"{ft.get('left', bx0):g}'")
    if plot["w"] - bx1 > 0.1:
        d.dim_h(bx1, plot["w"], plot["d"] + 1.5, f"{ft.get('right', plot['w'] - bx1):g}'")
    d.dim_h(0, plot["w"], plot["d"] + 4, f"PLOT {ft_in(plot['w'])}")
    d.dim_v(plot["w"] + 3.5, 0, plot["d"], f"{ft_in(plot['d'])}")
    for gx in (0, plot["w"]):  # boundary stones
        for gy in (0, plot["d"]):
            d.rect(gx - 0.35, gy - 0.35, 0.7, 0.7, "PLOT", "#111111", 0)
    _north(d, plan, plot["w"] + 7, plot["d"] - 3)
    return d


def _north(d: Dwg, plan: dict, ax: float, ay: float):
    up, right = plan["compass"]["up"], plan["compass"]["right"]
    nx, ny = right[1], up[1]
    d.arc(ax, ay, 2.6, 0, 360, "TEXT")
    d.line(ax - nx * 2.4, ay - ny * 2.4, ax + nx * 2.4, ay + ny * 2.4, "TEXT")
    d.line(ax + nx * 2.4, ay + ny * 2.4, ax - ny * 0.9 - nx * 0.6, ay + nx * 0.9 - ny * 0.6, "TEXT")
    d.line(ax + nx * 2.4, ay + ny * 2.4, ax + ny * 0.9 - nx * 0.6, ay - nx * 0.9 - ny * 0.6, "TEXT")
    d.text(ax + nx * 3.6, ay + ny * 3.6 - 0.45, "N", 1.0, bold=True)


def _extent(lv: dict):
    xs = [r["x"] for r in lv["rooms"]] + [r["x"] + r["w"] for r in lv["rooms"]]
    ys = [r["y"] for r in lv["rooms"]] + [r["y"] + r["d"] for r in lv["rooms"]]
    return min(xs), max(xs), min(ys), max(ys)


def _levels_z(plan: dict) -> list[float]:
    H = float(plan.get("floor_height_ft") or 10)
    return [PLINTH + i * H for i in range(len(plan["levels"]) + 1)]


def _ground(d: Dwg, a: float, b: float):
    d.line(a, 0, b, 0, "GROUND")
    k = a
    while k < b - 0.6:  # earth hatch below ground line
        d.line(k, -0.05, k + 0.7, -0.75, "HATCH")
        k += 0.9


def _window_elev(d: Dwg, x0: float, x1: float, z: float, h: float, vent: bool):
    d.rect(x0, z, x1 - x0, h, "WINDOW", "#e0f2fe")
    d.rect(x0 + 0.2, z + 0.2, x1 - x0 - 0.4, h - 0.4, "WINDOW")
    if not vent:
        n = max(2, int(round((x1 - x0) / 2)))
        for i in range(1, n):
            xx = x0 + i * (x1 - x0) / n
            d.line(xx, z + 0.2, xx, z + h - 0.2, "WINDOW")
        for k in range(1, 4):  # grill bars
            d.line(x0 + 0.2, z + k * h / 4, x1 - 0.2, z + k * h / 4, "HATCH")
    else:
        for k in range(1, 4):
            d.line(x0 + 0.2, z + k * h / 4, x1 - 0.2, z + k * h / 4, "WINDOW")
    d.rect(x0 - 0.3, z - 0.25, x1 - x0 + 0.6, 0.25, "OUTLINE", "#d4d4d8")  # sill
    d.rect(x0 - 0.75, z + h + 0.35, x1 - x0 + 1.5, 0.25, "SUNSHADE", "#a1a1aa")  # chajja
    d.rect(x0 - 0.75, z + h - 0.1, x1 - x0 + 1.5, 0.45, "SHADOW", "#e4e4e7", 0)


SEE_THROUGH = {"terrace", "balcony", "sitout", "parking", "portico", "open", "garden"}


def front_openings(lv: dict) -> list[dict]:
    """1.13: openings that are really seen from the road (front = smallest y): on a wall running along x,
    with nothing enclosed between the road and the opening (parking / sit-out / balcony are open).
    Internal doors near the front are NOT drawn any more (that was the window/door mix-up).
    The same rule is used by the 3D model, so 2D elevation and 3D always match."""
    rooms = lv.get("rooms", [])
    out = []
    for o in lv.get("openings", []):
        if abs(o["y1"] - o["y2"]) > 0.01:
            continue
        if o["type"] not in ("window", "vent", "main_door", "door", "pooja_door", "toilet_door"):
            continue
        yo = o["y1"]
        xm = (o["x1"] + o["x2"]) / 2
        blocked = False
        for r in rooms:
            if r["x"] - 0.01 <= xm <= r["x"] + r["w"] + 0.01 and r["y"] + r["d"] <= yo + 0.01 and r["y"] < yo - 0.05:
                if r["type"] not in SEE_THROUGH:
                    blocked = True
                    break
        if blocked:
            continue
        # the room the opening belongs to must be BEHIND the wall (wall is its front face)
        own = next((r for r in rooms if r["id"] == o.get("room")), None)
        if own and abs(own["y"] - yo) > 0.05:
            # the opening is on the room's far (back) wall – seen from the road only if that room is open
            if own["type"] not in SEE_THROUGH and own["y"] < yo:
                continue
        out.append(o)
    return out


def front_elevation(plan: dict) -> Dwg:
    from .roof import draw_side, full_roof, headroom_sheet
    d = Dwg("Front Elevation")
    zs = _levels_z(plan)
    n = len(plan["levels"])
    no_top_slab, sheet_mumty = full_roof(plan), headroom_sheet(plan)
    gx0 = min(_extent(lv)[0] for lv in plan["levels"])
    gx1 = max(_extent(lv)[1] for lv in plan["levels"])
    _ground(d, gx0 - 5, gx1 + 5)
    d.rect(gx0 - 0.4, 0, gx1 - gx0 + 0.8, PLINTH, "OUTLINE", "#d4d4d8")
    d.hatch(gx0 - 0.4, 0, gx1 - gx0 + 0.8, PLINTH, 0.5)
    for i, lv in enumerate(plan["levels"]):
        x0, x1, y0, _ = _extent(lv)
        z0, z1 = zs[i], zs[i + 1]
        park = [r for r in lv["rooms"] if r["type"] == "parking" and r["y"] <= y0 + 0.1] if i == 0 else []
        if lv.get("stilt") or park:
            for r in park:
                for xx in (r["x"], r["x"] + r["w"] - 0.75):
                    d.rect(xx, z0, 0.75, z1 - z0 - SLAB, "COLUMN", "#e5e7eb")
                d.rect(r["x"] + 0.75, z1 - SLAB - 1.25, r["w"] - 1.5, 1.25, "OUTLINE", "#f4f4f5")  # beam
                d.rect(r["x"] + 0.75, z0, r["w"] - 1.5, z1 - z0 - SLAB - 1.25, "SHADOW", "#f4f4f5", 0)
            for r in lv["rooms"]:
                if r["y"] <= y0 + 0.1 and r["type"] != "parking":
                    d.rect(r["x"], z0, r["w"], z1 - z0 - SLAB, "OUTLINE", "#fafaf9")
        else:
            d.rect(x0, z0, x1 - x0, z1 - z0 - SLAB, "OUTLINE", "#fafaf9")
        if not (no_top_slab and i == n - 1):  # 1.17: a full sheet roof has no RCC slab on the top floor
            d.rect(x0 - 0.5, z1 - SLAB, x1 - x0 + 1.0, SLAB, "SLAB", "#a1a1aa")
        d.line(x0, z0 + 7.5, x1, z0 + 7.5, "HATCH")  # lintel band line
        for o in front_openings(lv):
            ox0, ox1 = min(o["x1"], o["x2"]), max(o["x1"], o["x2"])
            if o["type"] in ("window", "vent"):
                sz = z0 + SILL[o["type"]]
                _window_elev(d, ox0, ox1, sz, o["h"], o["type"] == "vent")
                mz = sz - 1.0
            elif o["type"] == "main_door":
                d.rect(ox0 - 0.25, z0, ox1 - ox0 + 0.5, o["h"] + 0.25, "DOOR", "#fde68a")
                d.rect(ox0, z0, (ox1 - ox0) / 2, o["h"], "DOOR", "#d6b48a")
                d.rect((ox0 + ox1) / 2, z0, (ox1 - ox0) / 2, o["h"], "DOOR", "#d6b48a")
                for k in (0.25, 0.55):
                    d.rect(ox0 + 0.25, z0 + o["h"] * k, (ox1 - ox0) / 2 - 0.5, o["h"] * 0.22, "DOOR")
                    d.rect((ox0 + ox1) / 2 + 0.25, z0 + o["h"] * k, (ox1 - ox0) / 2 - 0.5, o["h"] * 0.22, "DOOR")
                mz = z0 + o["h"] + 0.5
            elif o["type"] in ("door", "pooja_door", "toilet_door"):  # single shutter
                d.rect(ox0 - 0.2, z0, ox1 - ox0 + 0.4, o["h"] + 0.2, "DOOR", "#fde68a")
                d.rect(ox0, z0, ox1 - ox0, o["h"], "DOOR", "#d6b48a")
                for k in (0.2, 0.55):
                    d.rect(ox0 + 0.3, z0 + o["h"] * k, ox1 - ox0 - 0.6, o["h"] * 0.25, "DOOR")
                mz = z0 + o["h"] + 0.5
            else:
                continue
            if o.get("mark"):
                d.text((ox0 + ox1) / 2, mz, o["mark"], 0.55, layer="MARK")
        d.level(x1 + 1.5, z0, f"+{z0 * FT_M:.2f} m  {lv['name'].upper()}")
    tx0, tx1, _, _ = _extent(plan["levels"][-1])
    roof = zs[-1]
    stair = next((r for r in plan["levels"][-1]["rooms"] if r["type"] == "stair"), None)
    if not no_top_slab:
        d.rect(tx0, roof, tx1 - tx0, PARAPET, "PARAPET", "#fafaf9")
        d.rect(tx0 - 0.25, roof + PARAPET, tx1 - tx0 + 0.5, 0.3, "PARAPET", "#a1a1aa")  # coping
        if stair and n > 1:
            d.rect(stair["x"], roof, stair["w"], HEADROOM, "OUTLINE", "#fafaf9")
            if not sheet_mumty:
                d.rect(stair["x"] - 0.6, roof + HEADROOM, stair["w"] + 1.2, SLAB + 0.15, "SLAB", "#a1a1aa")
            d.text(stair["x"] + stair["w"] / 2, roof + HEADROOM / 2, "HEAD ROOM", 0.55, layer="DIM")
    top = roof + (0.3 if no_top_slab else HEADROOM + SLAB if stair and n > 1 else PARAPET + 0.3)
    top = max(top, draw_side(d, plan, "front"))  # 1.17 sheet roofs
    d.level(tx1 + 1.5, roof, f"+{roof * FT_M:.2f} m  {'EAVE (SHEET ROOF)' if no_top_slab else 'TERRACE'}")
    d.level(gx1 + 1.5, 0, "±0.00 m  G.L.")
    d.dim_v(gx0 - 3.0, 0, top, f"{top * FT_M:.2f} m", ext_from=gx0 - 0.5)
    for i in range(n):
        d.dim_v(gx0 - 1.5, zs[i], zs[i + 1], ft_in(zs[i + 1] - zs[i]))
    d.dim_h(gx0, gx1, -2.5, ext_from=-0.2)
    d.text((gx0 + gx1) / 2, -4.6, "FRONT ELEVATION  (ROAD SIDE)", 0.85, bold=True)
    d.line((gx0 + gx1) / 2 - 6.5, -4.9, (gx0 + gx1) / 2 + 6.5, -4.9, "TEXT")
    return d


def section(plan: dict) -> Dwg:
    """Section A-A along the depth, cut through the staircase (or the middle of the building)."""
    from .roof import draw_side, full_roof, headroom_sheet
    d = Dwg("Section A-A")
    zs = _levels_z(plan)
    n = len(plan["levels"])
    no_top_slab, sheet_mumty = full_roof(plan), headroom_sheet(plan)
    lv0 = plan["levels"][0]
    stair = next((r for r in lv0["rooms"] if r["type"] == "stair"), None)
    x0, x1, _, _ = _extent(lv0)
    xc = stair["x"] + stair["w"] / 2 if stair else (x0 + x1) / 2
    gy0 = min(_extent(lv)[2] for lv in plan["levels"])
    gy1 = max(_extent(lv)[3] for lv in plan["levels"])
    _ground(d, gy0 - 5, gy1 + 5)
    walls_y = sorted({round(w["y1"], 2) for w in lv0.get("walls", []) if w["y1"] == w["y2"]
                      and min(w["x1"], w["x2"]) - 0.01 <= xc <= max(w["x1"], w["x2"]) + 0.01})
    for y in walls_y:
        d.rect(y - 2.0, -5.0, 4.0, 0.33, "PCC", "#e5e7eb")
        d.hatch(y - 2.0, -5.0, 4.0, 0.33, 0.25)
        d.rect(y - 1.75, -4.67, 3.5, 1.3, "FOOTING", "#d4d4d8")
        d.hatch(y - 1.75, -4.67, 3.5, 1.3, 0.45, angle=135)
        d.rect(y - 0.375, -3.37, 0.75, 3.37 + PLINTH, "COLUMN", "#d4d4d8")
    d.rect(gy0, PLINTH - 0.33, gy1 - gy0, 0.33, "SLAB", "#d4d4d8")
    d.hatch(gy0, 0, gy1 - gy0, PLINTH - 0.33, 0.8)  # plinth filling
    d.text(walls_y[0] - 2.5 if walls_y else gy0, -4.1, "FOOTING", 0.55, anchor="end", layer="DIM")
    d.text(walls_y[0] - 2.5 if walls_y else gy0, -5.0, "PCC 1:4:8", 0.55, anchor="end", layer="DIM")
    for i, lv in enumerate(plan["levels"]):
        z0, z1 = zs[i], zs[i + 1]
        cut = [r for r in lv["rooms"] if r["x"] - 0.01 <= xc <= r["x"] + r["w"] + 0.01]
        if not cut:
            continue
        ly0 = min(r["y"] for r in cut)
        ly1 = max(r["y"] + r["d"] for r in cut)
        if not (no_top_slab and i == n - 1):
            d.rect(ly0 - 0.5, z1 - SLAB, ly1 - ly0 + 1.0, SLAB, "SLAB", "#52525b")  # cut slab (dark)
        hw = [w for w in lv.get("walls", []) if w["y1"] == w["y2"] and min(w["x1"], w["x2"]) - 0.01 <= xc <= max(w["x1"], w["x2"]) + 0.01]
        for w in hw:
            t = THK.get(w["kind"], 0.5)
            d.rect(w["y1"] - t / 2, z1 - SLAB - 1.25, t, 1.25, "SLAB", "#52525b")  # beam under slab
            gap = next((o for o in lv.get("openings", []) if o["y1"] == o["y2"] and abs(o["y1"] - w["y1"]) < 0.01
                        and min(o["x1"], o["x2"]) - 0.01 <= xc <= max(o["x1"], o["x2"]) + 0.01), None)
            hz = z1 - SLAB - 1.25 - z0
            if gap and gap["type"] in ("window", "vent"):
                s = SILL[gap["type"]]
                d.rect(w["y1"] - t / 2, z0, t, s, "WALL", "#3f3f46", 0)
                d.rect(w["y1"] - t / 2, z0 + s, t, gap["h"], "WINDOW", "#e0f2fe")
                d.line(w["y1"], z0 + s, w["y1"], z0 + s + gap["h"], "WINDOW")
                d.rect(w["y1"] - t / 2, z0 + s + gap["h"], t, max(0, hz - s - gap["h"]), "WALL", "#3f3f46", 0)
            elif gap:
                d.rect(w["y1"] - t / 2, z0 + gap["h"], t, max(0, hz - gap["h"]), "WALL", "#3f3f46", 0)
            elif w["kind"] != "parapet":
                d.rect(w["y1"] - t / 2, z0, t, hz, "WALL", "#3f3f46", 0)
        for r in cut:
            cy = r["y"] + r["d"] / 2
            d.text(cy, z0 + 3.2, r["name"].upper(), 0.65, layer="ROOMTEXT", bold=True, mask=True)
            if r["type"] == "stair" and i < n - 1:
                steps = max(1, int((z1 - z0) / 0.5))  # 6" risers
                run = (r["d"] - 1.0) / steps
                pts = []
                for s_ in range(steps):
                    yy = r["y"] + 0.5 + s_ * run
                    zz = z0 + s_ * (z1 - z0) / steps
                    d.line(yy, zz, yy + run, zz, "STAIR")
                    d.line(yy + run, zz, yy + run, zz + (z1 - z0) / steps, "STAIR")
                    pts.append((yy, zz))
                d.line(r["y"] + 0.5, z0 - 0.6, r["y"] + r["d"] - 0.5, z1 - 0.6, "STAIR")  # waist slab
                d.line(r["y"] + 0.5, z0 + 3.0, r["y"] + r["d"] - 0.5, z1 + 3.0, "FURNITURE")  # handrail
        d.level(gy1 + 1.5, z0, f"+{z0 * FT_M:.2f} m  {lv['name'].upper()}")
        d.dim_v(gy0 - 2.5, z0, z1, ext_from=gy0 - 0.5)
    lvt = plan["levels"][-1]
    ty0, ty1 = _extent(lvt)[2], _extent(lvt)[3]
    roof = zs[-1]
    st = next((r for r in lvt["rooms"] if r["type"] == "stair" and r["x"] - 0.01 <= xc <= r["x"] + r["w"] + 0.01), None)
    if not no_top_slab:
        for yy in (ty0 - 0.25, ty1 - 0.25):
            d.rect(yy, roof, 0.5, PARAPET, "PARAPET", "#3f3f46", 0)
        if st and n > 1:
            d.rect(st["y"], roof, 0.5, HEADROOM, "WALL", "#3f3f46", 0)
            d.rect(st["y"] + st["d"] - 0.5, roof, 0.5, HEADROOM, "WALL", "#3f3f46", 0)
            if not sheet_mumty:
                d.rect(st["y"] - 0.5, roof + HEADROOM, st["d"] + 1.0, SLAB, "SLAB", "#52525b")
            d.text(st["y"] + st["d"] / 2, roof + HEADROOM / 2, "HEAD ROOM", 0.55, layer="DIM")
    draw_side(d, plan, "section")  # 1.17 sheet roofs (truss shown where the section cuts it)
    d.level(gy1 + 1.5, roof, f"+{roof * FT_M:.2f} m  {'EAVE (SHEET ROOF)' if no_top_slab else 'TERRACE'}")
    d.level(gy1 + 1.5, 0, "±0.00 m  G.L.")
    d.text((gy0 + gy1) / 2, -7.0, "SECTION A-A", 0.9, bold=True)
    d.line((gy0 + gy1) / 2 - 3.5, -7.3, (gy0 + gy1) / 2 + 3.5, -7.3, "TEXT")
    d.text((gy0 + gy1) / 2, -8.5, f"(cut through the {'staircase' if stair else 'middle'} · front / road side on the left)", 0.55, layer="DIM")
    return d


# ---------------------------------------------------------------- renderers
def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _arc_pts(it, steps=24):
    a0, a1 = math.radians(it["a0"]), math.radians(it["a1"])
    return [(it["cx"] + it["r"] * math.cos(a0 + (a1 - a0) * i / steps), it["cy"] + it["r"] * math.sin(a0 + (a1 - a0) * i / steps))
            for i in range(steps + 1)]


def _order(items):
    """Draw order: fills/shadows, hatch, rects, lines, arcs, then text on top."""
    rank = {"SHADOW": 0, "HATCH": 2, "MASK": 3.5}
    return sorted(items, key=lambda it: (4 if it["t"] == "text" else rank.get(it["layer"], 1 if it["t"] == "rect" else 3)))


def _fill(it, style: str):
    """Fill colour for a rect in this style (CAD screen: no fills, masks become the black background)."""
    if it["layer"] == "MASK":
        return PALETTE[style]["BG"]
    if style == "cad":
        return None
    return it["fill"]


def to_svg(d: Dwg, px: int = 900, style: str = "paper") -> str:
    x0, y0, x1, y1 = d.bounds()
    pad = 2
    W, H = (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad
    k = px / W
    mmk = k * 0.9  # px per mm of pen weight on screen

    def X(x):
        return (x - x0 + pad) * k

    def Y(y):
        return (y1 - y + pad) * k

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W * k:.0f} {H * k:.0f}" width="100%" '
           f'style="background:{PALETTE[style]["BG"]};font-family:Arial,Helvetica,sans-serif">']
    for it in _order(d.items):
        col, wmm, dash = pen(it["layer"], style)
        sw = max(0.35, wmm * mmk)
        da = f' stroke-dasharray="{",".join(f"{v * mmk:.1f}" for v in dash)}"' if dash else ""
        if it["t"] == "rect":
            if style == "cad" and it["layer"] == "SHADOW":
                continue
            fill = _fill(it, style) or "none"
            stroke = f'stroke="{col}" stroke-width="{sw:.2f}"{da}' if (it["lw"] or (style == "cad" and it["layer"] not in ("MASK",) and it["fill"])) else 'stroke="none"'
            out.append(f'<rect x="{X(it["x"]):.1f}" y="{Y(it["y"] + it["h"]):.1f}" width="{it["w"] * k:.1f}" '
                       f'height="{it["h"] * k:.1f}" fill="{fill}" {stroke}/>')
        elif it["t"] == "line":
            out.append(f'<line x1="{X(it["x1"]):.1f}" y1="{Y(it["y1"]):.1f}" x2="{X(it["x2"]):.1f}" '
                       f'y2="{Y(it["y2"]):.1f}" stroke="{col}" stroke-width="{sw:.2f}"{da}/>')
        elif it["t"] == "arc":
            pts = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in _arc_pts(it))
            out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="{sw:.2f}"{da}/>')
        else:
            out.append(f'<text x="{X(it["x"]):.1f}" y="{Y(it["y"]):.1f}" font-size="{it["h"] * k:.1f}" '
                       f'text-anchor="{it["anchor"]}" fill="{col}"{" font-weight=\"bold\"" if it["bold"] else ""}>'
                       f'{_esc(it["s"])}</text>')
    out.append("</svg>")
    return "".join(out)


STD_SCALES = [50, 75, 100, 125, 150, 200, 250, 300, 400, 500]


def _draw_pdf(c, d: Dwg, bx: float, by: float, bw: float, bh: float, style: str = "paper", scales=None) -> str:
    """Draw d into the box (points), at the largest standard scale that fits. Returns the scale text.
    Pen weights are real millimetres on paper (CAD plot style)."""
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    x0, y0, x1, y1 = d.bounds()
    wm, hm = (x1 - x0) * FT_M * 1000, (y1 - y0) * FT_M * 1000
    sc = next((s for s in (scales or STD_SCALES) if wm / s * mm <= bw and hm / s * mm <= bh), None)
    if sc:
        k = FT_M * 1000 / sc * mm
        label = f"1:{sc}"
    else:
        k = min(bw / (x1 - x0), bh / (y1 - y0))
        label = "NTS"
    ox = bx + (bw - (x1 - x0) * k) / 2 - x0 * k
    oy = by + (bh - (y1 - y0) * k) / 2 - y0 * k

    def safe(s):
        return (s.replace("×", "x").replace("–", "-").replace("²", "2").replace("³", "3").replace("±", "+/-"))

    if style == "cad":
        c.setFillColor(colors.HexColor(PALETTE["cad"]["BG"]))
        c.rect(bx, by, bw, bh, fill=1, stroke=0)
    for it in _order(d.items):
        col, wmm, dash = pen(it["layer"], style)
        c.setStrokeColor(colors.HexColor(col))
        c.setLineWidth(max(0.1, wmm * mm))
        c.setDash([v * mm for v in dash] if dash else [])
        if it["t"] == "rect":
            if style == "cad" and it["layer"] == "SHADOW":
                continue
            fl = _fill(it, style)
            if fl:
                c.setFillColor(colors.HexColor(fl))
            stroke = it["lw"] or (style == "cad" and it["layer"] != "MASK" and bool(it["fill"]))
            c.rect(ox + it["x"] * k, oy + it["y"] * k, it["w"] * k, it["h"] * k,
                   fill=1 if fl else 0, stroke=1 if stroke else 0)
        elif it["t"] == "line":
            c.line(ox + it["x1"] * k, oy + it["y1"] * k, ox + it["x2"] * k, oy + it["y2"] * k)
        elif it["t"] == "arc":
            p = c.beginPath()
            pts = _arc_pts(it)
            p.moveTo(ox + pts[0][0] * k, oy + pts[0][1] * k)
            for a, b in pts[1:]:
                p.lineTo(ox + a * k, oy + b * k)
            c.drawPath(p, stroke=1, fill=0)
        else:
            c.setDash([])
            c.setFillColor(colors.HexColor(col))
            fs = max(4.5, min(11, it["h"] * k))
            c.setFont("Helvetica-Bold" if it["bold"] else "Helvetica", fs)
            fn = {"start": c.drawString, "middle": c.drawCentredString, "end": c.drawRightString}[it["anchor"]]
            fn(ox + it["x"] * k, oy + it["y"] * k, safe(it["s"]))
    c.setDash([])
    return label


def sheet_set_pdf(plan: dict, project: dict, meta: dict, style: str = "paper") -> bytes:
    """A3 landscape drawing set: A-01 title & area statement, A-02 site plan, floor plans, elevation, section,
    door & window schedule. Title block with the firm's name on every sheet (no seal / signature printed)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    W, H = landscape(A3)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    co = project.get("company") or {}
    sched = schedule(plan)
    area = area_details(plan)
    drawings = [("A-02", "Site Plan", site_plan(plan))]
    drawings += [(f"A-{3 + i:02d}", f"{lv['name']} Plan", floor_plan(plan, i)) for i, lv in enumerate(plan["levels"])]
    n0 = 3 + len(plan["levels"])
    drawings += [(f"A-{n0:02d}", "Front Elevation", front_elevation(plan)), (f"A-{n0 + 1:02d}", "Section A-A", section(plan))]
    if plan.get("roof_sheets"):  # 1.17
        from .roof import roof_plan, truss_detail
        drawings += [(f"A-{n0 + 2:02d}", "Roof Plan (Sheet Roof)", roof_plan(plan)), (f"A-{n0 + 3:02d}", "Truss & Purlin Detail", truss_detail(plan))]
        n0 += 2
    from .stair import has_stair, stair_detail  # 1.18
    if has_stair(plan):
        drawings += [(f"A-{n0 + 2:02d}", "Staircase Detail", stair_detail(plan))]
        n0 += 1
    sheet_list = [("A-01", "Title Sheet & Area Statement")] + [(no, t) for no, t, _ in drawings] + \
                 [(f"A-{n0 + 2:02d}", "Door & Window Schedule")]
    navy = colors.HexColor("#0F2350")
    M = 10 * mm
    TB_W = 120 * mm  # title block on the right

    def frame(no: str, title: str, scale: str):
        c.setStrokeColor(colors.black)
        c.setLineWidth(1.2)
        c.rect(M, M, W - 2 * M, H - 2 * M)
        x = W - M - TB_W
        c.setLineWidth(0.8)
        c.line(x, M, x, H - M)
        y = H - M
        c.setFillColor(navy)
        c.rect(x, y - 24 * mm, TB_W, 24 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(x + 5 * mm, y - 11 * mm, (co.get("name") or "")[:34])
        c.setFont("Helvetica", 8.5)
        line = " · ".join(v for v in [f"Proprietor: {co['proprietor']}" if co.get("proprietor") else "", co.get("phone", "")] if v)
        c.drawString(x + 5 * mm, y - 18 * mm, line[:70])
        rows = [("Project", project.get("name", "")), ("Project code", project.get("code", "")),
                ("Client / owner", project.get("client_name") or "-"),
                ("Location", ", ".join(v for v in [project.get("location"), project.get("district")] if v) or "-"),
                ("Plot", (f"Irregular · {plan['plot']['info']['area_sqft']:g} sq ft" if plan['plot'].get('info') else f"{plan['plot']['w']:g}' x {plan['plot']['d']:g}'") + f" · {plan['facing'].title()} facing"),
                ("Drawing", title), ("Sheet no.", no), ("Scale (on A3)", scale),
                ("Design version", f"v{meta.get('version', '')}"), ("Date", meta.get("date", ""))]
        yy = y - 24 * mm
        c.setFillColor(colors.black)
        for k, v in rows:
            yy -= 9 * mm
            c.setStrokeColor(colors.HexColor("#94a3b8"))
            c.setLineWidth(0.4)
            c.line(x, yy, W - M, yy)
            c.setFont("Helvetica", 7)
            c.setFillColor(colors.HexColor("#475569"))
            c.drawString(x + 3 * mm, yy + 5.5 * mm, k)
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(colors.black)
            c.drawString(x + 3 * mm, yy + 1.8 * mm, str(v)[:60])
        # signature boxes – left empty on purpose (signed by hand)
        yy -= 4 * mm
        for lab in ("Prepared by (signature)", "Owner (signature)", "Licensed engineer / architect (signature & reg. no.)"):
            c.setFont("Helvetica", 7)
            c.setFillColor(colors.HexColor("#475569"))
            c.drawString(x + 3 * mm, yy - 3.5 * mm, lab)
            yy -= 17 * mm
            c.line(x, yy, W - M, yy)
        c.setFont("Helvetica-Oblique", 6.5)
        c.setFillColor(colors.HexColor("#64748b"))
        notes = ["Concept / submission drawing prepared from the design.", "All dimensions in feet and inches unless noted.",
                 "Structural members as per structural drawings.", "Verify setbacks, FSI and coverage with the local body."]
        for i, t in enumerate(notes):
            c.drawString(x + 3 * mm, M + (4 + 3.5 * (len(notes) - i)) * mm, t)
        c.setFont("Helvetica-Bold", 22)
        c.setFillColor(navy)
        c.drawRightString(W - M - 4 * mm, M + 2 * mm, no)

    area_box = (M + 8 * mm, M + 8 * mm, W - 2 * M - TB_W - 16 * mm, H - 2 * M - 22 * mm)

    def heading(t):
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(navy)
        c.drawString(M + 8 * mm, H - M - 12 * mm, t)

    def table(x, y, headers, rows, widths, fs=8.5, rh=6.5 * mm):
        c.setFillColor(navy)
        c.rect(x, y - rh, sum(widths), rh, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", fs)
        xx = x
        for h_, w_ in zip(headers, widths):
            c.drawString(xx + 2 * mm, y - rh + 2 * mm, h_)
            xx += w_
        c.setFont("Helvetica", fs)
        for ri, r in enumerate(rows):
            y -= rh
            if ri % 2:
                c.setFillColor(colors.HexColor("#F4F7FC"))
                c.rect(x, y - rh, sum(widths), rh, fill=1, stroke=0)
            c.setFillColor(colors.black)
            xx = x
            for v, w_ in zip(r, widths):
                c.drawString(xx + 2 * mm, y - rh + 2 * mm, str(v)[: int(w_ / (fs * 0.5))])
                xx += w_
            c.setStrokeColor(colors.HexColor("#cbd5e1"))
            c.setLineWidth(0.3)
            c.line(x, y - rh, x + sum(widths), y - rh)
        return y - rh

    # A-01 title sheet
    frame("A-01", "Title Sheet & Area Statement", "-")
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(navy)
    c.drawString(M + 8 * mm, H - M - 20 * mm, (project.get("name") or "")[:50])
    c.setFont("Helvetica", 11)
    c.setFillColor(colors.black)
    c.drawString(M + 8 * mm, H - M - 28 * mm, f"Proposed residential building · {len(plan['levels'])} floor(s) · "
                                               f"plot {plan['plot']['w']:g}' x {plan['plot']['d']:g}'")
    y = table(M + 8 * mm, H - M - 38 * mm, ["Sheet", "Drawing"], sheet_list, [25 * mm, 90 * mm])
    rows = [[r["floor"], f"{r['builtup_sqft']:,.0f}", f"{r['builtup_sqft'] * FT_M ** 2:,.1f}", f"{r['carpet_sqft']:,.0f}", r["use"]]
            for r in area["rows"]]
    rows.append(["Total", f"{area['total_builtup_sqft']:,.0f}", f"{area['total_builtup_m2']:,.1f}",
                 f"{sum(r['carpet_sqft'] for r in area['rows']):,.0f}", ""])
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(navy)
    c.drawString(M + 140 * mm, H - M - 35 * mm, "AREA STATEMENT")
    y2 = table(M + 140 * mm, H - M - 38 * mm, ["Floor", "Built-up sq ft", "m²".replace("²", "2"), "Carpet sq ft", "Use"],
               rows, [34 * mm, 28 * mm, 20 * mm, 26 * mm, 26 * mm])
    sbm = area["setbacks_m"]
    facts = [["Plot area", f"{area['plot_sqft']:,.0f} sq ft ({area['plot_m2']:,.1f} m2)"],
             ["Total built-up", f"{area['total_builtup_sqft']:,.0f} sq ft ({area['total_builtup_m2']:,.1f} m2)"],
             ["FSI (achieved)", f"{area['fsi']}"], ["Ground coverage", f"{area['coverage_pct']}%"],
             ["Open space", f"{area['open_space_sqft']:,.0f} sq ft ({area['open_space_pct']}%)"],
             ["Building height", f"{area['height_m']} m (incl. parapet / head room)"]]
    for rs in area.get("roof_sheets") or []:
        facts.append([f"Sheet roof ({rs['level']})", f"{rs['type']} · {rs['covered_sqft']:,.0f} sq ft covered"])
    if sbm:
        facts.append(["Setbacks (m)", " · ".join(f"{k[0].upper()} {sbm[k]:g}" for k in ("front", "rear", "left", "right") if k in sbm)])
    table(M + 140 * mm, y2 - 8 * mm, ["Particular", "Value"], facts, [40 * mm, 94 * mm])
    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColor(colors.HexColor("#64748b"))
    for i, t in enumerate(area["note"].split("; ")):
        c.drawString(M + 140 * mm, M + (16 - 4 * i) * mm, t[:110])
    c.showPage()

    for no, title, dwg in drawings:
        frame(no, title, "")
        heading(title)
        scale = _draw_pdf(c, dwg, *area_box, style=style)
        c.setFillColor(colors.white)  # overwrite the scale row of the title block
        x = W - M - TB_W
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.black)
        yy = H - M - 24 * mm - 8 * 9 * mm
        c.drawString(x + 3 * mm, yy + 1.8 * mm, scale)
        c.showPage()

    no = f"A-{n0 + 2:02d}"
    frame(no, "Door & Window Schedule", "-")
    heading("Door & Window Schedule")
    levels = [lv["name"] for lv in plan["levels"]]
    rows = [[s["mark"], s["label"], s["size"], f"{s['sill_ft']:g}'" if s["sill_ft"] else "-",
             *[s["per_level"].get(l, 0) or "-" for l in levels], s["count"], s["material"]] for s in sched]
    avail = W - 2 * M - TB_W - 16 * mm
    lw = 18 * mm
    mat_w = max(50 * mm, avail - (118 * mm + lw * len(levels)))
    table(M + 8 * mm, H - M - 20 * mm, ["Mark", "Type", "Size (W x H)", "Sill", *[l.replace(" Floor", "") for l in levels], "Total", "Material / remarks"],
          rows, [16 * mm, 38 * mm, 34 * mm, 14 * mm, *[lw] * len(levels), 16 * mm, mat_w])
    c.showPage()
    c.save()
    return buf.getvalue()


def sheets_dxf(plan: dict, project: dict, meta: dict) -> bytes:
    """All drawings (site plan, floor plans, elevation, section) side by side in one DXF (feet)."""
    schedule(plan)
    dwgs = [site_plan(plan)] + [floor_plan(plan, i) for i in range(len(plan["levels"]))] + [front_elevation(plan), section(plan)]
    if plan.get("roof_sheets"):
        from .roof import roof_plan, truss_detail
        dwgs += [roof_plan(plan), truss_detail(plan)]
    from .stair import has_stair, stair_detail  # 1.18
    if has_stair(plan):
        dwgs.append(stair_detail(plan))
    co = project.get("company") or {}
    return dwgs_dxf(dwgs, f"{co.get('name', '')} - {project.get('name', '')} - design v{meta.get('version', '')}")


def dwgs_dxf(dwgs: list, footer: str) -> bytes:
    from .exports import _dxf_line, _dxf_text
    layers = sorted({it["layer"] for d in dwgs for it in d.items} | {"TITLE"})
    out = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "2", "0", "ENDSEC",
           "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", str(len(layers))]
    for name in layers:
        out += ["0", "LAYER", "2", name, "70", "0", "62", str(DXF_COLOR.get(name, 7)), "6", "CONTINUOUS"]
    out += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    ox = 0.0
    for d in dwgs:
        x0, y0, x1, y1 = d.bounds()
        dx = ox - x0
        for it in d.items:
            if it["t"] == "line":
                _dxf_line(out, it["layer"], it["x1"] + dx, it["y1"] - y0, it["x2"] + dx, it["y2"] - y0)
            elif it["t"] == "rect" and it["layer"] in ("MASK", "SHADOW"):
                continue
            elif it["t"] == "rect":
                x, y, w, h = it["x"] + dx, it["y"] - y0, it["w"], it["h"]
                for a, b, cc, dd in ((x, y, x + w, y), (x + w, y, x + w, y + h), (x + w, y + h, x, y + h), (x, y + h, x, y)):
                    _dxf_line(out, it["layer"], a, b, cc, dd)
            elif it["t"] == "arc":
                out += ["0", "ARC", "8", it["layer"], "10", f"{it['cx'] + dx:.3f}", "20", f"{it['cy'] - y0:.3f}", "30", "0",
                        "40", f"{it['r']:.3f}", "50", f"{it['a0'] % 360:.2f}", "51", f"{(it['a1'] if it['a1'] - it['a0'] < 360 else it['a0'] + 359.99) % 360:.2f}"]
            else:
                _dxf_text(out, it["layer"], it["x"] + dx, it["y"] - y0, it["h"], it["s"].replace("±", "+/-"), center=it["anchor"] == "middle")
        _dxf_text(out, "TITLE", ox + (x1 - x0) / 2, -4, 1.5, d.title.upper())
        ox += (x1 - x0) + 20
    _dxf_text(out, "TITLE", 0, -8, 1.2, footer, center=False)
    out += ["0", "ENDSEC", "0", "EOF"]
    return ("\r\n".join(out) + "\r\n").encode("ascii", "replace")


def sheet_pages(plan: dict) -> dict:
    """1.13: preview key -> page number (1-based) in sheet_set_pdf, so each sheet can be downloaded alone."""
    from .stair import has_stair
    n = len(plan["levels"])
    k = 2 if plan.get("roof_sheets") else 0
    st = 1 if has_stair(plan) else 0
    out = {"title": 1, "site": 2, **{f"plan_{i}": 3 + i for i in range(n)}, "elevation": 3 + n, "section": 4 + n,
           "schedule": 5 + n + k + st}
    if k:
        out.update({"roof": 5 + n, "truss": 6 + n})
    if st:
        out["stair"] = 5 + n + k
    return out


def pdf_pages(data: bytes, pages: list[int]) -> bytes:
    """Keep only the given pages (1-based) of a PDF."""
    from pypdf import PdfReader, PdfWriter
    r = PdfReader(io.BytesIO(data))
    w = PdfWriter()
    for pg in pages:
        if 1 <= pg <= len(r.pages):
            w.add_page(r.pages[pg - 1])
    if not len(w.pages):
        raise ValueError("No such sheet")
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def sheet_previews(plan: dict) -> dict:
    """SVG previews (paper and CAD-screen colours) + tables for the Design page."""
    sched = schedule(plan)
    dw = {"site": site_plan(plan), "elevation": front_elevation(plan), "section": section(plan),
          **{f"plan_{i}": floor_plan(plan, i) for i in range(len(plan["levels"]))}}
    if plan.get("roof_sheets"):
        from .roof import roof_plan, truss_detail
        dw.update({"roof": roof_plan(plan), "truss": truss_detail(plan)})
    from .stair import design as stair_design, has_stair, stair_detail  # 1.18
    if has_stair(plan):
        dw["stair"] = stair_detail(plan)
    return {
        "stair": stair_design(plan) if has_stair(plan) else None,
        "schedule": sched, "area": area_details(plan),
        "svgs": {k: to_svg(v) for k, v in dw.items()},
        "svgs_cad": {k: to_svg(v, style="cad") for k, v in dw.items()},
        "levels": [lv["name"] for lv in plan["levels"]],
        "pages": sheet_pages(plan),
    }
