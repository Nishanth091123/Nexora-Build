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
    plot_sqft = plot["w"] * plot["d"]
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
        "setbacks_m": sb.get("m", {}), "setbacks_ft": sb.get("ft", {}),
        "note": "FSI = total built-up / plot area; coverage = ground floor built-up / plot area. "
                "Check the permitted values for the local body (DTCP / CMDA / Corporation / Panchayat).",
    }


def building_height(plan: dict) -> float:
    H = float(plan.get("floor_height_ft") or 10)
    n = len(plan["levels"])
    stair = any(r["type"] == "stair" for lv in plan["levels"] for r in lv["rooms"]) and n > 1
    return PLINTH + n * H + PARAPET + (HEADROOM - PARAPET if stair else 0)


# ---------------------------------------------------------------- primitive drawings
class Dwg:
    """lines / rects / texts in feet. layer names follow DXF layers; 'fill' is a hex colour or None."""

    def __init__(self, title: str):
        self.title = title
        self.items: list[dict] = []

    def line(self, x1, y1, x2, y2, layer="LINE", w=0.6):
        self.items.append({"t": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "layer": layer, "w": w})

    def rect(self, x, y, w, h, layer="LINE", fill=None, lw=0.6):
        self.items.append({"t": "rect", "x": x, "y": y, "w": w, "h": h, "layer": layer, "fill": fill, "lw": lw})

    def text(self, x, y, s, h=0.9, anchor="middle", layer="TEXT", bold=False):
        self.items.append({"t": "text", "x": x, "y": y, "s": str(s), "h": h, "anchor": anchor, "layer": layer, "bold": bold})

    def dim_h(self, x1, x2, y, label=None, off=0.0):
        self.line(x1, y, x2, y, "DIM", 0.3)
        for x in (x1, x2):
            self.line(x, y - 0.5, x, y + 0.5, "DIM", 0.3)
        self.text((x1 + x2) / 2, y + 0.35 + off, label or ft_in(abs(x2 - x1)), 0.75, layer="DIM")

    def dim_v(self, x, y1, y2, label=None):
        self.line(x, y1, x, y2, "DIM", 0.3)
        for y in (y1, y2):
            self.line(x - 0.5, y, x + 0.5, y, "DIM", 0.3)
        self.text(x - 0.6, (y1 + y2) / 2, label or ft_in(abs(y2 - y1)), 0.75, anchor="end", layer="DIM")

    def bounds(self):
        xs, ys = [], []
        for it in self.items:
            if it["t"] == "line":
                xs += [it["x1"], it["x2"]]
                ys += [it["y1"], it["y2"]]
            elif it["t"] == "rect":
                xs += [it["x"], it["x"] + it["w"]]
                ys += [it["y"], it["y"] + it["h"]]
            else:
                L = len(it["s"]) * it["h"] * 0.55
                a = {"start": 0, "middle": -L / 2, "end": -L}[it["anchor"]]
                xs += [it["x"] + a, it["x"] + a + L]
                ys += [it["y"], it["y"] + it["h"]]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 1, 1)


FILL = {"bedroom": "#dbeafe", "toilet": "#e0f2fe", "common_toilet": "#e0f2fe", "kitchen": "#fef3c7",
        "hall": "#fde7d3", "lounge": "#fde7d3", "dining": "#fef9c3", "pooja": "#fce7f3", "stair": "#e5e7eb",
        "parking": "#f3f4f6", "passage": "#f8fafc", "dress": "#ede9fe", "terrace": "#ecfccb", "balcony": "#ecfccb",
        "sitout": "#ecfccb"}
THK = {"ext": 0.755, "int230": 0.755, "int115": 0.377, "parapet": 0.5}


def floor_plan(plan: dict, li: int) -> Dwg:
    lv = plan["levels"][li]
    d = Dwg(f"{lv['name']} Plan")
    for r in lv["rooms"]:
        d.rect(r["x"], r["y"], r["w"], r["d"], "ROOM", FILL.get(r["type"], "#ffffff"), 0.2)
    for w in lv.get("walls", []):
        t = THK.get(w["kind"], 0.5)
        if w["y1"] == w["y2"]:
            d.rect(min(w["x1"], w["x2"]), w["y1"] - t / 2, abs(w["x2"] - w["x1"]), t, "WALL", "#1e293b", 0)
        else:
            d.rect(w["x1"] - t / 2, min(w["y1"], w["y2"]), t, abs(w["y2"] - w["y1"]), "WALL", "#1e293b", 0)
    for o in lv.get("openings", []):
        win = o["type"] in ("window", "vent")
        col = "#38bdf8" if win else "#ffffff"
        horiz = o["y1"] == o["y2"]
        if horiz:
            d.rect(min(o["x1"], o["x2"]), o["y1"] - 0.42, o["w"], 0.84, "WINDOW" if win else "DOOR", col, 0.2)
            tx, ty = (o["x1"] + o["x2"]) / 2, o["y1"] + (1.0 if o["y1"] > 0.1 else -1.6)
        else:
            d.rect(o["x1"] - 0.42, min(o["y1"], o["y2"]), 0.84, o["w"], "WINDOW" if win else "DOOR", col, 0.2)
            tx, ty = o["x1"] + (1.3 if o["x1"] < 0.1 else -1.3), (o["y1"] + o["y2"]) / 2
        if o.get("mark"):
            d.text(tx, ty, o["mark"], 0.65, layer="TEXT")
    for r in lv["rooms"]:
        cx, cy = r["x"] + r["w"] / 2, r["y"] + r["d"] / 2
        m = min(r["w"], r["d"])
        fs = 0.85 if m >= 7 else 0.6 if m >= 5.5 else 0.45
        d.text(cx, cy + 0.2, r["name"].upper(), fs, bold=True)
        d.text(cx, cy - fs - 0.1, f"{ft_in(r['w'])} x {ft_in(r['d'])}", fs * 0.85)
        if r["type"] == "stair":
            for k in range(1, int(r["d"] // 1)):
                d.line(r["x"] + 0.4, r["y"] + k, r["x"] + r["w"] - 0.4, r["y"] + k, "LINE", 0.15)
    xs = [r["x"] for r in lv["rooms"]] + [r["x"] + r["w"] for r in lv["rooms"]]
    ys = [r["y"] for r in lv["rooms"]] + [r["y"] + r["d"] for r in lv["rooms"]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    d.dim_h(x0, x1, y1 + 2.5)
    d.dim_v(x0 - 2.5, y0, y1)
    d.text((x0 + x1) / 2, y0 - 4.2, "FRONT (ROAD SIDE)", 0.8, layer="TEXT")
    return d


def site_plan(plan: dict) -> Dwg:
    plot, b, sb = plan["plot"], plan["building"], plan.get("setbacks") or {}
    d = Dwg("Site Plan")
    d.rect(0, 0, plot["w"], plot["d"], "PLOT", "#f0fdf4", 0.8)
    lv0 = plan["levels"][0]
    xs = [r["x"] for r in lv0["rooms"]] + [r["x"] + r["w"] for r in lv0["rooms"]]
    ys = [r["y"] for r in lv0["rooms"]] + [r["y"] + r["d"] for r in lv0["rooms"]]
    bx0, bx1, by0, by1 = b["x"] + min(xs), b["x"] + max(xs), b["y"] + min(ys), b["y"] + max(ys)
    d.rect(bx0, by0, bx1 - bx0, by1 - by0, "BUILDING", "#cbd5e1", 0.8)
    d.text((bx0 + bx1) / 2, (by0 + by1) / 2, "PROPOSED BUILDING", 1.0, bold=True)
    d.text((bx0 + bx1) / 2, (by0 + by1) / 2 - 1.5, f"{len(plan['levels'])} floor(s)", 0.8)
    d.rect(-2, -7, plot["w"] + 4, 4.5, "ROAD", "#e2e8f0", 0.3)
    road = sb.get("road_width_m") or (plan.get("requirements") or {}).get("road_width_m")
    d.text(plot["w"] / 2, -5.4, f"ROAD{f' ({road:g} m wide)' if isinstance(road, (int, float)) else ''}", 0.9, bold=True)
    ft = sb.get("ft") or {}
    d.dim_v(-1.2, 0, by0, f"Front {ft.get('front', by0):g}'") if by0 > 0.1 else None
    d.dim_v(-1.2, by1, plot["d"], f"Rear {ft.get('rear', plot['d'] - by1):g}'") if plot["d"] - by1 > 0.1 else None
    d.dim_h(0, bx0, plot["d"] + 1.5, f"{ft.get('left', bx0):g}'") if bx0 > 0.1 else None
    d.dim_h(bx1, plot["w"], plot["d"] + 1.5, f"{ft.get('right', plot['w'] - bx1):g}'") if plot["w"] - bx1 > 0.1 else None
    d.dim_h(0, plot["w"], plot["d"] + 4, f"Plot {ft_in(plot['w'])}")
    d.dim_v(plot["w"] + 3, 0, plot["d"], f"{ft_in(plot['d'])}")
    _north(d, plan, plot["w"] + 6, plot["d"] - 3)
    return d


def _north(d: Dwg, plan: dict, ax: float, ay: float):
    up, right = plan["compass"]["up"], plan["compass"]["right"]
    nx, ny = right[1], up[1]
    d.line(ax - nx * 2.5, ay - ny * 2.5, ax + nx * 2.5, ay + ny * 2.5, "TEXT", 1.0)
    d.line(ax + nx * 2.5, ay + ny * 2.5, ax + nx * 1.5 - ny * 0.7, ay + ny * 1.5 + nx * 0.7, "TEXT", 1.0)
    d.line(ax + nx * 2.5, ay + ny * 2.5, ax + nx * 1.5 + ny * 0.7, ay + ny * 1.5 - nx * 0.7, "TEXT", 1.0)
    d.text(ax + nx * 3.6, ay + ny * 3.6 - 0.4, "N", 1.1, bold=True)


def _extent(lv: dict):
    xs = [r["x"] for r in lv["rooms"]] + [r["x"] + r["w"] for r in lv["rooms"]]
    ys = [r["y"] for r in lv["rooms"]] + [r["y"] + r["d"] for r in lv["rooms"]]
    return min(xs), max(xs), min(ys), max(ys)


def _levels_z(plan: dict) -> list[float]:
    H = float(plan.get("floor_height_ft") or 10)
    return [PLINTH + i * H for i in range(len(plan["levels"]) + 1)]  # floor top of each level + roof


def front_elevation(plan: dict) -> Dwg:
    d = Dwg("Front Elevation")
    H = float(plan.get("floor_height_ft") or 10)
    zs = _levels_z(plan)
    n = len(plan["levels"])
    gx0 = min(_extent(lv)[0] for lv in plan["levels"])
    gx1 = max(_extent(lv)[1] for lv in plan["levels"])
    d.line(gx0 - 4, 0, gx1 + 4, 0, "GROUND", 1.2)
    for k in range(int(gx0 - 4), int(gx1 + 4), 2):  # ground hatch
        d.line(k, 0, k + 1, -1, "GROUND", 0.2)
    d.rect(gx0 - 0.4, 0, gx1 - gx0 + 0.8, PLINTH, "WALL", "#cbd5e1", 0.5)
    for i, lv in enumerate(plan["levels"]):
        x0, x1, y0, _ = _extent(lv)
        z0, z1 = zs[i], zs[i + 1]
        if lv.get("stilt") or any(r["type"] == "parking" and r["y"] <= y0 + 0.1 for r in lv["rooms"]) and i == 0:
            # open parking front: columns only where the parking is
            park = [r for r in lv["rooms"] if r["type"] == "parking" and r["y"] <= y0 + 0.1]
            for r in park:
                for xx in (r["x"], r["x"] + r["w"] - 0.75):
                    d.rect(xx, z0, 0.75, z1 - z0 - SLAB, "COLUMN", "#94a3b8", 0.4)
            solid = [(r["x"], r["x"] + r["w"]) for r in lv["rooms"] if r["y"] <= y0 + 0.1 and r["type"] != "parking"]
            for a, b in solid:
                d.rect(a, z0, b - a, z1 - z0 - SLAB, "WALL", "#f8fafc", 0.5)
        else:
            d.rect(x0, z0, x1 - x0, z1 - z0 - SLAB, "WALL", "#f8fafc", 0.6)
        d.rect(x0 - 0.5, z1 - SLAB, x1 - x0 + 1.0, SLAB, "SLAB", "#64748b", 0.4)
        # front openings: on horizontal external walls in the front 6 ft of this floor
        for o in lv.get("openings", []):
            if o["y1"] != o["y2"] or o["y1"] > y0 + 6.01:
                continue
            ox0, ox1 = min(o["x1"], o["x2"]), max(o["x1"], o["x2"])
            if o["type"] in ("window", "vent"):
                sz = z0 + SILL[o["type"]]
                d.rect(ox0, sz, ox1 - ox0, o["h"], "WINDOW", "#bae6fd", 0.5)
                d.line((ox0 + ox1) / 2, sz, (ox0 + ox1) / 2, sz + o["h"], "WINDOW", 0.3)
                d.rect(ox0 - 0.5, sz + o["h"] + 0.4, ox1 - ox0 + 1.0, 0.25, "SUNSHADE", "#475569", 0.3)
            elif o["type"] in ("main_door", "door"):
                d.rect(ox0, z0, ox1 - ox0, o["h"], "DOOR", "#d6b48a", 0.5)
            if o.get("mark"):
                mz = z0 + SILL[o["type"]] - 0.9 if o["type"] in ("window", "vent") else z0 + o["h"] + 0.3
                d.text((ox0 + ox1) / 2, mz, o["mark"], 0.55, layer="DIM")
        d.text(x1 + 1.2, z0 + 0.3, f"+{z0 * FT_M:.2f} m", 0.7, anchor="start", layer="DIM")
        d.text(x1 + 1.2, z0 + 1.4, lv["name"], 0.7, anchor="start", layer="DIM")
    tx0, tx1, _, _ = _extent(plan["levels"][-1])
    roof = zs[-1]
    d.rect(tx0, roof, tx1 - tx0, PARAPET, "PARAPET", "#e2e8f0", 0.5)
    stair = next((r for r in plan["levels"][-1]["rooms"] if r["type"] == "stair"), None)
    if stair and n > 1:
        d.rect(stair["x"], roof, stair["w"], HEADROOM, "WALL", "#f1f5f9", 0.6)
        d.rect(stair["x"] - 0.5, roof + HEADROOM, stair["w"] + 1.0, SLAB, "SLAB", "#64748b", 0.4)
        d.text(stair["x"] + stair["w"] / 2, roof + HEADROOM / 2, "HEAD ROOM", 0.6, layer="DIM")
    top = roof + (HEADROOM if stair and n > 1 else PARAPET)
    d.text(tx1 + 1.2, roof + 0.3, f"+{roof * FT_M:.2f} m Terrace", 0.7, anchor="start", layer="DIM")
    d.dim_v(gx0 - 2.5, 0, top, f"{top * FT_M:.2f} m")
    d.dim_h(gx0, gx1, -2.5)
    d.text((gx0 + gx1) / 2, -4.3, "FRONT ELEVATION (ROAD SIDE)", 0.85, bold=True)
    return d


def section(plan: dict) -> Dwg:
    """Section A-A along the depth, cut through the staircase (or the middle of the building)."""
    d = Dwg("Section A-A")
    zs = _levels_z(plan)
    n = len(plan["levels"])
    lv0 = plan["levels"][0]
    stair = next((r for r in lv0["rooms"] if r["type"] == "stair"), None)
    x0, x1, _, _ = _extent(lv0)
    xc = stair["x"] + stair["w"] / 2 if stair else (x0 + x1) / 2
    gy0 = min(_extent(lv)[2] for lv in plan["levels"])
    gy1 = max(_extent(lv)[3] for lv in plan["levels"])
    # ground, footings, PCC
    d.line(gy0 - 4, 0, gy1 + 4, 0, "GROUND", 1.2)
    for k in range(int(gy0 - 4), int(gy1 + 4), 2):
        d.line(k, 0, k + 1, -1, "GROUND", 0.2)
    walls_y = sorted({round(w["y1"], 2) for w in lv0.get("walls", []) if w["y1"] == w["y2"]
                      and min(w["x1"], w["x2"]) - 0.01 <= xc <= max(w["x1"], w["x2"]) + 0.01})
    for y in walls_y:
        d.rect(y - 2.0, -5.0, 4.0, 0.33, "PCC", "#e5e7eb", 0.3)
        d.rect(y - 1.75, -4.67, 3.5, 1.3, "FOOTING", "#94a3b8", 0.4)
        d.rect(y - 0.375, -3.37, 0.75, 3.37 + PLINTH, "COLUMN", "#cbd5e1", 0.3)
    d.rect(gy0, PLINTH - 0.33, gy1 - gy0, 0.33, "SLAB", "#94a3b8", 0.3)  # floor bed
    d.text(gy0 - 3, -4.2, "FOOTING", 0.6, anchor="end", layer="DIM")
    for i, lv in enumerate(plan["levels"]):
        z0, z1 = zs[i], zs[i + 1]
        cut = [r for r in lv["rooms"] if r["x"] - 0.01 <= xc <= r["x"] + r["w"] + 0.01]
        if not cut:
            continue
        ly0 = min(r["y"] for r in cut)
        ly1 = max(r["y"] + r["d"] for r in cut)
        d.rect(ly0 - 0.5, z1 - SLAB, ly1 - ly0 + 1.0, SLAB, "SLAB", "#475569", 0.3)
        hw = [w for w in lv.get("walls", []) if w["y1"] == w["y2"] and min(w["x1"], w["x2"]) - 0.01 <= xc <= max(w["x1"], w["x2"]) + 0.01]
        for w in hw:
            t = THK.get(w["kind"], 0.5)
            gap = next((o for o in lv.get("openings", []) if o["y1"] == o["y2"] and abs(o["y1"] - w["y1"]) < 0.01
                        and min(o["x1"], o["x2"]) - 0.01 <= xc <= max(o["x1"], o["x2"]) + 0.01), None)
            hz = z1 - SLAB - z0
            if gap and gap["type"] in ("window", "vent"):
                s = SILL[gap["type"]]
                d.rect(w["y1"] - t / 2, z0, t, s, "WALL", "#334155", 0)
                d.rect(w["y1"] - t / 2, z0 + s, t, gap["h"], "WINDOW", "#bae6fd", 0.2)
                d.rect(w["y1"] - t / 2, z0 + s + gap["h"], t, hz - s - gap["h"], "WALL", "#334155", 0)
            elif gap:
                d.rect(w["y1"] - t / 2, z0 + gap["h"], t, hz - gap["h"], "WALL", "#334155", 0)
            elif w["kind"] != "parapet":
                d.rect(w["y1"] - t / 2, z0, t, hz, "WALL", "#334155", 0)
        for r in cut:
            cy = r["y"] + r["d"] / 2
            d.text(cy, z0 + (z1 - z0) / 2, r["name"].upper(), 0.7, bold=True)
            if r["type"] == "stair" and i < n - 1:
                steps = max(1, int((z1 - z0) / 0.5))  # 6" risers
                for s_ in range(steps):  # one straight flight drawn across the stair room
                    yy = r["y"] + 0.5 + s_ * (r["d"] - 1.0) / steps
                    d.line(yy, z0 + s_ * (z1 - z0) / steps, yy + (r["d"] - 1.0) / steps, z0 + s_ * (z1 - z0) / steps, "STAIR", 0.3)
                    d.line(yy + (r["d"] - 1.0) / steps, z0 + s_ * (z1 - z0) / steps, yy + (r["d"] - 1.0) / steps,
                           z0 + (s_ + 1) * (z1 - z0) / steps, "STAIR", 0.3)
        d.text(gy1 + 1.5, z0 + 0.3, f"+{z0 * FT_M:.2f} m  {lv['name']}", 0.7, anchor="start", layer="DIM")
        d.dim_v(gy0 - 2.5, z0, z1)
    lvt = plan["levels"][-1]
    ty0, ty1 = _extent(lvt)[2], _extent(lvt)[3]
    roof = zs[-1]
    d.rect(ty0 - 0.25, roof, 0.5, PARAPET, "PARAPET", "#94a3b8", 0.2)
    d.rect(ty1 - 0.25, roof, 0.5, PARAPET, "PARAPET", "#94a3b8", 0.2)
    st = next((r for r in lvt["rooms"] if r["type"] == "stair" and r["x"] - 0.01 <= xc <= r["x"] + r["w"] + 0.01), None)
    if st and n > 1:
        d.rect(st["y"], roof, 0.5, HEADROOM, "WALL", "#334155", 0)
        d.rect(st["y"] + st["d"] - 0.5, roof, 0.5, HEADROOM, "WALL", "#334155", 0)
        d.rect(st["y"] - 0.5, roof + HEADROOM, st["d"] + 1.0, SLAB, "SLAB", "#475569", 0.3)
        d.text(st["y"] + st["d"] / 2, roof + HEADROOM / 2, "HEAD ROOM", 0.6, layer="DIM")
    d.text(gy1 + 1.5, roof + 0.3, f"+{roof * FT_M:.2f} m  Terrace", 0.7, anchor="start", layer="DIM")
    d.text(gy1 + 1.5, 0.3, "+0.00 m  GL", 0.7, anchor="start", layer="DIM")
    d.text((gy0 + gy1) / 2, -7.0, f"SECTION A-A (cut through {'staircase' if stair else 'middle'}, looking from the left side)", 0.8, bold=True)
    d.text(gy0, -8.6, "FRONT (road) on the left", 0.6, anchor="start", layer="DIM")
    return d


# ---------------------------------------------------------------- renderers
def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def to_svg(d: Dwg, px: int = 900) -> str:
    x0, y0, x1, y1 = d.bounds()
    pad = 2
    W, H = (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad
    k = px / W

    def X(x):
        return (x - x0 + pad) * k

    def Y(y):
        return (y1 - y + pad) * k

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W * k:.0f} {H * k:.0f}" width="100%" '
           f'style="background:#fff;font-family:Arial,Helvetica,sans-serif">']
    for it in d.items:
        if it["t"] == "rect":
            fill = it["fill"] or "none"
            sw = it["lw"] * k * 0.06 if it["lw"] else 0
            out.append(f'<rect x="{X(it["x"]):.1f}" y="{Y(it["y"] + it["h"]):.1f}" width="{it["w"] * k:.1f}" '
                       f'height="{it["h"] * k:.1f}" fill="{fill}" stroke="#334155" stroke-width="{sw:.2f}"/>')
    for it in d.items:
        if it["t"] == "line":
            col = "#2563eb" if it["layer"] == "DIM" else "#1e293b"
            out.append(f'<line x1="{X(it["x1"]):.1f}" y1="{Y(it["y1"]):.1f}" x2="{X(it["x2"]):.1f}" '
                       f'y2="{Y(it["y2"]):.1f}" stroke="{col}" stroke-width="{max(0.4, it["w"] * k * 0.06):.2f}"/>')
    for it in d.items:
        if it["t"] == "text":
            col = "#2563eb" if it["layer"] == "DIM" else "#0f172a"
            out.append(f'<text x="{X(it["x"]):.1f}" y="{Y(it["y"]):.1f}" font-size="{it["h"] * k:.1f}" '
                       f'text-anchor="{it["anchor"]}" fill="{col}"{" font-weight=\"bold\"" if it["bold"] else ""}>'
                       f'{_esc(it["s"])}</text>')
    out.append("</svg>")
    return "".join(out)


STD_SCALES = [50, 75, 100, 125, 150, 200, 250, 300, 400, 500]


def _draw_pdf(c, d: Dwg, bx: float, by: float, bw: float, bh: float) -> str:
    """Draw d into the box (points), at the largest standard scale that fits. Returns the scale text."""
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    x0, y0, x1, y1 = d.bounds()
    wm, hm = (x1 - x0) * FT_M * 1000, (y1 - y0) * FT_M * 1000  # mm real
    sc = next((s for s in STD_SCALES if wm / s * mm <= bw and hm / s * mm <= bh), None)
    if sc:
        k = FT_M * 1000 / sc * mm  # points per foot
        label = f"1:{sc}"
    else:
        k = min(bw / (x1 - x0), bh / (y1 - y0))
        label = "NTS"
    ox = bx + (bw - (x1 - x0) * k) / 2 - x0 * k
    oy = by + (bh - (y1 - y0) * k) / 2 - y0 * k

    def safe(s):
        return (s.replace("×", "x").replace("–", "-").replace("²", "2").replace("³", "3"))

    for it in d.items:
        if it["t"] == "rect":
            c.setLineWidth(max(0.15, it["lw"] * 0.5) if it["lw"] else 0.01)
            c.setStrokeColor(colors.HexColor("#334155"))
            if it["fill"]:
                c.setFillColor(colors.HexColor(it["fill"]))
            c.rect(ox + it["x"] * k, oy + it["y"] * k, it["w"] * k, it["h"] * k,
                   fill=1 if it["fill"] else 0, stroke=1 if it["lw"] else 0)
    for it in d.items:
        if it["t"] == "line":
            c.setStrokeColor(colors.HexColor("#2563eb" if it["layer"] == "DIM" else "#1e293b"))
            c.setLineWidth(max(0.15, it["w"] * 0.5))
            c.line(ox + it["x1"] * k, oy + it["y1"] * k, ox + it["x2"] * k, oy + it["y2"] * k)
    for it in d.items:
        if it["t"] == "text":
            c.setFillColor(colors.HexColor("#2563eb" if it["layer"] == "DIM" else "#0f172a"))
            fs = max(4.5, min(11, it["h"] * k))
            c.setFont("Helvetica-Bold" if it["bold"] else "Helvetica", fs)
            fn = {"start": c.drawString, "middle": c.drawCentredString, "end": c.drawRightString}[it["anchor"]]
            fn(ox + it["x"] * k, oy + it["y"] * k, safe(it["s"]))
    return label


def sheet_set_pdf(plan: dict, project: dict, meta: dict) -> bytes:
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
                ("Plot", f"{plan['plot']['w']:g}' x {plan['plot']['d']:g}' · {plan['facing'].title()} facing"),
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
        scale = _draw_pdf(c, dwg, *area_box)
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
    from .exports import _dxf_line, _dxf_text
    schedule(plan)
    dwgs = [site_plan(plan)] + [floor_plan(plan, i) for i in range(len(plan["levels"]))] + [front_elevation(plan), section(plan)]
    layers = sorted({it["layer"] for d in dwgs for it in d.items} | {"TITLE"})
    out = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "2", "0", "ENDSEC",
           "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", str(len(layers))]
    for i, name in enumerate(layers):
        out += ["0", "LAYER", "2", name, "70", "0", "62", str(1 + i % 7), "6", "CONTINUOUS"]
    out += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    ox = 0.0
    for d in dwgs:
        x0, y0, x1, y1 = d.bounds()
        dx = ox - x0
        for it in d.items:
            if it["t"] == "line":
                _dxf_line(out, it["layer"], it["x1"] + dx, it["y1"] - y0, it["x2"] + dx, it["y2"] - y0)
            elif it["t"] == "rect":
                x, y, w, h = it["x"] + dx, it["y"] - y0, it["w"], it["h"]
                for a, b, cc, dd in ((x, y, x + w, y), (x + w, y, x + w, y + h), (x + w, y + h, x, y + h), (x, y + h, x, y)):
                    _dxf_line(out, it["layer"], a, b, cc, dd)
            else:
                _dxf_text(out, it["layer"], it["x"] + dx, it["y"] - y0, it["h"], it["s"], center=it["anchor"] == "middle")
        _dxf_text(out, "TITLE", ox + (x1 - x0) / 2, -4, 1.5, d.title.upper())
        ox += (x1 - x0) + 20
    co = project.get("company") or {}
    _dxf_text(out, "TITLE", 0, -8, 1.2, f"{co.get('name', '')} - {project.get('name', '')} - design v{meta.get('version', '')}", center=False)
    out += ["0", "ENDSEC", "0", "EOF"]
    return ("\r\n".join(out) + "\r\n").encode("ascii", "replace")


def sheet_previews(plan: dict) -> dict:
    """SVG previews + tables for the Design page."""
    sched = schedule(plan)
    return {
        "schedule": sched, "area": area_details(plan),
        "svgs": {"site": to_svg(site_plan(plan)), "elevation": to_svg(front_elevation(plan)), "section": to_svg(section(plan)),
                 **{f"plan_{i}": to_svg(floor_plan(plan, i)) for i in range(len(plan["levels"]))}},
        "levels": [lv["name"] for lv in plan["levels"]],
    }
