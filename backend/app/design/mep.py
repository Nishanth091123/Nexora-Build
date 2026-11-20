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
WATTS = {"L": 12, "F": 75, "S5": 60, "S15": 500, "AC": 1500, "GY": 2000, "EX": 40, "TV": 150, "CH": 250, "FR": 300,
         "WM": 500, "PU": 25, "EV": 1000, "BL": 10}
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




# ---------------------------------------------------------------- editable settings
DEFAULTS = {"phase": "auto", "pump_kw": 0.75, "diversity": 0.6, "persons": None, "lpcd": 135, "oht_l": None, "sump_l": None}
STD_A = [6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125]


def norm_opts(raw: dict | None) -> dict:
    """Saved settings -> clean numbers. phase: auto | single | three. Blank / None = automatic."""
    o = dict(DEFAULTS)
    raw = raw or {}
    if raw.get("phase") in ("auto", "single", "three"):
        o["phase"] = raw["phase"]
    for k, lo, hi in (("pump_kw", 0, 15), ("diversity", 0.3, 1.0), ("persons", 1, 300), ("lpcd", 40, 400),
                      ("oht_l", 0, 200000), ("sump_l", 0, 500000)):
        v = raw.get(k)
        if v in (None, ""):
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        if lo <= v <= hi:
            o[k] = v
    return o


def _std(a: float) -> int:
    return next((x for x in STD_A if x >= a - 1e-9), STD_A[-1])


def _wire_for(a: float) -> float:
    for lim, mm in ((16, 2.5), (20, 4), (32, 6), (40, 10), (63, 16), (80, 25), (100, 35)):
        if a <= lim:
            return mm
    return 50


# ---------------------------------------------------------------- electrical
# (point keys, code, name, wire mm2, MCB A, points per circuit)
GROUPS = [(("L", "F", "EX", "BL"), "L", "Lights + fans", 1.5, 6, 8),
          (("S5", "TV", "PU"), "P", "5A sockets / TV / purifier", 2.5, 16, 8),
          (("S15",), "S", "15A power sockets", 2.5, 16, 3),
          (("AC",), "AC", "Split AC", 4, 20, 1), (("GY",), "GY", "Geyser", 2.5, 16, 1),
          (("CH",), "CH", "Chimney", 2.5, 16, 1), (("FR",), "FR", "Fridge", 2.5, 16, 1),
          (("WM",), "WM", "Washing machine", 2.5, 16, 1), (("EV",), "EV", "EV / spare 15A", 4, 20, 1)]
PHASES = ["R", "Y", "B"]


def electrical(plan: dict, opts: dict | None = None) -> dict:
    """Points per room, numbered circuits with phase / MCB / wire, switch boards, DB per floor and the main supply."""
    o = norm_opts(opts)
    floors, totals, all_ckts = [], {}, []
    for li, lv in enumerate(plan["levels"]):
        pfx = "G" if li == 0 else f"F{li}"
        doors = _doors(lv)
        rooms_out, counts, boards = [], {}, []
        for r in lv["rooms"]:
            pts = _room_points(r, doors.get(r["id"], []))
            if not pts:
                continue
            rooms_out.append({"id": r["id"], "name": r["name"], "points": pts})
            for p in pts:
                if p["t"] != "SW":
                    counts[p["t"]] = counts.get(p["t"], 0) + 1
        db = None
        for op in lv.get("openings", []):
            if op["type"] == "main_door":
                db = (op["x1"] + op["x2"]) / 2 + (1.5 if op["y1"] == op["y2"] else 0), op["y1"] + 0.8
        if db is None:
            st = next((r for r in lv["rooms"] if r["type"] in ("stair", "passage", "lounge")), lv["rooms"][0])
            db = (st["x"] + 0.8, st["y"] + 0.8)
        # --- circuits: room by room so one room stays on one circuit where it fits
        ckts = []
        for keys, code, name, wire, mcb, chunk in GROUPS:
            cur = None
            for rm in rooms_out:
                mine = [p for p in rm["points"] if p["t"] in keys]
                if not mine:
                    continue
                for p in mine:
                    if cur is None or len(cur["_pts"]) >= chunk or (chunk > 1 and len(cur["_pts"]) + 1 > chunk):
                        cur = {"id": f"{pfx}-{code}{sum(1 for c_ in ckts if c_['code'] == code) + 1}", "code": code, "name": name,
                               "wire": wire, "mcb": mcb, "_pts": [], "rooms": [], "floor": lv["name"], "level": li}
                        ckts.append(cur)
                    cur["_pts"].append(p)
                    p["ckt"] = cur["id"]
                    if rm["name"] not in cur["rooms"]:
                        cur["rooms"].append(rm["name"])
        for ck in ckts:
            ck["points"] = len(ck["_pts"])
            ck["load_w"] = int(sum(WATTS.get(p["t"], 0) for p in ck["_pts"]))
            del ck["_pts"]
        all_ckts += ckts
        # --- switch boards (one per room, at the door)
        for k, rm in enumerate([x for x in rooms_out if any(p["t"] == "SW" for p in x["points"])], 1):
            sw = next(p for p in rm["points"] if p["t"] == "SW")
            cnt: dict = {}
            for p in rm["points"]:
                cnt[p["t"]] = cnt.get(p["t"], 0) + 1
            sid = f"SB{pfx}{k}"
            sw["sb"] = sid
            sw_n = math.ceil(cnt.get("L", 0) / 2) + cnt.get("EX", 0) + cnt.get("BL", 0) + (1 if cnt.get("AC") else 0) + (1 if cnt.get("GY") else 0)
            boards.append({"id": sid, "room": rm["name"], "x": sw["x"], "y": sw["y"], "switches": sw_n, "regulators": cnt.get("F", 0),
                           "s5": cnt.get("S5", 0), "s15": cnt.get("S15", 0), "tv": cnt.get("TV", 0)})
        floors.append({"level": li, "name": lv["name"], "prefix": pfx, "rooms": rooms_out, "counts": counts, "boards": boards,
                       "db": {"x": db[0], "y": db[1]}, "circuits": ckts})
        for k, v in counts.items():
            totals[k] = totals.get(k, 0) + v
    # --- supply: phase choice (editable) and phase balancing
    connected = sum(WATTS.get(k, 0) * v for k, v in totals.items()) / 1000.0 + o["pump_kw"]
    demand = connected * o["diversity"]
    auto_three = connected > 5.0
    three = (o["phase"] == "three") or (o["phase"] == "auto" and auto_three)
    pump_ck = {"id": "PUMP", "code": "PU", "name": "Water pump (sump / borewell)", "wire": 2.5 if o["pump_kw"] <= 1.1 else 4,
               "mcb": 16 if o["pump_kw"] <= 1.1 else 25, "points": 1, "load_w": int(o["pump_kw"] * 1000), "rooms": ["Pump"],
               "floor": "Ground floor", "level": 0}
    ph_load = {p: 0 for p in PHASES}
    if three:
        for ck in sorted(all_ckts + [pump_ck], key=lambda c_: -c_["load_w"]):
            p = min(PHASES, key=lambda x: ph_load[x])
            ck["phase"] = p
            ph_load[p] += ck["load_w"]
    else:
        for ck in all_ckts + [pump_ck]:
            ck["phase"] = "R"
        ph_load["R"] = sum(c_["load_w"] for c_ in all_ckts + [pump_ck])
    floors[0]["circuits"].append(pump_ck)
    volt = 415 if three else 230
    amps = demand * 1000 / ((math.sqrt(3) * 415 * 0.9) if three else (230 * 0.9))
    inc = _std(max(amps * 1.25, 16 if not three else 25))
    for fl in floors:
        fc = sum(c_["load_w"] for c_ in fl["circuits"]) / 1000.0
        fa = fc * o["diversity"] * 1000 / ((math.sqrt(3) * 415 * 0.9) if three else (230 * 0.9))
        fl["db"].update({"name": f"DB-{fl['prefix']}", "type": "TPN" if three else "SPN", "ways": len(fl["circuits"]) + 2,
                         "incomer_a": _std(max(fa * 1.25, 16)), "connected_kw": round(fc, 1)})
    main = {"phase": "three-phase" if three else "single-phase", "volt": volt, "poles": "4P" if three else "2P",
            "demand_a": round(amps, 1), "incomer_a": inc, "wire_mm2": _wire_for(inc), "rccb_a": max(25, inc) if three else max(25, inc),
            "pump_kw": o["pump_kw"], "balance_w": ph_load, "auto_would_be": "three-phase" if auto_three else "single-phase",
            "chosen_by": "you" if o["phase"] != "auto" else "automatic"}
    return {"floors": floors, "totals": totals, "connected_kw": round(connected, 1), "demand_kw": round(demand, 1),
            "phase": main["phase"], "main": main, "labels": LABEL, "options": o}


def electrical_notes(e: dict, plan: dict) -> list[str]:
    m = e["main"]
    n = [f"Connected load about {e['connected_kw']} kW (incl. {m['pump_kw']:g} kW water pump); with the demand factor about {e['demand_kw']} kW "
         f"= {m['demand_a']} A. Supply chosen: {m['phase']} ({m['chosen_by']}). Suggested main {m['poles']} MCB / MCCB {m['incomer_a']} A, "
         f"incoming copper cable {m['wire_mm2']:g} mm2. TNPDCL decides the sanctioned load and supply.",
         "One distribution board (DB) per floor with a 30 mA RCCB on the incoming side and an MCB per circuit; keep 2 spare ways. "
         + ("Three-phase: TPN boards, circuits spread over R / Y / B to balance the load." if m["phase"] == "three-phase"
            else "Single-phase: SPN boards, all circuits on one phase and neutral.")
         + " A surge protector at the main DB is recommended.",
         "Concealed copper-wire PVC conduit, red (phase) / black (neutral) / green (earth). Earth pit (GI or copper plate, kept moist) "
         "near the meter board; all sockets 3-pin with earth; geyser, AC and metal fixtures earthed.",
         "Switch boards 4 ft above floor (kitchen counter sockets 3.5 ft, bed-side 2 ft, TV 3.5 ft). Keep sockets away from sinks and shower.",
         "Provide conduit-only pipes for TV / internet / CCTV to the roof and the gate; keep a separate circuit for the water pump.",
         "This is a suggested point layout. Final points, wire sizes and MCB ratings are set by the licensed electrician on the actual load."]
    if m["phase"] == "single-phase" and e["connected_kw"] > 7.5:
        n.append(f"Warning: {e['connected_kw']} kW connected is high for a single-phase service; three-phase is normally taken above about 5 – 7.5 kW. "
                 "Check the limit with TNPDCL.")
    if len(plan["levels"]) > 1:
        n.append("Run the first-floor sub-main (6 mm2 wire, from the ground-floor DB) through the staircase wall in its own conduit.")
    return n


# ---------------------------------------------------------------- plumbing
FIXTURE_LABEL = {"WC": "Water closet (EWC) with flush tank", "WB": "Wash basin", "SH": "Shower with hot/cold mixer",
                 "HF": "Health faucet", "FD": "Floor drain (trap)", "SK": "Kitchen sink", "RO": "Water-purifier / RO inlet",
                 "WM": "Washing-machine tap + drain", "TP": "Tap (hose / car wash)", "GY": "Geyser (hot water)"}
# supply dia, waste dia (mm), trap
FIXTURE_SPEC = {"WC": ('1/2"', 110, "P / S trap (in pan)"), "WB": ('1/2"', 40, "Bottle trap"), "SH": ('1/2"', 50, "Floor trap"),
                "HF": ('1/2"', 0, "-"), "FD": (None, 75, "Floor trap with jali"), "SK": ('1/2"', 50, "Bottle trap + gully"),
                "RO": ('1/2"', 0, "-"), "WM": ('1/2"', 50, "Standpipe trap"), "TP": ('1/2"', 0, "-"), "GY": ('1/2"', 0, "-")}


def _wet(rooms: list[dict]) -> list[dict]:
    return [r for r in rooms if r["type"] in ("toilet", "common_toilet", "kitchen", "utility")]


def _toilet_fixtures(r: dict, doors: list[tuple[float, float]]) -> list[dict]:
    x0, y0, x1, y1 = _inset(r, 0.7)
    d = doors[0] if doors else (r["x"] + r["w"] / 2, r["y"])
    corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
    corners.sort(key=lambda p: -math.hypot(p[0] - d[0], p[1] - d[1]))
    wc, sh = corners[0], corners[1]
    near = min(corners, key=lambda p: math.hypot(p[0] - d[0], p[1] - d[1]))
    side = 0.7 if wc[0] < r["x"] + r["w"] / 2 else -0.7
    gy_dx = 0.9 if sh[0] < r["x"] + r["w"] / 2 else -0.9
    return [{"t": "WC", "x": wc[0], "y": wc[1]}, {"t": "HF", "x": wc[0] + side, "y": wc[1]},
            {"t": "SH", "x": sh[0], "y": sh[1]}, {"t": "GY", "x": sh[0] + gy_dx, "y": sh[1]},
            {"t": "WB", "x": near[0], "y": near[1]}, {"t": "FD", "x": (x0 + x1) / 2, "y": (y0 + y1) / 2}]


def _plen(pts) -> float:
    return sum(abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))


def plumbing(plan: dict, opts: dict | None = None) -> dict:
    o = norm_opts(opts)
    b = plan["building"]
    nlev = len(plan["levels"])
    riser_dia = '3/4"' if nlev <= 2 else '1"'
    floors, totals, schedule = [], {}, []
    ground_stacks: list[dict] = []
    issues: list[str] = []
    units = len({r.get("unit") for lv in plan["levels"] for r in lv["rooms"] if r.get("unit")}) or 1
    persons = o["persons"] or PERSONS_PER_HOUSE * units
    for li, lv in enumerate(plan["levels"]):
        doors = _doors(lv)
        fx, pipes, valves, ics, stacks = [], [], [], [], []
        groups = []          # (room, fixtures, soil-point)
        for r in _wet(lv["rooms"]):
            if r["type"] in ("toilet", "common_toilet"):
                fr = _toilet_fixtures(r, doors.get(r["id"], []))
                for f in fr:
                    f["room"] = r["name"]
                groups.append((r, fr, next(f for f in fr if f["t"] == "WC")))
            elif r["type"] == "kitchen":
                x0, y0, x1, y1 = _inset(r, 0.7)
                d = (doors.get(r["id"]) or [(r["x"], r["y"])])[0]
                far = max([(x0, y0), (x1, y0), (x0, y1), (x1, y1)], key=lambda p: math.hypot(p[0] - d[0], p[1] - d[1]))
                fr = [{"t": "SK", "x": far[0], "y": far[1]}, {"t": "RO", "x": far[0] + (0.9 if far[0] < r["x"] + r["w"] / 2 else -0.9), "y": far[1]}]
                if not any(q["type"] == "utility" for q in lv["rooms"]):
                    fr.append({"t": "WM", "x": far[0], "y": far[1] + (-1.2 if far[1] > r["y"] + r["d"] / 2 else 1.2)})
                for f in fr:
                    f["room"] = r["name"]
                groups.append((r, fr, fr[0]))
            else:
                x0, y0, x1, y1 = _inset(r, 0.6)
                fr = [{"t": "WM", "x": x0, "y": y0, "room": r["name"]}, {"t": "FD", "x": (x0 + x1) / 2, "y": (y0 + y1) / 2, "room": r["name"]}]
                groups.append((r, fr, fr[0]))
        if li == 0:
            dn = next((r for r in lv["rooms"] if r["type"] == "dining"), None) or next((r for r in lv["rooms"] if r["type"] == "hall"), None)
            if dn:
                f = {"t": "WB", "x": dn["x"] + dn["w"] - 0.8, "y": dn["y"] + 0.8, "room": dn["name"] + " (wash area)"}
                groups.append((dn, [f], f))
            for pk in (r for r in lv["rooms"] if r["type"] == "parking"):
                groups.append((pk, [{"t": "TP", "x": pk["x"] + 0.5, "y": pk["y"] + pk["d"] - 0.6, "room": pk["name"]}], None))
        for r, fr, soil in groups:
            fx += fr
        # supply riser beside the first wet fixture of this floor
        riser = None
        if fx:
            first = next((f for f in fx if f["t"] in ("WC", "SK")), fx[0])
            rx, ry = first["x"] + (0.8 if first["x"] < b["w"] / 2 else -0.8), first["y"]
            riser = {"x": rx, "y": ry, "dia": riser_dia}
        if riser:
            ys = [f["y"] for f in fx if f["t"] != "FD"] + [riser["y"]]
            if max(ys) - min(ys) > 0.5:
                pipes.append({"kind": "cold", "size": riser_dia, "pts": [(riser["x"], min(ys)), (riser["x"], max(ys))]})
        for r, fr, soil in groups:
            if riser:
                rx, ry = riser["x"], riser["y"]
                # stop-cock where the branch enters the room
                f0 = fr[0]
                edge = r["x"] if rx < r["x"] else (r["x"] + r["w"] if rx > r["x"] + r["w"] else rx + (1.2 if f0["x"] > rx else -1.2))
                valves.append({"x": edge, "y": f0["y"], "room": r["name"]})
                for f in fr:
                    if f["t"] == "FD":
                        continue
                    pipes.append({"kind": "cold", "size": '1/2"', "pts": [(rx, f["y"]), (f["x"], f["y"])]})
            gy = next((f for f in fr if f["t"] == "GY"), None)
            if gy:
                for f in fr:
                    if f["t"] in ("SH", "WB"):
                        pipes.append({"kind": "hot", "size": '1/2"', "pts": [(gy["x"], gy["y"]), (gy["x"], f["y"]), (f["x"], f["y"])]})
            # drains
            if soil is not None:
                sx, sy = soil["x"], soil["y"]
                for f in fr:
                    if f is soil or FIXTURE_SPEC[f["t"]][1] == 0:
                        continue
                    sz = FIXTURE_SPEC[f["t"]][1]
                    pipes.append({"kind": "waste", "size": f"{sz} mm", "pts": [(f["x"], f["y"]), (sx, f["y"]), (sx, sy)]})
                sides = [(sx, 0.0), (sx, b["d"]), (0.0, sy), (b["w"], sy)]
                tx, ty = min(sides, key=lambda s_: abs(s_[0] - sx) + abs(s_[1] - sy))
                big = soil["t"] == "WC"
                if li == 0:
                    ex = 2.0
                    icx, icy = (tx + (ex if tx >= b["w"] else -ex if tx <= 0 else 0), ty + (ex if ty >= b["d"] else -ex if ty <= 0 else 0))
                    pipes.append({"kind": "soil" if big else "waste", "size": "110 mm" if big else "50 mm",
                                  "pts": [(sx, sy), (tx, ty), (icx, icy)]})
                    ics.append({"x": icx, "y": icy, "room": r["name"]})
                stk = {"x": sx, "y": sy, "room": r["name"], "t": soil["t"]}
                if soil["t"] == "WC":
                    if li == 0:
                        stk["id"] = f"SS{len(ground_stacks) + 1}"
                        ground_stacks.append(stk)
                    else:
                        near = min(ground_stacks, key=lambda g: abs(g["x"] - sx) + abs(g["y"] - sy), default=None)
                        if near and abs(near["x"] - sx) < 4.5 and abs(near["y"] - sy) < 4.5:
                            stk["id"] = near["id"]
                        else:
                            stk["id"] = f"SS{len(ground_stacks) + 1}"
                            issues.append(f"{lv['name']}: the WC in {r['name']} is not above a ground-floor toilet – the soil pipe must be boxed "
                                          f"through the ceiling below. Align the toilets one above the other if you can.")
                            ground_stacks.append(stk)
                stacks.append(stk)
        for f in fx:
            totals[f["t"]] = totals.get(f["t"], 0) + 1
        for r, fr, soil in groups:
            cnt: dict = {}
            for f in fr:
                cnt[f["t"]] = cnt.get(f["t"], 0) + 1
            schedule.append({"floor": lv["name"], "room": r["name"], "fixtures": cnt})
        ln = {k: round(sum(_plen(p["pts"]) for p in pipes if p["kind"] == k), 1) for k in ("cold", "hot", "soil", "waste")}
        floors.append({"level": li, "name": lv["name"], "fixtures": fx, "pipes": pipes, "riser": riser, "stacks": stacks, "valves": valves,
                       "ics": ics, "lengths": ln, "supply_ft": round(ln["cold"] + ln["hot"], 1), "drain_ft": round(ln["soil"] + ln["waste"], 1)})
    day = persons * o["lpcd"]
    oht = o["oht_l"] or max(1000.0, _round_up(day * 0.5, 500))
    sump = o["sump_l"] or max(1000.0, _round_up(day * 1.5, 500))
    return {"floors": floors, "totals": totals, "labels": FIXTURE_LABEL, "issues": issues, "schedule": schedule, "spec": FIXTURE_SPEC,
            "riser_dia": riser_dia, "stack_ids": sorted({s["id"] for s in ground_stacks}),
            "water": {"persons": persons, "lpcd": o["lpcd"], "daily_l": day, "oht_l": oht, "sump_l": sump, "pump_kw": o["pump_kw"]},
            "options": o}


def plumbing_notes(p: dict, plan: dict) -> list[str]:
    w = p["water"]
    n = [f"Water demand about {w['daily_l']:,.0f} L/day ({w['persons']:g} persons x {w['lpcd']:g} litres). Overhead tank {w['oht_l']:,.0f} L "
         f"(on the roof above the toilets) and underground sump {w['sump_l']:,.0f} L. Values are editable on this page.",
         f"Supply: CPVC / UPVC; {p['riser_dia']} riser from the tank, 1/2\" branches to the fixtures; hot line (geyser to shower and basin) kept apart "
         "from the cold line and insulated; a stop-cock at the entry of every toilet and at the kitchen.",
         "Drainage: WC soil pipe 110 mm, basin 40 mm, shower / sink / washing-machine 50 mm, floor drain 75 mm; every fixture with a trap; "
         "each soil stack 110 mm carried above the roof as a vent with a cowl. Slope 1:40 for 110 mm and 1:60 for 50 – 75 mm.",
         "Inspection chamber (IC) at every change of direction and just outside the house wall; the septic tank / sewer connection is decided by "
         "the local body – keep it away from the sump and borewell (at least 7 m) and outside the car path.",
         "Toilet floor sunk 1.5 – 2 inches below the passage with a slope to the floor drain; waterproofing before tiling. "
         "Keep the pipes of the floors in one shaft so repair never needs wall cutting.",
         "Suggested schematic layout only – pipe routes are drawn straight for clarity; the plumber sets the real routes on site."]
    n += p["issues"]
    return n


# ---------------------------------------------------------------- PDF
def _pdf_safe(t: str) -> str:
    for k, v in {"²": "2", "³": "3", "≈": "~", "₹": "Rs.", "≤": "<=", "≥": ">=", "–": "-", "×": "x", "·": "-", "Ø": "ph", "’": "'"}.items():
        t = str(t).replace(k, v)
    return t


def to_pdf(plan: dict, project: dict, kind: str = "both", opts: dict | None = None) -> bytes:
    """kind: electrical | plumbing | both. Per floor drawing + schedules + single-line / riser diagram + suggestions."""
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
    E = electrical(plan, opts) if "electrical" in kinds else None
    P = plumbing(plan, opts) if "plumbing" in kinds else None
    margin = 14 * mm
    dw, dh = W * 0.60 - margin - 12 * mm, H - 2 * margin - 36 * mm
    sc = min(dw / b["w"], dh / b["d"])
    ox, oy = margin + 12 * mm, margin + 16 * mm
    HX = colors.HexColor
    INK, MUTE = HX("#0F172A"), HX("#475569")
    st = {"first": True}

    def Pt(x, y):
        return ox + x * sc, oy + y * sc

    def newpage():
        if not st["first"]:
            lh.later_page(c, W)
            c.showPage()
        st["first"] = False

    def head(title: str, sub: str = ""):
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(INK)
        c.drawString(margin, H - margin, _pdf_safe(f"{project.get('name', '')} - {title}"))
        if sub:
            c.setFont("Helvetica", 8.5)
            c.setFillColor(MUTE)
            c.drawString(margin, H - margin - 12, _pdf_safe(sub))

    def base(lv: dict, title: str):
        head(f"{title} - {lv['name']}", f"{plan.get('facing', '').title()} facing - suggested schematic layout, not to scale for runs")
        for w in lv.get("walls", []):
            t = THK.get(w["kind"], 0.5) * sc
            c.setStrokeColor(HX("#1E293B" if w["kind"] == "ext" else "#64748B"))
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
        c.setFont("Helvetica", 6.2)
        c.setFillColor(HX("#94A3B8"))
        for r in lv["rooms"]:
            x, y = Pt(r["x"] + r["w"] / 2, r["y"] + r["d"] - 0.9)
            c.drawCentredString(x, y, _pdf_safe(r["name"][:22]))

    def sym(x, y, txt, col, r=3.4, tag=""):
        px, py = Pt(x, y)
        c.setFillColor(colors.white)
        c.setStrokeColor(col)
        c.setLineWidth(0.7)
        c.circle(px, py, r, fill=1)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 4.4 if len(txt) > 2 else 5.2)
        c.drawCentredString(px, py - 1.7, txt)
        if tag:
            c.setFont("Helvetica", 3.7)
            c.setFillColor(HX("#64748B"))
            c.drawCentredString(px, py - r - 4, tag)

    def legend_item(x, y, code, text, col):
        c.setFillColor(colors.white)
        c.setStrokeColor(col)
        c.circle(x + 6, y + 2, 5, fill=1)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 4.6)
        c.drawCentredString(x + 6, y + 0.2, code)
        c.setFillColor(HX("#1E293B"))
        c.setFont("Helvetica", 7.8)
        c.drawString(x + 18, y, _pdf_safe(text))

    def lines_at(x, y, rows, size=7.6, gap=10.5, bold=False):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.setFillColor(HX("#1E293B"))
        for t in rows:
            c.drawString(x, y, _pdf_safe(t))
            y -= gap
        return y

    def table(title: str, cols: list[str], widths: list[float], rows: list[list], sub: str = ""):
        """Simple paged table (A4 landscape)."""
        first = True
        i = 0
        while first or i < len(rows):
            newpage()
            head(title + ("" if first else " (continued)"), sub if first else "")
            first = False
            y = H - margin - 34
            x = margin
            c.setFillColor(HX("#E2E8F0"))
            c.rect(margin - 2, y - 4, sum(widths) + 4, 14, fill=1, stroke=0)
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 8)
            for cn, wd in zip(cols, widths):
                c.drawString(x, y, _pdf_safe(cn))
                x += wd
            y -= 16
            c.setFont("Helvetica", 7.8)
            while i < len(rows) and y > 70:
                x = margin
                if i % 2:
                    c.setFillColor(HX("#F8FAFC"))
                    c.rect(margin - 2, y - 3, sum(widths) + 4, 11.5, fill=1, stroke=0)
                c.setFillColor(HX("#1E293B"))
                for cell, wd in zip(rows[i], widths):
                    s = _pdf_safe(cell)
                    while c.stringWidth(s, "Helvetica", 7.8) > wd - 4 and len(s) > 3:
                        s = s[:-2]
                    c.drawString(x, y, s)
                    x += wd
                y -= 12
                i += 1
        return

    def text_page(title: str, blocks: list[tuple[str, list[str]]]):
        newpage()
        head(title)
        y = H - margin - 28
        for hd, rows in blocks:
            c.setFont("Helvetica-Bold", 9.5)
            c.setFillColor(HX("#1E3A8A"))
            c.drawString(margin, y, _pdf_safe(hd))
            y -= 13
            c.setFont("Helvetica", 8.4)
            c.setFillColor(HX("#1E293B"))
            for r_ in rows:
                words, line, first = _pdf_safe(r_).split(), "", True
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

    def box(x, y, w, h, txt, fill="#FFFFFF", edge="#1E293B", size=7.5, bold=False):
        c.setFillColor(HX(fill))
        c.setStrokeColor(HX(edge))
        c.setLineWidth(0.9)
        c.rect(x, y, w, h, fill=1)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        parts = _pdf_safe(txt).split("\n")
        yy = y + h / 2 + (len(parts) - 1) * 4.2 - 2.6
        for p_ in parts:
            c.drawCentredString(x + w / 2, yy, p_)
            yy -= 8.4

    elec_col = HX("#B45309")
    ph_col = {"R": HX("#DC2626"), "Y": HX("#CA8A04"), "B": HX("#2563EB")}
    cold_c, hot_c, soil_c, waste_c = HX("#1D4ED8"), HX("#DC2626"), HX("#7C2D12"), HX("#A16207")

    # ============================================================ ELECTRICAL
    if E:
        m = E["main"]
        three = m["phase"] == "three-phase"
        for fl in E["floors"]:
            lv = plan["levels"][fl["level"]]
            newpage()
            base(lv, "ELECTRICAL LAYOUT")
            dbp = fl["db"]
            # wiring: home-run conduit from the DB to every switch board, and switch / power legs inside each room
            for rm in fl["rooms"]:
                sw = next((p for p in rm["points"] if p["t"] == "SW"), None)
                if not sw:
                    continue
                c.setStrokeColor(HX("#FDBA74"))
                c.setLineWidth(0.7)
                a, bb, cc_ = Pt(dbp["x"], dbp["y"]), Pt(sw["x"], dbp["y"]), Pt(sw["x"], sw["y"])
                c.line(a[0], a[1], bb[0], bb[1])
                c.line(bb[0], bb[1], cc_[0], cc_[1])
                for p in rm["points"]:
                    if p["t"] == "SW":
                        continue
                    pa, pb = Pt(sw["x"], sw["y"]), Pt(p["x"], p["y"])
                    ctl = p["t"] in ("L", "F", "EX", "BL")
                    c.setStrokeColor(HX("#CBD5E1") if ctl else HX("#86EFAC"))
                    c.setLineWidth(0.35)
                    c.setDash(1.5, 1.5) if ctl else c.setDash()
                    c.line(pa[0], pa[1], pb[0], pb[1])
                    c.setDash()
            for rm in fl["rooms"]:
                for p in rm["points"]:
                    if p["t"] == "SW":
                        px, py = Pt(p["x"], p["y"])
                        c.setFillColor(HX("#334155"))
                        c.rect(px - 2.4, py - 2.4, 4.8, 4.8, fill=1)
                        c.setFont("Helvetica-Bold", 4)
                        c.setFillColor(HX("#0F172A"))
                        c.drawString(px + 3.5, py + 1, p.get("sb", ""))
                    else:
                        sym(p["x"], p["y"], SYM[p["t"]], ph_col.get(next((k_["phase"] for k_ in fl["circuits"] if k_["id"] == p.get("ckt")), "R"), elec_col)
                            if three else elec_col, tag=p.get("ckt", ""))
            dx, dy = Pt(dbp["x"], dbp["y"])
            c.setFillColor(HX("#DC2626"))
            c.rect(dx - 7, dy - 5, 14, 10, fill=1)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 5)
            c.drawCentredString(dx, dy - 1.8, dbp["name"])
            # right panel
            X = W * 0.66
            y = H - margin - 6
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(X, y, f"{lv['name']} - symbols")
            y -= 16
            for k in [k for k in LABEL if fl["counts"].get(k)]:
                legend_item(X, y, SYM[k], f"{LABEL[k]}  x {fl['counts'][k]}", elec_col)
                y -= 12.5
            y -= 4
            y = lines_at(X, y, ["[ ] SBx  Switch board (switches, regulators, sockets)", f"{dbp['name']}  Distribution board ({dbp['type']}, {dbp['ways']} way)",
                                "Orange line = DB to switch-board conduit", "Grey dashed = switch / light legs; green = socket legs",
                                "Small text under a symbol = circuit number"], 7.4, 10)
            y -= 6
            c.setFont("Helvetica-Bold", 9)
            c.drawString(X, y, "Supply and load")
            y -= 12
            fc = [k for k in fl["circuits"] if k["id"] != "PUMP"]
            rows = [f"Supply: {m['phase']} ({m['poles']}, {m['volt']} V)", f"Main MCB / MCCB: {m['incomer_a']} A, cable {m['wire_mm2']:g} mm2 Cu",
                    f"This floor: {len(fl['circuits'])} circuits, {fl['db']['connected_kw']} kW connected",
                    f"{dbp['name']} incomer {dbp['incomer_a']} A + 30 mA RCCB, 2 spare ways"]
            if three:
                rows.append("Phase load (W): " + "  ".join(f"{p}={int(v)}" for p, v in m["balance_w"].items()))
                rows.append("Symbol colour = phase: R red, Y amber, B blue")
            lines_at(X, y, rows, 7.6)
            lh.later_page(c, W)
        # DB schedule per floor
        for fl in E["floors"]:
            rows = [[k["id"], k["name"], ", ".join(k["rooms"])[:46], str(k["points"]), str(k["load_w"]), f"{k['mcb']} A", f"{k['wire']:g}", k["phase"] if three else "1ph"]
                    for k in fl["circuits"]]
            table(f"DB SCHEDULE - {fl['db']['name']} ({fl['name']})", ["Ckt", "Circuit", "Rooms", "Points", "Load W", "MCB", "Wire mm2", "Phase"],
                  [48, 170, 250, 42, 52, 42, 52, 44], rows,
                  f"{fl['db']['type']} board, {fl['db']['ways']} ways, incomer {fl['db']['incomer_a']} A + 30 mA RCCB; copper wire PVC conduit")
        # switch board schedule
        rows = [[bd["id"], f"{fl['name']} - {bd['room']}", str(bd["switches"]), str(bd["regulators"]), str(bd["s5"]), str(bd["s15"]), str(bd["tv"])]
                for fl in E["floors"] for bd in fl["boards"]]
        table("SWITCH BOARD SCHEDULE", ["Board", "Floor / room", "Switches", "Fan regulators", "5A sockets", "15A sockets", "TV / data"],
              [60, 280, 60, 80, 70, 70, 60], rows, "Modular boards; mounting heights in the suggestions page")
        # single line diagram
        newpage()
        head("SINGLE-LINE DIAGRAM", f"{m['phase']} supply - suggested; final design by the licensed electrician")
        cx = W / 2
        y0 = H - margin - 52
        box(cx - 90, y0 - 4, 180, 24, f"TNPDCL service / energy meter\n{m['phase']}, {m['volt']} V", "#FEF3C7")
        c.line(cx, y0 - 4, cx, y0 - 22)
        box(cx - 90, y0 - 46, 180, 24, f"Main {m['poles']} MCB / MCCB {m['incomer_a']} A + isolator", "#FEE2E2")
        c.line(cx, y0 - 46, cx, y0 - 62)
        box(cx - 110, y0 - 88, 220, 26, f"RCCB {m['poles']} {m['rccb_a']} A, 30 mA + surge protector", "#DBEAFE")
        c.line(cx, y0 - 88, cx, y0 - 104)
        c.setLineWidth(2)
        n_fl = len(E["floors"])
        span = min(W - 2 * margin - 160, 230 * n_fl)
        xs = [cx - span / 2 + span * (i + 0.5) / n_fl for i in range(n_fl)]
        c.line(xs[0], y0 - 104, xs[-1], y0 - 104)
        c.setLineWidth(0.9)
        for fl, x in zip(E["floors"], xs):
            c.line(x, y0 - 104, x, y0 - 128)
            c.setFont("Helvetica", 6.5)
            c.setFillColor(MUTE)
            c.drawString(x + 3, y0 - 120, "sub-main " + ("6 mm2" if fl["level"] else f"{m['wire_mm2']:g} mm2"))
            box(x - 70, y0 - 156, 140, 28, f"{fl['db']['name']} ({fl['db']['type']})\nincomer {fl['db']['incomer_a']} A + RCCB", "#ECFCCB")
            groups: dict = {}
            for k in fl["circuits"]:
                key = k["name"].split(" (")[0]
                groups.setdefault(key, []).append(k)
            yy = y0 - 168
            c.setFont("Helvetica", 6.6)
            c.setFillColor(HX("#1E293B"))
            for nm, ks in groups.items():
                ph = "/".join(sorted({k["phase"] for k in ks})) if three else ""
                c.drawString(x - 68, yy, _pdf_safe(f"{len(ks)} x {nm[:24]}  {ks[0]['mcb']}A {ks[0]['wire']:g}mm2 {ph}"))
                yy -= 9
        ey = 78
        c.setStrokeColor(HX("#15803D"))
        c.setLineWidth(1.2)
        c.line(cx + 140, y0 - 30, cx + 200, y0 - 30)
        c.line(cx + 200, y0 - 30, cx + 200, ey + 14)
        for i in range(3):
            c.line(cx + 188 + i * 4, ey + 14 - i * 5, cx + 212 - i * 4, ey + 14 - i * 5)
        c.setFont("Helvetica", 7)
        c.setFillColor(HX("#15803D"))
        c.drawString(cx + 150, ey - 8, "Earth pit (GI / copper plate) - earth resistance below 5 ohm")

    # ============================================================ PLUMBING
    if P:
        for fl in P["floors"]:
            lv = plan["levels"][fl["level"]]
            if not fl["fixtures"]:
                continue
            newpage()
            base(lv, "PLUMBING LAYOUT")
            style = {"cold": (cold_c, 0.9, (3, 2)), "hot": (hot_c, 0.9, (3, 2)), "soil": (soil_c, 1.9, None), "waste": (waste_c, 1.1, None)}
            for pp in fl["pipes"]:
                col, wd, dash = style[pp["kind"]]
                c.setStrokeColor(col)
                c.setLineWidth(wd)
                if dash:
                    c.setDash(*dash)
                pts = [Pt(*q) for q in pp["pts"]]
                for a, b2 in zip(pts, pts[1:]):
                    c.line(a[0], a[1], b2[0], b2[1])
                c.setDash()
                # size label on the longest straight part + slope arrow on drains
                seg = max(zip(pts, pts[1:]), key=lambda s_: abs(s_[1][0] - s_[0][0]) + abs(s_[1][1] - s_[0][1]))
                mx, my = (seg[0][0] + seg[1][0]) / 2, (seg[0][1] + seg[1][1]) / 2
                if abs(seg[1][0] - seg[0][0]) + abs(seg[1][1] - seg[0][1]) > 14:
                    c.setFont("Helvetica", 4.4)
                    c.setFillColor(col)
                    c.drawString(mx + 1.5, my + 1.5, _pdf_safe(pp["size"]))
                    if pp["kind"] in ("soil", "waste"):
                        dx_, dy_ = seg[1][0] - seg[0][0], seg[1][1] - seg[0][1]
                        ln = math.hypot(dx_, dy_) or 1
                        ux, uy = dx_ / ln, dy_ / ln
                        c.setLineWidth(0.8)
                        c.line(mx, my, mx + ux * 5, my + uy * 5)
                        c.line(mx + ux * 5, my + uy * 5, mx + ux * 2.8 - uy * 1.8, my + uy * 2.8 + ux * 1.8)
                        c.line(mx + ux * 5, my + uy * 5, mx + ux * 2.8 + uy * 1.8, my + uy * 2.8 - ux * 1.8)
            for v in fl["valves"]:
                vx, vy = Pt(v["x"], v["y"])
                c.setFillColor(colors.white)
                c.setStrokeColor(cold_c)
                c.setLineWidth(0.8)
                p_ = c.beginPath()
                p_.moveTo(vx - 3, vy - 2.4)
                p_.lineTo(vx + 3, vy + 2.4)
                p_.lineTo(vx + 3, vy - 2.4)
                p_.lineTo(vx - 3, vy + 2.4)
                p_.close()
                c.drawPath(p_, fill=1)
            for f in fl["fixtures"]:
                sym(f["x"], f["y"], f["t"], HX("#7C2D12") if f["t"] == "FD" else (hot_c if f["t"] == "GY" else cold_c))
            for ic in fl["ics"]:
                ix, iy = Pt(ic["x"], ic["y"])
                c.setFillColor(HX("#FEF3C7"))
                c.setStrokeColor(soil_c)
                c.rect(ix - 4, iy - 4, 8, 8, fill=1)
                c.setFillColor(soil_c)
                c.setFont("Helvetica-Bold", 4.4)
                c.drawCentredString(ix, iy - 1.6, "IC")
            if fl["riser"]:
                rx, ry = Pt(fl["riser"]["x"], fl["riser"]["y"])
                c.setFillColor(cold_c)
                c.circle(rx, ry, 4.6, fill=1)
                c.setFillColor(colors.white)
                c.setFont("Helvetica-Bold", 5)
                c.drawCentredString(rx, ry - 1.8, "R")
                c.setFillColor(cold_c)
                c.setFont("Helvetica", 4.6)
                c.drawString(rx + 5.5, ry + 2, f"{fl['riser']['dia']} riser")
            for s_ in fl["stacks"]:
                if s_["t"] == "WC":
                    sx, sy = Pt(s_["x"], s_["y"])
                    c.setStrokeColor(soil_c)
                    c.setLineWidth(1.2)
                    c.circle(sx, sy, 5.8)
                    c.setFillColor(soil_c)
                    c.setFont("Helvetica-Bold", 4.6)
                    c.drawString(sx + 7, sy - 8, s_["id"])
            X = W * 0.66
            y = H - margin - 6
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(X, y, f"{lv['name']} - fixtures")
            y -= 16
            for k in sorted({f["t"] for f in fl["fixtures"]}):
                legend_item(X, y, k, f"{FIXTURE_LABEL[k]}  x {sum(1 for f in fl['fixtures'] if f['t'] == k)}", hot_c if k == "GY" else cold_c)
                y -= 12.5
            y -= 4
            y = lines_at(X, y, ["R   Water riser from the overhead tank", "Dashed blue = cold supply (1/2\")", "Dashed red = hot supply (geyser to shower, basin)",
                                "Thick brown = 110 mm soil line;  thin = 50 / 40 / 75 mm waste", "Ring + SS = soil stack (110 mm), vent above roof",
                                "Valve symbol = stop-cock at the toilet / kitchen entry", "IC = inspection chamber, then to septic tank / sewer",
                                "Arrow on a drain = fall of the pipe (1:40 / 1:60)"], 7.4, 10)
            y -= 6
            ln = fl["lengths"]
            lines_at(X, y, [f"Cold {ln['cold']:g} ft,  hot {ln['hot']:g} ft", f"Soil {ln['soil']:g} ft,  waste {ln['waste']:g} ft (schematic lengths on this floor)"], 7.6)
            lh.later_page(c, W)
        # fixture schedule
        rows = []
        for s_ in P["schedule"]:
            for t_, n_ in s_["fixtures"].items():
                sp = FIXTURE_SPEC[t_]
                rows.append([s_["floor"], s_["room"][:30], f"{FIXTURE_LABEL[t_][:34]}", str(n_), sp[0] or "-", f"{sp[1]} mm" if sp[1] else "-", sp[2]])
        table("PLUMBING FIXTURE AND PIPE SCHEDULE", ["Floor", "Room", "Fixture", "Nos", "Supply", "Waste", "Trap"], [78, 170, 215, 36, 46, 56, 130], rows,
              "Supply 1/2\" CPVC / UPVC branches; waste lines in UPVC / SWR")
        # riser diagram
        newpage()
        head("WATER SUPPLY AND DRAINAGE - RISER DIAGRAM (schematic, not to scale)", "")
        w_ = P["water"]
        nl = len(P["floors"])
        gx, top = 150, H - margin - 70
        fh = min(110, (top - 215) / max(1, nl))
        ground_y = 165
        roof_y = ground_y + fh * nl
        c.setStrokeColor(HX("#64748B"))
        c.setLineWidth(1.4)
        c.line(gx - 60, ground_y, gx + 330, ground_y)
        for i in range(nl + 1):
            c.setLineWidth(1.1 if i else 1.8)
            c.line(gx - 40, ground_y + i * fh, gx + 190, ground_y + i * fh)
        c.setFont("Helvetica", 7)
        c.setFillColor(MUTE)
        for i, fl in enumerate(P["floors"]):
            c.drawString(gx - 120, ground_y + i * fh + fh / 2, _pdf_safe(fl["name"]))
        box(gx + 30, roof_y + 6, 110, 26, f"Overhead tank\n{w_['oht_l']:,.0f} L", "#DBEAFE", "#1D4ED8")
        c.setStrokeColor(cold_c)
        c.setLineWidth(2)
        rxx = gx + 60
        c.line(rxx, roof_y + 6, rxx, ground_y + 6)
        c.setFont("Helvetica", 6.8)
        c.setFillColor(cold_c)
        c.drawString(rxx + 4, roof_y - 10, f"{P['riser_dia']} down-take (cold)")
        for i, fl in enumerate(P["floors"]):
            yy = ground_y + i * fh + fh * 0.45
            c.setLineWidth(1)
            c.line(rxx, yy, rxx + 55, yy)
            c.drawString(rxx + 58, yy - 2, _pdf_safe(f"1/2\" branches - {sum(1 for f in fl['fixtures'] if f['t'] != 'FD')} fixtures"))
            c.setFillColor(colors.white)
            c.setStrokeColor(cold_c)
            c.rect(rxx + 8, yy - 3, 6, 6, fill=1)
            c.setFillColor(cold_c)
        sx = gx + 230
        c.setStrokeColor(soil_c)
        c.setLineWidth(3)
        c.line(sx, roof_y + 40, sx, ground_y - 14)
        c.setFillColor(soil_c)
        c.setFont("Helvetica", 6.8)
        c.drawString(sx + 5, roof_y + 36, "Vent pipe with cowl above the roof")
        c.drawString(sx + 5, roof_y - 10, "110 mm soil stack (" + ", ".join(P["stack_ids"][:4]) + ")")
        c.setLineWidth(1.6)
        c.line(sx, ground_y - 14, sx + 120, ground_y - 14)
        box(sx + 120, ground_y - 22, 34, 16, "IC", "#FEF3C7", "#7C2D12")
        c.line(sx + 154, ground_y - 14, sx + 190, ground_y - 14)
        box(sx + 190, ground_y - 40, 90, 34, "Septic tank\n(or sewer)", "#FEE2E2", "#7C2D12")
        c.line(sx + 280, ground_y - 22, sx + 305, ground_y - 22)
        box(sx + 305, ground_y - 40, 70, 34, "Soak pit", "#ECFCCB", "#15803D")
        box(gx - 120, ground_y - 62, 120, 34, f"Underground sump\n{w_['sump_l']:,.0f} L", "#DBEAFE", "#1D4ED8")
        c.setStrokeColor(cold_c)
        c.setLineWidth(1.6)
        c.line(gx - 60, ground_y - 28, gx - 60, ground_y - 12)
        c.line(gx - 60, ground_y - 12, gx + 8, ground_y - 12)
        box(gx + 8, ground_y - 22, 52, 20, f"Pump\n{w_['pump_kw']:g} kW", "#FEE2E2", "#B91C1C")
        c.line(gx + 34, ground_y - 2, gx + 34, ground_y)
        c.setStrokeColor(cold_c)
        c.line(gx + 60, ground_y - 12, gx - 70, ground_y - 12) if False else None
        c.setFillColor(MUTE)
        c.setFont("Helvetica", 7)
        c.drawString(margin, 62, "Rising main from the pump to the overhead tank runs in the same shaft as the down-take; non-return valve and gate valve after the pump.")
    # ============================================================ suggestions
    sections: list[tuple[str, list[str]]] = []
    if E:
        sections.append(("ELECTRICAL - total points (whole house)", [f"{LABEL[k]}: {v}" for k, v in E["totals"].items()]))
        sections.append(("ELECTRICAL - suggestions", electrical_notes(E, plan)))
    if P:
        sections.append(("PLUMBING - total fixtures (whole house)", [f"{FIXTURE_LABEL[k]}: {v}" for k, v in P["totals"].items()]
                         + [f"Approx. supply pipe {sum(f['supply_ft'] for f in P['floors']):g} ft, drain / soil pipe {sum(f['drain_ft'] for f in P['floors']):g} ft "
                            "(schematic lengths + 15 % for bends and drops)"]))
        sections.append(("PLUMBING - suggestions", plumbing_notes(P, plan)))
    text_page("Schedule and suggestions", sections)
    lh.later_page(c, W)
    lh.seal_box(c, W, 56)
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------- DXF (layers per service)
def to_dxf(plan: dict, project: dict, kind: str = "both", opts: dict | None = None) -> bytes:
    from .exports import THK, _dxf_line, _dxf_rect, _dxf_text
    out = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "2", "0", "ENDSEC",
           "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", "14"]
    layers = {"WALL": 7, "DOOR": 1, "ROOM_NAME": 8, "ELEC_POINTS": 30, "ELEC_DB": 1, "ELEC_WIRING": 40, "ELEC_TAG": 8, "PLUMB_COLD": 5,
              "PLUMB_HOT": 1, "PLUMB_SOIL": 34, "PLUMB_WASTE": 42, "PLUMB_FIXTURE": 150, "PLUMB_IC": 34, "PLUMB_TEXT": 8, "TEXT": 7}
    for name, col in layers.items():
        out += ["0", "LAYER", "2", name, "70", "0", "62", str(col), "6", "CONTINUOUS"]
    out += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    b = plan["building"]
    kinds = ["electrical", "plumbing"] if kind == "both" else [kind]
    E = electrical(plan, opts) if "electrical" in kinds else None
    P = plumbing(plan, opts) if "plumbing" in kinds else None
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
                d = fl["db"]
                for rm in fl["rooms"]:
                    sw = next((p for p in rm["points"] if p["t"] == "SW"), None)
                    if sw:
                        _dxf_line(out, "ELEC_WIRING", ox + d["x"], d["y"], ox + sw["x"], d["y"])
                        _dxf_line(out, "ELEC_WIRING", ox + sw["x"], d["y"], ox + sw["x"], sw["y"])
                    for p in rm["points"]:
                        _dxf_rect(out, "ELEC_POINTS", ox + p["x"] - 0.25, p["y"] - 0.25, 0.5, 0.5)
                        _dxf_text(out, "ELEC_POINTS", ox + p["x"], p["y"] + 0.4, 0.3, p["t"] if p["t"] != "SW" else p.get("sb", "SB"))
                        if p.get("ckt"):
                            _dxf_text(out, "ELEC_TAG", ox + p["x"], p["y"] - 0.7, 0.22, p["ckt"])
                        if sw and p is not sw:
                            _dxf_line(out, "ELEC_WIRING", ox + sw["x"], sw["y"], ox + p["x"], p["y"])
                _dxf_rect(out, "ELEC_DB", ox + d["x"] - 0.6, d["y"] - 0.45, 1.2, 0.9)
                _dxf_text(out, "ELEC_DB", ox + d["x"], d["y"] + 0.8, 0.4, d["name"])
            if k == "plumbing" and P:
                fl = P["floors"][li]
                lay = {"cold": "PLUMB_COLD", "hot": "PLUMB_HOT", "soil": "PLUMB_SOIL", "waste": "PLUMB_WASTE"}
                for pp in fl["pipes"]:
                    for a, b2 in zip(pp["pts"], pp["pts"][1:]):
                        _dxf_line(out, lay[pp["kind"]], ox + a[0], a[1], ox + b2[0], b2[1])
                    a, b2 = pp["pts"][0], pp["pts"][-1]
                    _dxf_text(out, "PLUMB_TEXT", ox + (a[0] + b2[0]) / 2, (a[1] + b2[1]) / 2 + 0.4, 0.25, pp["size"])
                for f in fl["fixtures"]:
                    _dxf_rect(out, "PLUMB_FIXTURE", ox + f["x"] - 0.3, f["y"] - 0.3, 0.6, 0.6)
                    _dxf_text(out, "PLUMB_FIXTURE", ox + f["x"], f["y"] + 0.5, 0.3, f["t"])
                for ic in fl["ics"]:
                    _dxf_rect(out, "PLUMB_IC", ox + ic["x"] - 0.5, ic["y"] - 0.5, 1.0, 1.0)
                    _dxf_text(out, "PLUMB_IC", ox + ic["x"], ic["y"] + 0.8, 0.3, "IC")
                for s_ in fl["stacks"]:
                    if s_["t"] == "WC":
                        _dxf_text(out, "PLUMB_TEXT", ox + s_["x"], s_["y"] - 1.0, 0.3, s_["id"])
    out += ["0", "ENDSEC", "0", "EOF"]
    return ("\r\n".join(out) + "\r\n").encode("ascii", "replace")
