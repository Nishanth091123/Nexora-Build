"""Design exports: plan PDF (one page per floor + schedules) and a simple DXF (R12 ASCII, feet).

The DXF opens in AutoCAD / LibreCAD / DraftSight. Layers: PLOT, SETBACK, WALL_EXT, WALL_INT, PARTITION,
PARAPET, ROOM, DOOR, WINDOW, TEXT. Each floor is drawn side by side (gap of 15 ft).
"""
from __future__ import annotations

import io

THK = {"ext": 0.755, "int230": 0.755, "int115": 0.377, "parapet": 0.5}
FILL = {"bedroom": "#dbeafe", "toilet": "#e0f2fe", "common_toilet": "#e0f2fe", "kitchen": "#fef3c7",
        "hall": "#fde7d3", "lounge": "#fde7d3", "dining": "#fef9c3", "pooja": "#fce7f3", "stair": "#e5e7eb",
        "parking": "#f3f4f6", "passage": "#f8fafc", "dress": "#ede9fe", "terrace": "#ecfccb"}


def _pdf_safe(t: str) -> str:
    return (str(t).replace("×", "x").replace("–", "-").replace("—", "-").replace("₹", "Rs ").replace("²", "2")
            .replace("³", "3").replace("’", "'").replace("‘", "'").replace("≤", "<=").replace("≥", ">=")
            .replace("≈", "~").replace("…", "..."))


def to_pdf(plan: dict, project: dict, meta: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    W, H = landscape(A4)
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    plot = plan["plot"]
    b = plan["building"]
    sb = plan["setbacks"]
    margin = 14 * mm
    draw_w, draw_h = W * 0.62 - margin, H - 2 * margin - 18 * mm
    scale = min(draw_w / plot["w"], draw_h / plot["d"])
    ox, oy = margin, margin + 8 * mm

    def P(x, y):  # plot feet -> page points (road at the bottom)
        return ox + x * scale, oy + y * scale

    for li, lv in enumerate(plan["levels"]):
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin, H - margin, _pdf_safe(f"{project.get('name', '')} – {lv['name']}"))
        c.setFont("Helvetica", 8.5)
        c.drawString(margin, H - margin - 12,
                     _pdf_safe(f"Design v{meta.get('version', '')} · {plan['facing'].title()} facing · "
                               f"Plot {plot['w']:g} × {plot['d']:g} ft · Concept plan – not for construction"))
        # plot & setback
        c.setStrokeColor(colors.HexColor("#334155"))
        c.setLineWidth(1)
        x0, y0 = P(0, 0)
        c.rect(x0, y0, plot["w"] * scale, plot["d"] * scale)
        c.setDash(4, 3)
        c.setStrokeColor(colors.HexColor("#f97316"))
        bx, by = P(b["x"], b["y"])
        c.rect(bx, by, b["w"] * scale, b["d"] * scale)
        c.setDash()
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawCentredString(x0 + plot["w"] * scale / 2, y0 - 11, "ROAD")
        # rooms
        for r in lv["rooms"]:
            rx, ry = P(b["x"] + r["x"], b["y"] + r["y"])
            c.setFillColor(colors.HexColor(FILL.get(r["type"], "#ffffff")))
            c.setStrokeColor(colors.HexColor("#cbd5e1"))
            c.setLineWidth(0.3)
            c.rect(rx, ry, r["w"] * scale, r["d"] * scale, fill=1, stroke=1)
            c.setFillColor(colors.HexColor("#0f172a"))
            fs = 7 if min(r["w"], r["d"]) * scale > 40 else 5.5
            c.setFont("Helvetica-Bold", fs)
            cx, cy = rx + r["w"] * scale / 2, ry + r["d"] * scale / 2
            c.drawCentredString(cx, cy + 2, _pdf_safe(r["name"]))
            c.setFont("Helvetica", fs - 0.5)
            c.drawCentredString(cx, cy - fs, _pdf_safe(f"{r['w']:g}' × {r['d']:g}'"))
        # walls
        c.setFillColor(colors.HexColor("#1e293b"))
        for w in lv.get("walls", []):
            t = THK.get(w["kind"], 0.5)
            x1, y1 = P(b["x"] + min(w["x1"], w["x2"]), b["y"] + min(w["y1"], w["y2"]))
            if w["y1"] == w["y2"]:
                c.rect(x1, y1 - t * scale / 2, abs(w["x2"] - w["x1"]) * scale, t * scale, fill=1, stroke=0)
            else:
                c.rect(x1 - t * scale / 2, y1, t * scale, abs(w["y2"] - w["y1"]) * scale, fill=1, stroke=0)
        # openings
        for o in lv.get("openings", []):
            col = {"window": "#38bdf8", "vent": "#7dd3fc"}.get(o["type"], "#ffffff")
            x1, y1 = P(b["x"] + min(o["x1"], o["x2"]), b["y"] + min(o["y1"], o["y2"]))
            t = 0.8
            c.setFillColor(colors.HexColor(col))
            if o["y1"] == o["y2"]:
                c.rect(x1, y1 - t * scale / 2, abs(o["x2"] - o["x1"]) * scale, t * scale, fill=1, stroke=0)
            else:
                c.rect(x1 - t * scale / 2, y1, t * scale, abs(o["y2"] - o["y1"]) * scale, fill=1, stroke=0)
        # north arrow
        up, right = plan["compass"]["up"], plan["compass"]["right"]
        nxv, nyv = right[1], up[1]
        axp, ayp = ox + plot["w"] * scale + 22, oy + plot["d"] * scale - 22
        c.setStrokeColor(colors.HexColor("#0f172a"))
        c.setLineWidth(1.5)
        c.line(axp - nxv * 14, ayp - nyv * 14, axp + nxv * 14, ayp + nyv * 14)
        c.line(axp + nxv * 14, ayp + nyv * 14, axp + nxv * 8 - nyv * 5, ayp + nyv * 8 + nxv * 5)
        c.line(axp + nxv * 14, ayp + nyv * 14, axp + nxv * 8 + nyv * 5, ayp + nyv * 8 - nxv * 5)
        c.setFillColor(colors.HexColor("#dc2626"))
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(axp + nxv * 22, ayp + nyv * 22 - 4, "N")
        c.setLineWidth(1)
        # right panel: schedule
        px = W * 0.64
        py = H - margin - 30
        c.setFillColor(colors.HexColor("#0f172a"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(px, py, "Room schedule")
        c.setFont("Helvetica", 8)
        py -= 13
        for r in lv["summary"]["rooms"]:
            c.drawString(px, py, _pdf_safe(r["name"]))
            c.drawRightString(px + 150, py, _pdf_safe(r["size"]))
            c.drawRightString(px + 210, py, f"{r['area_sqft']:g} sft")
            py -= 11
            if py < 150:
                break
        s = lv["summary"]
        py -= 8
        c.setFont("Helvetica-Bold", 10)
        c.drawString(px, py, "This floor")
        c.setFont("Helvetica", 8)
        for line in [f"Built-up {s['builtup_sqft']:g} sq ft  ·  carpet {s['carpet_sqft']:g} sq ft",
                     f"Walls: external {s['ext_wall_ft']:g} ft, internal 230 {s['int230_wall_ft']:g} ft, "
                     f"115 {s['int115_wall_ft']:g} ft",
                     f"Doors: main {s['main_doors']}, room {s['doors']}, toilet {s['toilet_doors']}  ·  "
                     f"windows/vents {s['windows']} ({s['window_area_sqft']:g} sq ft)"]:
            py -= 11
            c.drawString(px, py, _pdf_safe(line))
        if li == 0:
            py -= 18
            c.setFont("Helvetica-Bold", 10)
            c.drawString(px, py, "Setbacks (auto, TNCDBR 2019)")
            c.setFont("Helvetica", 8)
            for k in ("front", "rear", "left", "right"):
                py -= 11
                c.drawString(px, py, f"{k.title()}: {sb['m'][k]:g} m ({sb['ft'][k]:g} ft)")
            py -= 11
            c.drawString(px, py, _pdf_safe(f"Height ≈ {sb['height_m']} m · coverage {sb['coverage_pct']}%"))
        c.setFont("Helvetica-Oblique", 7)
        c.setFillColor(colors.HexColor("#64748b"))
        c.drawString(margin, 8 * mm, _pdf_safe("Nexora Build – concept plan. Verify setbacks with the local body "
                                               "(DTCP/CMDA/Panchayat); structural design by a qualified engineer."))
        c.showPage()
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------- DXF (R12 ASCII)
def _dxf_line(out, layer, x1, y1, x2, y2):
    out += ["0", "LINE", "8", layer, "10", f"{x1:.3f}", "20", f"{y1:.3f}", "30", "0",
            "11", f"{x2:.3f}", "21", f"{y2:.3f}", "31", "0"]


def _dxf_rect(out, layer, x, y, w, d):
    _dxf_line(out, layer, x, y, x + w, y)
    _dxf_line(out, layer, x + w, y, x + w, y + d)
    _dxf_line(out, layer, x + w, y + d, x, y + d)
    _dxf_line(out, layer, x, y + d, x, y)


def _dxf_text(out, layer, x, y, h, text, center=True):
    text = _pdf_safe(text)
    out += ["0", "TEXT", "8", layer, "10", f"{x:.3f}", "20", f"{y:.3f}", "30", "0", "40", f"{h:.3f}", "1", text]
    if center:
        out += ["72", "1", "11", f"{x:.3f}", "21", f"{y:.3f}", "31", "0"]


def to_dxf(plan: dict, project: dict, meta: dict) -> bytes:
    out = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "2", "0", "ENDSEC",
           "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", "11"]
    layers = {"PLOT": 7, "SETBACK": 30, "WALL_EXT": 7, "WALL_INT": 8, "PARTITION": 9, "PARAPET": 3,
              "ROOM": 252, "DOOR": 1, "WINDOW": 5, "TEXT": 7}
    for name, col in layers.items():
        out += ["0", "LAYER", "2", name, "70", "0", "62", str(col), "6", "CONTINUOUS"]
    out += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    plot, b = plan["plot"], plan["building"]
    gap = 15.0
    for li, lv in enumerate(plan["levels"]):
        ox = li * (plot["w"] + gap)
        _dxf_rect(out, "PLOT", ox, 0, plot["w"], plot["d"])
        _dxf_rect(out, "SETBACK", ox + b["x"], b["y"], b["w"], b["d"])
        _dxf_text(out, "TEXT", ox + plot["w"] / 2, -3, 1.2, f"{lv['name']} (units: feet) - ROAD")
        bx, by = ox + b["x"], b["y"]
        for r in lv["rooms"]:
            _dxf_rect(out, "ROOM", bx + r["x"], by + r["y"], r["w"], r["d"])
            cx, cy = bx + r["x"] + r["w"] / 2, by + r["y"] + r["d"] / 2
            _dxf_text(out, "TEXT", cx, cy + 0.4, 0.75, r["name"])
            _dxf_text(out, "TEXT", cx, cy - 0.8, 0.6, f"{r['w']:g}' x {r['d']:g}'")
        for w in lv.get("walls", []):
            t = THK.get(w["kind"], 0.5) / 2
            layer = {"ext": "WALL_EXT", "int230": "WALL_INT", "int115": "PARTITION", "parapet": "PARAPET"}[w["kind"]]
            x1, y1, x2, y2 = bx + w["x1"], by + w["y1"], bx + w["x2"], by + w["y2"]
            if y1 == y2:
                _dxf_line(out, layer, x1, y1 - t, x2, y2 - t)
                _dxf_line(out, layer, x1, y1 + t, x2, y2 + t)
            else:
                _dxf_line(out, layer, x1 - t, y1, x2 - t, y2)
                _dxf_line(out, layer, x1 + t, y1, x2 + t, y2)
        for o in lv.get("openings", []):
            layer = "WINDOW" if o["type"] in ("window", "vent") else "DOOR"
            _dxf_line(out, layer, bx + o["x1"], by + o["y1"], bx + o["x2"], by + o["y2"])
    # north arrow (from the plan compass) above the first floor drawing
    up, right = plan["compass"]["up"], plan["compass"]["right"]
    nx, ny = right[1], up[1]
    ax, ay = plot["w"] + 6, plot["d"] + 2
    _dxf_line(out, "TEXT", ax - nx * 3, ay - ny * 3, ax + nx * 3, ay + ny * 3)
    _dxf_line(out, "TEXT", ax + nx * 3, ay + ny * 3, ax + nx * 1.8 - ny * 0.8, ay + ny * 1.8 + nx * 0.8)
    _dxf_line(out, "TEXT", ax + nx * 3, ay + ny * 3, ax + nx * 1.8 + ny * 0.8, ay + ny * 1.8 - nx * 0.8)
    _dxf_text(out, "TEXT", ax + nx * 4.5, ay + ny * 4.5, 1.2, "N")
    _dxf_text(out, "TEXT", 0, plot["d"] + 4, 1.5,
              f"{project.get('name', '')} - design v{meta.get('version', '')} - concept plan", center=False)
    out += ["0", "ENDSEC", "0", "EOF"]
    return ("\r\n".join(out) + "\r\n").encode("ascii", "replace")
