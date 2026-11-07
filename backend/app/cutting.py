"""1.19 Steel cutting optimiser – from a BBS, plan how to cut 12 m stock bars with the least waste.

Per bar diameter: first-fit-decreasing bin packing of every cut piece into 12 m bars (saw / shear kerf allowed),
then off-cuts of a useful length are listed for re-use (chairs, extra pieces). Compared with cutting each bar mark
from its own fresh bars (what usually happens on site), the saving is shown in bars, kg and – only when the steel
rate is set in the rate library – in ₹."""
from __future__ import annotations

import math

from .bbs import kg_per_m


def _split_long(cut: int, stock: int, dia: float) -> tuple[list[int], int]:
    """A piece longer than the stock bar is made of full bars + a remainder, each joint lapped 50 d."""
    lap = int(round(50 * dia))
    pieces, rest, joints = [], cut, 0
    while rest > stock:
        pieces.append(stock)
        rest = rest - stock + lap
        joints += 1
    pieces.append(rest)
    return pieces, joints


def optimise(rows: list[dict], stock_mm: int = 12000, kerf_mm: int = 5, reuse_min_mm: int = 1000,
             steel_rate: float | None = None) -> dict:
    by: dict[float, list[tuple[int, str]]] = {}
    laps = []
    for r in rows:
        d = float(r["dia"])
        cut = int(r["cut_mm"])
        n = int(r["nos"])
        if cut <= 0 or n <= 0:
            continue
        if cut > stock_mm:
            parts, joints = _split_long(cut, stock_mm, d)
            laps.append(f"{r.get('mark') or r.get('member')}: {cut} mm > {stock_mm} mm – made of {len(parts)} pieces with "
                        f"{joints} lap(s) of {int(50 * d)} mm (50 d); stagger the laps.")
        else:
            parts = [cut]
        for p in parts:
            by.setdefault(d, []).extend([(p, str(r.get("mark") or r.get("member") or ""))] * n)
    out = []
    tot_naive = tot_opt = 0.0
    for d in sorted(by):
        pieces = sorted(by[d], key=lambda t: -t[0])
        bars: list[dict] = []
        for ln, mark in pieces:
            for b in bars:  # first fit (pieces are longest first)
                if b["left"] >= ln + (kerf_mm if b["cuts"] else 0):
                    b["left"] -= ln + (kerf_mm if b["cuts"] else 0)
                    b["cuts"].append((ln, mark))
                    break
            else:
                bars.append({"left": stock_mm - ln, "cuts": [(ln, mark)]})
        # naive: every mark cut from its own bars
        naive = 0
        marks: dict[str, list[int]] = {}
        for ln, mark in pieces:
            marks.setdefault(mark, []).append(ln)
        for lst in marks.values():
            per = max(1, stock_mm // (lst[0] + kerf_mm)) if lst[0] + kerf_mm <= stock_mm else 1
            naive += math.ceil(len(lst) / per)
        kgm = kg_per_m(d)
        used_m = sum(ln for ln, _ in pieces) / 1000
        opt_kg = len(bars) * stock_mm / 1000 * kgm
        naive_kg = naive * stock_mm / 1000 * kgm
        waste = sum(b["left"] for b in bars)
        reuse = sorted([b["left"] for b in bars if b["left"] >= reuse_min_mm], reverse=True)
        # cutting patterns: identical bars grouped
        pats: dict[tuple, int] = {}
        for b in bars:
            key = tuple(sorted(((ln, mk) for ln, mk in b["cuts"]), key=lambda t: -t[0]))
            pats[key] = pats.get(key, 0) + 1
        def txt(k):
            grp: dict[tuple, int] = {}
            for c in k:
                grp[c] = grp.get(c, 0) + 1
            return " + ".join(f"{m} × {ln} mm ({mk})" if m > 1 else f"{ln} mm ({mk})" for (ln, mk), m in grp.items())
        patterns = [{"bars": n, "cuts": [{"mm": ln, "mark": mk} for ln, mk in k], "text": txt(k),
                     "offcut_mm": stock_mm - sum(ln for ln, _ in k) - kerf_mm * (len(k) - 1)}
                    for k, n in sorted(pats.items(), key=lambda kv: -kv[1])]
        out.append({"dia": d, "pieces": len(pieces), "bars_needed": len(bars), "bars_naive": naive,
                    "steel_used_kg": round(used_m * kgm, 1), "bars_kg": round(opt_kg, 1), "naive_kg": round(naive_kg, 1),
                    "waste_kg": round(waste / 1000 * kgm, 1), "waste_pct": round(100 * waste / (len(bars) * stock_mm), 1) if bars else 0,
                    "reusable_offcuts_mm": reuse[:30], "patterns": patterns})
        tot_naive += naive_kg
        tot_opt += opt_kg
    saved = max(0.0, tot_naive - tot_opt)
    return {"stock_mm": stock_mm, "kerf_mm": kerf_mm, "by_dia": out, "laps": laps,
            "total_bars": sum(x["bars_needed"] for x in out), "total_bars_naive": sum(x["bars_naive"] for x in out),
            "total_kg": round(tot_opt, 1), "naive_kg": round(tot_naive, 1), "saved_kg": round(saved, 1),
            "steel_rate": steel_rate, "saved_rs": round(saved * steel_rate) if steel_rate else None,
            "notes": ["Cut the longest pieces first; mark each bundle with the bar mark.",
                      f"Off-cuts of {reuse_min_mm} mm and more are listed for re-use (chairs, extra bars, stirrup hangers).",
                      "Order quantity = bars needed per diameter (12 m bars). Weight = d²/162 kg/m."]}


def pdf(res: dict, project: dict, title: str) -> bytes:
    from .site.pdfdoc import Doc
    d = Doc("Steel Cutting Plan (12 m bars)", project, f"From BBS: {title}")
    d.table(["Dia", "Pieces", "Bars (optimised)", "Bars (mark by mark)", "Order kg", "Waste", "Saved kg"],
            [[f"{x['dia']:g} mm", x["pieces"], x["bars_needed"], x["bars_naive"], x["bars_kg"], f"{x['waste_kg']} kg ({x['waste_pct']}%)",
              round(x["naive_kg"] - x["bars_kg"], 1)] for x in res["by_dia"]] +
            [["Total", "", res["total_bars"], res["total_bars_naive"], res["total_kg"], "", res["saved_kg"]]],
            [10, 10, 14, 16, 12, 18, 12], bold_last=True)
    if res.get("saved_rs") is not None:
        d.para(f"Saving ≈ {res['saved_kg']:,.0f} kg × ₹{res['steel_rate']:,.0f}/kg = ₹{res['saved_rs']:,.0f} (rate from your rate library).")
    for x in res["by_dia"]:
        d.h(f"{x['dia']:g} mm bars – cutting patterns", 3)
        d.table(["No. of bars", "Cut each bar into", "Off-cut"],
                [[p["bars"], p["text"], f"{p['offcut_mm']} mm"] for p in x["patterns"]],
                [12, 70, 18])
        if x["reusable_offcuts_mm"]:
            d.para("Re-usable off-cuts: " + ", ".join(f"{v} mm" for v in x["reusable_offcuts_mm"]), True)
    if res["laps"]:
        d.h("Bars longer than 12 m")
        d.bullets(res["laps"])
    d.h("Notes")
    d.bullets(res["notes"], True)
    return d.build()
