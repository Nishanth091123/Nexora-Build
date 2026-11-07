"""1.19 Small PDF helper for the site documents (marking guide, services, variation sheet, handover pack).

Plain printable A4 pages: title block with the firm / project, tables, notes and simple line sketches.
No seals, stamps or signatures are printed – only empty signature boxes where a person signs by hand."""
from __future__ import annotations

import io
from datetime import date

from ..design.exports import _pdf_safe


class Doc:
    def __init__(self, title: str, project: dict, subtitle: str = "", landscape_pages: bool = False):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        self.colors, self.mm = colors, mm
        self.size = landscape(A4) if landscape_pages else A4
        ss = getSampleStyleSheet()
        self.body = ParagraphStyle("b", parent=ss["Normal"], fontSize=8.8, leading=11.5)
        self.small = ParagraphStyle("s", parent=self.body, fontSize=7.6, leading=9.6, textColor=colors.HexColor("#475569"))
        self.h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, spaceAfter=2, textColor=colors.HexColor("#0f2a5c"))
        self.h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11, spaceBefore=9, spaceAfter=3,
                                 textColor=colors.HexColor("#0f2a5c"))
        self.h3 = ParagraphStyle("h3", parent=ss["Heading3"], fontSize=9.5, spaceBefore=5, spaceAfter=2)
        self.title, self.project, self.flow = title, project, []
        co = (project.get("company") or {}).get("name") or ""
        self.flow.append(self.P(f"<b>{_pdf_safe(co)}</b>" if co else "", self.small))
        self.flow.append(self.P(title, self.h1, raw=True))
        meta = " · ".join(x for x in [project.get("name"), project.get("code"), project.get("location"),
                                       f"Date {date.today().strftime('%d-%m-%Y')}"] if x)
        self.flow.append(self.P(meta, self.small))
        if subtitle:
            self.flow.append(self.P(subtitle, self.small))

    def P(self, t, st=None, raw=False):
        from reportlab.platypus import Paragraph
        s = str(t if t is not None else "")
        return Paragraph(s if raw else _pdf_safe(s).replace("\n", "<br/>"), st or self.body)

    def h(self, t, level=2):
        self.flow.append(self.P(t, self.h2 if level == 2 else self.h3))

    def para(self, t, small=False):
        self.flow.append(self.P(t, self.small if small else self.body))

    def bullets(self, items, small=False):
        for it in items:
            self.flow.append(self.P("• " + str(it), self.small if small else self.body))

    def table(self, head, rows, widths=None, zebra=True, bold_last=False):
        from reportlab.platypus import Table, TableStyle
        c = self.colors
        data = [[self.P(f"<b>{_pdf_safe(str(x))}</b>", self.small, raw=True) for x in head]]
        data += [[self.P(x, self.small) for x in r] for r in rows]
        avail = self.size[0] - 30 * self.mm
        if widths:
            tot = sum(widths)
            widths = [w / tot * avail for w in widths]
        t = Table(data, colWidths=widths, repeatRows=1)
        st = [("GRID", (0, 0), (-1, -1), 0.4, c.HexColor("#cbd5e1")),
              ("BACKGROUND", (0, 0), (-1, 0), c.HexColor("#e8eef9")),
              ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
        if zebra:
            for i in range(2, len(data), 2):
                st.append(("BACKGROUND", (0, i), (-1, i), c.HexColor("#f8fafc")))
        if bold_last and len(data) > 1:
            st.append(("BACKGROUND", (0, len(data) - 1), (-1, len(data) - 1), c.HexColor("#eef2ff")))
        t.setStyle(TableStyle(st))
        self.flow.append(t)

    def space(self, h=4):
        from reportlab.platypus import Spacer
        self.flow.append(Spacer(1, h * self.mm))

    def page(self):
        from reportlab.platypus import PageBreak
        self.flow.append(PageBreak())

    def sketch(self, draw_fn, w_mm=180, h_mm=120):
        """draw_fn(drawing, w_pt, h_pt) adds reportlab.graphics shapes."""
        from reportlab.graphics.shapes import Drawing
        d = Drawing(w_mm * self.mm, h_mm * self.mm)
        draw_fn(d, w_mm * self.mm, h_mm * self.mm)
        self.flow.append(d)

    def signatures(self, labels):
        from reportlab.platypus import Table, TableStyle
        c = self.colors
        t = Table([[self.P(f"{lab}<br/><br/><br/>Name / date: ____________", self.small, raw=True) for lab in labels]],
                  colWidths=[(self.size[0] - 30 * self.mm) / len(labels)] * len(labels), rowHeights=[26 * self.mm])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, c.HexColor("#94a3b8")),
                               ("INNERGRID", (0, 0), (-1, -1), 0.5, c.HexColor("#94a3b8")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        self.flow.append(t)

    def build(self) -> bytes:
        from reportlab.platypus import SimpleDocTemplate
        buf = io.BytesIO()
        title, proj = self.title, self.project

        def foot(c, d):
            c.saveState()
            c.setFont("Helvetica", 7)
            c.setFillColor(self.colors.HexColor("#64748b"))
            c.drawString(15 * self.mm, 8 * self.mm, _pdf_safe(f"{proj.get('name') or ''} – {title}"))
            c.drawRightString(self.size[0] - 15 * self.mm, 8 * self.mm, f"Page {d.page}")
            c.restoreState()
        doc = SimpleDocTemplate(buf, pagesize=self.size, leftMargin=15 * self.mm, rightMargin=15 * self.mm,
                                topMargin=13 * self.mm, bottomMargin=14 * self.mm, title=title)
        doc.build(self.flow, onFirstPage=foot, onLaterPages=foot)
        return buf.getvalue()


def plot_sketch(plan: dict, marks: list[dict], extra=None):
    """A plot / building outline sketch with marked items: marks = [{x, y, w?, d?, r?, label, color}] in plot ft."""
    from reportlab.graphics.shapes import Circle, Line, Rect, String
    from reportlab.lib import colors

    def fn(d, W, H):
        pw, pd = float(plan["plot"]["w"]), float(plan["plot"]["d"])
        poly = (plan["plot"].get("poly") or None)
        s = min((W - 40) / pw, (H - 40) / pd)
        ox, oy = 20 + (W - 40 - pw * s) / 2, 26

        def X(x):
            return ox + x * s

        def Y(y):
            return oy + y * s
        if poly:
            pts = poly if isinstance(poly[0], (list, tuple)) else [(p["x"], p["y"]) for p in poly]
            for a, b in zip(pts, pts[1:] + pts[:1]):
                d.add(Line(X(a[0]), Y(a[1]), X(b[0]), Y(b[1]), strokeColor=colors.black, strokeWidth=1, strokeDashArray=[4, 2]))
        else:
            d.add(Rect(X(0), Y(0), pw * s, pd * s, strokeColor=colors.black, fillColor=None, strokeWidth=1, strokeDashArray=[4, 2]))
        b = plan["building"]
        d.add(Rect(X(b["x"]), Y(b["y"]), b["w"] * s, b["d"] * s, strokeColor=colors.HexColor("#c2410c"),
                   fillColor=colors.HexColor("#fff7ed"), strokeWidth=1.2))
        d.add(String(X(pw / 2), Y(0) - 14, "ROAD SIDE (FRONT)", fontSize=7, textAnchor="middle"))
        for m in marks:
            col = colors.HexColor(m.get("color", "#1d4ed8"))
            if m.get("r"):
                d.add(Circle(X(m["x"]), Y(m["y"]), m["r"] * s, strokeColor=col, fillColor=None, strokeWidth=1))
            elif m.get("w"):
                d.add(Rect(X(m["x"]), Y(m["y"]), m["w"] * s, m["d"] * s, strokeColor=col, fillColor=None, strokeWidth=1))
            else:
                d.add(Circle(X(m["x"]), Y(m["y"]), 2, strokeColor=col, fillColor=col))
            if m.get("label"):
                lx = X(m["x"] + (m.get("w") or 0) / 2)
                ly = Y(m["y"] + (m.get("d") or 0) / 2) - 3
                d.add(String(lx, ly, m["label"][:28], fontSize=6.2, textAnchor="middle", fillColor=col))
        if extra:
            extra(d, X, Y, s)
    return fn
