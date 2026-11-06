"""1.12 – Structural drawing sheets (A3, same CAD pens as the architectural set):
S-01 column layout & grid, S-02 foundation plan + footing detail, S-03 column schedule + section,
S-04 beam layout + schedule + typical beam detail, S-05 slab layout + schedule, S-06 notes & quantities.
Primitives in feet (plans) or millimetres/1000 (details are drawn in metres scaled to feet units)."""
from __future__ import annotations

import io

from ..design.sheets import Dwg, _draw_pdf, ft_in, to_svg

FT = 0.3048
MM = 1 / 304.8  # millimetre → feet


def _grid(d: Dwg, res: dict, plan: dict):
    xs = sorted({round(c["x"], 1) for c in res["columns"]})
    ys = sorted({round(c["y"], 1) for c in res["columns"]})
    X0, X1, Y0, Y1 = min(xs), max(xs), min(ys), max(ys)
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    for i, x in enumerate(xs):
        d.line(x, Y0 - 3, x, Y1 + 3, "GRID")
        d.arc(x, Y1 + 4.2, 1.0, 0, 360, "GRID")
        d.text(x, Y1 + 3.85, str(i + 1), 0.8, layer="GRID", bold=True)
    for j, y in enumerate(ys):
        d.line(X0 - 3, y, X1 + 3, y, "GRID")
        d.arc(X0 - 4.2, y, 1.0, 0, 360, "GRID")
        d.text(X0 - 4.2, y - 0.35, letters[j % len(letters)], 0.8, layer="GRID", bold=True)
    for a, b in zip(xs, xs[1:]):
        d.dim_h(a, b, Y1 + 6.5)
    for a, b in zip(ys, ys[1:]):
        d.dim_v(X0 - 7.0, a, b)
    return xs, ys


def _outline(d: Dwg, plan: dict, li: int = 0):
    lv = plan["levels"][li]
    for w in lv.get("walls", []):
        if w["kind"] in ("ext", "int230"):
            t = 0.377
            if w["y1"] == w["y2"]:
                d.line(min(w["x1"], w["x2"]), w["y1"] - t, max(w["x1"], w["x2"]), w["y1"] - t, "HATCH")
                d.line(min(w["x1"], w["x2"]), w["y1"] + t, max(w["x1"], w["x2"]), w["y1"] + t, "HATCH")
            else:
                d.line(w["x1"] - t, min(w["y1"], w["y2"]), w["x1"] - t, max(w["y1"], w["y2"]), "HATCH")
                d.line(w["x1"] + t, min(w["y1"], w["y2"]), w["x1"] + t, max(w["y1"], w["y2"]), "HATCH")


def column_layout(res: dict, plan: dict) -> Dwg:
    d = Dwg("Column Layout Plan")
    _outline(d, plan)
    _grid(d, res, plan)
    for c in res["columns"]:
        b, D = c["b_mm"] * MM, c["D_mm"] * MM
        d.rect(c["x"] - b / 2, c["y"] - D / 2, b, D, "COLUMN", "#fecaca")
        d.hatch(c["x"] - b / 2, c["y"] - D / 2, b, D, 0.18, layer="COLUMN")
        d.text(c["x"] + b / 2 + 0.3, c["y"] + D / 2 + 0.2, c["mark"], 0.6, anchor="start", layer="MARK", bold=True)
    d.text(min(c["x"] for c in res["columns"]), min(c["y"] for c in res["columns"]) - 6,
           "COLUMN LAYOUT & GRID (all floors)", 0.85, anchor="start", bold=True)
    return d


def foundation_plan(res: dict, plan: dict) -> Dwg:
    d = Dwg("Foundation Plan")
    _grid(d, res, plan)
    for f, c in zip(res["footings"], res["columns"]):
        B = f["B_m"] / FT
        d.rect(f["x"] - (B + 0.33) / 2, f["y"] - (B + 0.33) / 2, B + 0.33, B + 0.33, "PCC")
        d.rect(f["x"] - B / 2, f["y"] - B / 2, B, B, "FOOTING")
        b, D = c["b_mm"] * MM, c["D_mm"] * MM
        d.rect(c["x"] - b / 2, c["y"] - D / 2, b, D, "COLUMN", "#fecaca")
        d.text(f["x"], f["y"] - B / 2 + 0.3, f["mark"], 0.6, layer="MARK", bold=True)
    d.text(min(c["x"] for c in res["columns"]), min(c["y"] for c in res["columns"]) - 6,
           "FOUNDATION PLAN (isolated footings)", 0.85, anchor="start", bold=True)
    return d


def footing_detail(res: dict) -> Dwg:
    """Typical isolated footing – section (largest footing). Drawn in feet units from mm."""
    f = max(res["footings"], key=lambda x: x["B_m"])
    c = next(c for c in res["columns"] if c["mark"] == f["col_mark"])
    d = Dwg("Typical Footing Section")
    B, Dt = f["B_m"] / FT, f["D_mm"] * MM
    depth = res["inputs"]["foundation_depth_m"] / FT
    b = c["b_mm"] * MM
    d.line(-B, depth, B, depth, "GROUND")
    d.text(B * 0.9, depth + 0.3, "G.L.", 0.5, layer="DIM")
    d.rect(-B / 2 - 0.33, 0, B + 0.66, 0.33, "PCC")
    d.hatch(-B / 2 - 0.33, 0, B + 0.66, 0.33, 0.25)
    d.rect(-B / 2, 0.33, B, Dt, "FOOTING", "#fde68a")
    d.rect(-b / 2, 0.33 + Dt, b, depth - Dt - 0.33 + 1.5, "COLUMN", "#fecaca")
    cov = 50 * MM
    d.line(-B / 2 + cov, 0.33 + cov, B / 2 - cov, 0.33 + cov, "REBAR")  # bottom mesh
    for k in range(9):
        x = -B / 2 + cov + k * (B - 2 * cov) / 8
        d.arc(x, 0.33 + cov + 0.08, 0.06, 0, 360, "REBAR")
    for sx in (-1, 1):  # column starter bars with L bend
        d.line(sx * (b / 2 - 40 * MM), 0.33 + cov + 0.1, sx * (b / 2 - 40 * MM), depth + 1.5, "REBAR")
        d.line(sx * (b / 2 - 40 * MM), 0.33 + cov + 0.1, sx * (b / 2 - 40 * MM + 1.0), 0.33 + cov + 0.1, "REBAR")
    d.dim_h(-B / 2, B / 2, -0.8, f"{f['B_m'] * 1000:.0f}")
    d.dim_v(-B / 2 - 1.3, 0.33, 0.33 + Dt, f"{f['D_mm']}")
    d.dim_v(B / 2 + 1.6, 0, depth, f"{res['inputs']['foundation_depth_m']:.2f} m")
    d.text(B / 2 + 0.5, 0.15, "PCC 1:4:8, 100 thk", 0.45, anchor="start", layer="DIM")
    d.text(B / 2 + 0.5, 0.33 + Dt / 2, f"{f['mark']}: {f['steel']}", 0.45, anchor="start", layer="DIM")
    d.text(0, -1.9, f"TYPICAL FOOTING {f['mark']} – SECTION (all sizes mm)", 0.6, bold=True)
    return d


def column_section(res: dict) -> Dwg:
    sch = res["column_schedule"]
    d = Dwg("Column Sections")
    x = 0.0
    for c in sch:
        b, D = c["b_mm"] * MM, c["D_mm"] * MM
        nb, db = map(int, c["bars"].replace(" mm", "").split("-"))
        cov = 40 * MM
        d.rect(x, 0, b, D, "OUTLINE", "#f5f5f4")
        d.rect(x + cov - 0.03, cov - 0.03, b - 2 * cov + 0.06, D - 2 * cov + 0.06, "STIRRUP")
        per_side = max(2, nb // 2)
        for k in range(per_side):
            yy = cov + 0.05 + k * (D - 2 * cov - 0.1) / (per_side - 1)
            for xx in (x + cov + 0.05, x + b - cov - 0.05):
                d.arc(xx, yy, db * MM / 2 + 0.02, 0, 360, "REBAR")
        d.text(x + b / 2, D + 0.35, c["mark"], 0.45, layer="MARK", bold=True)
        d.text(x + b / 2, -0.45, f"{c['b_mm']}x{c['D_mm']}", 0.32, layer="DIM")
        d.text(x + b / 2, -0.85, c["bars"], 0.32, layer="DIM")
        d.text(x + b / 2, -1.25, f"ties {c['ties']}", 0.3, layer="DIM")
        x += max(b, 1.6) + 1.2
    return d


def beam_layout(res: dict, plan: dict, level: str) -> Dwg:
    d = Dwg(f"Beam Layout – {level} roof")
    _grid(d, res, plan)
    for c in res["columns"]:
        b, D = c["b_mm"] * MM, c["D_mm"] * MM
        d.rect(c["x"] - b / 2, c["y"] - D / 2, b, D, "COLUMN", "#fecaca")
    for bm in [b for b in res["beams"] if b["level"] == level]:
        t = bm["b_mm"] * MM / 2
        if bm["dir"] == "h":
            d.line(bm["x1"], bm["y1"] - t, bm["x2"], bm["y1"] - t, "BEAM")
            d.line(bm["x1"], bm["y1"] + t, bm["x2"], bm["y1"] + t, "BEAM")
            d.text((bm["x1"] + bm["x2"]) / 2, bm["y1"] + 0.6, f"{bm['mark']} ({bm['b_mm']}x{bm['D_mm']})", 0.42, layer="MARK")
        else:
            d.line(bm["x1"] - t, bm["y1"], bm["x1"] - t, bm["y2"], "BEAM")
            d.line(bm["x1"] + t, bm["y1"], bm["x1"] + t, bm["y2"], "BEAM")
            d.text(bm["x1"] + 0.5, (bm["y1"] + bm["y2"]) / 2, f"{bm['mark']}", 0.42, anchor="start", layer="MARK")
    return d


def beam_detail(res: dict) -> Dwg:
    bm = max(res["beams"], key=lambda b: b["span_m"])
    d = Dwg("Typical Beam Detail")
    L, D = bm["span_m"] / FT, bm["D_mm"] * MM
    cov = 25 * MM
    d.rect(-1.0, 0, 1.0, D + 1.5, "COLUMN", "#fecaca")
    d.rect(L, 0, 1.0, D + 1.5, "COLUMN", "#fecaca")
    d.rect(0, 0, L, D, "OUTLINE", "#f5f5f4")
    d.line(-0.8, cov, L + 0.8, cov, "REBAR")
    d.line(-0.8, D - cov, L + 0.8, D - cov, "REBAR")
    d.line(-0.8, D - cov - 0.1, -0.8, D - cov - 1.2, "REBAR")
    d.line(L + 0.8, D - cov - 0.1, L + 0.8, D - cov - 1.2, "REBAR")
    s_end = min(bm["sv"], 100) * MM
    s_mid = bm["sv"] * MM
    zone = 2 * D
    x = 0.17
    while x < L - 0.1:
        d.line(x, cov, x, D - cov, "STIRRUP")
        x += s_end if (x < zone or x > L - zone) else s_mid
    d.dim_h(0, L, -0.9, f"clear span {bm['span_m']:.2f} m")
    d.dim_v(-1.6, 0, D, f"{bm['D_mm']}")
    d.text(L / 2, D + 0.5, f"TOP {bm['top']}", 0.4, layer="DIM")
    d.text(L / 2, -2.0, f"BOTTOM {bm['bottom']} · stirrups 2L-8 @ 100 c/c for 2D at ends, {bm['sv']} c/c middle", 0.4, layer="DIM")
    d.text(L / 2, -2.8, f"TYPICAL BEAM {bm['mark']} ({bm['b_mm']} x {bm['D_mm']})", 0.55, bold=True)
    return d


def slab_layout(res: dict, plan: dict, level: str) -> Dwg:
    d = Dwg(f"Slab Layout – {level} roof")
    lv = next(l for l in plan["levels"] if l["name"] == level)
    for r in lv["rooms"]:
        d.rect(r["x"], r["y"], r["w"], r["d"], "SLABEDGE")
    for s in [s for s in res["slabs"] if s["level"] == level]:
        cx, cy = s["x"] + s["w"] / 2, s["y"] + s["d"] / 2
        d.line(s["x"] + 0.8, s["y"] + 0.8, s["x"] + s["w"] - 0.8, s["y"] + s["d"] - 0.8, "HATCH")
        d.text(cx, cy + 0.4, f"{s['mark']}  D={s['D_mm']}", 0.5, layer="MARK", bold=True, mask=True)
        d.text(cx, cy - 0.5, f"{s['type']}", 0.4, layer="DIM", mask=True)
        horiz_short = s["w"] <= s["d"]
        if horiz_short:  # short span along x → main bars drawn along x
            d.line(s["x"] + 0.6, cy - 1.4, s["x"] + s["w"] - 0.6, cy - 1.4, "REBAR")
            d.line(cx + 1.4, s["y"] + 0.6, cx + 1.4, s["y"] + s["d"] - 0.6, "STIRRUP")
        else:
            d.line(cx - 1.4, s["y"] + 0.6, cx - 1.4, s["y"] + s["d"] - 0.6, "REBAR")
            d.line(s["x"] + 0.6, cy + 1.4, s["x"] + s["w"] - 0.6, cy + 1.4, "STIRRUP")
    stair = next((r for r in lv["rooms"] if r["type"] == "stair"), None)
    if stair:
        d.text(stair["x"] + stair["w"] / 2, stair["y"] + stair["d"] / 2, "STAIR (waist slab)", 0.45, layer="DIM", mask=True)
    return d


def structural_pdf(res: dict, plan: dict, project: dict, meta: dict, style: str = "paper") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    W, H = landscape(A3)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    co = project.get("company") or {}
    navy = colors.HexColor("#0F2350")
    M, TB_W = 10 * mm, 120 * mm

    def frame(no, title, scale):
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
        c.drawString(x + 5 * mm, y - 18 * mm, " · ".join(v for v in [f"Proprietor: {co['proprietor']}" if co.get("proprietor") else "", co.get("phone", "")] if v)[:70])
        rows = [("Project", project.get("name", "")), ("Project code", project.get("code", "")),
                ("Client / owner", project.get("client_name") or "-"), ("Drawing", title), ("Sheet no.", no),
                ("Scale (on A3)", scale), ("Concrete / steel", f"M{res['inputs']['fck']} / Fe{res['inputs']['fy']}"),
                ("SBC / seismic zone", f"{res['inputs']['sbc_kn_m2']:g} kN/m2 / Zone {res['inputs']['seismic_zone']}"),
                ("Version / date", f"v{meta.get('version', '')} · {meta.get('date', '')}")]
        yy = y - 24 * mm
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
        yy -= 4 * mm
        for lab in ("Prepared by (signature)", "Structural engineer (signature & reg. no.)"):
            c.setFont("Helvetica", 7)
            c.setFillColor(colors.HexColor("#475569"))
            c.drawString(x + 3 * mm, yy - 3.5 * mm, lab)
            yy -= 20 * mm
            c.line(x, yy, W - M, yy)
        c.setFont("Helvetica-Bold", 22)
        c.setFillColor(navy)
        c.drawRightString(W - M - 4 * mm, M + 2 * mm, no)

    def heading(t):
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(navy)
        c.drawString(M + 8 * mm, H - M - 12 * mm, t)

    def table(x, y, headers, rows, widths, fs=8, rh=6 * mm):
        c.setFillColor(navy)
        c.rect(x, y - rh, sum(widths), rh, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", fs)
        xx = x
        for h_, w_ in zip(headers, widths):
            c.drawString(xx + 1.5 * mm, y - rh + 1.8 * mm, h_)
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
                c.drawString(xx + 1.5 * mm, y - rh + 1.8 * mm, str(v)[: int(w_ / (fs * 0.5))])
                xx += w_
        return y - rh

    def scale_row(scale):
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.black)
        c.drawString(W - M - TB_W + 3 * mm, H - M - 24 * mm - 6 * 9 * mm + 1.8 * mm, scale)

    full = (M + 8 * mm, M + 8 * mm, W - 2 * M - TB_W - 16 * mm, H - 2 * M - 22 * mm)
    half_top = (M + 8 * mm, M + 95 * mm, W - 2 * M - TB_W - 16 * mm, H - 2 * M - 110 * mm)
    lv_roofs = res["levels"]

    # S-01 column layout
    frame("S-01", "Column Layout & Grid", "")
    heading("Column Layout & Grid")
    scale_row(_draw_pdf(c, column_layout(res, plan), *full, style=style))
    c.showPage()
    # S-02 foundation plan + schedule + detail
    frame("S-02", "Foundation Plan & Footing Schedule", "")
    heading("Foundation Plan & Footing Schedule")
    scale_row(_draw_pdf(c, foundation_plan(res, plan), M + 8 * mm, M + 8 * mm, 138 * mm, H - 2 * M - 22 * mm, style=style))
    y = table(M + 152 * mm, H - M - 20 * mm, ["Mark", "Size (m)", "Depth (mm)", "Steel", "Column", "Nos"],
              [[f["mark"], f"{f['B_m']} x {f['B_m']}", f["D_mm"], f["steel"], f["col"], f["count"]] for f in res["footing_schedule"]],
              [12 * mm, 20 * mm, 17 * mm, 46 * mm, 18 * mm, 10 * mm])
    _draw_pdf(c, footing_detail(res), M + 152 * mm, M + 10 * mm, 120 * mm, max(60 * mm, y - M - 20 * mm), style=style, scales=[10, 15, 20, 25, 30, 40, 50, 75, 100])
    c.showPage()
    # S-03 column schedule + sections
    frame("S-03", "Column Schedule & Sections", "see sections")
    heading("Column Schedule & Sections")
    y = table(M + 8 * mm, H - M - 20 * mm, ["Mark", "Size (mm)", "Main bars", "Ties", "Pu (kN)", "Nos"],
              [[r["mark"], f"{r['b_mm']} x {r['D_mm']}", r["bars"], r["ties"], r["Pu_kn"], r["count"]] for r in res["column_schedule"]],
              [16 * mm, 28 * mm, 28 * mm, 34 * mm, 20 * mm, 12 * mm])
    sc = _draw_pdf(c, column_section(res), M + 8 * mm, M + 10 * mm, W - 2 * M - TB_W - 16 * mm, y - M - 20 * mm, style=style, scales=[10, 15, 20, 25, 30, 40, 50, 75, 100])
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.black)
    c.drawString(M + 8 * mm, M + 12 * mm, f"Column sections – scale {sc} on A3")
    c.showPage()
    # S-04 beam layouts (one per floor roof) + schedule + typical detail
    for li, lvn in enumerate(lv_roofs):
        frame(f"S-04{chr(97 + li)}", f"Beam Layout – {lvn} roof", "")
        heading(f"Beam Layout – {lvn} roof")
        scale_row(_draw_pdf(c, beam_layout(res, plan, lvn), M + 8 * mm, M + 8 * mm, 138 * mm, H - 2 * M - 22 * mm, style=style))
        rows = sorted({b["mark"]: b for b in res["beams"] if b["level"] == lvn}.values(), key=lambda b: int(b["mark"][1:]))
        y = table(M + 152 * mm, H - M - 20 * mm, ["Mark", "b x D", "Bottom", "Top", "Stirrups"],
                  [[b["mark"], f"{b['b_mm']}x{b['D_mm']}", b["bottom"], b["top"], b["stirrups"]] for b in rows],
                  [12 * mm, 20 * mm, 22 * mm, 22 * mm, 44 * mm])
        if li == 0:
            _draw_pdf(c, beam_detail(res), M + 152 * mm, M + 10 * mm, 120 * mm, max(55 * mm, y - M - 20 * mm), style=style, scales=[10, 15, 20, 25, 30, 40, 50, 75, 100])
        c.showPage()
    # S-05 slab layouts
    for li, lvn in enumerate(lv_roofs):
        frame(f"S-05{chr(97 + li)}", f"Slab Layout – {lvn} roof", "")
        heading(f"Slab Layout – {lvn} roof")
        scale_row(_draw_pdf(c, slab_layout(res, plan, lvn), M + 8 * mm, M + 8 * mm, 138 * mm, H - 2 * M - 22 * mm, style=style))
        rows = [s for s in res["slabs"] if s["level"] == lvn]
        table(M + 152 * mm, H - M - 20 * mm, ["Mark", "Room", "lx x ly (m)", "D", "Main (short)", "Dist./long"],
              [[s["mark"], s["room"][:14], f"{s['lx_m']} x {s['ly_m']}", s["D_mm"], s["short_steel"], s["long_steel"][:18]] for s in rows],
              [11 * mm, 24 * mm, 20 * mm, 9 * mm, 28 * mm, 31 * mm])
        c.showPage()
    # S-06 notes & quantities
    frame("S-06", "General Notes & Quantities", "-")
    heading("General Notes, Checks & Quantities")
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    yy = H - M - 22 * mm
    for t in res["notes"] + [f"WARNING: {w}" for w in res["warnings"]]:
        c.setFillColor(colors.HexColor("#b91c1c") if t.startswith("WARNING") else colors.black)
        c.drawString(M + 8 * mm, yy, ("• " + t)[:170])
        yy -= 6 * mm
    table(M + 8 * mm, yy - 6 * mm, ["Member", "Concrete (m3)", "Steel (kg, approx.)"],
          [[q["member"], q["concrete_m3"], q["steel_kg"]] for q in res["quantities"]] +
          [["Total", res["summary"]["concrete_m3"], res["summary"]["steel_kg"]]], [40 * mm, 34 * mm, 40 * mm])
    if res.get("roof_sheets"):  # 1.17 sheet roofs – loads and MS steel (sizes as entered)
        rows = [[r["label"][:40], f"{r['dead_kn_m2']} + {r['live_kn_m2']}", r["total_kn"], r["span_m"], r["trusses"] or "-",
                 r["reaction_kn"], r["steel_kg"]] for r in res["roof_sheets"]]
        table(M + 125 * mm, yy - 6 * mm, ["Sheet roof", "DL+LL kN/m2", "Total kN", "Span m", "Trusses", "React. kN", "MS kg"], rows,
              [50 * mm, 20 * mm, 15 * mm, 13 * mm, 13 * mm, 15 * mm, 13 * mm], fs=7)
    c.showPage()
    c.save()
    return buf.getvalue()


def sheet_pages(res: dict) -> dict:
    """1.13: preview key -> page (1-based) in structural_pdf."""
    n = len(res["levels"])
    out = {"columns": 1, "foundation": 2, "footing": 2, "column_sections": 3, "beam_detail": 4, "notes": 4 + 2 * n}
    for i, lvn in enumerate(res["levels"]):
        out[f"beams:{lvn}"] = 4 + i
        out[f"slabs:{lvn}"] = 4 + n + i
    return out


def previews(res: dict, plan: dict) -> dict:
    out = {}
    dw = {"columns": column_layout(res, plan), "foundation": foundation_plan(res, plan), "footing": footing_detail(res),
          "column_sections": column_section(res), "beam_detail": beam_detail(res)}
    for lvn in res["levels"]:
        dw[f"beams:{lvn}"] = beam_layout(res, plan, lvn)
        dw[f"slabs:{lvn}"] = slab_layout(res, plan, lvn)
    for k, d in dw.items():
        out[k] = {"paper": to_svg(d), "cad": to_svg(d, style="cad"), "title": d.title}
    return out
