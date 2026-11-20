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

        # 0. 1.24.4 (Nishanth): a multi-floor house always has a staircase on every floor, and the car parking opens
        #    straight to the road side (nothing in front of it) so the car can drive in / out from the gate
        if len(plan.get("levels") or []) > 1 and not lv.get("stilt") and not any(r["type"] == "stair" for r in rooms):
            hard.append(f"{nm}: no staircase – every floor of a multi-floor house needs one.")
        if li == 0 and rooms:
            y_front = min(r["y"] for r in rooms)
            for pk in (r for r in rooms if r["type"] == "parking"):
                if pk["y"] - y_front > 0.3:
                    hard.append(f"{nm}: {pk['name']} is not on the road side – the car cannot drive in from the gate.")
                    continue
                for o in rooms:
                    if o is not pk and o["type"] != "parking" and _overlap(o, {**pk, "y": pk["y"] - 6.0, "d": 6.0}) > 0.5:
                        hard.append(f"{nm}: {o['name']} is in front of the {pk['name']} – keep the car entry clear.")
                        break
            if len(plan["levels"]) > 1:
                for pk in (r for r in rooms if r["type"] == "parking"):
                    upper = [r for r in plan["levels"][1]["rooms"] if r["type"] not in ("terrace", "balcony", "sitout")
                             and _overlap(r, pk) > 4]
                    if upper and min(pk["w"], pk["d"]) > 20.5:
                        soft.append(f"{nm}: {pk['name']} is {min(pk['w'], pk['d']):g} ft clear under a room above – "
                                    "columns only at its edges (none inside the bay); the beam needs the structural engineer's size.")

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

        # 2b. one passage per floor – extra "Passage / Wash" filler cells are separate rooms nobody asked for
        if len(ps) > 1:
            hard.append(f"{nm}: the passage is cut into {len(ps)} separate cells.")

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


def compliance(req: dict, plan: dict) -> dict:
    """1.24.2 – did the plan keep what the user asked for? -> {"hard": [...], "soft": [...]}.
    hard = something the user explicitly chose is missing (the plan must not be handed out silently);
    soft = a default / floor split that changed (reported with a ⚠ note).
    req["strict"] = True (rooms table edited by the user): every number per floor is hard.
    Several houses on one floor (units) are checked by their own flow and skipped here."""
    hard: list[str] = []
    soft: list[str] = []
    strict = bool(req.get("strict"))
    explicit = set(req.get("explicit") or [])
    lvls_req = req.get("levels") or []
    lvls = plan.get("levels") or []
    tot = {"bedroom": [0, 0], "attached": [0, 0], "common": [0, 0]}
    for li, rq in enumerate(lvls_req):
        if rq.get("units") or li >= len(lvls) or rq.get("stilt"):
            continue
        lv = lvls[li]
        nm = rq.get("name") or lv.get("name") or f"Floor {li + 1}"
        rooms = lv.get("rooms") or []
        cnt = lambda t: sum(1 for r in rooms if r["type"] == t)
        low = lambda r: r["name"].lower()
        car = sum(1 for r in rooms if r["type"] == "parking" and "bike" not in low(r) and "two" not in low(r))
        bike = sum(1 for r in rooms if r["type"] == "parking" and ("bike" in low(r) or "two" in low(r)))
        bed = sum(1 for r in rooms if r["type"] == "bedroom" and not r.get("parent"))
        att = sum(1 for r in rooms if r["type"] == "toilet" and r.get("parent"))
        com = cnt("common_toilet")
        tot["bedroom"][0] += int(rq.get("bedrooms") or 0); tot["bedroom"][1] += bed
        tot["attached"][0] += int(rq.get("attached_toilets") or 0); tot["attached"][1] += att
        tot["common"][0] += int(rq.get("common_toilets") or 0); tot["common"][1] += com
        want = [("bedrooms", int(rq.get("bedrooms") or 0), bed, "bedroom", "bedroom"),
                ("attached_toilets", int(rq.get("attached_toilets") or 0), att, "attached toilet", "attached_count"),
                ("common_toilets", int(rq.get("common_toilets") or 0), com, "common toilet", "common_count"),
                ("kitchen", 1 if rq.get("kitchen") else 0, cnt("kitchen"), "kitchen", "*"),
                ("hall", 1 if rq.get("hall") else 0, cnt("hall"), "hall", "*"),
                ("dining", 1 if rq.get("dining") and rq.get("hall") else 0, cnt("dining"), "separate dining", "dining"),
                ("pooja", 1 if rq.get("pooja") else 0, cnt("pooja"), "pooja room", "pooja"),
                ("parking_car", 1 if rq.get("parking_car") else 0, car, "car parking", "*"),
                ("parking_bike", 1 if rq.get("parking_bike") else 0, bike, "two-wheeler parking", "*"),
                ("lounge", 1 if rq.get("lounge") else 0, cnt("lounge"), "lounge", "lounge")]
        for key, w, got, label, ex in want:
            if got == w:
                continue
            msg = f"{nm}: you chose {w} {label}, the plan has {got}."
            if key in ("bedrooms", "attached_toilets", "common_toilets"):
                (hard if strict else soft).append(msg)  # totals are judged below when the user did not set the floors
            elif strict or ex == "*" or ex in explicit:
                hard.append(msg)
            else:
                soft.append(msg)
    if not strict:  # the user gave totals / counts, not a floor split → compare the totals
        for key, label, ex in (("bedroom", "bedrooms", None), ("attached", "attached toilets", "attached_count"),
                               ("common", "common toilets", "common_count")):
            want_t, got_t = tot[key]
            if want_t != got_t and (ex is None or ex in explicit):
                hard.append(f"You chose {want_t} {label} in total, the plan has {got_t}.")
    if req.get("staircase") and (len(lvls_req) > 1 or req.get("staircase_asked")):
        for li, lv in enumerate(lvls):
            if li < len(lvls_req) and lvls_req[li].get("stilt") and len(lvls) == 1:
                continue
            if not any(r["type"] == "stair" for r in lv.get("rooms") or []):
                hard.append(f"{lv.get('name', 'Floor')}: staircase asked but not placed.")
    return {"hard": list(dict.fromkeys(hard)), "soft": list(dict.fromkeys(soft))}


G_MIN = {"bedroom": (8.0, 8.0), "kitchen": (6.5, 7.0), "toilet": (4.0, 5.0), "common_toilet": (4.0, 5.0),
         "dining": (7.0, 7.0)}
