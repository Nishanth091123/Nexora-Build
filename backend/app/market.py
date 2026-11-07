"""1.18 Material Library → estimate rates.

* Brand tiers: the owner tags each brand A / B / C. Where variants have rates, the average rate of the A brands
  becomes the Premium rate of the linked estimate item, B → Standard, C → Basic (converted to the item's unit).
* Project choices: a variant picked for a project (e.g. Ramco PPC for cement) sets that item's rate for every grade
  of that project's estimate.
Only items that HAVE owner-entered rates change; everything else keeps the Rate Library value.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from .market_seed import CAT

TIER_LEVEL = {"A": "premium", "B": "standard", "C": "basic"}


def link(v) -> tuple[str | None, float]:
    """(rate code, factor) for a variant: its own spec first, else its category."""
    c = CAT.get(v.category)
    spec = v.spec or {}
    code = spec["rate_code"] if "rate_code" in spec else (c[4] if c else None)
    factor = float(spec.get("factor") or (c[5] if c else 1.0) or 1.0)
    if "factor" not in spec and c and code and code != c[4]:
        factor = c[5]  # same unit family as the category
    return code, factor


def tier_rates(db: Session) -> dict[str, dict[str, dict]]:
    """{rate_code: {"premium": {"rate": x, "n": brands, "names": [...]}, ...}} from tagged brands with rates."""
    from .models import MarketBrand, MarketVariant
    brands = {b.id: b for b in db.query(MarketBrand).filter(MarketBrand.is_hidden.is_(False), MarketBrand.tier.in_(("A", "B", "C"))).all()}
    if not brands:
        return {}
    acc: dict[str, dict[str, list]] = {}
    for v in db.query(MarketVariant).filter(MarketVariant.is_hidden.is_(False), MarketVariant.rate.isnot(None),
                                            MarketVariant.brand_id.in_(list(brands))).all():
        code, f = link(v)
        if not code or not v.rate:
            continue
        b = brands[v.brand_id]
        acc.setdefault(code, {}).setdefault(TIER_LEVEL[b.tier], []).append((v.rate * f, b.name))
    out: dict[str, dict[str, dict]] = {}
    for code, lv in acc.items():
        out[code] = {}
        for level, vals in lv.items():
            out[code][level] = {"rate": round(sum(x for x, _ in vals) / len(vals), 2), "n": len(vals),
                                "names": sorted({n for _, n in vals})}
    return out


def project_choices(db: Session, project_id: int | None) -> dict[str, dict]:
    """{rate_code: {"rate": x, "label": "Ramco · PPC"}} from the variants picked for this project."""
    if not project_id:
        return {}
    from .models import MarketBrand, MarketVariant, Project
    p = db.get(Project, project_id)
    ch = (p.brand_choices or {}) if p else {}
    out = {}
    for _cat, vid in ch.items():
        v = db.get(MarketVariant, int(vid)) if vid else None
        if not v or v.is_hidden or not v.rate:
            continue
        code, f = link(v)
        if not code:
            continue
        b = db.get(MarketBrand, v.brand_id)
        out[code] = {"rate": round(v.rate * f, 2), "label": f"{b.name if b else ''} · {v.name}".strip(" ·"),
                     "variant_rate": v.rate, "unit": v.unit}
    return out


def apply_market(db: Session, rates: dict[str, dict], project_id: int | None = None) -> list[str]:
    """Change the rate dict in place; returns notes for the estimate's 'Assumptions & checks'."""
    notes: list[str] = []
    try:
        tiers = tier_rates(db)
        chosen = project_choices(db, project_id)
    except Exception:  # tables missing on a very old DB – rates stay as they are
        return notes
    for code, lv in tiers.items():
        r = rates.get(code)
        if not r or code in chosen:
            continue
        for level, info in lv.items():
            r[level] = info["rate"]
        bits = [f"{lvl.title()} = {', '.join(info['names'][:3])}{'…' if len(info['names']) > 3 else ''} (avg ₹{info['rate']:,.0f})"
                for lvl, info in sorted(lv.items(), key=lambda kv: ["basic", "standard", "premium"].index(kv[0]))]
        notes.append(f"{r['name']}: brand grades from Material Library – " + "; ".join(bits))
    for code, info in chosen.items():
        r = rates.get(code)
        if not r:
            continue
        r["basic"] = r["standard"] = r["premium"] = info["rate"]
        notes.append(f"{r['name']}: this project uses {info['label']} – ₹{info['variant_rate']:,.2f}/{info['unit']} (Material Library)")
    return notes
