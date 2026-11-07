"""1.16 – Estimate downloads for every tab + Part estimate (choose floor and work).

Everything here is a different *view* of the same calculation result (engine.calculate). Nothing is guessed:
quantities, rates and amounts come straight from the result items. The only approximations are labelled as such
(steel diameter split and mixing water) and are shown with that label in the file.
"""
from __future__ import annotations

import io
import json
import math
import re
from datetime import datetime

from .exports import NAVY, inr

# ---------------------------------------------------------------- work types for the Part estimate
WORKS: dict[str, str] = {
    "all": "All works", "excavation": "Excavation & earthwork", "foundation": "Foundation & PCC",
    "columns": "Columns", "beams": "Beams, lintels & bands", "slab": "Roof slab & sunshades",
    "staircase": "Staircase", "brickwork": "Brickwork / blockwork", "plastering": "Plastering",
    "flooring": "Flooring, tiling & waterproofing", "painting": "Painting", "doors_windows": "Doors & Windows",
    "plumbing": "Plumbing & Sanitary", "electrical": "Electrical", "roofing": "Roofing sheet (sheet + truss)",
    "external": "External works",
    "other": "Other / additional items",
}
WORK_SHORT = {"all": "", "excavation": "Excavation", "foundation": "Foundation", "columns": "Columns",
              "beams": "Beams", "slab": "Slab", "staircase": "Staircase", "brickwork": "Brickwork",
              "plastering": "Plastering", "flooring": "Flooring", "painting": "Painting",
              "doors_windows": "Doors_Windows", "plumbing": "Plumbing", "electrical": "Electrical", "roofing": "Roofing_Sheet",
              "external": "External_Works", "other": "Other_Items"}
STRUCT = ("RCC", "Steel", "Formwork")


def _d(i: dict) -> str:
    return i["description"].lower()


def work_of(i: dict) -> str:
    cat, d = i["category"], _d(i)
    if cat == "Roofing Sheet" or "roof steel" in d:  # 1.17
        return "roofing"
    if cat == "Earthwork":
        return "excavation"
    if "staircase railing" in d or "staircase treads" in d:  # 1.18
        return "staircase"
    if cat == "Concrete (PCC)" or (i["floor"] in ("Foundation", "Plinth") and cat in STRUCT + ("Masonry",)):
        return "foundation"
    if cat in STRUCT:
        if "staircase" in d:
            return "staircase"
        if "column" in d:
            return "columns"
        if "slab" in d or "sunshade" in d:
            return "slab"
        return "beams"
    return {"Masonry": "brickwork", "Plastering": "plastering", "Flooring & Tiling": "flooring",
            "Waterproofing": "flooring", "Painting": "painting", "Doors & Windows": "doors_windows",
            "Plumbing & Sanitary": "plumbing", "Electrical": "electrical", "External Works": "external"}.get(cat, "other")


def floor_options(result: dict) -> list[str]:
    seen: list[str] = []
    for i in result.get("items", []):
        if i["floor"] not in seen:
            seen.append(i["floor"])
    order = ["Foundation", "Plinth"]
    tail = ["Terrace", "External", "Additional", "Site"]
    mid = [f for f in seen if f not in order + tail]
    return [f for f in order if f in seen] + mid + [f for f in tail if f in seen]


# Typical share of steel by diameter for each element (approximate – the exact split comes from the BBS tab)
DIA_SPLIT = {"footing": {12: 0.7, 10: 0.3}, "column": {16: 0.55, 12: 0.2, 8: 0.25},
             "beam": {16: 0.45, 12: 0.3, 8: 0.25}, "slab": {10: 0.6, 8: 0.4}, "stair": {12: 0.6, 10: 0.2, 8: 0.2}}


def _element(d: str) -> str:
    if "footing" in d:
        return "footing"
    if "column" in d:
        return "column"
    if "slab" in d or "sunshade" in d:
        return "slab"
    if "stair" in d:
        return "stair"
    return "beam"


def _agg(items: list[dict], key: str, qty: str) -> list[dict]:
    out: dict[str, dict] = {}
    for it in items:
        for x in it.get(key, []):
            o = out.setdefault(x["code"], {"code": x["code"], "name": x["name"], "unit": x.get("unit", "man-days"),
                                           "qty": 0.0, "rate": x["rate"], "amount": 0.0})
            o["qty"] += x[qty]
            o["amount"] += x["amount"]
    for o in out.values():
        o["qty"], o["amount"] = round(o["qty"], 2), round(o["amount"], 2)
    return sorted(out.values(), key=lambda o: -o["amount"])


def part_estimate(result: dict, floor: str = "all", work: str = "all") -> dict:
    if work not in WORKS:
        raise ValueError(f"work must be one of {', '.join(WORKS)}")
    floors = floor_options(result)
    if floor != "all" and floor not in floors:
        raise ValueError(f"floor must be 'all' or one of {', '.join(floors)}")
    items = [i for i in result.get("items", [])
             if (floor == "all" or i["floor"] == floor) and (work == "all" or work_of(i) == work)]
    mats = _agg(items, "materials", "qty")
    labour = _agg(items, "labour", "days")
    for l in labour:
        l["unit"] = "man-days"
    eqp = _agg(items, "equipment", "qty")
    m = round(sum(i["material_cost"] for i in items), 2)
    lab = round(sum(i["labour_cost"] for i in items), 2)
    e = round(sum(i["equipment_cost"] for i in items), 2)

    def mq(code):
        return sum(x["qty"] for x in mats if x["code"] == code)

    steel_dia: dict[int, float] = {}
    for i in items:
        if i["category"] != "Steel":
            continue
        kg = sum(x["qty"] for x in i.get("materials", []) if x["code"] == "steel") or i["qty"]
        for dia, sh in DIA_SPLIT[_element(_d(i))].items():
            steel_dia[dia] = steel_dia.get(dia, 0) + kg * sh
    cement = mq("cement")
    key = [
        {"name": "Cement", "qty": math.ceil(cement), "unit": "bags (50 kg)"},
        {"name": "Steel (TMT) total", "qty": round(mq("steel")), "unit": "kg"},
        *({"name": f"  Steel {dia} mm (approx. split)", "qty": round(kg), "unit": "kg"}
          for dia, kg in sorted(steel_dia.items(), reverse=True)),
        {"name": "M-sand", "qty": round(mq("msand"), 2), "unit": "m³"},
        {"name": "P-sand (plastering)", "qty": round(mq("psand"), 2), "unit": "m³"},
        {"name": "Aggregate 20 mm", "qty": round(mq("agg20"), 2), "unit": "m³"},
        {"name": "Aggregate 40 mm", "qty": round(mq("agg40"), 2), "unit": "m³"},
        {"name": "Bricks", "qty": math.ceil(mq("brick")), "unit": "nos"},
        {"name": "Mixing water (approx. w/c 0.5, curing extra)", "qty": round(cement * 25), "unit": "litres"},
        {"name": "Roofing sheet (incl. laps)", "qty": round(sum(x["qty"] for x in mats if x["code"].startswith("sheet_") and x["code"] != "sheet_ridge"), 2), "unit": "m²"},
        {"name": "MS truss / purlin steel", "qty": round(mq("ms_struct")), "unit": "kg"},
    ]
    key = [k for k in key if k["qty"]]
    return {"floor": floor, "work": work, "floor_label": "All floors" if floor == "all" else floor,
            "work_label": WORKS[work], "floors": floors, "works": WORKS,
            "file_label": WORK_SHORT[work],
            "items": [{k: i[k] for k in ("sl", "category", "description", "floor", "qty", "unit", "rate", "amount",
                                         "material_cost", "labour_cost", "equipment_cost")} for i in items],
            "materials": mats, "labour": labour, "equipment": eqp, "key_materials": key,
            "totals": {"materials": m, "labour": lab, "equipment": e, "total": round(m + lab + e, 2),
                       "items": len(items)},
            "note": "Direct cost of the chosen part (materials + labour + equipment, with wastage). Transport, "
                    "contingency, contractor margin and GST are added only in the full estimate."}


# ---------------------------------------------------------------- tab → tables
TAB_TITLE = {"overview": "Overview", "floorboq": "Floor-wise BOQ", "takeoff": "Quantity Takeoff",
             "material": "Material Estimate", "cost": "Cost Analysis", "boq": "BOQ", "payment": "Payment Schedule",
             "compare": "Spec Comparison", "part": "Part Estimate"}


def _f(v, nd=2):
    return f"{v:,.{nd}f}".rstrip("0").rstrip(".") if isinstance(v, (int, float)) else str(v)


def sections_for(tab: str, r: dict, extra: dict | None = None) -> list[dict]:
    """Each section: {title, headers, rows, money (column indexes from the right side that are rupees)}."""
    t = r.get("totals", {})
    S = []
    if tab == "overview":
        S.append({"title": "Cost summary", "headers": ["Cost head", "Amount (Rs.)"], "money": [1],
                  "rows": [["Materials", t.get("materials")], ["Labour", t.get("labour")],
                           ["Equipment", t.get("equipment")], ["Extras (transport, contingency, margin, GST, fees)",
                                                               t.get("extras")], ["GRAND TOTAL", t.get("grand_total")]]})
        S.append({"title": "Key figures", "headers": ["Item", "Value"], "money": [],
                  "rows": [["Built-up area", f"{_f(t.get('builtup_sqft', 0), 0)} sq ft"],
                           ["Cost per sq ft", f"Rs. {inr(t.get('cost_per_sqft', 0))}"],
                           ["Cement", f"{t.get('cement_bags', 0)} bags"], ["Steel", f"{t.get('steel_kg', 0)} kg"],
                           ["Bricks", f"{t.get('bricks', 0)} nos"], ["M-sand", f"{t.get('msand_m3', 0)} m³"],
                           ["Aggregate", f"{t.get('aggregate_m3', 0)} m³"],
                           ["Duration", f"{t.get('duration_months', 0)} months (approx.)"]]})
        S.append({"title": "Floor-wise cost", "headers": ["Floor", "Material", "Labour", "Equipment", "Total"],
                  "money": [1, 2, 3, 4], "rows": [[f["floor"], f["material_cost"], f["labour_cost"],
                                                   f["equipment_cost"], f["total"]] for f in r.get("floors", [])]})
        S.append({"title": "Breakdown", "headers": ["Group", "Amount (Rs.)", "%"], "money": [1],
                  "rows": [[b["group"], b["amount"], b["pct"]] for b in r.get("breakdown", [])]})
    elif tab == "floorboq":
        fb = r.get("floor_boq") or {"columns": [], "rows": []}
        cols = fb["columns"]
        S.append({"title": "Floor-wise BOQ", "headers": ["Description", "Unit", *cols, "Total qty", "Rate", "Amount"],
                  "money": [len(cols) + 3, len(cols) + 4],
                  "rows": [[x["description"], x["unit"], *[x["qty"].get(c, "") for c in cols], x["total_qty"],
                            x["rate"], x["amount"]] for x in fb["rows"]]})
        if r.get("area_statement"):
            S.append({"title": "Area statement", "headers": ["Floor", "Built-up sq ft", "Carpet sq ft", "Common sq ft",
                                                             "Remarks"], "money": [],
                      "rows": [[a["floor"], a["builtup_sqft"], a["carpet_sqft"], a["common_sqft"], a["remarks"]]
                               for a in r["area_statement"]]})
    elif tab == "takeoff":
        S.append({"title": "Quantity takeoff", "headers": ["#", "Category", "Description", "Floor", "Qty", "Unit"],
                  "money": [], "rows": [[i["sl"], i["category"], i["description"], i["floor"], i["qty"], i["unit"]]
                                        for i in r.get("items", [])]})
        if r.get("key_quantities"):
            S.append({"title": "Key quantities", "headers": ["Item", "Qty", "Unit"], "money": [],
                      "rows": [[k["name"], k["qty"], k["unit"]] for k in r["key_quantities"]]})
    elif tab == "material":
        S.append({"title": "Material estimate", "headers": ["Material", "Qty", "Unit", "Rate", "Amount"],
                  "money": [3, 4], "rows": [[m["name"], m["qty"], m["unit"], m["rate"], m["amount"]]
                                            for m in r.get("materials", [])]})
    elif tab == "cost":
        S.append({"title": "Labour", "headers": ["Trade", "Man-days", "Rate", "Amount"], "money": [2, 3],
                  "rows": [[l["name"], l["qty"], l["rate"], l["amount"]] for l in r.get("labour", [])]})
        S.append({"title": "Equipment", "headers": ["Equipment", "Qty", "Unit", "Rate", "Amount"], "money": [3, 4],
                  "rows": [[e["name"], e["qty"], e["unit"], e["rate"], e["amount"]] for e in r.get("equipment", [])]})
        S.append({"title": "Extras", "headers": ["Item", "Basis", "Amount"], "money": [2],
                  "rows": [[e["name"], e["basis"], e["amount"]] for e in r.get("extras", [])]})
    elif tab == "boq":
        S.append({"title": "Bill of quantities", "headers": ["#", "Description", "Floor", "Qty", "Unit", "Rate",
                                                             "Material", "Labour", "Amount"], "money": [5, 6, 7, 8],
                  "rows": [[i["sl"], i["description"], i["floor"], i["qty"], i["unit"], i["rate"], i["material_cost"],
                            i["labour_cost"], i["amount"]] for i in r.get("items", [])]})
        S[-1]["rows"].append(["", "TOTAL (before extras)", "", "", "", "", t.get("materials"), t.get("labour"),
                              round((t.get("materials") or 0) + (t.get("labour") or 0) + (t.get("equipment") or 0), 2)])
    elif tab == "payment":
        S.append({"title": "Payment schedule", "headers": ["#", "Stage", "%", "Amount (Rs.)"], "money": [3],
                  "rows": [[n + 1, s["stage"], s["pct"], s.get("amount", 0)]
                           for n, s in enumerate(r.get("payment_schedule", []))]})
    elif tab == "compare":
        cmp = (extra or {}).get("compare") or {}
        lv = [k for k in ("basic", "standard", "premium") if k in cmp]
        heads = [("Materials", "materials"), ("Labour", "labour"), ("Equipment", "equipment"), ("Extras", "extras"),
                 ("Grand total", "grand_total"), ("Cost per sq ft", "cost_per_sqft")]
        S.append({"title": "Spec level comparison", "headers": ["Cost head", *[x.title() for x in lv]],
                  "money": list(range(1, len(lv) + 1)),
                  "rows": [[h, *[cmp[x]["totals"][k] for x in lv]] for h, k in heads]})
    elif tab == "part":
        p = extra or {}
        tt = p["totals"]
        S.append({"title": f"{p['work_label']} – {p['floor_label']}", "headers": ["#", "Description", "Floor", "Qty",
                                                                                 "Unit", "Rate", "Amount"],
                  "money": [5, 6], "rows": [[i["sl"], i["description"], i["floor"], i["qty"], i["unit"], i["rate"],
                                             i["amount"]] for i in p["items"]]})
        S.append({"title": "Materials needed", "headers": ["Material", "Qty", "Unit"], "money": [],
                  "rows": [[k["name"], k["qty"], k["unit"]] for k in p["key_materials"]]})
        S.append({"title": "All materials (with wastage)", "headers": ["Material", "Qty", "Unit", "Rate", "Amount"],
                  "money": [3, 4], "rows": [[m["name"], m["qty"], m["unit"], m["rate"], m["amount"]]
                                            for m in p["materials"]]})
        S.append({"title": "Labour", "headers": ["Trade", "Man-days", "Rate", "Amount"], "money": [2, 3],
                  "rows": [[l["name"], l["qty"], l["rate"], l["amount"]] for l in p["labour"]]})
        if p["equipment"]:
            S.append({"title": "Equipment", "headers": ["Equipment", "Qty", "Unit", "Rate", "Amount"], "money": [3, 4],
                      "rows": [[e["name"], e["qty"], e["unit"], e["rate"], e["amount"]] for e in p["equipment"]]})
        S.append({"title": "Total", "headers": ["Cost head", "Amount (Rs.)"], "money": [1],
                  "rows": [["Materials", tt["materials"]], ["Labour", tt["labour"]], ["Equipment", tt["equipment"]],
                           ["TOTAL (direct cost)", tt["total"]]], "note": p["note"]})
    else:
        raise ValueError(f"tab must be one of {', '.join(TAB_TITLE)}")
    return [s for s in S if s["rows"]]


# ---------------------------------------------------------------- file names + renderers
def file_stem(code: str, name: str, *parts: str) -> str:
    def clean(x: str) -> str:
        return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9-]+", "_", x or "")).strip("_-")
    return "_".join(p for p in [clean(code), clean(name), *[clean(x) for x in parts]] if p)


def _safe(text) -> str:
    s = "" if text is None else str(text)
    for k, v in {"²": "2", "³": "3", "≈": "~", "₹": "Rs.", "≤": "<=", "≥": ">=", "–": "-", "×": "x", "→": "->"}.items():
        s = s.replace(k, v)
    return s


def _cell(v, money: bool):
    if money and isinstance(v, (int, float)):
        return inr(v)
    if isinstance(v, float):
        return _f(v)
    return _safe(v)


def render_pdf(project: dict, title: str, subtitle: str, sections: list[dict]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title=_safe(title))
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=colors.HexColor("#" + NAVY), alignment=0, fontSize=16)
    h2 = ParagraphStyle("h2", parent=ss["Heading3"], textColor=colors.HexColor("#" + NAVY))
    small = ParagraphStyle("small", parent=ss["BodyText"], fontSize=8, leading=10)
    cellst = ParagraphStyle("cell", parent=ss["BodyText"], fontSize=7.5, leading=9)
    co = project.get("company") or {}
    story = [Paragraph(_safe(f"{co.get('name') or 'Nexora Build'} – {title}"), h1),
             Paragraph(_safe(" · ".join(x for x in [f"{project.get('code', '')} {project.get('name', '')}",
                                                    project.get("client_name") and f"Client: {project['client_name']}",
                                                    subtitle, datetime.now().strftime("%d %b %Y")] if x)), small),
             Spacer(1, 6)]
    width = landscape(A4)[0] - 24 * mm
    for s in sections:
        story.append(Paragraph(_safe(s["title"]), h2))
        n = len(s["headers"])
        desc_col = next((k for k, h in enumerate(s["headers"]) if h in ("Description", "Stage", "Material", "Trade",
                                                                       "Cost head", "Item", "Group", "Floor",
                                                                       "Equipment")), 0)
        rest = (width * 0.55) / max(1, n - 1) if n > 1 else width
        widths = [width - rest * (n - 1) if k == desc_col else rest for k in range(n)]
        data = [[Paragraph(f"<b>{_safe(h)}</b>", ParagraphStyle("hh", parent=cellst, textColor=colors.white))
                 for h in s["headers"]]]
        for row in s["rows"]:
            data.append([Paragraph(_cell(v, k in s["money"]), cellst) for k, v in enumerate(row)])
        tb = Table(data, colWidths=widths, repeatRows=1)
        tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + NAVY)),
                                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D9DEE8")),
                                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FC")]),
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        story += [tb, Spacer(1, 4)]
        if s.get("note"):
            story.append(Paragraph(_safe(s["note"]), small))
        story.append(Spacer(1, 6))
    story.append(Paragraph("Quantities from the Nexora Build estimate engine. Rates as per the rate library at the "
                           "time of download. Structural sizes must be confirmed by a qualified engineer.", small))
    doc.build(story)
    return buf.getvalue()


def render_excel(project: dict, title: str, subtitle: str, sections: list[dict]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = re.sub(r"[^A-Za-z0-9 ]", "", title)[:30] or "Estimate"
    ws.append([f"{(project.get('company') or {}).get('name') or 'Nexora Build'} – {title}"])
    ws["A1"].font = Font(bold=True, size=14, color=NAVY)
    ws.append([f"{project.get('code', '')} {project.get('name', '')}", subtitle,
               datetime.now().strftime("%d %b %Y")])
    for s in sections:
        ws.append([])
        ws.append([s["title"]])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, color=NAVY)
        ws.append(s["headers"])
        for c in ws[ws.max_row]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor=NAVY)
        for row in s["rows"]:
            ws.append([v if isinstance(v, (int, float)) or v is None else str(v) for v in row])
            for k in s["money"]:
                ws.cell(row=ws.max_row, column=k + 1).number_format = '#,##,##0'
        if s.get("note"):
            ws.append([s["note"]])
    for col, w in zip("ABCDEFGHIJKL", (8, 48, 14, 12, 12, 12, 14, 14, 14, 14, 14, 14)):
        ws.column_dimensions[col].width = w
    ws.column_dimensions["A"].width = 30
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def dumps(x) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)
