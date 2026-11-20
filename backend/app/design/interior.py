"""1.26 – Interior design package from the saved plan: room-wise woodwork / ceiling items, quantities, editable rates.

Rates are SUGGESTED DEFAULT RATES taken from public Tamil Nadu (Chennai / Coimbatore) price pages checked in Nov 2026 –
a typical (default) value with the low and high seen. The owner edits every rate; items with no searched rate (loose
furniture, curtains, pooja unit …) are listed with a quantity and a blank rate – the app never guesses them.
"""
from __future__ import annotations

import io

CHECKED = "Nov 2026"
# key: (label, unit, low, default, high, source note)
RATES: dict[str, tuple] = {
    "kitchen_cabinet": ("Modular kitchen cabinets (base + wall, laminate)", "sq ft of cabinet face", 1200, 1800, 2500,
                        "Chennai laminate Rs.1,650-2,400; other TN pages Rs.1,200-2,500 per sq ft"),
    "wardrobe": ("Wardrobe (modular, floor to ceiling)", "sq ft", 1050, 1200, 1800,
                 "Coimbatore / Chennai sellers Rs.1,050-1,800 per sq ft"),
    "tv_unit": ("TV unit with back panel", "sq ft", 400, 700, 1000,
                "Cost guides Rs.400-800; TN sellers up to Rs.1,000-1,150 per sq ft"),
    "ceiling_gypsum": ("Gypsum false ceiling (flat, material + labour)", "sq ft", 75, 90, 120,
                       "Chennai gypsum Rs.75-110; guides Rs.75-120 per sq ft, lights extra"),
    "ceiling_cove": ("Cove / peripheral false ceiling", "sq ft", 110, 135, 160, "Chennai cove / peripheral Rs.110-160 per sq ft"),
    "fluted_panel": ("Fluted / reeded TV-wall panel (HDHMR + PU)", "sq ft", 450, 650, 900, "Chennai 2026 guide Rs.450-900 per sq ft"),
    "study_table": ("Study table (fabricated)", "unit", 8000, 12000, 18000, "Cost guide Rs.8,000-18,000 per unit"),
}
# optional items are OFF until the owner switches them on
OPTIONAL = {"ceiling_cove", "fluted_panel", "study_table"}
LOOSE = [  # no searched rate – quantity only, the owner types the rate
    ("Cot / bed with mattress", "bedroom", 1), ("Sofa set", "hall", 1), ("Dining table with chairs", "dining", 1),
    ("Pooja unit", "pooja", 1), ("Curtains + rods (per window)", "bedroom", 1), ("Shoe rack (foyer)", "hall", 1),
]


def _floor_of(r: dict, lv: dict) -> str:
    return lv["name"]


def compute(plan: dict, saved: dict | None = None) -> dict:
    """Items per room with quantities; saved = {"rates": {key: v}, "qty": {"roomid|key": v}, "off": [keys], "on": [keys],
    "loose_rates": {name: v}}."""
    saved = saved or {}
    rates = {}
    for k, (label, unit, lo, de, hi, src) in RATES.items():
        v = (saved.get("rates") or {}).get(k)
        rates[k] = {"key": k, "label": label, "unit": unit, "low": lo, "default": de, "high": hi, "source": src,
                    "rate": float(v) if v not in (None, "") else float(de), "edited": v not in (None, ""),
                    "on": (k in (saved.get("on") or [])) if k in OPTIONAL else (k not in (saved.get("off") or []))}
    items = []
    qty_over = saved.get("qty") or {}

    from . import catalog as CAT
    picks = saved.get("picks") or {}
    picked = []
    cur = {"li": 0}      # room ids repeat between floors (bedroom_1 on both) - so keys carry the floor number

    def add(lv, room, key, qty, note):
        rt = rates[key]
        if not rt["on"]:
            return
        uid = f"{cur['li']}:{room['id']}"
        dz = CAT.interior_get(picks.get(f"{uid}|{next((t for t, k in CAT.PRICE_KEY.items() if k == key), '')}", ""))
        rate, name = rt["rate"], ""
        if dz:   # a chosen design sets the layout quantity and, unless you edited the rate, the price tier
            qty, extra = CAT.qty_for(dz, qty, room)
            note = extra or note
            if not rt["edited"]:
                rate = float((rt["low"], rt["default"], rt["high"])[CAT.TIER[dz["tier"]]])
            name = dz["name"]
        q = qty_over.get(f"{uid}|{key}", qty_over.get(f"{room['id']}|{key}") if cur["li"] == 0 else None)
        q = float(q) if q not in (None, "") else round(qty, 1)
        items.append({"id": f"{uid}|{key}", "floor": lv["name"], "room": room["name"], "key": key, "item": rt["label"],
                      "unit": rt["unit"], "qty": q, "auto_qty": round(qty, 1), "rate": rate, "amount": round(q * rate),
                      "note": note, "design": name, "design_id": dz["id"] if dz else "", "tier": dz["tier"] if dz else ""})

    for li_, lv in enumerate(plan["levels"]):
        cur["li"] = li_
        for r in lv["rooms"]:
            t = r["type"]
            if t == "kitchen":
                run = max(6.0, r["w"] + r["d"] - 3.5)
                add(lv, r, "kitchen_cabinet", run * 4.5, f"{run:g} ft running x 4.5 ft (base 2.5 + wall 2.0)")
            elif t == "bedroom":
                has_dress = any(x.get("parent") == r["id"] and x["type"] == "dress" for x in lv["rooms"])
                master = "master" in r["name"].lower() or has_dress
                wd = min(8.0 if master else 6.0, max(4.0, max(r["w"], r["d"]) - 3.5))
                add(lv, r, "wardrobe", wd * 7, f"{wd:g} ft wide x 7 ft high" + (" (in the dress area if drawn)" if has_dress else ""))
                if master or r["w"] * r["d"] >= 110:
                    add(lv, r, "ceiling_gypsum", r["w"] * r["d"], f"room area {r['w'] * r['d']:.0f} sq ft")
                add(lv, r, "study_table", 1, "one table")
            elif t in ("hall", "lounge"):
                wd = min(8.0, max(4.0, min(r["w"], r["d"]) - 3.0))
                add(lv, r, "tv_unit", wd * 6, f"{wd:g} ft wide x 6 ft high")
                add(lv, r, "fluted_panel", wd * 7, f"TV wall {wd:g} ft x 7 ft")
                if rates["ceiling_cove"]["on"]:   # cove ceiling REPLACES the flat one in the same room (never both)
                    add(lv, r, "ceiling_cove", r["w"] * r["d"], f"room area {r['w'] * r['d']:.0f} sq ft")
                else:
                    add(lv, r, "ceiling_gypsum", r["w"] * r["d"], f"room area {r['w'] * r['d']:.0f} sq ft")
            elif t == "dining":
                add(lv, r, "ceiling_gypsum", r["w"] * r["d"], f"room area {r['w'] * r['d']:.0f} sq ft")
    rooms_by_id = {f"{li_}:{r['id']}": (lv["name"], r) for li_, lv in enumerate(plan["levels"]) for r in lv["rooms"]}
    for k, did in picks.items():
        rid, _, t = k.partition("|")
        dz, rr = CAT.interior_get(did), rooms_by_id.get(rid)
        if dz and rr:
            picked.append({"key": k, "room_id": rid, "floor": rr[0], "room": rr[1]["name"], "type": t, "type_label": CAT.TYPES.get(t, t),
                           "design_id": did, "name": dz["name"], "tier": dz["tier"], "priced": t in CAT.PRICE_KEY})
    loose = []
    types = {r["type"] for lv in plan["levels"] for r in lv["rooms"]}
    n_bed = sum(1 for lv in plan["levels"] for r in lv["rooms"] if r["type"] == "bedroom")
    lr = saved.get("loose_rates") or {}
    for name, rtype, q in LOOSE:
        if rtype not in types:
            continue
        qty = q * (n_bed if rtype == "bedroom" else 1)
        rate = lr.get(name)
        loose.append({"item": name, "qty": qty, "rate": float(rate) if rate not in (None, "") else None,
                      "amount": round(qty * float(rate)) if rate not in (None, "") else None})
    searched = sum(i["amount"] for i in items)
    loose_total = sum(x["amount"] or 0 for x in loose)
    floors = {}
    for i in items:
        floors[i["floor"]] = floors.get(i["floor"], 0) + i["amount"]
    return {"picked": picked, "items": items, "loose": loose, "rates": list(rates.values()), "totals": {
        "searched_items": searched, "loose_entered": loose_total, "grand": searched + loose_total, "by_floor": floors,
        "gst_note": "Rates are GST-inclusive where the source says so; confirm with the vendor quote."},
        "checked": CHECKED,
        "notes": ["Suggested default rates from public TN price pages (Chennai / Coimbatore), checked " + CHECKED +
                  ". Edit any rate or quantity; the vendor's written quote is final.",
                  "Interior painting and flooring are already in the construction estimate – not repeated here.",
                  "Items with a blank rate (loose furniture, pooja unit, curtains) were not priced – type your rate.",
                  "Electrical points, light fittings and plumbing fixtures are in the Electrical / Plumbing drawings."]}


def to_pdf(plan: dict, project: dict, res: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from .. import letterhead as lh
    from ..estimate.exports import inr

    def S(t):
        for k, v in {"₹": "Rs.", "–": "-", "×": "x", "²": "2", "·": "-"}.items():
            t = str(t).replace(k, v)
        return t
    ss = getSampleStyleSheet()
    navy = colors.HexColor("#1E3A8A")
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=navy, fontSize=15, spaceAfter=3)
    h2 = ParagraphStyle("h2", parent=ss["Heading3"], textColor=navy, spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=8.5, leading=11)
    cell = ParagraphStyle("c", parent=ss["BodyText"], fontSize=7.8, leading=9.5)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=18 * mm,
                            title="Interior estimate")
    PW, PH = A4

    def tb(data, widths, right=None, bold_last=False):
        t = Table(data, colWidths=widths, repeatRows=1)
        st = [("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
              ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C9D2E3")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FC")])]
        if right is not None:
            st.append(("ALIGN", (right, 1), (-1, -1), "RIGHT"))
        if bold_last:
            st += [("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8EEFB"))]
        t.setStyle(TableStyle(st))
        return t
    story = [Spacer(1, lh.header_height(PW) + 18 + 4 - 14 * mm),
             Paragraph("INTERIOR ESTIMATE - SUGGESTED PACKAGE", h1),
             Paragraph(S(f"{project.get('name', '')} ({project.get('code', '')}) - {plan.get('facing', '').title()} facing - "
                         f"rates: suggested defaults, checked {res['checked']}, editable"), body), Spacer(1, 6)]
    rows = [["Floor / room", "Item", "Qty", "Unit", "Rate", "Amount (Rs.)"]]
    for i in res["items"]:
        rows.append([Paragraph(S(f"{i['floor']} - {i['room']}"), cell), Paragraph(S(i["item"]), cell), f"{i['qty']:g}",
                     Paragraph(S(i["unit"]), cell), inr(i["rate"]), inr(i["amount"])])
    rows.append(["", "TOTAL (priced items)", "", "", "", inr(res["totals"]["searched_items"])])
    story.append(tb(rows, [44 * mm, 52 * mm, 14 * mm, 22 * mm, 20 * mm, 28 * mm], 4, True))
    if res["loose"]:
        story.append(Paragraph("Loose furniture and extras (rate not searched - type your rate)", h2))
        lr = [["Item", "Qty", "Rate (Rs.)", "Amount (Rs.)"]]
        for x in res["loose"]:
            lr.append([S(x["item"]), f"{x['qty']:g}", inr(x["rate"]) if x["rate"] else "________", inr(x["amount"]) if x["amount"] else "________"])
        story.append(tb(lr, [90 * mm, 20 * mm, 35 * mm, 35 * mm], 1))
    story.append(Paragraph("Rates used (suggested default rate, low - high seen)", h2))
    rr = [["Item", "Unit", "Rate used", "Low - High", "Where from"]]
    for r in res["rates"]:
        if r["on"]:
            rr.append([Paragraph(S(r["label"]), cell), Paragraph(S(r["unit"]), cell), inr(r["rate"]) + (" (edited)" if r["edited"] else ""),
                       f"{inr(r['low'])} - {inr(r['high'])}", Paragraph(S(r["source"]), cell)])
    story.append(tb(rr, [48 * mm, 24 * mm, 24 * mm, 26 * mm, 58 * mm]))
    story.append(Paragraph("Notes", h2))
    for n in res["notes"]:
        story.append(Paragraph(S("- " + n), body))
    if not res.get("picked"):
        story += [Spacer(1, 10), lh.SealSignature(180 * mm)]
    if res.get("picked"):
        from reportlab.platypus import Flowable, PageBreak
        from . import catalog as CAT

        class Pic(Flowable):
            def __init__(self, scene, w, h):
                super().__init__()
                self.scene, self.w, self.h = scene, w, h

            def wrap(self, aw, ah):
                return self.w, self.h

            def draw(self):
                self.scene.pdf(self.canv, 0, 0, self.w, self.h)
        story += [PageBreak(), Paragraph("SELECTED DESIGNS", h1),
                  Paragraph(S("Pictures drawn by Nexora for the design you chose in each room. Final shop-drawing, finish and colour are confirmed with the vendor."), body),
                  Spacer(1, 6)]
        seen = set()
        for pk in res["picked"]:
            if pk["design_id"] in seen:
                continue
            seen.add(pk["design_id"])
            rooms_ = ", ".join(f"{x['floor']} - {x['room']}" for x in res["picked"] if x["design_id"] == pk["design_id"])
            dz = CAT.interior_get(pk["design_id"])
            story += [Paragraph(S(f"{pk['type_label']}: {pk['name']}"), h2), Paragraph(S(f"Rooms: {rooms_}. Price tier: {pk['tier']}" +
                      ("" if pk["priced"] else " (not priced - no searched rate)")), body), Spacer(1, 3), Pic(CAT.draw_interior(dz), 110 * mm, 62 * mm), Spacer(1, 6)]
        story += [Spacer(1, 6), lh.SealSignature(180 * mm)]
    doc.build(story, onFirstPage=lh.on_first(PW, PH), onLaterPages=lh.on_later(PW))
    return buf.getvalue()


def to_excel(plan: dict, project: dict, res: dict) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Interior"
    ws.append(["Floor", "Room", "Item", "Qty", "Unit", "Rate", "Amount", "Basis"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for r, i in enumerate(res["items"], 2):
        ws.append([i["floor"], i["room"], i["item"], i["qty"], i["unit"], i["rate"], None, i["note"]])
        ws.cell(r, 7).value = f"=D{r}*F{r}"          # live formula: change qty / rate and the amount follows
    n = len(res["items"]) + 2
    ws.append(["", "", "TOTAL", "", "", "", f"=SUM(G2:G{n - 1})"])
    ws.cell(n, 3).font = Font(bold=True)
    ws2 = wb.create_sheet("Loose furniture")
    ws2.append(["Item", "Qty", "Rate (type yours)", "Amount"])
    for r, x in enumerate(res["loose"], 2):
        ws2.append([x["item"], x["qty"], x["rate"], f"=B{r}*C{r}"])
    ws3 = wb.create_sheet("Rates")
    ws3.append(["Item", "Unit", "Rate used", "Low", "High", "Source (checked " + res["checked"] + ")"])
    for r in res["rates"]:
        ws3.append([r["label"], r["unit"], r["rate"], r["low"], r["high"], r["source"]])
    for w in (ws, ws2, ws3):
        for col, wd in zip("ABCDEFGH", (16, 22, 44, 9, 18, 12, 14, 40)):
            w.column_dimensions[col].width = wd
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
