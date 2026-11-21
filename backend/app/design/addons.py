"""1.27.9 – optional drawing add-ons for the approval set (each one is a switch, off by default):

  * Key plan / location plan  – plan["keyplan"]      all data typed by the owner (landmarks, roads, distances, survey no.)
  * Column position + footing layout + design calculation – plan["column_addon"]  uses the existing structural engine; the
    soil bearing capacity and the seismic zone are NEVER assumed – they must be typed in, otherwise the sheet says what is missing.

Nothing here invents data: the key plan only draws what was entered and says "not to scale"."""
from __future__ import annotations

import math

COMPASS = {"N": (0.0, 1.0), "NE": (0.7071, 0.7071), "E": (1.0, 0.0), "SE": (0.7071, -0.7071),
           "S": (0.0, -1.0), "SW": (-0.7071, -0.7071), "W": (-1.0, 0.0), "NW": (-0.7071, 0.7071)}
FT = 0.3048


def _s(v, n=60) -> str:
    return str(v or "").strip()[:n]


def _num(v, lo, hi):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return round(max(lo, min(hi, x)), 2) if x == x else None


def clean_keyplan(raw) -> dict | None:
    if not isinstance(raw, dict) or not raw.get("on"):
        return None
    out = {"on": True}
    for k in ("place", "taluk", "district", "survey_no", "plot_no", "ward", "road_name"):
        out[k] = _s(raw.get(k))
    roads, marks = [], []
    for r in (raw.get("roads") or [])[:6]:
        if isinstance(r, dict) and _s(r.get("name")) and r.get("dir") in COMPASS:
            roads.append({"name": _s(r["name"]), "dir": r["dir"]})
    for m in (raw.get("landmarks") or [])[:12]:
        if isinstance(m, dict) and _s(m.get("name")) and m.get("dir") in COMPASS:
            marks.append({"name": _s(m["name"]), "dir": m["dir"], "dist_m": _num(m.get("dist_m"), 0, 20000)})
    out["roads"], out["landmarks"] = roads, marks
    return out


def clean_column(raw) -> dict | None:
    if not isinstance(raw, dict) or not raw.get("on"):
        return None
    out = {"on": True}
    for k, lo, hi in (("sbc_kn_m2", 40, 600), ("foundation_depth_m", 0.9, 4)):
        v = _num(raw.get(k), lo, hi)
        if v is not None:
            out[k] = v
    z = str(raw.get("seismic_zone") or "").upper().replace("ZONE", "").strip()
    if z in ("II", "III", "IV", "V"):
        out["seismic_zone"] = z
    for k, ok in (("fck", (20, 25, 30)), ("fy", (415, 500, 550))):
        try:
            if int(raw.get(k)) in ok:
                out[k] = int(raw[k])
        except (TypeError, ValueError):
            pass
    return out


# ------------------------------------------------------------------ key plan drawing
def _to_xy(plan: dict, de: float, dn: float) -> tuple[float, float]:
    """compass vector (east, north) → drawing x (to the right) / y (up) for this plan's orientation."""
    up, right = plan["compass"]["up"], plan["compass"]["right"]
    return de * right[0] + dn * right[1], de * up[0] + dn * up[1]


def key_plan(plan: dict):
    from .sheets import Dwg, _north
    kp = plan.get("keyplan") or {}
    d = Dwg("Key Plan")
    plot = plan["plot"]
    W0, D0 = float(plot["w"]), float(plot["d"])
    k = 22.0 / max(W0, D0)
    W, D = W0 * k, D0 * k
    cx, cy = W / 2, D / 2
    d.rect(0, 0, W, D, "PLOT", "#fef9c3")
    d.text(cx, cy + 0.5, "SITE", 1.2, bold=True, layer="ROOMTEXT")
    d.text(cx, cy - 1.0, f"{W0:g}' x {D0:g}'", 0.8, layer="ROOMTEXT")
    if kp.get("survey_no"):
        d.text(cx, cy - 2.3, f"S.No. {kp['survey_no']}", 0.7, layer="ROOMTEXT")
    # the road on the road side of the plot (front = bottom of the sheet)
    d.rect(-6, -9, W + 12, 5, "ROAD", "#e2e8f0")
    d.line(-6, -6.5, W + 6, -6.5, "CENTRE")
    road_w = (plan.get("requirements") or {}).get("road_width_m") or (plan.get("setbacks") or {}).get("road_width_m")
    d.text(cx, -8.3, ((kp.get("road_name") or "ROAD") + (f"  ({road_w:g} m wide)" if isinstance(road_w, (int, float)) else "")).upper()[:60], 0.8, bold=True)
    # other roads the owner entered (a strip on that side)
    for r in kp.get("roads", []):
        de, dn = COMPASS[r["dir"]]
        vx, vy = _to_xy(plan, de, dn)
        if abs(vy + 1) < 0.01 and abs(vx) < 0.01:      # same side as the front road – it is already drawn
            continue
        R = (max(W, D) / 2) + 11
        px, py = cx + vx * R, cy + vy * R
        ex, ey = -vy, vx
        d.line(px - ex * 17, py - ey * 17, px + ex * 17, py + ey * 17, "CENTRE")
        d.line(px - ex * 17 + vx * 1.2, py - ey * 17 + vy * 1.2, px + ex * 17 + vx * 1.2, py + ey * 17 + vy * 1.2, "ROAD")
        d.line(px - ex * 17 - vx * 1.2, py - ey * 17 - vy * 1.2, px + ex * 17 - vx * 1.2, py + ey * 17 - vy * 1.2, "ROAD")
        d.text(px + vx * 2.6, py + vy * 2.6 - 0.3, r["name"].upper()[:30], 0.7, bold=True)
    # landmarks: direction as entered, distance as entered in the label (placing is only schematic)
    for i, m in enumerate(kp.get("landmarks", [])):
        de, dn = COMPASS[m["dir"]]
        vx, vy = _to_xy(plan, de, dn)
        dist = m.get("dist_m")
        R = (max(W, D) / 2) + 16 + (min(dist, 1000.0) / 1000.0 * 10 if dist is not None else 4)
        # fan out landmarks that share a direction so their labels do not overlap
        same = sum(1 for q in kp["landmarks"][:i] if q["dir"] == m["dir"])
        px, py = cx + vx * R + (-vy) * same * 4.5, cy + vy * R + vx * same * 4.5
        d.arc(px, py, 0.7, 0, 360, "MARK")
        d.line(cx + vx * (max(W, D) / 2 + 2), cy + vy * (max(W, D) / 2 + 2), px, py, "HATCH")
        lab = m["name"].upper()[:28] + (f" – {m['dist_m']:g} m" if dist is not None else "")
        d.text(px, py + 1.2, lab, 0.65, layer="ROOMTEXT", bold=True)
    lx = cx + 48                                           # particulars: a column at the right, clear of the roads / landmarks
    _north(d, plan, lx + 6, D + 6)
    lines = [("Place / village", kp.get("place")), ("Taluk", kp.get("taluk")), ("District", kp.get("district")),
             ("Survey no.", kp.get("survey_no")), ("Plot no.", kp.get("plot_no")), ("Ward / block", kp.get("ward"))]
    d.text(lx, D - 2.5, "LOCATION", 0.8, anchor="start", bold=True)
    for i, (a_, b_) in enumerate(lines):
        d.text(lx, D - 4.5 - i * 1.7, f"{a_}: {b_ if b_ else '____________'}", 0.7, anchor="start", layer="ROOMTEXT")
    d.text(cx, cy - 46, "KEY PLAN / LOCATION PLAN  (not to scale - directions and distances as entered)", 0.8, bold=True)
    return d


# ------------------------------------------------------------------ column + footing add-on
def column_result(plan: dict):
    """(structural result or None, questions). Soil SBC + seismic zone must be typed by the owner – never assumed."""
    ca = plan.get("column_addon")
    if not ca or not ca.get("on"):
        return None, []
    from ..structural import engine
    try:
        return engine.design(plan, {k: v for k, v in ca.items() if k != "on"}), []
    except engine.NeedInfo as e:
        return None, list(e.questions)
    except Exception as e:   # never break the whole drawing set because of an add-on
        return None, [f"Column & footing sheet could not be designed for this plan: {e}"]


def column_dwgs(res: dict, plan: dict):
    from ..structural import sheets as ss
    return ss.column_layout(res, plan), ss.foundation_plan(res, plan)


def calc_lines(res: dict) -> list[dict]:
    """Worked column and footing checks, one per mark (first member of each mark), same formulas as the structural engine."""
    from ..structural.engine import BAR_AREA, ast_req, tau_c
    inp = res["inputs"]
    fck, fy, sbc = inp["fck"], inp["fy"], inp["sbc_kn_m2"]
    rows = []
    seen = set()
    for c, f in zip(res["columns"], res["footings"]):
        if f["mark"] in seen:
            continue
        seen.add(f["mark"])
        P = c["P_kn"]
        Pf = P * 1.1
        B = f["B_m"]
        area_req = Pf / sbc
        qu = 1.5 * P / (B * B)
        a, bc = c["b_mm"] / 1000, c["D_mm"] / 1000
        d = max(0.2, (f["D_mm"] - 56) / 1000)
        b0 = 2 * ((a + d) + (bc + d))
        tp = qu * (B * B - (a + d) * (bc + d)) / (b0 * d) / 1000
        cant = (B - min(a, bc)) / 2
        t1 = qu * B * max(0.0, cant - d) / (B * d) / 1000
        mu = qu * B * cant * cant / 2
        ast_r = max(ast_req(mu, B * 1000, d * 1000, fck, fy), 0.0012 * B * 1000 * (d * 1000 + 60)) / B
        ast_p = 1000 * BAR_AREA[f["dia"]] / f["s"]
        ag, asc = c["b_mm"] * c["D_mm"], c["nb"] * BAR_AREA[c["db"]]
        cap = (0.4 * fck * (ag - asc) + 0.67 * fy * asc) / 1000
        rows.append({
            "col": c["mark"], "foot": f["mark"], "size": f"{c['b_mm']} x {c['D_mm']} mm", "P": round(P, 1), "Pu": c["Pu_kn"],
            "Pcap": round(cap, 1), "bars": c["bars"], "ties": c["ties"],
            "Pf": round(Pf, 1), "A_req": round(area_req, 2), "B": B, "pressure": round(Pf / (B * B), 1),
            "qu": round(qu, 1), "d_mm": round(d * 1000), "tp": round(tp, 2), "tp_all": round(0.25 * math.sqrt(fck), 2),
            "t1": round(t1, 2), "t1_all": round(tau_c(0.25, fck), 2), "mu": round(mu, 1),
            "ast_r": round(ast_r), "ast_p": round(ast_p), "steel": f["steel"], "D": f["D_mm"],
            "ok": bool(cap >= c["Pu_kn"] and Pf / (B * B) <= sbc + 1e-6 and ast_p + 1e-6 >= ast_r),
        })
    return rows
