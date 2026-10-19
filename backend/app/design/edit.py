"""Edited plans: clean what the 2D editor sends, re-derive walls/openings, compare two versions."""
from __future__ import annotations

from .geometry import add_openings
from .layout import NAMES

ROOM_TYPES = {"bedroom", "toilet", "common_toilet", "kitchen", "hall", "lounge", "dining", "pooja", "stair",
              "parking", "passage", "dress", "terrace", "utility", "store", "sitout", "balcony"}
EXTRA_NAMES = {"utility": "Utility", "store": "Store", "sitout": "Sit-out", "balcony": "Balcony"}


def _snap(v) -> float:
    return round(float(v) * 4) / 4


class PlanError(ValueError):
    pass


def clean_plan(plan: dict) -> dict:
    """Validate and normalise a plan coming from the browser. Raises PlanError with a clear message."""
    if not isinstance(plan, dict) or "levels" not in plan or "building" not in plan:
        raise PlanError("Plan data is incomplete – generate the plan again.")
    b = plan["building"]
    bw, bd = float(b["w"]), float(b["d"])
    levels = plan["levels"]
    if not levels:
        raise PlanError("The plan has no floors.")
    for lv in levels:
        rooms = []
        seen = set()
        for i, r in enumerate(lv.get("rooms") or []):
            t = str(r.get("type") or "")
            if t not in ROOM_TYPES:
                raise PlanError(f"Unknown room type '{t}'.")
            w, d = _snap(r.get("w", 0)), _snap(r.get("d", 0))
            if w < 2 or d < 2:
                raise PlanError(f"{lv.get('name')}: {r.get('name') or t} is smaller than 2 ft.")
            rid = str(r.get("id") or f"{t}_{i + 1}")
            while rid in seen:
                rid += "x"
            seen.add(rid)
            room = {"id": rid, "type": t, "name": str(r.get("name") or NAMES.get(t) or EXTRA_NAMES.get(t, t))[:40],
                    "x": _snap(r.get("x", 0)), "y": _snap(r.get("y", 0)), "w": w, "d": d}
            if r.get("parent"):
                room["parent"] = str(r["parent"])
            rooms.append(room)
        ids = {r["id"] for r in rooms}
        for r in rooms:
            if r.get("parent") and r["parent"] not in ids:
                r.pop("parent")  # parent bedroom was deleted
        lv["rooms"] = rooms
        lv["name"] = str(lv.get("name") or "Floor")[:40]
    plan["building"] = {"x": float(b.get("x", 0)), "y": float(b.get("y", 0)), "w": bw, "d": bd}
    return plan


def recompute(plan: dict) -> dict:
    plan = clean_plan(plan)
    return add_openings(plan)


def _room_key(r: dict) -> str:
    return r["id"]


def compare(a: dict, b: dict) -> dict:
    """Differences from design a (older) to design b (newer): rooms added/removed/resized per floor + totals."""
    levels = []
    na, nb = a["plan"]["levels"], b["plan"]["levels"]
    for i in range(max(len(na), len(nb))):
        la = na[i] if i < len(na) else {"name": nb[i]["name"], "rooms": []}
        lb = nb[i] if i < len(nb) else {"name": na[i]["name"], "rooms": []}
        ra = {_room_key(r): r for r in la["rooms"]}
        rb = {_room_key(r): r for r in lb["rooms"]}
        added = [{"name": r["name"], "size": f"{r['w']:g}' × {r['d']:g}'"} for k, r in rb.items() if k not in ra]
        removed = [{"name": r["name"], "size": f"{r['w']:g}' × {r['d']:g}'"} for k, r in ra.items() if k not in rb]
        changed = []
        for k, r in rb.items():
            if k in ra:
                o = ra[k]
                if (o["w"], o["d"]) != (r["w"], r["d"]):
                    changed.append({"name": r["name"], "from": f"{o['w']:g}' × {o['d']:g}'",
                                    "to": f"{r['w']:g}' × {r['d']:g}'",
                                    "area_change": round(r["w"] * r["d"] - o["w"] * o["d"], 1)})
                elif (o["x"], o["y"]) != (r["x"], r["y"]):
                    changed.append({"name": r["name"], "from": "moved", "to": f"at {r['x']:g}', {r['y']:g}'",
                                    "area_change": 0})
                elif o["name"] != r["name"]:
                    changed.append({"name": r["name"], "from": f"renamed from {o['name']}", "to": "", "area_change": 0})
        levels.append({"name": lb["name"], "added": added, "removed": removed, "changed": changed})
    sa, sb = a["plan"].get("summary", {}), b["plan"].get("summary", {})
    keys = ["builtup_sqft", "carpet_sqft", "bedrooms", "toilets", "kitchens"]
    totals = {k: {"a": sa.get(k, 0), "b": sb.get(k, 0), "change": round((sb.get(k, 0) or 0) - (sa.get(k, 0) or 0), 1)}
              for k in keys}

    def walls(p):
        s = {"ext": 0.0, "int": 0.0}
        for lv in p["levels"]:
            s["ext"] += lv["summary"]["ext_wall_ft"]
            s["int"] += lv["summary"]["int230_wall_ft"] + lv["summary"]["int115_wall_ft"]
        return s
    wa, wb = walls(a["plan"]), walls(b["plan"])
    totals["ext_wall_ft"] = {"a": round(wa["ext"], 1), "b": round(wb["ext"], 1), "change": round(wb["ext"] - wa["ext"], 1)}
    totals["int_wall_ft"] = {"a": round(wa["int"], 1), "b": round(wb["int"], 1), "change": round(wb["int"] - wa["int"], 1)}
    totals["estimate"] = {"a": a.get("estimate_total", 0), "b": b.get("estimate_total", 0),
                          "change": round((b.get("estimate_total") or 0) - (a.get("estimate_total") or 0))}
    return {"a": {"id": a["id"], "version": a["version"], "title": a["title"]},
            "b": {"id": b["id"], "version": b["version"], "title": b["title"]},
            "levels": levels, "totals": totals}
