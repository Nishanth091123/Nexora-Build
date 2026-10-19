"""Phase 5 – site & project-management logic (pure Python, no database).

Schedule template, planned vs actual progress, project health, default quality checklist, insights.
"""
from __future__ import annotations

from datetime import date, timedelta

# (name, group, relative duration, weight = share of cost/effort)
BASE_STAGES = [
    ("Site Preparation & Marking", "foundation", 3, 1),
    ("Excavation & Foundation", "foundation", 10, 8),
    ("Plinth Beam & Filling", "foundation", 6, 4),
]
PER_FLOOR = [("Columns", "structure", 7, 6), ("Beams & Slab", "structure", 12, 10)]
AFTER = [
    ("Brick Work", "masonry", 18, 9),
    ("Electrical & Plumbing Conduits", "services", 10, 6),
    ("Plastering", "finishing", 15, 8),
    ("Flooring & Tiling", "finishing", 12, 9),
    ("Doors, Windows & Grills", "finishing", 8, 6),
    ("Painting", "finishing", 12, 6),
    ("Electrical & Sanitary Fittings", "services", 7, 5),
    ("External Works (sump, septic, compound)", "finishing", 8, 4),
    ("Cleaning & Handover", "handover", 3, 1),
]
FLOOR_NAMES = ["Ground Floor", "First Floor", "Second Floor", "Third Floor", "Fourth Floor", "Fifth Floor"]
PIPELINE = [("Foundation", ("foundation",)), ("Columns", ("structure:Columns",)), ("Slab", ("structure:Beams",)),
            ("Finishing", ("masonry", "services", "finishing")), ("Handover", ("handover",))]


def levels_of(floors: str) -> tuple[int, bool]:
    f = (floors or "G").upper().replace(" ", "")
    stilt = f.startswith("S")
    n = 1
    if "+" in f:
        try:
            n = int(f.split("+", 1)[1]) + 1
        except ValueError:
            n = 1
    return n, stilt


def schedule_template(floors: str, start: date | None, end: date | None) -> list[dict]:
    n, stilt = levels_of(floors)
    stages = list(BASE_STAGES)
    for i in range(n):
        lvl = ("Stilt" if stilt and i == 0 else FLOOR_NAMES[i - (1 if stilt else 0)] if i - (1 if stilt else 0) < 6 else f"Level {i}")
        for nm, grp, dur, w in PER_FLOOR:
            stages.append((f"{nm} – {lvl}", grp, dur, w))
    stages += AFTER
    start = start or date.today()
    total = sum(s[2] for s in stages)
    span = (end - start).days if end and end > start else int(total * 1.6)
    k = span / total
    for _ in range(4):
        out = _lay(stages, start, k)
        got = (out[-1]["end_date"] - start).days + 1
        if abs(got - span) <= 1:
            break
        k *= span / max(1, got)
    if end and out and out[-1]["end_date"] != end:
        out[-1]["end_date"] = max(out[-1]["start_date"], end)
    return out


def _lay(stages, start, k):
    out, cur = [], start
    for i, (nm, grp, dur, w) in enumerate(stages):
        d = max(1, round(dur * k))
        s0 = cur
        e0 = s0 + timedelta(days=d - 1)
        out.append({"name": nm, "stage_group": grp, "start_date": s0, "end_date": e0, "weight": w, "sort": i,
                    "is_milestone": nm.startswith("Beams & Slab") or nm.startswith("Cleaning") or nm.startswith("Plinth")})
        if grp == "masonry":  # brick work starts with the services; finishing trades overlap a little
            cur = s0 + timedelta(days=round(d * 0.5))
        elif grp in ("finishing", "services"):
            cur = e0 + timedelta(days=1) - timedelta(days=round(d * 0.15))
        else:
            cur = e0 + timedelta(days=1)
    return out


def overall(stages: list[dict]) -> float:
    tw = sum(float(s.get("weight") or 0) for s in stages)
    if not tw:
        return 0.0
    return round(sum(float(s.get("weight") or 0) * float(s.get("progress") or 0) for s in stages) / tw, 1)


def planned(stages: list[dict], on: date) -> float:
    tw = sum(float(s.get("weight") or 0) for s in stages)
    if not tw:
        return 0.0
    tot = 0.0
    for s in stages:
        a, b = s.get("start_date"), s.get("end_date")
        if not a or not b:
            continue
        if on < a:
            f = 0.0
        elif on >= b:
            f = 1.0
        else:
            f = ((on - a).days + 1) / ((b - a).days + 1)
        tot += float(s.get("weight") or 0) * f * 100
    return round(tot / tw, 1)


def schedule_variance_days(stages: list[dict], on: date) -> int:
    """+ = ahead, − = behind. Compares actual progress with the plan curve."""
    act = overall(stages)
    if not stages:
        return 0
    lo = min((s["start_date"] for s in stages if s.get("start_date")), default=on)
    hi = max((s["end_date"] for s in stages if s.get("end_date")), default=on)
    if act >= 100:
        return max(0, (hi - on).days)
    # day when the plan reaches the actual progress
    d = lo
    while d <= hi and planned(stages, d) < act:
        d += timedelta(days=1)
    return (d - on).days


def health(stages: list[dict], on: date) -> str:
    return "delayed" if schedule_variance_days(stages, on) < -3 else "on_track"


def pipeline(stages: list[dict]) -> list[dict]:
    out = []
    for label, keys in PIPELINE:
        sel = []
        for s in stages:
            for k in keys:
                g, _, nm = k.partition(":")
                if s.get("stage_group") == g and (not nm or s["name"].startswith(nm)):
                    sel.append(s)
                    break
        if not sel:
            continue
        p = overall(sel) if any(x.get("weight") for x in sel) else 0
        status = "completed" if p >= 100 else "in_progress" if p > 0 else "pending"
        out.append({"label": label, "progress": p, "status": status})
    return out


def group_progress(stages: list[dict]) -> list[dict]:
    names = [("foundation", "Foundation"), ("structure", "Structure"), ("masonry", "Masonry"),
             ("services", "Electrical & Plumbing"), ("finishing", "Finishing"), ("handover", "Handover")]
    out = []
    for g, label in names:
        sel = [s for s in stages if s.get("stage_group") == g]
        if sel:
            out.append({"group": g, "label": label, "progress": overall(sel)})
    return out


QC_TEMPLATE = [
    ("foundation", "Excavation depth & size as per drawing", "Depth ±25 mm, size not less than drawing"),
    ("foundation", "PCC level & thickness", "1:4:8, 100–150 mm, level checked"),
    ("foundation", "Footing reinforcement (dia, spacing, cover)", "Spacing ±10 mm, cover 50 mm"),
    ("structure", "RCC column alignment & plumb", "Plumb within 5 mm per 3 m; centre lines checked"),
    ("structure", "Steel reinforcement – bar size, laps, stirrups", "As per bar bending schedule; lap 50d; hooks 135°"),
    ("structure", "Concrete grade & slump", "M20 minimum; slump 75–100 mm; cubes taken"),
    ("structure", "Cover blocks & shuttering", "Cover: slab 20, beam 25, column 40 mm; props firm"),
    ("structure", "Curing of RCC", "Minimum 7 days (OPC) / 10 days (PPC)"),
    ("masonry", "Brick work quality – line, level, joints", "Joints ≤10 mm, bricks soaked, plumb checked"),
    ("masonry", "Mortar mix", "CM 1:6 (walls), 1:4 (half-brick)"),
    ("finishing", "Plaster thickness & finish", "Internal 12 mm, external 18–20 mm, ceiling 6 mm"),
    ("finishing", "Floor & tile level / slope in toilets", "Toilet slope 1:100 towards drain"),
    ("finishing", "Waterproofing test (toilets & terrace)", "48-hour water ponding test"),
    ("services", "Electrical conduits & earthing", "Earth resistance < 5 Ω"),
    ("services", "Plumbing pressure test", "No leakage at test pressure for 1 hour"),
]


def insights(stages: list[dict], on: date, cement_used: float, cement_planned: float, qc_pending: int,
             qc_failed: int, open_issues: int, open_safety: int) -> list[dict]:
    out = []
    if stages:
        v = schedule_variance_days(stages, on)
        if v > 0:
            out.append({"kind": "good", "text": f"Project is {v} day{'s' if v != 1 else ''} ahead of schedule."})
        elif v < 0:
            out.append({"kind": "risk", "text": f"Project is {-v} day{'s' if v != -1 else ''} behind schedule – check manpower / materials."})
        else:
            out.append({"kind": "good", "text": "Project is on schedule."})
        nxt = sorted([s for s in stages if float(s.get("progress") or 0) < 100 and s.get("start_date")],
                     key=lambda s: s["start_date"])
        if nxt:
            s = nxt[0]
            out.append({"kind": "info", "text": f"Next focus: {s['name']} (planned {s['start_date']:%d %b} – {s['end_date']:%d %b})."})
    else:
        out.append({"kind": "info", "text": "No schedule yet – create one from the template on the Overview."})
    if cement_planned:
        pct = cement_used / cement_planned * 100
        prog = overall(stages) if stages else 0
        if prog and pct > prog * 1.25 + 5:
            out.append({"kind": "risk", "text": f"Cement used {pct:.0f}% of estimate at {prog:.0f}% progress – check wastage / pilferage."})
        else:
            out.append({"kind": "good", "text": f"Cement consumption is normal ({pct:.0f}% of estimate used)."})
    if qc_failed:
        out.append({"kind": "risk", "text": f"{qc_failed} quality check(s) failed – rectify before the next stage."})
    elif qc_pending:
        out.append({"kind": "info", "text": f"{qc_pending} quality check(s) pending for the current stages."})
    else:
        out.append({"kind": "good", "text": "No quality issues detected."})
    if open_issues:
        out.append({"kind": "risk", "text": f"{open_issues} open issue(s) / delay(s) need action."})
    if open_safety:
        out.append({"kind": "risk", "text": f"{open_safety} open safety observation(s)."})
    return out
