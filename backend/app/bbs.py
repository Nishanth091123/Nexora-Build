"""Bar Bending Schedule (BBS) – cutting lengths, numbers and weights of bars for columns, beams, footings and slabs.

Sizes always come from the user (missing ones are asked, never assumed). Standard practice values are used only
where the user leaves them blank, and every one of them is listed under "assumptions":
  * bend deductions 45° = 1d, 90° = 2d, 135° = 3d (site practice / SP 34)
  * stirrup / tie hook: 135° with 10d (min 75 mm) extension (IS 13920)
  * column lap 50d, placed in the middle half of the floor height (IS 13920 cl. 6.2.6 / 7.2.1)
  * close tie spacing near joints over l0 = max(D, h/6, 450 mm) at min(b/4, 6·dmin, 100 mm) (IS 13920 cl. 8.1)
  * close stirrup spacing over 2d from beam supports at min(d/4, 8·dmin, 100 mm) (IS 13920 cl. 6.3.5)
  * unit weight d²/162 kg/m
Structural design (bar sizes / numbers) must come from the engineer's drawing – this only schedules it.
"""
from __future__ import annotations

import math

BAR_12M = 12000


class BBSMissing(ValueError):
    def __init__(self, questions: list[str]):
        super().__init__("; ".join(questions))
        self.questions = questions


def kg_per_m(d: float) -> float:
    return d * d / 162.0


def _num(m: dict, key: str, label: str, miss: list, positive=True):
    v = m.get(key)
    if v in (None, ""):
        miss.append(label)
        return 0.0
    try:
        v = float(v)
    except (TypeError, ValueError):
        miss.append(f"{label} (must be a number)")
        return 0.0
    if positive and v <= 0:
        miss.append(f"{label} (must be more than 0)")
    return v


def _bars(m: dict, key: str, label: str, miss: list, required=True) -> list[tuple[float, int]]:
    out = []
    for b in m.get(key) or []:
        try:
            d, n = float(b.get("dia") or 0), int(float(b.get("nos") or 0))
        except (TypeError, ValueError):
            continue
        if d > 0 and n > 0:
            out.append((d, n))
    if required and not out:
        miss.append(label)
    return out


def _hook(d: float) -> float:
    return max(10 * d, 75)


def _tie_length(b: float, D: float, cover: float, d: float) -> tuple[float, float, float]:
    """Closed rectangular tie / stirrup with two 135° hooks. Returns (cut length, a, b) – a, b = centre-line sides."""
    a = b - 2 * cover
    bb = D - 2 * cover
    cl = 2 * (a + bb) + 2 * _hook(d) - 3 * 2 * d - 2 * 3 * d
    return cl, a, bb


def _row(member, mark, desc, shape, dims, d, per_member, count, cl):
    nos = per_member * count
    total_m = nos * cl / 1000
    return {"member": member, "mark": mark, "desc": desc, "shape": shape, "dims": {k: round(v) for k, v in dims.items()},
            "dia": d, "per_member": per_member, "members": count, "nos": nos, "cut_mm": round(cl),
            "total_m": round(total_m, 2), "kg": round(total_m * kg_per_m(d), 2)}


# ------------------------------------------------------------------ members
def column(m: dict) -> dict:
    miss = []
    name = m.get("mark") or "C"
    count = int(_num(m, "count", f"{name}: number of such columns", miss))
    b = _num(m, "b", f"{name}: column width b (mm)", miss)
    D = _num(m, "d", f"{name}: column depth D (mm)", miss)
    h = _num(m, "height", f"{name}: floor-to-floor height (mm)", miss)
    floors = int(_num(m, "floors", f"{name}: number of floors (lifts)", miss))
    cover = _num(m, "cover", f"{name}: clear cover (mm)", miss)
    mains = _bars(m, "main", f"{name}: main bars (dia + nos)", miss)
    td = _num(m, "tie_dia", f"{name}: tie diameter (mm)", miss)
    ts = _num(m, "tie_spacing", f"{name}: tie spacing (mm)", miss)
    fd = _num(m, "footing_depth", f"{name}: footing depth (mm) – bars go into the footing", miss)
    fb = _num(m, "bottom_bend", f"{name}: L-bend at the bottom of the bars in the footing (mm)", miss)
    if miss:
        raise BBSMissing(miss)
    ass = []
    lapf = float(m.get("lap_factor") or 50)
    if not m.get("lap_factor"):
        ass.append(f"{name}: lap = 50 × bar diameter, in the middle half of each floor height (IS 13920)")
    dmin = min(d for d, _ in mains)
    es = float(m.get("tie_end_spacing") or min(b / 4, 6 * dmin, 100))
    if not m.get("tie_end_spacing"):
        ass.append(f"{name}: ties at {es:g} mm near beams / footing (IS 13920 confining zone), {ts:g} mm in the middle")
    l0 = max(D, b, h / 6, 450)
    rows = []
    for d, n in mains:
        lap = lapf * d
        if floors == 1:
            cl = fd - 50 + fb + h - cover - 2 * d
            rows.append(_row(name, f"{name}-M{int(d)}", f"Main bar {int(d)} mm (footing + full height)", "L",
                             {"a": fb, "b": cl - fb + 2 * d}, d, n, count, cl))
        else:
            cl1 = fd - 50 + fb + h + lap - 2 * d
            rows.append(_row(name, f"{name}-M{int(d)}a", f"Main bar {int(d)} mm – footing + floor 1 + lap", "L",
                             {"a": fb, "b": cl1 - fb + 2 * d}, d, n, count, cl1))
            if floors > 2:
                clm = h + lap
                rows.append(_row(name, f"{name}-M{int(d)}b", f"Main bar {int(d)} mm – middle floors (each) + lap", "straight",
                                 {"a": clm}, d, n * (floors - 2), count, clm))
            clt = h - cover
            rows.append(_row(name, f"{name}-M{int(d)}c", f"Main bar {int(d)} mm – top floor", "straight", {"a": clt}, d, n, count, clt))
    tcl, ta, tb = _tie_length(b, D, cover, td)
    per_floor = 2 * math.ceil(l0 / es) + max(0, math.ceil((h - 2 * l0) / ts)) + 1
    ties = per_floor * floors + math.ceil((fd - 100) / ts)  # a few ties inside the footing
    rows.append(_row(name, f"{name}-T", f"Ties {int(td)} mm, 135° hooks", "stirrup", {"a": ta, "b": tb, "hook": _hook(td)},
                     td, ties, count, tcl))
    return {"rows": rows, "assumptions": ass,
            "drawing": {"type": "column", "b": b, "d": D, "h": h, "floors": floors, "cover": cover,
                        "mains": [{"dia": d, "nos": n} for d, n in mains], "lap_mm": round(lapf * max(d for d, _ in mains)),
                        "l0": round(l0), "end_spacing": es, "spacing": ts, "tie_dia": td, "footing_depth": fd, "bottom_bend": fb}}


def beam(m: dict) -> dict:
    miss = []
    name = m.get("mark") or "B"
    count = int(_num(m, "count", f"{name}: number of such beams", miss))
    L = _num(m, "span", f"{name}: clear span (mm)", miss)
    sup = _num(m, "support", f"{name}: support (column) width (mm)", miss)
    b = _num(m, "b", f"{name}: beam width b (mm)", miss)
    D = _num(m, "d", f"{name}: beam depth D (mm)", miss)
    cover = _num(m, "cover", f"{name}: clear cover (mm)", miss)
    bot = _bars(m, "bottom", f"{name}: bottom bars (dia + nos)", miss)
    top = _bars(m, "top", f"{name}: top bars (dia + nos)", miss)
    sd = _num(m, "stirrup_dia", f"{name}: stirrup diameter (mm)", miss)
    ss = _num(m, "stirrup_spacing", f"{name}: stirrup spacing (mm)", miss)
    if miss:
        raise BBSMissing(miss)
    ass = [f"{name}: bars go into the supports with a 90° bend of 12 × diameter (check development length on the drawing)"]
    dmin = min(d for d, _ in bot + top)
    deff = D - cover - sd - dmin / 2
    es = float(m.get("stirrup_end_spacing") or min(deff / 4, 8 * dmin, 100))
    if not m.get("stirrup_end_spacing"):
        ass.append(f"{name}: stirrups at {es:.0f} mm for 2d from each support (IS 13920), {ss:g} mm in the middle")
    rows = []
    for tag, group in (("B", bot), ("T", top)):
        for d, n in group:
            leg = 12 * d
            cl = L + 2 * (sup - cover) + 2 * leg - 2 * 2 * d
            rows.append(_row(name, f"{name}-{tag}{int(d)}", f"{'Bottom' if tag == 'B' else 'Top'} bar {int(d)} mm", "U",
                             {"a": leg, "b": L + 2 * (sup - cover), "c": leg}, d, n, count, cl))
    scl, sa, sb = _tie_length(b, D, cover, sd)
    zone = 2 * deff
    nos = 2 * math.ceil(zone / es) + max(0, math.ceil((L - 2 * zone) / ss)) + 1
    rows.append(_row(name, f"{name}-S", f"Stirrups {int(sd)} mm, 135° hooks", "stirrup", {"a": sa, "b": sb, "hook": _hook(sd)},
                     sd, nos, count, scl))
    return {"rows": rows, "assumptions": ass,
            "drawing": {"type": "beam", "span": L, "support": sup, "b": b, "d": D, "cover": cover,
                        "bottom": [{"dia": d, "nos": n} for d, n in bot], "top": [{"dia": d, "nos": n} for d, n in top],
                        "zone": round(zone), "end_spacing": round(es), "spacing": ss, "stirrup_dia": sd}}


def footing(m: dict) -> dict:
    miss = []
    name = m.get("mark") or "F"
    count = int(_num(m, "count", f"{name}: number of such footings", miss))
    L = _num(m, "length", f"{name}: footing length L (mm)", miss)
    B = _num(m, "width", f"{name}: footing width B (mm)", miss)
    D = _num(m, "depth", f"{name}: footing depth (mm)", miss)
    cover = _num(m, "cover", f"{name}: clear cover (mm)", miss)
    dl = _num(m, "dia_l", f"{name}: bar diameter along length (mm)", miss)
    sl = _num(m, "spacing_l", f"{name}: bar spacing along length (mm)", miss)
    db = _num(m, "dia_b", f"{name}: bar diameter along width (mm)", miss)
    sb = _num(m, "spacing_b", f"{name}: bar spacing along width (mm)", miss)
    up = _num(m, "bend_up", f"{name}: end bend-up length (mm)", miss)
    if miss:
        raise BBSMissing(miss)
    rows = []
    nl = math.floor((B - 2 * cover) / sl) + 1
    cll = L - 2 * cover + 2 * up - 2 * 2 * dl
    rows.append(_row(name, f"{name}-L", f"Bottom mesh along length {int(dl)} mm @ {sl:g}", "U",
                     {"a": up, "b": L - 2 * cover, "c": up}, dl, nl, count, cll))
    nb = math.floor((L - 2 * cover) / sb) + 1
    clb = B - 2 * cover + 2 * up - 2 * 2 * db
    rows.append(_row(name, f"{name}-B", f"Bottom mesh along width {int(db)} mm @ {sb:g}", "U",
                     {"a": up, "b": B - 2 * cover, "c": up}, db, nb, count, clb))
    return {"rows": rows, "assumptions": [],
            "drawing": {"type": "footing", "length": L, "width": B, "depth": D, "cover": cover, "dia_l": dl, "spacing_l": sl,
                        "dia_b": db, "spacing_b": sb, "nl": nl, "nb": nb, "bend_up": up}}


def slab(m: dict) -> dict:
    miss = []
    name = m.get("mark") or "S"
    count = int(_num(m, "count", f"{name}: number of such slab panels", miss))
    lx = _num(m, "lx", f"{name}: short span Lx (clear, mm)", miss)
    ly = _num(m, "ly", f"{name}: long span Ly (clear, mm)", miss)
    t = _num(m, "thickness", f"{name}: slab thickness (mm)", miss)
    cover = _num(m, "cover", f"{name}: clear cover (mm)", miss)
    sup = _num(m, "support", f"{name}: support (beam) width (mm)", miss)
    dm = _num(m, "main_dia", f"{name}: main bar diameter (mm)", miss)
    sm = _num(m, "main_spacing", f"{name}: main bar spacing (mm)", miss)
    dd = _num(m, "dist_dia", f"{name}: distribution bar diameter (mm)", miss)
    sd = _num(m, "dist_spacing", f"{name}: distribution bar spacing (mm)", miss)
    if miss:
        raise BBSMissing(miss)
    ass = [f"{name}: straight bars running into the supports; add cranked / extra top bars at supports as per the drawing"]
    nm = math.floor((ly - 2 * cover) / sm) + 1
    clm = lx + 2 * (sup - cover)
    nd = math.floor((lx - 2 * cover) / sd) + 1
    cld = ly + 2 * (sup - cover)
    rows = [_row(name, f"{name}-M", f"Main bars {int(dm)} mm @ {sm:g} (short span)", "straight", {"a": clm}, dm, nm, count, clm),
            _row(name, f"{name}-D", f"Distribution {int(dd)} mm @ {sd:g} (long span)", "straight", {"a": cld}, dd, nd, count, cld)]
    return {"rows": rows, "assumptions": ass,
            "drawing": {"type": "slab", "lx": lx, "ly": ly, "thickness": t, "main_dia": dm, "main_spacing": sm,
                        "dist_dia": dd, "dist_spacing": sd, "nm": nm, "nd": nd}}


KINDS = {"column": column, "beam": beam, "footing": footing, "slab": slab}


def schedule(members: list[dict], wastage_pct: float = 3.0) -> dict:
    if not members:
        raise BBSMissing(["Add at least one member (column, beam, footing or slab)"])
    rows, ass, draws, miss = [], [], [], []
    for m in members:
        kind = m.get("type")
        if kind not in KINDS:
            miss.append(f"Unknown member type '{kind}'")
            continue
        try:
            r = KINDS[kind](m)
        except BBSMissing as e:
            miss.extend(e.questions)
            continue
        rows.extend(r["rows"])
        ass.extend(r["assumptions"])
        draws.append({"mark": m.get("mark") or kind, **r["drawing"]})
    if miss:
        raise BBSMissing(miss)
    by = {}
    for r in rows:
        x = by.setdefault(r["dia"], {"dia": r["dia"], "total_m": 0.0, "kg": 0.0})
        x["total_m"] += r["total_m"]
        x["kg"] += r["kg"]
    summary = []
    for d in sorted(by):
        x = by[d]
        need = x["total_m"] * (1 + wastage_pct / 100)
        summary.append({"dia": d, "kg_per_m": round(kg_per_m(d), 3), "total_m": round(x["total_m"], 1),
                        "kg": round(x["kg"], 1), "kg_with_wastage": round(x["kg"] * (1 + wastage_pct / 100), 1),
                        "bars_12m": math.ceil(need / 12)})
    total = sum(s["kg_with_wastage"] for s in summary)
    ass = list(dict.fromkeys(ass)) + [
        "Bend deductions: 45° = 1d, 90° = 2d, 135° = 3d; hooks 10d (min 75 mm); weight = d²/162 kg/m",
        f"{wastage_pct:g}% cutting wastage added in the order quantity (not in the cutting lengths)",
        "Bar sizes and numbers must come from the structural drawing – this schedule only measures them"]
    return {"rows": rows, "summary": summary, "total_kg": round(total, 1), "wastage_pct": wastage_pct,
            "assumptions": ass, "drawings": draws}
