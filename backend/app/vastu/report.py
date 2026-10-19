"""Vastu report PDF (reportlab): plan with the 3×3 Vastu grid, direction overview, room-wise checks."""
from __future__ import annotations

import io

from ..design.exports import FILL, _pdf_safe
from .engine import ZONE_NAME

STATUS = {"matched": ("Matched", "#16a34a"), "partly": ("Partly", "#d97706"), "not_matched": ("Not matched", "#dc2626")}


def to_pdf(plan: dict, result: dict, project: dict, meta: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["Normal"], fontSize=9, leading=12)
    small = ParagraphStyle("s", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#475569"))
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=16, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=4)
    P = lambda t, st=body: Paragraph(_pdf_safe(t), st)

    class PlanDrawing(Flowable):
        def __init__(self, level: int, size: float):
            super().__init__()
            self.level, self.size = level, size
            b = plan["building"]
            self.k = size / max(b["w"], b["d"])
            self.width, self.height = b["w"] * self.k + 30, b["d"] * self.k + 30

        def draw(self):
            c = self.canv
            b, k = plan["building"], self.k
            lv = plan["levels"][self.level]
            ox, oy = 15, 15
            for r in lv["rooms"]:
                c.setFillColor(colors.HexColor(FILL.get(r["type"], "#ffffff")))
                c.setStrokeColor(colors.HexColor("#334155"))
                c.setLineWidth(0.6)
                c.rect(ox + r["x"] * k, oy + r["y"] * k, r["w"] * k, r["d"] * k, fill=1, stroke=1)
                c.setFillColor(colors.HexColor("#0f172a"))
                c.setFont("Helvetica-Bold", 6.5)
                c.drawCentredString(ox + (r["x"] + r["w"] / 2) * k, oy + (r["y"] + r["d"] / 2) * k, _pdf_safe(r["name"])[:18])
            # 3x3 grid with zone names
            c.setStrokeColor(colors.HexColor("#f97316"))
            c.setDash(3, 2)
            for i in (1, 2):
                c.line(ox + b["w"] * k * i / 3, oy, ox + b["w"] * k * i / 3, oy + b["d"] * k)
                c.line(ox, oy + b["d"] * k * i / 3, ox + b["w"] * k, oy + b["d"] * k * i / 3)
            c.setDash()
            from .engine import zone_of
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(colors.HexColor("#c2410c"))
            for i in range(3):
                for j in range(3):
                    cx, cy = b["w"] * (i + 0.5) / 3, b["d"] * (j + 0.5) / 3
                    z = zone_of(plan["compass"], b["w"], b["d"], cx, cy)
                    c.drawString(ox + b["w"] * k * i / 3 + 3, oy + b["d"] * k * (j + 1) / 3 - 9, z)
            # north arrow
            up, right = plan["compass"]["up"], plan["compass"]["right"]
            nx, ny = right[1], up[1]
            ax, ay = ox + b["w"] * k + 8, oy + b["d"] * k + 2
            c.setStrokeColor(colors.HexColor("#0f172a"))
            c.line(ax - nx * 10, ay - ny * 10, ax + nx * 10, ay + ny * 10)
            c.setFillColor(colors.HexColor("#dc2626"))
            c.circle(ax + nx * 10, ay + ny * 10, 2, fill=1, stroke=0)
            c.drawCentredString(ax + nx * 17, ay + ny * 17 - 3, "N")

    s = result["summary"]
    story = [P(f"Vastu Report – {project.get('name', '')}", h1),
             P(f"Design v{meta.get('version', '')} · {plan.get('facing', '').replace('-', ' ').title()} facing · "
               f"north arrow {result.get('north_deg', 0)}° · {meta.get('date', '')}", small), Spacer(1, 6),
             P(f"<b>{s['matched']} of {s['total']} rules matched</b> ({s['partly']} partly, {s['not_matched']} not matched) – "
               f"{s['label']}."), Spacer(1, 6)]
    ov = [["Direction", "Status", "Rooms"]] + [[k, v["status"], ", ".join(v["rooms"])[:70] or "—"] for k, v in result["overview"].items()]
    t = Table([[P(c) for c in row] for row in ov], colWidths=[28 * mm, 35 * mm, 110 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [P("Direction overview", h2), t]
    for li in range(len(plan["levels"])):
        story += [P(f"Plan with Vastu zones – {plan['levels'][li]['name']}", h2), PlanDrawing(li, 120 * mm)]
    rows = [["Rule", "Room / floor", "Zone", "Result", "Note"]]
    for c in result["checks"]:
        lab, col = STATUS[c["status"]]
        rows.append([P(c["title"]), P(f"{c['room']} {('· ' + c['level_name']) if c['level_name'] else ''}"),
                     P(ZONE_NAME.get(c["zone"], c["zone"] or "—")), Paragraph(f'<font color="{col}"><b>{lab}</b></font>', body),
                     P(c["message"], small)])
    t = Table(rows, colWidths=[30 * mm, 38 * mm, 26 * mm, 22 * mm, 60 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("FONTSIZE", (0, 0), (-1, 0), 9)]))
    story += [PageBreak(), P("Room-wise checks", h2), t]
    if result["suggestions"]:
        story += [P("Suggestions", h2)] + [P("• " + x) for x in result["suggestions"]]
    story += [P("General Vastu tips", h2)] + [P("• " + x) for x in result["tips"]]
    story += [Spacer(1, 8), P(result["note"], small)]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                      title="Vastu Report").build(story)
    return buf.getvalue()
