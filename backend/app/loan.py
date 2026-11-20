"""1.25 – Building Loan Process: ONE PDF for the bank.

Order: cover (letterhead, client / date typed by the user) → 2D plan → oral (quick) estimate → detailed estimate
(abstract + area + stage-wise payment, then the full BOQ) → stage-wise payment & loan release → common bank
document checklist.

Rules (owner): no auto date, no invented seal / signature (one blank "Seal & Signature" box), no "built with" text,
rates are the project's own estimate; the sq-ft total rate is ENTERED by the user and the whole estimate is scaled to it.
The checklist and release stages were compiled from the public pages of SBI, HDFC, Canara Bank, Aadhar Housing and
other lenders (checked Nov 2026) – banks differ, the bank's own list wins.
"""
from __future__ import annotations

import copy
import io

from . import letterhead as lh

# ---------------------------------------------------------------- sq-ft rate scaling
_ITEM_MONEY = ("rate", "material_cost", "labour_cost", "equipment_cost", "amount")


def scale_to_rate(result: dict, rate_per_sqft: float) -> dict:
    """Scale every rupee value of an estimate result so that  grand total = built-up sq ft × the rate typed by the user.
    Quantities never change. Returns a new result (the saved estimate is untouched)."""
    r = copy.deepcopy(result)
    t = r["totals"]
    sq = float(t.get("builtup_sqft") or 0)
    grand = float(t.get("grand_total") or 0)
    if rate_per_sqft <= 0 or sq <= 0 or grand <= 0:
        return r
    target = rate_per_sqft * sq
    f = target / grand
    for it in r.get("items", []):
        for k in _ITEM_MONEY:
            if isinstance(it.get(k), (int, float)):
                it[k] = round(it[k] * f, 2)
    for k in ("materials", "labour", "equipment", "grand_total"):
        if isinstance(t.get(k), (int, float)):
            t[k] = round(t[k] * f, 0)
    t["grand_total"] = round(target, 0)
    t["cost_per_sqft"] = round(rate_per_sqft, 0)
    for g in r.get("breakdown", []):
        if isinstance(g.get("amount"), (int, float)):
            g["amount"] = round(g["amount"] * f, 0)
    for e in r.get("extras", []):
        if isinstance(e.get("amount"), (int, float)):
            e["amount"] = round(e["amount"] * f, 0)
    for fl in r.get("floors", []):
        if isinstance(fl.get("total"), (int, float)):
            fl["total"] = round(fl["total"] * f, 0)
    for m in r.get("materials", []) if isinstance(r.get("materials"), list) else []:
        for k in ("rate", "amount"):
            if isinstance(m.get(k), (int, float)):
                m[k] = round(m[k] * f, 2)
    for m in r.get("labour", []) if isinstance(r.get("labour"), list) else []:
        for k in ("rate", "amount"):
            if isinstance(m.get(k), (int, float)):
                m[k] = round(m[k] * f, 2)
    fb = r.get("floor_boq")
    if fb:
        for x in fb.get("rows", []):
            for k in ("rate", "amount"):
                if isinstance(x.get(k), (int, float)):
                    x[k] = round(x[k] * f, 2)
    for x in r.get("payment_schedule", []):
        x["amount"] = round(t["grand_total"] * x["pct"] / 100, 0)
    r.setdefault("assumptions", []).append(
        f"Total cost set to Rs. {rate_per_sqft:,.0f} per sq ft × {sq:,.0f} sq ft (rate entered by the owner); every item is "
        f"scaled by {f:.3f} from the calculated rates. Quantities are unchanged.")
    r["scaled_to_rate"] = {"rate_per_sqft": rate_per_sqft, "factor": round(f, 4)}
    return r


# ---------------------------------------------------------------- reference lists (web-checked, Nov 2026)
LOAN_STAGES = [  # typical release plan – the bank's engineer certifies each stage first
    ("Plot / land (only if the loan includes the plot)", "Title deed check + own-contribution receipt"),
    ("Foundation / plinth", "Engineer / architect stage certificate + site photos"),
    ("Ground floor roof slab", "Engineer's verification of the roof level"),
    ("First floor roof slab (G+1)", "Structural stage report by the bank's inspector"),
    ("Brickwork / masonry", "Wall completion certificate"),
    ("Plaster, flooring, doors, windows", "Stage certificate + photos"),
    ("Finishing, painting, final", "Completion certificate; last instalment usually after final inspection"),
]

BANK_CHECKLIST = [
    ("Identity & address (every applicant / co-applicant)", [
        "Passport-size photographs (2 – 3 each)",
        "PAN card",
        "Aadhaar card / Passport / Voter ID / Driving licence (identity + address)",
        "Latest address proof (utility bill / ration card) if the ID address is old"]),
    ("Income proof – salaried", [
        "Last 3 – 6 months' salary slips",
        "Form 16 / last 2 years' ITR",
        "Last 6 months' salary account bank statement",
        "Employment / appointment letter (some banks)"]),
    ("Income proof – self-employed / business", [
        "Last 2 – 3 years' ITR with computation of income, balance sheet and P&L",
        "Last 6 – 12 months' current / savings account statements",
        "Form 26AS",
        "Business profile / registration (GST, Udyam, trade licence)"]),
    ("Property & land", [
        "Title deed / sale deed (registered) with the parent (mother) documents",
        "Encumbrance certificate (EC) – usually 13 – 30 years",
        "Patta / chitta / A-register extract in the applicant's name (Tamil Nadu)",
        "Latest property-tax receipt and EB (electricity) bill of the plot, if any",
        "Legal-opinion / title search report (the bank's advocate prepares it)"]),
    ("Construction papers", [
        "Plan sanctioned by the local authority (DTCP / CMDA / municipality / panchayat) and building permit",
        "Detailed estimate of construction cost by a civil engineer / architect (this file)",
        "2D plan with area statement (this file)",
        "Stage-wise payment schedule (this file)",
        "Proof of own contribution (margin money) – bank statement / receipts"]),
    ("Bank forms", [
        "Filled application form with photograph, signed",
        "Processing-fee cheque / online payment receipt",
        "Last 6 months' statement of all existing loans (if any)",
        "Any other paper the bank's branch asks for – banks differ, the bank's own list wins"]),
]

PLAN_NOTE = ("2D plan drawn from the saved design. Setbacks and sanction details come from the approved plan of the local body.")


# ---------------------------------------------------------------- PDF sections
def _styles():
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    ss = getSampleStyleSheet()
    navy = colors.HexColor("#1E3A8A")
    return dict(
        navy=navy, colors=colors,
        h1=ParagraphStyle("h1", parent=ss["Title"], textColor=navy, fontSize=15, spaceAfter=4),
        h2=ParagraphStyle("h2", parent=ss["Heading3"], textColor=navy, spaceBefore=8, spaceAfter=4),
        body=ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12),
        small=ParagraphStyle("s", parent=ss["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#475467")))


def _safe(t: str) -> str:
    for k, v in {"²": "2", "³": "3", "≈": "~", "₹": "Rs.", "≤": "<=", "≥": ">=", "–": "-", "×": "x", "·": "-"}.items():
        t = str(t).replace(k, v)
    return t


def _inr(v: float) -> str:
    from .estimate.exports import inr
    return inr(v)


def _doc(first_header: bool, title: str):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm,
                            bottomMargin=18 * mm, title=title)
    PW, PH = A4
    first = lh.on_first(PW, PH) if first_header else lh.on_later(PW)
    return buf, doc, first, lh.on_later(PW), PW


def _table(data, widths, S, right_from=None, bold_last=False):
    from reportlab.platypus import Table, TableStyle
    c = S["colors"]
    tb = Table(data, colWidths=widths, repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), S["navy"]), ("TEXTCOLOR", (0, 0), (-1, 0), c.white),
          ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
          ("GRID", (0, 0), (-1, -1), 0.3, c.HexColor("#C9D2E3")),
          ("ROWBACKGROUNDS", (0, 1), (-1, -1), [c.white, c.HexColor("#F4F7FC")]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    if right_from is not None:
        st.append(("ALIGN", (right_from, 1), (-1, -1), "RIGHT"))
    if bold_last:
        st += [("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("BACKGROUND", (0, -1), (-1, -1), c.HexColor("#E8EEFB"))]
    tb.setStyle(TableStyle(st))
    return tb


def cover_pdf(project: dict, est: dict, o: dict, sections: list[str]) -> bytes:
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer
    S = _styles()
    buf, doc, first, later, PW = _doc(True, "Building loan process")
    r = est["result"]
    t = r["totals"]
    story = [Spacer(1, lh.header_height(PW) + 18 + 4 - 14 * mm)]
    # client + date are typed by the user – blank lines stay blank
    from reportlab.platypus import Table
    story.append(Table([[Paragraph("<b>Client:</b> " + _safe(o.get("client_name") or "_" * 34), S["body"]),
                         Paragraph("<b>Date:</b> " + _safe(o.get("date") or "_" * 14), S["body"])]],
                       colWidths=[115 * mm, 65 * mm]))
    story += [Spacer(1, 6), Paragraph("BUILDING LOAN PROCESS - DOCUMENT SET", S["h1"])]
    site = ", ".join(x for x in [project.get("location"), project.get("district"), project.get("state")] if x) or "-"
    info = [["Particulars", "Details"],
            ["Project", _safe(f"{project.get('name', '')} ({project.get('code', '')})")],
            ["Site", _safe(site)], ["Plot size", _safe(project.get("plot") or "-")],
            ["Floors", _safe(project.get("floors") or "-")],
            ["Built-up area", f"{t['builtup_sqft']:,.0f} sq ft"],
            ["Estimated cost", f"Rs. {_inr(t['grand_total'])}  (Rs. {_inr(t['cost_per_sqft'])} per sq ft)"]]
    if o.get("bank_name"):
        info.append(["Bank", _safe(o["bank_name"])])
    if o.get("loan_amount"):
        info.append(["Loan applied", f"Rs. {_inr(o['loan_amount'])}"])
    story.append(_table(info, [55 * mm, 125 * mm], S))
    story += [Paragraph("Contents", S["h2"])]
    for i, nme in enumerate(sections, 1):
        story.append(Paragraph(f"{i}. {nme}", S["body"]))
    story.append(Spacer(1, 10))
    story.append(lh.SealSignature(180 * mm))
    doc.build(story, onFirstPage=first, onLaterPages=later)
    return buf.getvalue()


def oral_pdf(project: dict, est: dict) -> bytes:
    """One page in plain words: the quick (oral) estimate – rounded, by main work."""
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer
    S = _styles()
    buf, doc, first, later, PW = _doc(False, "Oral estimate")
    r = est["result"]
    t = r["totals"]
    grand = t["grand_total"]
    sq = t["builtup_sqft"]

    def rnd(v):  # round to the nearest Rs. 5,000 so it reads like a spoken figure
        return int(round(v / 5000.0) * 5000)
    groups = [g for g in r["breakdown"] if g["group"] != "Extras"]
    extra = sum(e["amount"] for e in r.get("extras", []) if e.get("amount"))
    story = [Paragraph("ORAL (QUICK) ESTIMATE", S["h1"]),
             Paragraph(_safe(f"{project.get('name', '')} - {sq:,.0f} sq ft built-up at about Rs. {_inr(round(t['cost_per_sqft'], -1))} "
                             f"per sq ft = about <b>Rs. {_inr(rnd(grand))}</b>."), S["body"]), Spacer(1, 6)]
    data = [["Work", "About (Rs.)", "%"]]
    for g in groups:
        data.append([_safe(g["group"]), _inr(rnd(g["amount"])), f"{100 * g['amount'] / grand:.0f}%"])
    if extra:
        data.append(["Contractor margin, overheads and other extras", _inr(rnd(extra)), f"{100 * extra / grand:.0f}%"])
    data.append(["TOTAL (about)", _inr(rnd(grand)), "100%"])
    story.append(_table(data, [110 * mm, 45 * mm, 25 * mm], S, 1, True))
    story += [Spacer(1, 8), Paragraph(
        _safe(f"Approx. time: {t['duration_months']} months. Main materials: cement {t['cement_bags']:,} bags, steel {t['steel_kg']:,} kg, "
              f"bricks {t['bricks']:,} nos. The detailed estimate follows; the bank's engineer will check it on site."), S["small"])]
    doc.build(story, onFirstPage=first, onLaterPages=later)
    return buf.getvalue()


def stages_pdf(project: dict, est: dict, o: dict) -> bytes:
    """Stage-wise payment to the contractor + (optional) bank release split + what the bank wants at each stage."""
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer
    S = _styles()
    buf, doc, first, later, PW = _doc(False, "Stage-wise payment")
    r = est["result"]
    ps = r.get("payment_schedule") or []
    grand = r["totals"]["grand_total"]
    loan_pct = o.get("loan_pct")
    story = [Paragraph("STAGE-WISE PAYMENT", S["h1"])]
    hdr = ["Stage", "Work", "%", "Amount (Rs.)"]
    if loan_pct:
        hdr += [f"Bank {loan_pct:g}%", f"Own {100 - loan_pct:g}%"]
    data = [hdr]
    for i, x in enumerate(ps, 1):
        a = x.get("amount") or grand * x["pct"] / 100
        row = [i, _safe(x["stage"]), f"{x['pct']:g}%", _inr(a)]
        if loan_pct:
            row += [_inr(a * loan_pct / 100), _inr(a * (100 - loan_pct) / 100)]
        data.append(row)
    tot = sum((x.get("amount") or 0) for x in ps)
    last = ["", "Total", f"{sum(x['pct'] for x in ps):g}%", _inr(tot)]
    if loan_pct:
        last += [_inr(tot * loan_pct / 100), _inr(tot * (100 - loan_pct) / 100)]
    data.append(last)
    w = [14 * mm, 76 * mm, 16 * mm, 34 * mm] + ([20 * mm, 20 * mm] if loan_pct else [])
    if loan_pct:
        w = [12 * mm, 58 * mm, 14 * mm, 32 * mm, 32 * mm, 32 * mm]
    story.append(_table(data, w, S, 2, True))
    if not loan_pct:
        story.append(Paragraph("Bank / own-contribution split is shown when the loan percentage is entered.", S["small"]))
    story += [Paragraph("How banks release the loan (typical)", S["h2"]),
              Paragraph("The loan is paid in instalments linked to the stage of construction, not in one lump sum. Before each "
                        "release the bank's engineer / valuer visits the site and certifies the stage. The percentages differ "
                        "from bank to bank - the sanction letter decides.", S["body"]), Spacer(1, 4)]
    story.append(_table([["Construction stage", "Paper the bank asks for"]] + [[_safe(a), _safe(b)] for a, b in LOAN_STAGES],
                        [85 * mm, 95 * mm], S))
    doc.build(story, onFirstPage=first, onLaterPages=later)
    return buf.getvalue()


def checklist_pdf() -> bytes:
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    S = _styles()
    buf, doc, first, later, PW = _doc(False, "Bank document checklist")
    story = [Paragraph("COMMON BANK DOCUMENT CHECKLIST - HOME CONSTRUCTION LOAN", S["h1"]),
             Paragraph("Tick each paper as it is collected. Compiled from the public requirement lists of SBI, HDFC, Canara Bank, "
                       "Aadhar Housing and other lenders (checked Nov 2026). Every bank adds or drops a few papers - the "
                       "bank branch's own list wins.", S["small"])]
    for title, items in BANK_CHECKLIST:
        story.append(Paragraph(_safe(title), S["h2"]))
        rows = [["[   ]", Paragraph(_safe(x), S["body"])] for x in items]
        tb = Table(rows, colWidths=[14 * mm, 166 * mm])
        tb.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (0, -1), 9),
                                ("LINEBELOW", (0, 0), (-1, -1), 0.25, S["colors"].HexColor("#D9DEE8"))]))
        story.append(tb)
    story += [Spacer(1, 6), lh.SealSignature(180 * mm)]
    doc.build(story, onFirstPage=first, onLaterPages=later)
    return buf.getvalue()


# ---------------------------------------------------------------- assemble
def build_pack(project: dict, est: dict, plan: dict | None, o: dict) -> bytes:
    """project / est as from routers.estimate.export_payload; plan = saved design plan (or None); o = typed options:
    rate_per_sqft, client_name, date, bank_name, loan_amount, loan_pct."""
    from pypdf import PdfReader, PdfWriter

    from .estimate.exports import _portrait_pdf, to_pdf
    est = copy.deepcopy(est)
    rate = float(o.get("rate_per_sqft") or 0)
    if rate > 0:
        est["result"] = scale_to_rate(est["result"], rate)
    names = ["2D plan", "Oral (quick) estimate", "Detailed estimate and BOQ", "Stage-wise payment and loan release",
             "Common bank document checklist"]
    if not plan:
        names = names[1:]
    parts: list[bytes] = [cover_pdf(project, est, o, names)]
    if plan:
        from .design.exports import to_pdf as plan_pdf
        parts.append(plan_pdf(plan, {"name": project.get("name", "")}, {}))
    parts += [oral_pdf(project, est),
              _portrait_pdf(project, est, "bank", header=False, seal=False),
              to_pdf(project, est, header=False, seal=False),
              stages_pdf(project, est, o), checklist_pdf()]
    w = PdfWriter()
    for b in parts:
        for pg in PdfReader(io.BytesIO(b)).pages:
            w.add_page(pg)
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()
