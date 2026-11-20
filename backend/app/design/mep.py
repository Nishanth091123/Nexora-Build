"""1.26 – Electrical and plumbing drawings with suggestions, made from the saved plan.

Everything here is a SUGGESTED layout (schematic routing, not to scale for pipe / wire runs). Counts per room are
editable defaults taken from common residential practice; the licensed electrician / plumber and the local EB / sewer
authority decide. No prices are invented: this module gives numbers (points, fixtures, lengths, load) only.
"""
from __future__ import annotations

import io
import math

# ---------------------------------------------------------------- electrical rules (points per room type)
# keys: L light, F fan, S5 5A socket, S15 15A socket, AC split-AC point, GY geyser, EX exhaust fan, TV tv/data,
#       CH chimney, FR fridge, WM washing machine, PU water purifier, EV EV / spare 15A, BL bell
ROOM_POINTS = {
    "hall":        {"L": 3, "F": 2, "S5": 4, "S15": 1, "AC": 1, "TV": 1},
    "lounge":      {"L": 3, "F": 2, "S5": 4, "S15": 1, "AC": 1, "TV": 1},
    "dining":      {"L": 2, "F": 1, "S5": 2, "S15": 1, "FR": 0},
    "kitchen":     {"L": 2, "EX": 1, "S5": 2, "S15": 3, "CH": 1, "FR": 1, "PU": 1},
    "bedroom":     {"L": 2, "F": 1, "S5": 3, "S15": 1, "AC": 1, "TV": 1},
    "toilet":      {"L": 1, "EX": 1, "S5": 1, "GY": 1},
    "common_toilet": {"L": 1, "EX": 1, "S5": 1, "GY": 1},
    "dress":       {"L": 1},
    "passage":     {"L": 2, "S5": 1},
    "stair":       {"L": 2},
    "parking":     {"L": 2, "S15": 1, "EV": 1},
    "pooja":       {"L": 1, "S5": 1},
    "utility":     {"L": 1, "EX": 1, "S15": 1, "WM": 1},
    "store":       {"L": 1, "S5": 1},
    "sitout":      {"L": 2, "F": 1, "S5": 1, "BL": 1},
    "terrace":     {"L": 1, "S5": 1},
    "balcony":     {"L": 1, "S5": 1},
}
WATTS = {"L": 12, "F": 75, "S5": 100, "S15": 1000, "AC": 1500, "GY": 2000, "EX": 40, "TV": 150, "CH": 250, "FR": 300,
         "WM": 500, "PU": 25, "EV": 1500, "BL": 10}
LABEL = {"L": "Light point (LED)", "F": "Ceiling fan point", "S5": "5A socket", "S15": "15A power socket",
         "AC": "Split-AC point (16A)", "GY": "Geyser point (16A)", "EX": "Exhaust fan", "TV": "TV / data point",
         "CH": "Chimney point", "FR": "Fridge point", "WM": "Washing-machine point", "PU": "Water-purifier point",
         "EV": "EV / spare 15A point", "BL": "Calling bell"}
SYM = {"L": "L", "F": "F", "S5": "5A", "S15": "15A", "AC": "AC", "GY": "GY", "EX": "EX", "TV": "TV", "CH": "CH",
       "FR": "FR", "WM": "WM", "PU": "PU", "EV": "EV", "BL": "BL"}

# ---------------------------------------------------------------- plumbing rules
FIXTURE_LABEL = {"WC": "Water closet (EWC) with flush tank", "WB": "Wash basin", "SH": "Shower with hot/cold mixer",
                 "HF": "Health faucet", "FD": "Floor drain (trap)", "SK": "Kitchen sink", "RO": "Water-purifier / RO inlet",
                 "WM": "Washing-machine tap + drain", "TP": "Tap (hose / car wash)", "OT": "Overhead-tank outlet"}
PERSONS_PER_HOUSE = 5
LPCD = 135


def _round_up(v: float, step: float) -> float:
    return math.ceil(v / step - 1e-9) * step


# ---------------------------------------------------------------- geometry helpers
def _doors(lv: dict) -> dict:
    out: dict = {}
    for o in lv.get("openings", []):
        if o["type"] in ("door", "main_door", "toilet_door", "pooja_door", "opening"):
            out.setdefault(o["room"], []).append(((o["x1"] + o["x2"]) / 2, (o["y1"] + o["y2"]) / 2))
    return out


def _inset(r: dict, m: float = 0.8) -> tuple[float, float, float, float]:
    return r["x"] + m, r["y"] + m, r["x"] + r["w"] - m, r["y"] + r["d"] - m


def _spread(lo: float, hi: float, n: int) -> list[float]:
    if n <= 1:
        return [(lo + hi) / 2]
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


def _room_points(r: dict, doors: list[tuple[float, float]]) -> list[dict]:
    """Where each point of a room sits (feet, plan co-ordinates). Lights / fans in the room, sockets on the walls."""
    spec = ROOM_POINTS.get(r["type"])
    if not spec:
        return []
    x0, y0, x1, y1 = _inset(r, 0.6)
    pts: list[dict] = []
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    n = spec.get("L", 0)
    if n:
        horiz = r["w"] >= r["d"]
        if n <= 2:
            xs = _spread(x0, x1, n) if horiz else [cx] * n
            ys = [cy] * n if horiz else _spread(y0, y1, n)
            pts += [{"t": "L", "x": a, "y": b} for a, b in zip(xs, ys)]
        else:
            k = 2 if n <= 4 else 3
            cols = _spread(x0, x1, k)
            rows = _spread(y0, y1, math.ceil(n / k))
            i = 0
            for yy in rows:
                for xx in cols:
                    if i < n:
                        pts.append({"t": "L", "x": xx, "y": yy})
                        i += 1
    if spec.get("F"):
        off = 0.0
        for i in range(spec["F"]):
            pts.append({"t": "F", "x": cx + (i - (spec["F"] - 1) / 2) * min(5.0, r["w"] / 2), "y": cy + (0.9 if spec.get("L") else 0) + off})
    # wall devices: walk the room perimeter, skip door spans
    perim: list[tuple[float, float]] = []
    step = 0.5
    for xx in _spread(x0, x1, max(2, int((x1 - x0) / step) + 1)):
        perim.append((xx, y0))
        perim.append((xx, y1))
    for yy in _spread(y0, y1, max(2, int((y1 - y0) / step) + 1)):
        perim.append((x0, yy))
        perim.append((x1, yy))

    def free(p):  # not in front of a door
        return all(math.hypot(p[0] - d[0], p[1] - d[1]) > 2.2 for d in doors)
    perim = [p for p in perim if free(p)] or perim
    wall_items = []
    for key in ("S5", "S15", "AC", "GY", "EX", "TV", "CH", "FR", "WM", "PU", "EV", "BL"):
        wall_items += [key] * spec.get(key, 0)
    if wall_items and perim:
        # spread over the perimeter, remote from the door first for the heavy loads
        perim.sort(key=lambda p: (round(math.atan2(p[1] - cy, p[0] - cx), 1), p[0]))
        stepi = max(1, len(perim) // max(1, len(wall_items)))
        for i, k in enumerate(wall_items):
            p = perim[(i * stepi + 1) % len(perim)]
            pts.append({"t": k, "x": p[0], "y": p[1]})
    # switch board beside the first door (inside the room)
    if doors:
        d = doors[0]
        sx = min(max(d[0] + 1.2, x0), x1)
        sy = y0 if abs(d[1] - r["y"]) < 0.6 else (y1 if abs(d[1] - (r["y"] + r["d"])) < 0.6 else min(max(d[1], y0), y1))
        if abs(d[0] - r["x"]) < 0.6 or abs(d[0] - (r["x"] + r["w"])) < 0.6:
            sx = x0 if abs(d[0] - r["x"]) < 0.6 else x1
            sy = min(max(d[1] + 1.2, y0), y1)
        pts.append({"t": "SW", "x": sx, "y": sy})
    return pts


def electrical(plan: dict) -> dict:
    """Points per room, circuits per floor, DB position and load for the whole house."""
    floors = []
    totals: dict[str, int] = {}
    load_w = 0.0
    for li, lv in enumerate(plan["levels"]):
        doors = _doors(lv)
        rooms_out, counts = [], {}
        for r in lv["rooms"]:
            pts = _room_points(r, doors.get(r["id"], []))
            if not pts:
                continue
            rooms_out.append({"id": r["id"], "name": r["name"], "points": pts})
            for p in pts:
                if p["t"] != "SW":
                    counts[p["t"]] = counts.get(p["t"], 0) + 1
        # distribution board: next to the main door (ground) or the stair lobby (upper floors)
        db = None
        for o in lv.get("openings", []):
            if o["type"] == "main_door":
                db = (o["x1"] + o["x2"]) / 2 + (1.5 if o["y1"] == o["y2"] else 0), o["y1"] + 0.8
        if db is None:
            st = next((r for r in lv["rooms"] if r["type"] in ("stair", "passage", "lounge")), lv["rooms"][0])
            db = (st["x"] + 0.8, st["y"] + 0.8)
        n_light = counts.get("L", 0) + counts.get("F", 0) + counts.get("EX", 0) + counts.get("BL", 0)
        n_sock = counts.get("S5", 0) + counts.get("TV", 0) + counts.get("PU", 0)
        circuits = [{"name": f"Lights + fans (1.5 mm² wire, 6A MCB each)", "count": max(1, math.ceil(n_light / 8)),
                     "points": n_light}]
        circuits.append({"name": "5A sockets / TV / purifier (2.5 mm² wire, 16A MCB each)", "count": max(1, math.ceil(n_sock / 8)),
                         "points": n_sock})
        for k, nm, wire in (("AC", "Split-AC, one circuit each (4 mm² wire, 20A MCB)", 4), ("GY", "Geyser, one circuit each (2.5 mm² wire, 16A MCB)", 2.5),
                            ("S15", "15A power sockets – kitchen / utility / hall (2.5 mm² wire, 16A MCB each)", 2.5),
                            ("CH", "Chimney (2.5 mm² wire, 16A MCB)", 2.5), ("FR", "Fridge (2.5 mm² wire, 16A MCB)", 2.5),
                            ("WM", "Washing machine (2.5 mm² wire, 16A MCB)", 2.5), ("EV", "EV / spare 15A (4 mm² wire, 20A MCB)", 4)):
            if counts.get(k):
                circuits.append({"name": nm, "count": counts[k] if k in ("AC", "GY", "EV") else max(1, math.ceil(counts[k] / (3 if k == "S15" else 1))),
                                 "points": counts[k]})
        floors.append({"level": li, "name": lv["name"], "rooms": rooms_out, "counts": counts, "db": {"x": db[0], "y": db[1]},
                       "circuits": circuits})
        for k, v in counts.items():
            totals[k] = totals.get(k, 0) + v
    connected = sum(WATTS.get(k, 0) * v for k, v in totals.items()) / 1000.0
    demand = connected * 0.6
    # sump / borewell pump 0.5 – 1 HP
    pump = 0.75
    demand += pump * 0.6
    phase = "single-phase" if (connected + pump) <= 5.0 else "three-phase"
    return {"floors": floors, "totals": totals, "connected_kw": round(connected + pump, 1), "demand_kw": round(demand, 1),
            "phase": phase, "labels": LABEL}


def electrical_notes(e: dict, plan: dict) -> list[str]:
    n = [f"Connected load about {e['connected_kw']} kW (incl. 0.75 kW water pump); after 0.6 diversity about {e['demand_kw']} kW – "
         f"{e['phase']} supply is usual at this load. TNPDCL decides the supply; apply for the load you will really use.",
         "One distribution board (DB) per floor with a 30 mA RCCB (40A) on the incoming side and an MCB for every circuit; "
         "keep 2 spare ways. A surge protector at the main DB is recommended.",
         "Concealed copper-wire PVC conduit, red / black / green colour code. Earth pit (GI or copper plate) near the meter board, "
         "all sockets 3-pin with earth; geyser, AC and metal fixtures earthed.",
         "Switch boards 4 ft above floor (kitchen counter sockets 3.5 ft, bed-side 2 ft, TV 3.5 ft). Keep sockets away from sinks and shower.",
         "Provide conduit-only pipes for TV / internet / CCTV to the roof and the gate; keep a separate circuit for the water pump.",
         "This is a suggested point layout. Final points, wire sizes and MCB ratings are set by the licensed electrician on the actual load."]
    if len(plan["levels"]) > 1:
        n.append("Run the first-floor sub-main (6 mm² wire) from the ground-floor DB through the staircase wall.")
    return n


# ---------------------------------------------------------------- plumbing
def _wet(rooms: list[dict]) -> list[dict]:
    return [r for r in rooms if r["type"] in ("toilet", "common_toilet", "kitchen", "utility")]


def _toilet_fixtures(r: dict, doors: list[tuple[float, float]]) -> list[dict]:
    x0, y0, x1, y1 = _inset(r, 0.7)
    d = doors[0] if doors else (r["x"] + r["w"] / 2, r["y"])
    # far corner from the door gets the WC, the near wall the basin, the remaining corner the shower
    corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
    corners.sort(key=lambda p: -math.hypot(p[0] - d[0], p[1] - d[1]))
    wc, sh = corners[0], corners[1] if r["w"] >= r["d"] and abs(corners[1][0] - corners[0][0]) > 1 else corners[1]
    near = min(corners, key=lambda p: math.hypot(p[0] - d[0], p[1] - d[1]))
    out = [{"t": "WC", "x": wc[0], "y": wc[1]}, {"t": "HF", "x": wc[0] + (0.7 if wc[0] < r["x"] + r["w"] / 2 else -0.7), "y": wc[1]},
           {"t": "SH", "x": sh[0], "y": sh[1]}, {"t": "WB", "x": near[0], "y": near[1]},
           {"t": "FD", "x": (x0 + x1) / 2, "y": (y0 + y1) / 2}]
    return out


def plumbing(plan: dict) -> dict:
    b = plan["building"]
    floors, totals = [], {}
    lvl0_wc = []
    issues: list[str] = []
    persons = PERSONS_PER_HOUSE * max(1, len({r.get("unit") for lv in plan["levels"] for r in lv["rooms"] if r.get("unit")}) or 1)
    for li, lv in enumerate(plan["levels"]):
        doors = _doors(lv)
        fx, pipes, stacks = [], [], []
        wcs = []
        for r in _wet(lv["rooms"]):
            if r["type"] in ("toilet", "common_toilet"):
                fx_r = _toilet_fixtures(r, doors.get(r["id"], []))
                for f in fx_r:
                    f["room"] = r["name"]
                fx += fx_r
                wc = next(f for f in fx_r if f["t"] == "WC")
                wcs.append((wc, r))
            elif r["type"] == "kitchen":
                x0, y0, x1, y1 = _inset(r, 0.7)
                d = (doors.get(r["id"]) or [(r["x"], r["y"])])[0]
                far = max([(x0, y0), (x1, y0), (x0, y1), (x1, y1)], key=lambda p: math.hypot(p[0] - d[0], p[1] - d[1]))
                fx += [{"t": "SK", "x": far[0], "y": far[1], "room": r["name"]},
                       {"t": "RO", "x": far[0] + (0.9 if far[0] < r["x"] + r["w"] / 2 else -0.9), "y": far[1], "room": r["name"]}]
                if not any(q["type"] == "utility" for q in lv["rooms"]):
                    fx.append({"t": "WM", "x": far[0], "y": far[1] + (-1.2 if far[1] > r["y"] + r["d"] / 2 else 1.2), "room": r["name"]})
                wcs.append(({"t": "SK", "x": far[0], "y": far[1]}, r))
            elif r["type"] == "utility":
                x0, y0, x1, y1 = _inset(r, 0.6)
                fx += [{"t": "WM", "x": x0, "y": y0, "room": r["name"]}, {"t": "FD", "x": (x0 + x1) / 2, "y": (y0 + y1) / 2, "room": r["name"]}]
                wcs.append(({"t": "WM", "x": x0, "y": y0}, r))
        # a wash basin in the dining / hall area (ground floor, outside the toilets)
        if li == 0:
            dn = next((r for r in lv["rooms"] if r["type"] == "dining"), None) or next((r for r in lv["rooms"] if r["type"] == "hall"), None)
            if dn:
                fx.append({"t": "WB", "x": dn["x"] + dn["w"] - 0.8, "y": dn["y"] + 0.8, "room": dn["name"] + " (wash area)"})
                wcs.append(({"t": "WB", "x": dn["x"] + dn["w"] - 0.8, "y": dn["y"] + 0.8}, dn))
            for pk in (r for r in lv["rooms"] if r["type"] == "parking"):
                fx.append({"t": "TP", "x": pk["x"] + 0.5, "y": pk["y"] + pk["d"] - 0.6, "room": pk["name"]})
        # drains: each fixture group runs by the shortest straight line to the nearest outside wall (ground) or down the stack
        for f, r in wcs:
            sx, sy = f["x"], f["y"]
            sides = [(sx, 0.0, "front"), (sx, b["d"], "rear"), (0.0, sy, "left"), (b["w"], sy, "right")]
            tx, ty, _ = min(sides, key=lambda s: abs(s[0] - sx) + abs(s[1] - sy))
            if f["t"] in ("WC", "SK", "WM", "WB"):
                if li == 0:
                    pipes.append({"kind": "drain", "pts": [(sx, sy), (tx, sy) if tx in (0.0, b["w"]) else (sx, ty), (tx, ty)]})
                stacks.append({"x": sx, "y": sy, "room": r["name"], "t": f["t"]})
        # supply: one riser per floor beside the first wet room; branch lines are drawn to every fixture
        if fx:
            first = next((f for f in fx if f["t"] in ("WC", "SK")), fx[0])
            rx, ry = first["x"] + (0.8 if first["x"] < b["w"] / 2 else -0.8), first["y"]
            riser = {"x": rx, "y": ry}
            for f in fx:
                if f["t"] in ("FD",):
                    continue
                pipes.append({"kind": "supply", "pts": [(rx, ry), (f["x"], ry), (f["x"], f["y"])]})
        else:
            riser = None
        for f in fx:
            totals[f["t"]] = totals.get(f["t"], 0) + 1
        sup_len = sum(sum(abs(p["pts"][i + 1][0] - p["pts"][i][0]) + abs(p["pts"][i + 1][1] - p["pts"][i][1])
                          for i in range(len(p["pts"]) - 1)) for p in pipes if p["kind"] == "supply")
        drn_len = sum(sum(abs(p["pts"][i + 1][0] - p["pts"][i][0]) + abs(p["pts"][i + 1][1] - p["pts"][i][1])
                          for i in range(len(p["pts"]) - 1)) for p in pipes if p["kind"] == "drain")
        floors.append({"level": li, "name": lv["name"], "fixtures": fx, "pipes": pipes, "riser": riser, "stacks": stacks,
                       "supply_ft": round(sup_len, 1), "drain_ft": round(drn_len, 1)})
        if li == 0:
            lvl0_wc = [(f, r) for f, r in wcs if f["t"] == "WC"]
    # stack alignment: a first-floor WC should sit over a ground-floor WC
    for fl in floors[1:]:
        for f in [x for x in fl["fixtures"] if x["t"] == "WC"]:
            if not any(abs(f["x"] - g["x"]) < 4.5 and abs(f["y"] - g["y"]) < 4.5 for g, _ in lvl0_wc):
                issues.append(f"{fl['name']}: the WC in {f['room']} is not above a ground-floor toilet – the soil pipe must be boxed "
                              f"through the ceiling below. Align the toilets one above the other if you can.")
    day = persons * LPCD
    oht = max(1000.0, _round_up(day * 0.5, 500))
    sump = max(1000.0, _round_up(day * 1.5, 500))
    return {"floors": floors, "totals": totals, "labels": FIXTURE_LABEL, "issues": issues,
            "water": {"persons": persons, "lpcd": LPCD, "daily_l": day, "oht_l": oht, "sump_l": sump}}


def plumbing_notes(p: dict, plan: dict) -> list[str]:
    w = p["water"]
    n = [f"Water demand about {w['daily_l']:,.0f} L/day ({w['persons']} persons × {w['lpcd']} litres). Suggested overhead tank "
         f"{w['oht_l']:,.0f} L (on the roof above the toilets) and underground sump {w['sump_l']:,.0f} L – same basis as Site → Water services; edit there.",
         "Supply: CPVC / UPVC ¾\" from the tank down a single riser, ½\" branches to the fixtures; hot and cold lines kept apart; "
         "a stop-cock at the start of every toilet and at the kitchen.",
         "Drainage: WC soil pipe 110 mm (4\"), wash basin / shower / sink waste 50 – 75 mm, every fixture with a trap; soil stack 110 mm taken "
         "above the roof as a vent pipe with a cowl. Slope 1:40 for 110 mm and 1:60 for 50 – 75 mm.",
         "Inspection chamber at every change of direction and at the house outlet; septic tank / sewer connection is decided by the "
         "local body – keep it away from the sump and borewell (at least 7 m) and outside the car path.",
         "Toilet floor sunk 1.5 – 2 inches below the passage with a slope to the floor drain; waterproofing before tiling. "
         "Keep the pipes of the two floors in the same shaft so repair never needs wall cutting.",
         "Suggested schematic layout only – pipe routes are drawn straight for clarity; the plumber sets the real routes on site."]
    n += p["issues"]
    return n


# ---------------------------------------------------------------- PDF
def _pdf_safe(t: str) -> str:
    for k, v in {"²": "2", "³": "3", "≈": "~", "₹": "Rs.", "≤": "<=", "≥": ">=", "–": "-", "×": "x", "\"": "\"", "·": "-"}.items():
        t = str(t).replace(k, v)
    return t


def to_pdf(plan: dict, project: dict, kind: str = "both") -> bytes:
    """kind: electrical | plumbing | both – drawings per floor (A4 landscape) + schedule / suggestions pages."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    from .. import letterhead as lh
    from .exports import THK
    buf = io.BytesIO()
    W, H = landscape(A4)
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    b = plan["building"]
    kinds = ["electrical", "plumbing"] if kind == "both" else [kind]
    E = electrical(plan) if "electrical" in kinds else None
    P = plumbing(plan) if "plumbing" in kinds else None
    margin = 14 * mm
    dw, dh = W * 0.60 - margin, H - 2 * margin - 22 * mm
    sc = min(dw / b["w"], dh / b["d"])
    ox, oy = margin + 4 * mm, margin + 14 * mm

    def Pt(x, y):
        return ox + x * sc, oy + y * sc

    def base(lv: dict, title: str):
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(colors.HexColor("#0F172A"))
        c.drawString(margin, H - margin, _pdf_safe(f"{project.get('name', '')} - {title} - {lv['name']}"))
        c.setFont("Helvetica", 8.5)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawString(margin, H - margin - 12, _pdf_safe(f"{plan.get('facing', '').title()} facing - suggested schematic layout, not to scale for runs"))
        for w in lv.get("walls", []):
            t = THK.get(w["kind"], 0.5) * sc
            c.setStrokeColor(colors.HexColor("#1E293B" if w["kind"] == "ext" else "#64748B"))
            c.setLineWidth(max(0.6, t * 0.55))
            x1, y1 = Pt(w["x1"], w["y1"])
            x2, y2 = Pt(w["x2"], w["y2"])
            c.line(x1, y1, x2, y2)
        for o in lv.get("openings", []):
            if o["type"] in ("window", "vent"):
                continue
            c.setStrokeColor(colors.white)
            c.setLineWidth(2.4)
            x1, y1 = Pt(o["x1"], o["y1"])
            x2, y2 = Pt(o["x2"], o["y2"])
            c.line(x1, y1, x2, y2)
        c.setFont("Helvetica", 6.5)
        c.setFillColor(colors.HexColor("#94A3B8"))
        for r in lv["rooms"]:
            x, y = Pt(r["x"] + r["w"] / 2, r["y"] + r["d"] - 0.9)
            c.drawCentredString(x, y, _pdf_safe(r["name"][:22]))

    def sym(x, y, txt, col, r=3.4):
        px, py = Pt(x, y)
        c.setFillColor(colors.white)
        c.setStrokeColor(col)
        c.setLineWidth(0.7)
        c.circle(px, py, r, fill=1)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 4.6 if len(txt) > 2 else 5.4)
        c.drawCentredString(px, py - 1.8, txt)

    def legend(items, title, extra=()):
        x = W * 0.66
        y = H - margin - 6
        c.setFillColor(colors.HexColor("#0F172A"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x, y, title)
        c.setFont("Helvetica", 8)
        y -= 16
        for code, text, col in items:
            sym_x, sym_y = x + 6, y + 2
            c.setFillColor(colors.white)
            c.setStrokeColor(col)
            c.circle(sym_x, sym_y, 5, fill=1)
            c.setFillColor(col)
            c.setFont("Helvetica-Bold", 5)
            c.drawCentredString(sym_x, sym_y - 1.8, code)
            c.setFillColor(colors.HexColor("#1E293B"))
            c.setFont("Helvetica", 8)
            c.drawString(x + 18, y, _pdf_safe(text))
            y -= 13
        for line in extra:
            c.setFillColor(colors.HexColor("#1E293B"))
            c.setFont("Helvetica", 8)
            c.drawString(x, y, _pdf_safe(line))
            y -= 12
        return y

    def text_page(title: str, lines: list[tuple[str, list[str]]]):
        c.showPage()
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(colors.HexColor("#0F172A"))
        c.drawString(margin, H - margin, _pdf_safe(title))
        y = H - margin - 22
        for head, rows in lines:
            c.setFont("Helvetica-Bold", 9.5)
            c.setFillColor(colors.HexColor("#1E3A8A"))
            c.drawString(margin, y, _pdf_safe(head))
            y -= 13
            c.setFont("Helvetica", 8.4)
            c.setFillColor(colors.HexColor("#1E293B"))
            for r_ in rows:
                words, line = _pdf_safe(r_).split(), ""
                first = True
                for w_ in words:
                    if c.stringWidth(line + " " + w_, "Helvetica", 8.4) > W - 2 * margin - 14:
                        c.drawString(margin + (0 if first else 10), y, ("- " if first else "") + line.strip())
                        y -= 11
                        first, line = False, w_
                    else:
                        line += " " + w_
                if line.strip():
                    c.drawString(margin + (0 if first else 10), y, ("- " if first else "") + line.strip())
                    y -= 11
                if y < 60:
                    lh.later_page(c, W)
                    c.showPage()
                    y = H - margin
                    c.setFont("Helvetica", 8.4)
            y -= 6

    first = True
    elec_col, plb_col, drn_col = colors.HexColor("#B45309"), colors.HexColor("#1D4ED8"), colors.HexColor("#7C2D12")
    if E:
        for fl in E["floors"]:
            lv = plan["levels"][fl["level"]]
            if not first:
                c.showPage()
            first = False
            base(lv, "ELECTRICAL LAYOUT", )
            for rm in fl["rooms"]:
                for p in rm["points"]:
                    if p["t"] == "SW":
                        px, py = Pt(p["x"], p["y"])
                        c.setFillColor(colors.HexColor("#334155"))
                        c.rect(px - 2, py - 2, 4, 4, fill=1)
                    else:
                        sym(p["x"], p["y"], SYM[p["t"]], elec_col)
            dbx, dby = Pt(fl["db"]["x"], fl["db"]["y"])
            c.setFillColor(colors.HexColor("#DC2626"))
            c.rect(dbx - 5, dby - 4, 10, 8, fill=1)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 5.5)
            c.drawCentredString(dbx, dby - 2, "DB")
            used = [k for k in LABEL if fl["counts"].get(k)]
            y = legend([(SYM[k], f"{LABEL[k]}  x {fl['counts'][k]}", elec_col) for k in used], f"{lv['name']} - symbols",
                       ["[]  Switch board (beside the door)", "DB  Distribution board (RCCB + MCBs)"])
            y -= 6
            c.setFont("Helvetica-Bold", 9)
            c.drawString(W * 0.66, y, "Circuits (suggested)")
            y -= 12
            c.setFont("Helvetica", 7.6)
            for ci in fl["circuits"]:
                c.drawString(W * 0.66, y, _pdf_safe(f"{ci['count']} x {ci['name'][:62]}"))
                y -= 10.5
            lh.later_page(c, W)
    if P:
        for fl in P["floors"]:
            lv = plan["levels"][fl["level"]]
            if not fl["fixtures"]:
                continue
            if not first:
                c.showPage()
            first = False
            base(lv, "PLUMBING LAYOUT")
            for pp in fl["pipes"]:
                col = plb_col if pp["kind"] == "supply" else drn_col
                c.setStrokeColor(col)
                c.setLineWidth(0.9)
                c.setDash(3, 2) if pp["kind"] == "supply" else c.setDash()
                pts = [Pt(*q) for q in pp["pts"]]
                for a, b2 in zip(pts, pts[1:]):
                    c.line(a[0], a[1], b2[0], b2[1])
                c.setDash()
            for f in fl["fixtures"]:
                sym(f["x"], f["y"], f["t"], plb_col if f["t"] not in ("FD",) else drn_col)
            if fl["riser"]:
                rx, ry = Pt(fl["riser"]["x"], fl["riser"]["y"])
                c.setFillColor(plb_col)
                c.circle(rx, ry, 4.2, fill=1)
                c.setFillColor(colors.white)
                c.setFont("Helvetica-Bold", 5)
                c.drawCentredString(rx, ry - 1.8, "R")
            for s_ in fl["stacks"]:
                if s_["t"] == "WC":
                    sx, sy = Pt(s_["x"], s_["y"])
                    c.setStrokeColor(drn_col)
                    c.setLineWidth(1.2)
                    c.circle(sx, sy, 5.6)
            used = sorted({f["t"] for f in fl["fixtures"]})
            y = legend([(k, f"{FIXTURE_LABEL[k]}  x {sum(1 for f in fl['fixtures'] if f['t'] == k)}", plb_col) for k in used],
                       f"{lv['name']} - fixtures",
                       ["R   Water riser from the overhead tank", "Dashed blue  = water supply line", "Brown line = drain / soil line (to septic / sewer)",
                        "Ring around WC = soil stack (110 mm)",
                        f"Approx. supply pipe {fl['supply_ft']:g} ft, drain {fl['drain_ft']:g} ft on this floor"])
            lh.later_page(c, W)
    # suggestions + totals
    sections: list[tuple[str, list[str]]] = []
    if E:
        sections.append(("ELECTRICAL - total points (whole house)", [f"{LABEL[k]}: {v}" for k, v in E["totals"].items()]))
        sections.append(("ELECTRICAL - suggestions", electrical_notes(E, plan)))
    if P:
        sections.append(("PLUMBING - total fixtures (whole house)", [f"{FIXTURE_LABEL[k]}: {v}" for k, v in P["totals"].items()]
                         + [f"Approx. supply pipe {sum(f['supply_ft'] for f in P['floors']):g} ft, drain / soil pipe {sum(f['drain_ft'] for f in P['floors']):g} ft (schematic lengths + 15 % for bends and drops)"]))
        sections.append(("PLUMBING - suggestions", plumbing_notes(P, plan)))
    text_page("Schedule and suggestions", sections)
    lh.later_page(c, W)
    lh.seal_box(c, W, 56)
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------- DXF (layers per service)
def to_dxf(plan: dict, project: dict, kind: str = "both") -> bytes:
    from .exports import _dxf_line, _dxf_rect, _dxf_text
    from .exports import THK
    out = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "2", "0", "ENDSEC",
           "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", "9"]
    layers = {"WALL": 7, "DOOR": 1, "ROOM_NAME": 8, "ELEC_POINTS": 30, "ELEC_DB": 1, "PLUMB_SUPPLY": 5, "PLUMB_DRAIN": 34,
              "PLUMB_FIXTURE": 150, "TEXT": 7}
    for name, col in layers.items():
        out += ["0", "LAYER", "2", name, "70", "0", "62", str(col), "6", "CONTINUOUS"]
    out += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    b = plan["building"]
    kinds = ["electrical", "plumbing"] if kind == "both" else [kind]
    E = electrical(plan) if "electrical" in kinds else None
    P = plumbing(plan) if "plumbing" in kinds else None
    n = 0
    for li, lv in enumerate(plan["levels"]):
        for k in kinds:
            ox = n * (b["w"] + 12)
            n += 1
            _dxf_text(out, "TEXT", ox + b["w"] / 2, -3, 1.0, f"{lv['name']} - {k.upper()} (feet, suggested layout)")
            for w in lv.get("walls", []):
                t = THK.get(w["kind"], 0.5) / 2
                x1, y1, x2, y2 = ox + w["x1"], w["y1"], ox + w["x2"], w["y2"]
                if y1 == y2:
                    _dxf_line(out, "WALL", x1, y1 - t, x2, y2 - t)
                    _dxf_line(out, "WALL", x1, y1 + t, x2, y2 + t)
                else:
                    _dxf_line(out, "WALL", x1 - t, y1, x2 - t, y2)
                    _dxf_line(out, "WALL", x1 + t, y1, x2 + t, y2)
            for o in lv.get("openings", []):
                if o["type"] not in ("window", "vent"):
                    _dxf_line(out, "DOOR", ox + o["x1"], o["y1"], ox + o["x2"], o["y2"])
            for r in lv["rooms"]:
                _dxf_text(out, "ROOM_NAME", ox + r["x"] + r["w"] / 2, r["y"] + r["d"] - 0.9, 0.5, r["name"])
            if k == "electrical" and E:
                fl = E["floors"][li]
                for rm in fl["rooms"]:
                    for p in rm["points"]:
                        _dxf_rect(out, "ELEC_POINTS", ox + p["x"] - 0.25, p["y"] - 0.25, 0.5, 0.5)
                        _dxf_text(out, "ELEC_POINTS", ox + p["x"], p["y"] + 0.4, 0.3, p["t"])
                _dxf_rect(out, "ELEC_DB", ox + fl["db"]["x"] - 0.5, fl["db"]["y"] - 0.4, 1.0, 0.8)
                _dxf_text(out, "ELEC_DB", ox + fl["db"]["x"], fl["db"]["y"] + 0.7, 0.4, "DB")
            if k == "plumbing" and P:
                fl = P["floors"][li]
                for pp in fl["pipes"]:
                    lay = "PLUMB_SUPPLY" if pp["kind"] == "supply" else "PLUMB_DRAIN"
                    for a, b2 in zip(pp["pts"], pp["pts"][1:]):
                        _dxf_line(out, lay, ox + a[0], a[1], ox + b2[0], b2[1])
                for f in fl["fixtures"]:
                    _dxf_rect(out, "PLUMB_FIXTURE", ox + f["x"] - 0.3, f["y"] - 0.3, 0.6, 0.6)
                    _dxf_text(out, "PLUMB_FIXTURE", ox + f["x"], f["y"] + 0.5, 0.3, f["t"])
    out += ["0", "ENDSEC", "0", "EOF"]
    return ("\r\n".join(out) + "\r\n").encode("ascii", "replace")
