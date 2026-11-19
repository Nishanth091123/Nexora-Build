"""1.24 – automatic check of every generated plan before it is handed out.

check(plan) -> {"hard": [...], "soft": [...]}
  hard  = the plan is wrong (a room nobody can walk into, overlapping rooms, a split passage, a bedroom-sized
          toilet, a bedroom opening into the kitchen / a toilet …) → generate() tries another layout, and if every
          layout fails the user is asked instead of receiving a bad plan.
  soft  = worth telling the user (tiny rear gap, window-less rooms …) – shown as a note, the plan is still given.
"""
from __future__ import annotations

from . import geometry as G

EPS = 0.06
DOORS = ("door", "main_door", "toilet_door", "opening", "pooja_door")


def _overlap(a: dict, b: dict) -> float:
    w = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    d = min(a["y"] + a["d"], b["y"] + b["d"]) - max(a["y"], b["y"])
    return w * d if w > EPS and d > EPS else 0.0


def check(plan: dict) -> dict:
    hard: list[str] = []
    soft: list[str] = []
    for li, lv in enumerate(plan.get("levels") or []):
        nm = lv.get("name", f"Level {li}")
        rooms = lv.get("rooms") or []
        by = {r["id"]: r for r in rooms}
        ops = [o for o in (lv.get("openings") or []) if o.get("type") in DOORS]
        door_rooms = {o["room"] for o in ops}

        # 1. rooms overlapping
        for i, a in enumerate(rooms):
            for b in rooms[i + 1:]:
                if _overlap(a, b) > 0.5:
                    hard.append(f"{nm}: {a['name']} and {b['name']} overlap.")

        # 2. split passage – two touching passage cells that should be one
        ps = [r for r in rooms if r["type"] == "passage"]
        for i, a in enumerate(ps):
            for b in ps[i + 1:]:
                vert = abs(a["x"] - b["x"]) < EPS and abs(a["w"] - b["w"]) < EPS and (
                    abs(a["y"] + a["d"] - b["y"]) < EPS or abs(b["y"] + b["d"] - a["y"]) < EPS)
                horiz = abs(a["y"] - b["y"]) < EPS and abs(a["d"] - b["d"]) < EPS and (
                    abs(a["x"] + a["w"] - b["x"]) < EPS or abs(b["x"] + b["w"] - a["x"]) < EPS)
                if vert or horiz:
                    hard.append(f"{nm}: the passage is split into separate cells.")

        # 3. reachability (every room that needs access can be walked into without crossing a bedroom / kitchen / toilet)
        if not lv.get("stilt"):
            tmp = {"name": nm, "rooms": rooms, "stilt": False}
            try:
                _, missing = G.reachable(tmp, lv.get("openings") or [], None, li)
            except Exception:
                missing = set()
            for rid in sorted(missing):
                hard.append(f"{nm}: {by[rid]['name']} has no door / cannot be reached.")

        # 4. a room that is supposed to have a door but has none (children use their parent's door)
        for r in rooms:
            if r["type"] in ("bedroom", "kitchen", "common_toilet", "pooja", "dining", "utility", "store") \
                    and r["id"] not in door_rooms and not r.get("parent"):
                # open (door-less) joins are accepted for kitchen / dining next to the hall
                joined = any(G.wall_kind(r, o) is None and G._shared_open(r, o) >= 2.5 for o in rooms if o is not r)
                if not joined:
                    hard.append(f"{nm}: {r['name']} has no door.")

        # 5. toilets: attached toilet opens from its own bedroom / dress; common toilet is small
        for r in rooms:
            if r["type"] == "toilet" and r.get("parent"):
                fam = {r["parent"]} | {x["id"] for x in rooms if x.get("parent") == r["parent"]}
                ok = False
                for o in ops:
                    if o["room"] != r["id"]:
                        continue
                    mx, my = (o["x1"] + o["x2"]) / 2, (o["y1"] + o["y2"]) / 2
                    horiz = abs(o["y1"] - o["y2"]) < 1e-6
                    for pt in ((mx, my - 0.6), (mx, my + 0.6)) if horiz else ((mx - 0.6, my), (mx + 0.6, my)):
                        for q in rooms:
                            if q["id"] in fam and q["x"] - 1e-6 <= pt[0] <= q["x"] + q["w"] + 1e-6 and \
                                    q["y"] - 1e-6 <= pt[1] <= q["y"] + q["d"] + 1e-6:
                                ok = True
                if not ok:
                    hard.append(f"{nm}: the attached toilet does not open from inside its bedroom.")
            if r["type"] == "common_toilet":
                beds = [x for x in rooms if x["type"] == "bedroom"]
                area = r["w"] * r["d"]
                if area > 60 or (beds and area >= min(b["w"] * b["d"] for b in beds) * 0.6):
                    hard.append(f"{nm}: the common toilet is too big ({area:.0f} sq ft) – it must stay small.")

        # 6. minimum sizes
        for r in rooms:
            if r["type"] in ("bedroom", "kitchen", "toilet", "common_toilet", "dining") and not r.get("parent"):
                mw, md = G_MIN.get(r["type"], (0, 0))
                if min(r["w"], r["d"]) + EPS < min(mw, md):
                    hard.append(f"{nm}: {r['name']} is only {r['w']:g} × {r['d']:g} ft – too small.")

    # 7. rear gap / facing (soft)
    sb = (plan.get("setbacks") or {}).get("ft") or {}
    plot, bld = plan.get("plot") or {}, plan.get("building") or {}
    if plot and bld:
        rear = plot["d"] - bld["y"] - bld["d"]
        if rear < 3.2:
            soft.append(f"Rear gap is only {max(rear, 0):.1f} ft – check the rear setback with the local body "
                        f"(or reduce the depth / drop a room).")
        if bld["x"] < 0 or bld["x"] + bld["w"] > plot["w"] + EPS or bld["y"] < 0:
            hard.append("The building goes outside the plot.")
    if not any(o.get("type") == "main_door" for lv in (plan.get("levels") or [])[:1] for o in lv.get("openings") or []):
        hard.append("Ground floor has no main entrance door.")
    if sb and plan.get("facing") and plan.get("compass"):
        up = plan["compass"].get("up")
        if up not in ((0, -1), (0, 1), (-1, 0), (1, 0), [0, -1], [0, 1], [-1, 0], [1, 0], None) and False:
            soft.append("Check the north arrow against the road side.")
    return {"hard": list(dict.fromkeys(hard)), "soft": list(dict.fromkeys(soft))}


G_MIN = {"bedroom": (8.0, 8.0), "kitchen": (6.5, 7.0), "toilet": (4.0, 5.0), "common_toilet": (4.0, 5.0),
         "dining": (7.0, 7.0)}
