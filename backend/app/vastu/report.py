"""Vastu report PDF (reportlab): plan with the 3×3 Vastu grid, direction overview, room-wise checks."""
from __future__ import annotations

import io

from ..design.exports import FILL, _pdf_safe
from .engine import ZONE_NAME

STATUS = {"matched": ("Matched", "#16a34a"), "partly": ("Partly", "#d97706"), "not_matched": ("Not matched", "#dc2626")}


def to_pdf(plan: dict, result: dict, project: dict, meta: dict, best: dict | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["Normal"], fontSize=9, leading=12)
    small = ParagraphStyle("s", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#475569"))
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=16, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=4)
    P = lambda t, st=body: Paragraph(_pdf_safe(t), st)

    class PlanDrawing(Flowable):
        def __init__(self, level: int, size: float, pl: dict | None = None, mandala: bool = True):
            super().__init__()
            self.level, self.size, self.pl, self.mandala = level, size, pl or plan, mandala
            b = self.pl["building"]
            self.k = size / max(b["w"], b["d"])
            self.width, self.height = b["w"] * self.k + 30, b["d"] * self.k + 30

        def draw(self):
            c = self.canv
            plan_ = self.pl
            b, k = plan_["building"], self.k
            lv = plan_["levels"][self.level]
            ox, oy = 15, 15
            for r in lv["rooms"]:
                c.setFillColor(colors.HexColor(FILL.get(r["type"], "#ffffff")))
                c.setStrokeColor(colors.HexColor("#334155"))
                c.setLineWidth(0.6)
                c.rect(ox + r["x"] * k, oy + r["y"] * k, r["w"] * k, r["d"] * k, fill=1, stroke=1)
                c.setFillColor(colors.HexColor("#0f172a"))
                c.setFont("Helvetica-Bold", 6.5)
                c.drawCentredString(ox + (r["x"] + r["w"] / 2) * k, oy + (r["y"] + r["d"] / 2) * k, _pdf_safe(r["name"])[:18])
            if self.mandala:  # 1.16: Brahmasthan + 16-zone mandala
                from .more import ZONES16, mandala_lines
                c.setStrokeColor(colors.HexColor("#f59e0b"))
                c.setFillColor(colors.HexColor("#fef3c7"))
                c.setDash(3, 2)
                c.saveState()
                c.setFillAlpha(0.35)
                c.rect(ox + b["w"] * k / 3, oy + b["d"] * k / 3, b["w"] * k / 3, b["d"] * k / 3, fill=1, stroke=1)
                c.restoreState()
                c.setDash(3, 2)
                rays = mandala_lines(plan_)
                c.setStrokeColor(colors.HexColor("#f97316"))
                cx0, cy0 = ox + b["w"] * k / 2, oy + b["d"] * k / 2
                c.setFont("Helvetica-Bold", 6.5)
                for i, rr in enumerate(rays):
                    c.line(cx0, cy0, cx0 + rr["dx"] * b["w"] * k / 2, cy0 + rr["dy"] * b["d"] * k / 2)
                    nx_ = rays[(i + 1) % 16]
                    mx, my = (rr["dx"] + nx_["dx"]) / 2, (rr["dy"] + nx_["dy"]) / 2
                    m = max(abs(mx), abs(my)) or 1
                    c.setFillColor(colors.HexColor("#c2410c"))
                    c.drawCentredString(cx0 + mx / m * b["w"] * k / 2 * 0.82, cy0 + my / m * b["d"] * k / 2 * 0.82 - 2,
                                        ZONES16[(ZONES16.index(rr["after"]) + 1) % 16])
                c.setDash()
                door = result.get("door") if plan_ is plan else None
                for o in lv.get("openings", []):
                    if o["type"] == "main_door":
                        c.setStrokeColor(colors.HexColor(STATUS.get((door or {}).get("status", ""), ("", "#2563eb"))[1]))
                        c.setLineWidth(3)
                        c.line(ox + o["x1"] * k, oy + o["y1"] * k, ox + o["x2"] * k, oy + o["y2"] * k)
                        c.setLineWidth(0.6)
                        if door:
                            c.setFillColor(colors.HexColor("#1d4ed8"))
                            c.drawCentredString(ox + (o["x1"] + o["x2"]) / 2 * k, oy + (o["y1"] + o["y2"]) / 2 * k + 5, door["code"])
            up, right = plan_["compass"]["up"], plan_["compass"]["right"]
            # north arrow
            nx, ny = right[1], up[1]
            ax, ay = ox + b["w"] * k + 8, oy + b["d"] * k + 2
            c.setStrokeColor(colors.HexColor("#0f172a"))
            c.line(ax - nx * 10, ay - ny * 10, ax + nx * 10, ay + ny * 10)
            c.setFillColor(colors.HexColor("#dc2626"))
            c.circle(ax + nx * 10, ay + ny * 10, 2, fill=1, stroke=0)
            c.drawCentredString(ax + nx * 17, ay + ny * 17 - 3, "N")

    s = result["summary"]
    story = [P(f"Vastu Report – {project.get('name', '')}", h1),
             P(f"{meta.get('code', '')} · Client: {meta.get('client') or '-'} · {meta.get('location', '')} · Design v{meta.get('version', '')} · "
               f"{plan.get('facing', '').replace('-', ' ').title()} facing · north arrow {result.get('north_deg', 0)}° · {meta.get('date', '')}", small),
             Spacer(1, 6),
             P(f"<b>Vastu score {result.get('score', s.get('score', 0))} / 100</b> – {s['matched']} of {s['total']} rules matched "
               f"({s['partly']} partly, {s['not_matched']} need attention) – {s['label']}."), Spacer(1, 4)]
    if result.get("floors"):
        ft = [["Floor", "Score", "Matched", "Partly", "Needs attention"]] + [[f["name"], f["score"], f["matched"], f["partly"], f["not_matched"]] for f in result["floors"]]
        t = Table([[P(str(c)) for c in row] for row in ft], colWidths=[60 * mm, 25 * mm, 25 * mm, 25 * mm, 35 * mm])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1"))]))
        story += [P("Floor-wise score", h2), t]
    if result.get("overview8"):
        o8 = result["overview8"]
        tone = {"Excellent": "#dcfce7", "Good": "#dbeafe", "Needs Attention": "#fef3c7"}
        cells = [[(z, o8.get(z)) for z in row] for row in (["NW", "N", "NE"], ["W", "", "E"], ["SW", "S", "SE"])]
        data = [[P(f"<b>{ZONE_NAME.get(z, '')}</b><br/>{v['status']}<br/><font size=7>{', '.join(v['items'][:3])}</font>") if z else P("<b>Centre</b>")
                 for z, v in row] for row in cells]
        t = Table(data, colWidths=[58 * mm] * 3, rowHeights=[20 * mm] * 3)
        st = [("GRID", (0, 0), (-1, -1), 0.5, colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP")]
        for i, row in enumerate(cells):
            for j, (z, v) in enumerate(row):
                st.append(("BACKGROUND", (j, i), (j, i), colors.HexColor(tone.get(v["status"], "#fef9c3") if z else "#fef9c3")))
        t.setStyle(TableStyle(st))
        story += [P("Direction overview (8 directions)", h2), t]
    else:
        ov = [["Direction", "Status", "Rooms"]] + [[k, v["status"], ", ".join(v["rooms"])[:70] or "—"] for k, v in result["overview"].items()]
        t = Table([[P(c) for c in row] for row in ov], colWidths=[28 * mm, 35 * mm, 110 * mm])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                               ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story += [P("Direction overview", h2), t]
    door = result.get("door")
    if door:
        lab, col = STATUS[door["status"]]
        story += [P("Main door – 32 pada check", h2),
                  Paragraph(f'<font color="{col}"><b>{door["code"]} {door["name"]} – {lab}</b></font>', body), P(door["advice"]),
                  P(f"{door['side_name']} side {door['side_ft']} ft = 8 padas × {door['pada_ft']} ft: " + ", ".join(door["padas"][door["side"]]), small)]
    for li in range(len(plan["levels"])):
        story += [PageBreak() if li else Spacer(1, 4), KeepTogether([P(f"Plan with 16 Vastu zones – {plan['levels'][li]['name']}", h2), PlanDrawing(li, 125 * mm),
                  P("Orange lines: 16 zones (22.5° each) from the building centre; yellow: Brahmasthan (centre).", small)])]
    rows = [["Rule / room", "Result", "Now → better", "Why / simple remedy"]]
    for c in result["checks"]:
        if c.get("level") == -1:
            continue
        lab, col = STATUS[c["status"]]
        rows.append([P(f"<b>{c['title']}</b><br/>{c['room']} {('· ' + c['level_name']) if c.get('level_name') else ''}"),
                     Paragraph(f'<font color="{col}"><b>{lab}</b></font><br/>{_pdf_safe(c["message"])}', small),
                     P((c.get("current") or ZONE_NAME.get(c["zone"], c["zone"] or "—")) + (f" → {c['better']}" if c.get("better") else ""), small),
                     P(c["why"] + (f"<br/><b>Remedy:</b> {c['remedy']}" if c.get("remedy") else ""), small)])
    t = Table(rows, colWidths=[38 * mm, 45 * mm, 32 * mm, 65 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("FONTSIZE", (0, 0), (-1, 0), 9)]))
    story += [PageBreak(), P("Room-wise guidance", h2), t]
    site = [c for c in result["checks"] if c.get("level") == -1]
    if site:
        rows = [["Item", "Result", "Note"]] + [[P(c["title"]), Paragraph(f'<font color="{STATUS[c["status"]][1]}"><b>{STATUS[c["status"]][0]}</b></font>', body),
                                                P(c["message"] + (f" – {c['remedy']}" if c.get("remedy") and c["status"] != "matched" else ""), small)] for c in site]
        t = Table(rows, colWidths=[45 * mm, 28 * mm, 107 * mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story += [P("Site & fixtures", h2), t]
    if result.get("questions"):
        story += [P("Details still needed (answer them in the Vastu page): " + "; ".join(q["question"] for q in result["questions"]), small)]
    if result["suggestions"]:
        story += [P("Recommendations", h2)] + [P("• " + x) for x in result["suggestions"]]
    story += [P("General Vastu tips", h2)] + [P("• " + x) for x in result["tips"]]
    if best:
        story += [PageBreak(), P(f"Before / after – score {result.get('score', 0)} → {best['score']}", h2),
                  P(f"{best['label']}: " + "; ".join(best.get("changes", [])), small),
                  Table([[P("<b>Before</b>"), P("<b>After (suggested option)</b>")],
                         [PlanDrawing(0, 80 * mm, plan, False), PlanDrawing(0, 80 * mm, best["plan"], False)]], colWidths=[90 * mm, 90 * mm])]
    story += [Spacer(1, 8), P(result["note"], small)]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                      title="Vastu Report").build(story)
    return buf.getvalue()
