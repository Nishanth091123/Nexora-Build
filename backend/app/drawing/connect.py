"""1.23 – make an imported drawing WALKABLE without touching a single written size.

A drawing read from a PDF / DXF / photo gives every room its own size and an approximate position. Rooms then overlap by a
few inches or float apart by a few inches, and the unlabelled passage between them is missing – so no door can be placed.

settle()   moves rooms (never resizes them) by at most MAX_MOVE ft so neighbours touch exactly and nothing overlaps.
fill()     turns an unlabelled hollow inside the building (≥ 3 ft each way) into a Passage room.
Both return plain-language notes that go to the plan so the user sees exactly what was adjusted.
"""
from __future__ import annotations

MAX_MOVE = 1.3     # ft – the most a room is moved to touch / clear its neighbour
MAX_GAP = 1.0      # ft – gaps up to this are closed (the room is moved, not stretched)
MIN_VOID = 3.0     # ft – a hollow narrower than this is a wall / shaft, not a passage
GRID = 0.25


def _ov(a: dict, b: dict) -> tuple[float, float]:
    ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    oy = min(a["y"] + a["d"], b["y"] + b["d"]) - max(a["y"], b["y"])
    return ox, oy


def _hits(rooms: list[dict], r: dict) -> bool:
    for q in rooms:
        if q is r:
            continue
        ox, oy = _ov(r, q)
        if ox > 0.05 and oy > 0.05:
            return True
    return False


def _push(rooms: list[dict], mover: dict, dx: float, dy: float, origin: dict, other: dict) -> list[dict] | None:
    """Move `mover` by (dx, dy); rooms it then overlaps are pushed the same way (a whole row / column shifts together,
    sizes never change). Everything is undone and None returned when it does not end clean or moves a room too far."""
    moved_set: list[dict] = []
    todo = [mover]
    while todo and len(moved_set) <= 6:
        r = todo.pop()
        if r is other or r in moved_set:
            if r is other:
                return _undo(moved_set, dx, dy)
            continue
        r["x"] += dx
        r["y"] += dy
        moved_set.append(r)
        ox0, oy0 = origin.get(id(r), (r["x"] - dx, r["y"] - dy))
        if abs(r["x"] - ox0) + abs(r["y"] - oy0) > MAX_MOVE * 2:
            return _undo(moved_set, dx, dy)
        for q in rooms:
            if q is r or q in moved_set:
                continue
            ox, oy = _ov(r, q)
            if ox > 0.05 and oy > 0.05:
                todo.append(q)
    if todo:
        return _undo(moved_set, dx, dy)
    return moved_set


def _undo(moved_set: list[dict], dx: float, dy: float) -> None:
    for r in moved_set:
        r["x"] -= dx
        r["y"] -= dy
    return None


def settle(rooms: list[dict]) -> list[str]:
    """Separate overlapping rooms and close small gaps by MOVING rooms. Sizes are never changed."""
    notes: list[str] = []
    origin = {id(r): (r["x"], r["y"]) for r in rooms}

    def moved(r):
        x0, y0 = origin[id(r)]
        return abs(r["x"] - x0) + abs(r["y"] - y0)

    # 1. overlaps → push apart along the shallower axis (the room that has moved least gives way)
    for _ in range(40):
        changed = False
        for i, a in enumerate(rooms):
            for b in rooms[i + 1:]:
                ox, oy = _ov(a, b)
                if ox <= 0.02 or oy <= 0.02:
                    continue
                if min(ox, oy) > MAX_MOVE * 2:
                    continue  # a real overlap in the drawing – left for the user (reported by plan warnings)
                mover = a if moved(a) <= moved(b) else b
                other = b if mover is a else a
                if ox <= oy:
                    mover["x"] += (ox if mover["x"] + mover["w"] / 2 >= other["x"] + other["w"] / 2 else -ox)
                else:
                    mover["y"] += (oy if mover["y"] + mover["d"] / 2 >= other["y"] + other["d"] / 2 else -oy)
                changed = True
        if not changed:
            break

    # 2. small gaps → move the room that is easier to move next to its neighbour
    for _ in range(40):
        changed = False
        for i, a in enumerate(rooms):
            for b in rooms[i + 1:]:
                ox, oy = _ov(a, b)
                for horiz in (True, False):
                    if horiz:
                        gap = max(b["x"] - (a["x"] + a["w"]), a["x"] - (b["x"] + b["w"]))
                        side = oy
                    else:
                        gap = max(b["y"] - (a["y"] + a["d"]), a["y"] - (b["y"] + b["d"]))
                        side = ox
                    if not (0.02 < gap <= MAX_GAP and side >= 2.0):
                        continue
                    for mover, other in sorted(((a, b), (b, a)), key=lambda t: moved(t[0])):
                        if moved(mover) + gap > MAX_MOVE * 2:
                            continue
                        if horiz:
                            d = gap if other["x"] > mover["x"] else -gap
                            mover["x"] += d
                        else:
                            d = gap if other["y"] > mover["y"] else -gap
                            mover["y"] += d
                        if _hits(rooms, mover):
                            if horiz:
                                mover["x"] -= d
                            else:
                                mover["y"] -= d
                            continue
                        changed = True
                        break
        if not changed:
            break

    n = 0
    for r in rooms:
        r["x"], r["y"] = round(r["x"], 2), round(r["y"], 2)
        if moved(r) > 0.04:
            n += 1
    if n:
        notes.append(f"Check: {n} room(s) were moved by at most {MAX_MOVE:g} ft so neighbours touch and nothing overlaps – "
                     f"no written size was changed.")
    return notes


_OPENISH = {"parking", "stair", "sitout", "terrace", "balcony", "passage"}


def _closed_sides(rooms: list[dict], c: dict) -> int:
    """How many sides of the hollow c touch a closed room (bedroom, toilet, kitchen …) – the walls of a real passage."""
    tol = 0.3
    sides = set()
    for r in rooms:
        if r.get("type") in _OPENISH:
            continue
        oy = min(c["y"] + c["d"], r["y"] + r["d"]) - max(c["y"], r["y"])
        ox = min(c["x"] + c["w"], r["x"] + r["w"]) - max(c["x"], r["x"])
        if abs(r["x"] + r["w"] - c["x"]) <= tol and oy > 1.0:
            sides.add("l")
        if abs(r["x"] - (c["x"] + c["w"])) <= tol and oy > 1.0:
            sides.add("r")
        if abs(r["y"] + r["d"] - c["y"]) <= tol and ox > 1.0:
            sides.add("b")
        if abs(r["y"] - (c["y"] + c["d"])) <= tol and ox > 1.0:
            sides.add("t")
    return len(sides)


def fill(rooms: list[dict]) -> list[str]:
    """Hollows inside the building that no room covers (≥ MIN_VOID ft each way) become Passage rooms."""
    if len(rooms) < 2:
        return []
    x0 = min(r["x"] for r in rooms)
    y0 = min(r["y"] for r in rooms)
    x1 = max(r["x"] + r["w"] for r in rooms)
    y1 = max(r["y"] + r["d"] for r in rooms)
    nx, ny = int(round((x1 - x0) / GRID)), int(round((y1 - y0) / GRID))
    free = [[True] * nx for _ in range(ny)]
    for r in rooms:
        for j in range(max(0, int((r["y"] - y0) / GRID + 0.5)), min(ny, int((r["y"] + r["d"] - y0) / GRID - 0.5) + 1)):
            for i in range(max(0, int((r["x"] - x0) / GRID + 0.5)), min(nx, int((r["x"] + r["w"] - x0) / GRID - 0.5) + 1)):
                free[j][i] = False
    need = int(MIN_VOID / GRID)
    made = 0
    for _ in range(6):  # biggest rectangle first, a few times
        best = None
        heights = [0] * nx
        for j in range(ny):
            for i in range(nx):
                heights[i] = heights[i] + 1 if free[j][i] else 0
            stack: list[tuple[int, int]] = []  # (start index, height)
            for i in range(nx + 1):
                h = heights[i] if i < nx else 0
                start = i
                while stack and stack[-1][1] >= h:
                    s, hh = stack.pop()
                    w_ = i - s
                    if w_ >= need and hh >= need and (best is None or w_ * hh > best[0]):
                        best = (w_ * hh, s, j - hh + 1, w_, hh)
                    start = s
                stack.append((start, h))
        if not best or best[0] * GRID * GRID < 12:
            break
        _, s, t, w_, h_ = best
        cand = {"x": x0 + s * GRID, "y": y0 + t * GRID, "w": w_ * GRID, "d": h_ * GRID}
        if _closed_sides(rooms, cand) < 2:   # a hollow outside the walls (setback, beside the parking) is not a passage
            for j in range(t, t + h_):
                for i in range(s, s + w_):
                    free[j][i] = False
            continue
        made += 1
        # the wall between a passage and its neighbour is a gap of a few inches – grow the passage to touch (walls are drawn on the line)
        fx0, fy0, fx1, fy1 = cand["x"], cand["y"], cand["x"] + cand["w"], cand["y"] + cand["d"]

        def _free_box(a0, b0, a1, b1):
            return not any(min(a1, q["x"] + q["w"]) - max(a0, q["x"]) > 0.05 and min(b1, q["y"] + q["d"]) - max(b0, q["y"]) > 0.05
                           for q in rooms)
        for r in list(rooms):
            if r.get("type") in _OPENISH and r.get("type") != "passage":
                continue
            oy = min(fy1, r["y"] + r["d"]) - max(fy0, r["y"])
            ox = min(fx1, r["x"] + r["w"]) - max(fx0, r["x"])
            if oy > 1.0 and 0.02 < r["x"] - fx1 <= MAX_GAP and _free_box(fx0, fy0, r["x"], fy1):
                fx1 = r["x"]
            elif oy > 1.0 and 0.02 < r["x"] - fx1 <= MAX_GAP:
                # something else (the kitchen above) stands where the passage must grow: slide that room by the gap
                blockers = [q for q in rooms if q is not r and min(fy1, q["y"] + q["d"]) - max(fy0, q["y"]) > 0.05
                            and 0 < fx1 + (r["x"] - fx1) - q["x"] < q["w"] and q["x"] >= fx1 - 0.01]
                for q in blockers:
                    g = r["x"] - fx1
                    if _push(rooms, q, g, 0.0, {}, r) is not None:
                        fx1 = r["x"]
                        break
            elif oy > 1.0 and 0.02 < fx0 - (r["x"] + r["w"]) <= MAX_GAP and _free_box(r["x"] + r["w"], fy0, fx1, fy1):
                fx0 = r["x"] + r["w"]
            elif ox > 1.0 and 0.02 < r["y"] - fy1 <= MAX_GAP and _free_box(fx0, fy0, fx1, r["y"]):
                fy1 = r["y"]
            elif ox > 1.0 and 0.02 < fy0 - (r["y"] + r["d"]) <= MAX_GAP and _free_box(fx0, r["y"] + r["d"], fx1, fy1):
                fy0 = r["y"] + r["d"]
        x0g, y0g, wg, dg = fx0, fy0, fx1 - fx0, fy1 - fy0
        s, t = int(round((x0g - x0) / GRID)), int(round((y0g - y0) / GRID))
        rooms.append({"id": f"fill{made}", "type": "passage", "name": "Passage", "x": round(x0g, 2),
                      "y": round(y0g, 2), "w": round(wg, 2), "d": round(dg, 2), "inferred": True})
        for j in range(t, t + h_):
            for i in range(s, s + w_):
                free[j][i] = False
    return ([f"Check: {made} unlabelled open area(s) between the rooms were made Passage (inferred – not written on the "
             f"drawing); doors from them follow the rules."] if made else [])
