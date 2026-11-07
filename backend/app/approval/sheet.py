"""1.14 – Part 6: building-approval (planning permission) drawing.

ONE submission sheet (A1 / A2 / A3, landscape) the way TN local bodies expect it:
  * site plan with the ACTUAL setbacks provided (ft and m), road, plot size, north, RWH pit / septic / sump marks
  * every floor plan, front elevation, section A-A
  * key plan (not to scale), area statement, setback check (required vs provided), schedule of openings,
    general notes, owner / licensed engineer signature boxes and an empty "for office use" box.
Nothing is guessed: owner name, survey no., village, taluk and district must be given; allowed FSI and
coverage are checked only when the owner enters the permitted values. No seal, stamp or signature is printed.
"""
import io

from ..design.sheets import (FT_M, PALETTE, Dwg, _draw_pdf, _north, area_details, dwgs_dxf, floor_plan,
                             front_elevation, ft_in, schedule, section)

REQUIRED = [("owner_name", "Owner name (as in the patta / sale deed)"), ("survey_no", "Survey / S.F. No."),
            ("village", "Village"), ("taluk", "Taluk"), ("district", "District")]
SIZES = {"A1": (841, 594), "A2": (594, 420), "A3": (420, 297)}
AUTHORITY_TITLE = {"dtcp": "DTCP / LOCAL PLANNING AUTHORITY", "cmda": "CHENNAI METROPOLITAN DEVELOPMENT AUTHORITY (CMDA)",
                   "corporation": "CORPORATION", "municipality": "MUNICIPALITY", "panchayat": "VILLAGE PANCHAYAT"}


class NeedInfo(Exception):
    def __init__(self, questions: list[str]):
        super().__init__("; ".join(questions))
        self.questions = questions


def missing(info: dict) -> list[str]:
    return [f"Please give the {label.rstrip('.')}." for k, label in REQUIRED if not str(info.get(k) or "").strip()]


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def provided_setbacks(plan: dict) -> dict:
    """Actual open space around the building (largest footprint of all floors), in ft."""
    b, P = plan["building"], plan["plot"]
    xs, ys = [], []
    for lv in plan["levels"]:
        for r in lv["rooms"]:
            xs += [b["x"] + r["x"], b["x"] + r["x"] + r["w"]]
            ys += [b["y"] + r["y"], b["y"] + r["y"] + r["d"]]
    from ..design.plot import provided
    pp = provided(P, min(xs), min(ys), max(xs), max(ys))  # 1.18 irregular plot: measured to every side
    if pp:
        return pp
    return {"front": round(min(ys), 2), "rear": round(P["d"] - max(ys), 2), "left": round(min(xs), 2),
            "right": round(P["w"] - max(xs), 2)}


def compliance(plan: dict, info: dict) -> dict:
    """Required vs provided. status: ok | fail | check (needs the owner's value / local body to confirm)."""
    area = area_details(plan)
    sb = plan.get("setbacks") or {}
    req_m = sb.get("m") or {}
    prov = provided_setbacks(plan)
    rows = []
    for k in ("front", "rear", "left", "right"):
        need = req_m.get(k)
        have = prov[k] * FT_M
        st = "check" if need is None else ("ok" if have + 0.005 >= float(need) else "fail")
        rows.append({"item": f"Setback – {k}", "required": f"{need:g} m" if need is not None else "-",
                     "provided": f"{have:.2f} m ({ft_in(prov[k])})", "status": st})
    hmax = sb.get("max_height_m")
    rows.append({"item": "Building height (incl. parapet / head room / sheet roof ridge)", "required": f"max {hmax:g} m" if hmax else "-",
                 "provided": f"{area['height_m']} m", "status": "check" if not hmax else ("ok" if area["height_m"] <= hmax + 0.005 else "fail")})
    fsi_allowed = _num(info.get("allowed_fsi"))
    rows.append({"item": "FSI (floor space index)", "required": f"max {fsi_allowed:g}" if fsi_allowed else "enter permitted FSI",
                 "provided": f"{area['fsi']}", "status": "check" if not fsi_allowed else ("ok" if area["fsi"] <= fsi_allowed + 1e-6 else "fail")})
    cov_allowed = _num(info.get("allowed_coverage_pct"))
    rows.append({"item": "Plot coverage", "required": f"max {cov_allowed:g}%" if cov_allowed else "enter permitted coverage",
                 "provided": f"{area['coverage_pct']}%", "status": "check" if not cov_allowed else ("ok" if area["coverage_pct"] <= cov_allowed + 1e-6 else "fail")})
    cars = sum(1 for lv in plan["levels"] for r in lv["rooms"] if r["type"] == "parking")
    rows.append({"item": "Car parking", "required": "as per local body", "provided": f"{cars} car space(s)" if cars else "none", "status": "check"})
    rows.append({"item": "Rain water harvesting", "required": "mandatory in TN", "provided": "shown on site plan" if info.get("rwh", True) else "not shown",
                 "status": "ok" if info.get("rwh", True) else "fail"})
    fails = sum(r["status"] == "fail" for r in rows)
    checks = sum(r["status"] == "check" for r in rows)
    return {"rows": rows, "area": area, "provided_ft": prov, "fails": fails, "checks": checks,
            "missing": missing(info),
            "note": "Setbacks / height from TNCDBR 2019 as built into the app. Permitted FSI, coverage and parking depend on the "
                    "local body, road width and zone – enter / confirm them with the planning office before submitting."}


def approval_site_plan(plan: dict, info: dict) -> Dwg:
    P, b = plan["plot"], plan["building"]
    d = Dwg("Site Plan")
    from ..design.plot import draw_plot
    poly = draw_plot(d, P)  # 1.18 irregular plot
    if not poly:
        d.rect(0, 0, P["w"], P["d"], "PLOT")
    prov = provided_setbacks(plan)
    for li, lv in enumerate(plan["levels"][:1]):
        for r in lv["rooms"]:
            d.rect(b["x"] + r["x"], b["y"] + r["y"], r["w"], r["d"], "BUILDING", "#ffffff")
    if poly:  # footprint straight from the rooms (the polygon setbacks are distances, not coordinates)
        xs = [b["x"] + r["x"] for r in plan["levels"][0]["rooms"]] + [b["x"] + r["x"] + r["w"] for r in plan["levels"][0]["rooms"]]
        ys = [b["y"] + r["y"] for r in plan["levels"][0]["rooms"]] + [b["y"] + r["y"] + r["d"] for r in plan["levels"][0]["rooms"]]
        bx0, by0, bx1, by1 = min(xs), min(ys), max(xs), max(ys)
    else:
        bx0, by0 = prov["left"], prov["front"]
        bx1, by1 = P["w"] - prov["right"], P["d"] - prov["rear"]
    d.hatch(bx0, by0, bx1 - bx0, by1 - by0, 1.2)
    d.text((bx0 + bx1) / 2, (by0 + by1) / 2 + 0.6, "PROPOSED BUILDING", 0.9, layer="ROOMTEXT", bold=True, mask=True)
    nlv = len(plan["levels"])
    fl = "G" if nlv == 1 else "G+" + str(nlv - 1)
    d.text((bx0 + bx1) / 2, (by0 + by1) / 2 - 1.0, fl + " · residential", 0.7, layer="ROOMTEXT", mask=True)
    # road
    d.rect(-4, -9, P["w"] + 8, 6, "ROAD", "#f1f5f9")
    d.line(-4, -6, P["w"] + 4, -6, "CENTRE")
    road = (plan.get("setbacks") or {}).get("road_width_m") or (plan.get("requirements") or {}).get("road_width_m")
    rn = str(info.get("road_name") or "").strip()
    d.text(P["w"] / 2, -8.2, f"{rn.upper() + ' – ' if rn else ''}ROAD{f' ({float(road):g} m WIDE)' if road else ''}", 0.8, bold=True)
    # actual setbacks (provided)
    m = lambda v: f"{ft_in(v)} ({v * FT_M:.2f} m)"
    if prov["front"] > 0.05:
        d.dim_v(-1.6, 0, by0, m(prov["front"]))
    if prov["rear"] > 0.05:
        d.dim_v(-1.6, by1, P["d"], m(prov["rear"]))
    if prov["left"] > 0.05:
        d.dim_h(0, bx0, P["d"] + 1.6, m(prov["left"]))
    if prov["right"] > 0.05:
        d.dim_h(bx1, P["w"], P["d"] + 1.6, m(prov["right"]))
    if not poly:
        d.dim_h(0, P["w"], P["d"] + 4.2, f"PLOT {m(P['w'])}")
        d.dim_v(P["w"] + 3.6, 0, P["d"], m(P["d"]))
    d.dim_h(bx0, bx1, by0 - 1.4, ft_in(bx1 - bx0))
    # compound wall + gate
    d.text(P["w"] / 2, 0.5, "GATE", 0.6, layer="DIM")
    # services (marks only – sizes as per local body / site)
    marks = []
    front_ok = by0 > 3.5
    fy = by0 / 2 if front_ok else None
    if info.get("rwh", True):
        marks.append(("RWH PIT", P["w"] - 2.4, fy if front_ok else P["d"] - 2.4))
    left_slots = [2.6, 8.0, 13.4]  # spread along the front so marks never overlap
    if info.get("sump"):
        marks.append(("SUMP", left_slots.pop(0), fy if front_ok else 2.4))
    if info.get("septic"):
        if prov["rear"] > 4.5:
            marks.append(("SEPTIC TANK", 3.0, P["d"] - prov["rear"] / 2))
        else:
            marks.append(("SEPTIC TANK", left_slots.pop(0), fy if front_ok else 2.4))
    for label, x, y in marks:
        d.arc(x, y, 1.1, 0, 360, "OUTLINE")
        d.line(x - 0.8, y - 0.8, x + 0.8, y + 0.8, "HATCH")
        d.text(x, y + 1.5, label, 0.6, layer="MARK", mask=True)
    for gx in (0, P["w"]):
        for gy in (0, P["d"]):
            d.rect(gx - 0.35, gy - 0.35, 0.7, 0.7, "PLOT", "#111111", 0)
    _north(d, plan, P["w"] + 8, P["d"] - 3)
    return d


def key_plan(plan: dict, info: dict) -> Dwg:
    """Location sketch, not to scale."""
    d = Dwg("Key Plan")
    d.rect(-30, -14, 60, 10, "ROAD", "#f1f5f9")
    d.line(-30, -9, 30, -9, "CENTRE")
    rn = str(info.get("road_name") or "").strip()
    d.text(0, -12.5, (rn.upper() + " ROAD") if rn else "ROAD", 2.4, bold=True)
    for x in (-26, -14, 14):  # neighbouring plots
        d.rect(x, -2, 10, 14, "SETBACK")
    d.rect(-2, -2, 12, 14, "PLOT", "#fde68a")
    d.hatch(-2, -2, 12, 14, 1.5)
    d.text(4, 5, "SITE", 2.8, bold=True, mask=True)
    lm = str(info.get("landmark") or "").strip()
    if lm:
        d.rect(-30, 15, 26, 7, "OUTLINE")
        d.text(-17, 17.6, lm[:24].upper(), 1.8, mask=True)
    _north(d, plan, 25, 14)
    return d


def _fmt_title(plan: dict, info: dict) -> list[str]:
    n = len(plan["levels"])
    floors = "GROUND FLOOR" if n == 1 else f"GROUND + {n - 1} FLOOR{'S' if n > 2 else ''}"
    parts = [f"S.F. No. {info.get('survey_no')}"]
    if info.get("subdivision"):
        parts[0] += f"/{info['subdivision']}"
    if info.get("plot_no"):
        parts.append(f"PLOT No. {info['plot_no']}")
    if info.get("layout_name"):
        parts.append(str(info["layout_name"]).upper())
    if info.get("door_no"):
        parts.insert(0, f"DOOR No. {info['door_no']}")
    loc = f"{str(info.get('village')).upper()} VILLAGE, {str(info.get('taluk')).upper()} TALUK, {str(info.get('district')).upper()} DISTRICT"
    owner = str(info.get("owner_name")).upper()
    pre = {"mr": "Thiru.", "mrs": "Tmt.", "ms": "Selvi."}.get(str(info.get("owner_title") or "").lower(), "Thiru./Tmt.")
    return [f"PROPOSED CONSTRUCTION OF RESIDENTIAL BUILDING ({floors})", "AT " + ", ".join(parts) + ",", loc,
            f"FOR {pre} {owner}" + (f" & {str(info['co_owner']).upper()}" if info.get("co_owner") else "")]


def approval_pdf(plan: dict, project: dict, info: dict, meta: dict, style: str = "paper", size: str = "A1") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    q = missing(info)
    if q:
        raise NeedInfo(q)
    W0, H0 = 841 * mm, 594 * mm  # drawn on A1, scaled to the chosen size
    pw, ph = SIZES.get(size, SIZES["A1"])
    f = pw / 841
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(pw * mm, ph * mm))
    c.scale(f, f)
    co = project.get("company") or {}
    navy = colors.HexColor("#0F2350")
    sched = schedule(plan)
    chk = compliance(plan, info)
    area = chk["area"]
    M, TB = 10 * mm, 170 * mm
    # frame
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.6)
    c.rect(M, M, W0 - 2 * M, H0 - 2 * M)
    tx = W0 - M - TB
    c.setLineWidth(1.0)
    c.line(tx, M, tx, H0 - M)

    def panel(dwg: Dwg, x, y, w, h, title, scales=None):
        c.setStrokeColor(colors.HexColor("#94a3b8"))
        c.setLineWidth(0.4)
        c.rect(x, y, w, h)
        sc = _draw_pdf(c, dwg, x + 4 * mm, y + 12 * mm, w - 8 * mm, h - 20 * mm, style=style, scales=scales)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(x + w / 2, y + 5.5 * mm, f"{title.upper()}  (SCALE {sc})")
        c.setLineWidth(0.6)
        c.setStrokeColor(colors.black)
        tw = c.stringWidth(f"{title.upper()}  (SCALE {sc})", "Helvetica-Bold", 11)
        c.line(x + w / 2 - tw / 2, y + 4.5 * mm, x + w / 2 + tw / 2, y + 4.5 * mm)

    # drawing area: floor plans on top, site plan / elevation / section below
    ax0, ay0, aw, ah = M + 3 * mm, M + 3 * mm, tx - M - 6 * mm, H0 - 2 * M - 6 * mm
    n = len(plan["levels"])
    top_h = ah * 0.52
    pw_each = aw / n
    for i in range(n):
        panel(floor_plan(plan, i), ax0 + i * pw_each, ay0 + ah - top_h, pw_each - 2 * mm, top_h - 2 * mm, f"{plan['levels'][i]['name']} plan")
    bh = ah - top_h - 2 * mm
    widths = [0.36, 0.34, 0.30]
    xx = ax0
    for dwg, ttl, wf in ((approval_site_plan(plan, info), "Site plan", widths[0]), (front_elevation(plan), "Front elevation", widths[1]),
                         (section(plan), "Section A-A", widths[2])):
        panel(dwg, xx, ay0, aw * wf - 2 * mm, bh, ttl)
        xx += aw * wf

    # ----- right column
    y = H0 - M
    c.setFillColor(navy)
    c.rect(tx, y - 16 * mm, TB, 16 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 12)
    auth = AUTHORITY_TITLE.get(str(info.get("authority") or ""), "")
    c.drawCentredString(tx + TB / 2, y - 7 * mm, "PLANNING PERMISSION / BUILDING APPROVAL DRAWING")
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(tx + TB / 2, y - 12.5 * mm, (f"Submitted to: {auth}" + (f" – {info['authority_place']}" if info.get("authority_place") else "")) if auth else "")
    y -= 16 * mm
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9.5)
    for ln in _fmt_title(plan, info):
        y -= 5.2 * mm
        c.drawCentredString(tx + TB / 2, y, ln[:78])
    y -= 3 * mm
    c.setLineWidth(0.5)
    c.line(tx, y, W0 - M, y)

    # key plan
    kh = 58 * mm
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(tx + 3 * mm, y - 4.5 * mm, "KEY PLAN (NOT TO SCALE)")
    _draw_pdf(c, key_plan(plan, info), tx + 3 * mm, y - kh + 2 * mm, TB - 6 * mm, kh - 9 * mm, style="paper", scales=[1e-9])  # not to scale: fit the box
    y -= kh
    c.line(tx, y, W0 - M, y)

    def table(x, y, headers, rows, widths, fs=7.6, rh=4.8 * mm, head_fill=navy):
        c.setFillColor(head_fill)
        c.rect(x, y - rh, sum(widths), rh, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", fs)
        xx = x
        for h_, w_ in zip(headers, widths):
            c.drawString(xx + 1.2 * mm, y - rh + 1.5 * mm, h_)
            xx += w_
        c.setFont("Helvetica", fs)
        for ri, r in enumerate(rows):
            y -= rh
            if ri % 2:
                c.setFillColor(colors.HexColor("#F4F7FC"))
                c.rect(x, y - rh, sum(widths), rh, fill=1, stroke=0)
            xx = x
            for v, w_ in zip(r, widths):
                s = str(v)
                col = colors.HexColor("#b91c1c") if s in ("NOT OK",) else colors.HexColor("#15803d") if s == "OK" else colors.black
                c.setFillColor(col)
                c.drawString(xx + 1.2 * mm, y - rh + 1.5 * mm, s[: int(w_ / (fs * 0.5))])
                xx += w_
            c.setStrokeColor(colors.HexColor("#cbd5e1"))
            c.setLineWidth(0.3)
            c.line(x, y - rh, x + sum(widths), y - rh)
        return y - rh

    # area statement
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(tx + 3 * mm, y - 4.5 * mm, "AREA STATEMENT")
    rows = [["Plot area", f"{area['plot_sqft']:,.0f}", f"{area['plot_m2']:,.2f}"]]
    for r in area["rows"]:
        rows.append([f"{r['floor']} (built-up)", f"{r['builtup_sqft']:,.0f}", f"{r['builtup_sqft'] * FT_M ** 2:,.2f}"])
        rows += [[f"   {u['name']} (carpet)", f"{u['carpet_sqft']:,.0f}", f"{u['carpet_sqft'] * FT_M ** 2:,.2f}"]
                 for u in r.get("units") or []]  # 1.19 unit-wise
    rows += [["Total built-up", f"{area['total_builtup_sqft']:,.0f}", f"{area['total_builtup_m2']:,.2f}"],
             ["FSI / coverage", f"{area['fsi']}", f"{area['coverage_pct']}%"]]
    rows += [[f"Sheet roof – {rs['level']}", f"{rs['covered_sqft']:,.0f}", f"{rs['covered_sqft'] * FT_M ** 2:,.2f}"]
             for rs in area.get("roof_sheets") or []]  # 1.17
    y = table(tx + 3 * mm, y - 6 * mm, ["Particular", "sq ft", "sq m"], rows, [84 * mm, 38 * mm, 42 * mm])
    y -= 3 * mm
    # compliance
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(tx + 3 * mm, y - 4.5 * mm, "SETBACKS & RULES – REQUIRED vs PROVIDED")
    lab = {"ok": "OK", "fail": "NOT OK", "check": "to confirm"}
    y = table(tx + 3 * mm, y - 6 * mm, ["Item", "Required", "Provided", ""],
              [[r["item"].replace("Setback – ", "Setback "), r["required"], r["provided"], lab[r["status"]]] for r in chk["rows"]],
              [52 * mm, 34 * mm, 52 * mm, 26 * mm])
    y -= 3 * mm
    # openings
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(tx + 3 * mm, y - 4.5 * mm, "SCHEDULE OF DOORS & WINDOWS")
    y = table(tx + 3 * mm, y - 6 * mm, ["Mark", "Type", "Size (W x H)", "Nos"],
              [[s["mark"], s["label"], s["size"], s["count"]] for s in sched][:12], [16 * mm, 62 * mm, 64 * mm, 22 * mm])
    y -= 3 * mm
    # notes
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(tx + 3 * mm, y - 4.5 * mm, "NOTES")
    c.setFont("Helvetica", 7.2)
    notes = ["All dimensions are in feet-inches unless noted; metric values in brackets.",
             "Setbacks shown are the open spaces actually provided on site.",
             "Rain water harvesting structure as per local body norms." if info.get("rwh", True) else "",
             "Structural design by a qualified engineer; materials as per IS codes.",
             str(info.get("extra_note") or "")]
    yy = y - 8.5 * mm
    for t in [t for t in notes if t]:
        c.drawString(tx + 4 * mm, yy, ("• " + t)[:110])
        yy -= 3.8 * mm
    y = yy - 1 * mm
    # signatures (empty boxes – signed by hand)
    sig_h = 24 * mm
    boxes = [("Signature of the owner(s)", str(info.get("owner_name") or "")),
             ("Licensed engineer / surveyor", " · ".join(v for v in [str(info.get("engineer_name") or ""), f"Reg. No. {info['engineer_reg_no']}" if info.get("engineer_reg_no") else ""] if v))]
    bw_ = (TB - 6 * mm) / 2
    by_ = max(M + 46 * mm, y - sig_h)
    for i, (lab_, sub) in enumerate(boxes):
        bx_ = tx + 3 * mm + i * bw_
        c.setStrokeColor(colors.HexColor("#64748b"))
        c.setLineWidth(0.5)
        c.rect(bx_, by_, bw_ - 2 * mm, sig_h)
        c.setFillColor(colors.HexColor("#475569"))
        c.setFont("Helvetica", 7)
        c.drawString(bx_ + 2 * mm, by_ + sig_h - 4 * mm, lab_)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(bx_ + 2 * mm, by_ + 2.5 * mm, sub[:44])
    # office use (left empty)
    c.setStrokeColor(colors.HexColor("#64748b"))
    c.rect(tx + 3 * mm, M + 20 * mm, TB - 6 * mm, min(24 * mm, by_ - M - 22 * mm))
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawString(tx + 5 * mm, M + 20 * mm + min(24 * mm, by_ - M - 22 * mm) - 4 * mm, "FOR OFFICE USE (approval no., date, seal of the authority)")
    # bottom strip: firm, drawing no, date
    c.setFillColor(navy)
    c.rect(tx, M, TB, 18 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(tx + 4 * mm, M + 11 * mm, (co.get("name") or "")[:40])
    c.setFont("Helvetica", 7.5)
    c.drawString(tx + 4 * mm, M + 5.5 * mm, " · ".join(v for v in [f"Proprietor: {co['proprietor']}" if co.get("proprietor") else "", co.get("phone", "")] if v)[:60])
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(W0 - M - 4 * mm, M + 11 * mm, f"Drawing AP-01 · {size}")
    c.setFont("Helvetica", 7.5)
    c.drawRightString(W0 - M - 4 * mm, M + 5.5 * mm, f"{project.get('code', '')} · v{meta.get('version', '')} · {meta.get('date', '')}")
    if style == "cad":
        pass  # drawing panels already carry the CAD background; the sheet frame stays white for printing
    c.showPage()
    c.save()
    return buf.getvalue()


def approval_dxf(plan: dict, info: dict, project: dict) -> bytes:
    q = missing(info)
    if q:
        raise NeedInfo(q)
    dw = [approval_site_plan(plan, info)] + [floor_plan(plan, i) for i in range(len(plan["levels"]))] + \
         [front_elevation(plan), section(plan), key_plan(plan, info)]
    return dwgs_dxf(dw, " ".join(_fmt_title(plan, info))[:200])


_ = PALETTE  # (kept for style reference)
