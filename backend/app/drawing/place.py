"""1.24.2 – put a room of WRITTEN size where the drawing really has it, using the wall geometry.

Old way: centre of the room name → wrong when the name sits off-centre, rooms landed beside their walls.
New way (raster on the drawing's own line grid, 0.25 ft cells):
  * wall cells  = thin closed bands (the black wall thickness) – a room never sits on them
  * placed rooms (closed rooms whose written size matches their walls) are obstacles
  * the written-size rectangle is moved to the place where it
        covers its own drawn area (the walls / counter lines around its name),
        hugs the walls like the drawing does,
        does not sit on walls or other rooms,
        stays near its name.
An open plan (hall + dining in one area) is placed one after the other; when a small closed room (sit-out, toilet)
stands in a corner of the hall box, the hall becomes an L (two rectangles) – never pushed away.
Nothing is changed silently: sizes that cannot fit are reported in `notes`.
"""
from __future__ import annotations

import numpy as np

STEP = 0.25      # ft per raster cell
WALL_T = 0.9     # ft – a closed band thinner than this is a wall


def _raster(grid: dict, k: float):
    xs, ys, reg = grid["xs"], grid["ys"], grid["region"]
    x0, y0, x1, y1 = xs[0], ys[0], xs[-1], ys[-1]
    st = STEP / k
    nx, ny = int((x1 - x0) / st) + 1, int((y1 - y0) / st) + 1
    cx = x0 + (np.arange(nx) + 0.5) * st
    cy = y0 + (np.arange(ny) + 0.5) * st
    ii = np.clip(np.searchsorted(xs, cx, side="right") - 1, 0, len(xs) - 2)
    jj = np.clip(np.searchsorted(ys, cy, side="right") - 1, 0, len(ys) - 2)
    R = np.asarray(reg)[np.ix_(ii, jj)].T          # [ny, nx] region id
    return R, x0, y0, st


def _erode(m: np.ndarray, it: int) -> np.ndarray:
    out = m.copy()
    for _ in range(it):
        p = np.pad(out, 1)
        out = p[1:-1, 1:-1] & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return out


def _dilate(m: np.ndarray, it: int) -> np.ndarray:
    out = m.copy()
    for _ in range(it):
        p = np.pad(out, 1)
        out = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return out


def _walls(R: np.ndarray, labelled: set[int]) -> np.ndarray:
    it = max(1, int(round(WALL_T / STEP / 2)))
    wall = np.zeros(R.shape, bool)
    for rid in np.unique(R):
        if rid < 0 or int(rid) in labelled:
            continue
        m = R == rid
        wall |= m & ~_dilate(_erode(m, it), it)
    return wall


def _integral(a: np.ndarray) -> np.ndarray:
    s = np.zeros((a.shape[0] + 1, a.shape[1] + 1), np.int32)
    s[1:, 1:] = a.astype(np.int32).cumsum(0).cumsum(1)
    return s


def _box_sum(S: np.ndarray, w: int, h: int) -> np.ndarray:
    """sum over every w×h window → array [ny-h+1, nx-w+1]"""
    return S[h:, w:] - S[:-h, w:] - S[h:, :-w] + S[:-h, :-w]


def place(rooms: list[dict], todo: list[dict], regions: list[dict], grid: dict, k: float, notes: list[str]) -> None:
    """rooms: every room (drawing units); todo: the rooms to place (their r['w'], r['d'] already the written size)."""
    R, gx0, gy0, st = _raster(grid, k)
    ny, nx = R.shape
    by_id = {g["id"]: g for g in regions}
    labelled = {r["region"] for r in rooms}
    wall = _walls(R, labelled)
    Sw = _integral(wall)

    def cells(r):
        return (int(round((r["x"] - gx0) / st)), int(round((r["y"] - gy0) / st)),
                max(1, int(round(r["w"] / st))), max(1, int(round(r["d"] / st))))

    occ = np.zeros(R.shape, bool)
    for r in rooms:
        if r in todo:
            continue
        i, j, w, h = cells(r)
        occ[max(0, j):max(0, j + h), max(0, i):max(0, i + w)] = True
    order = sorted(todo, key=lambda r: (bool(r.get("shared")), -r["w"] * r["d"]))
    for r in order:
        w, h = max(1, int(round(r["w"] / st))), max(1, int(round(r["d"] / st)))
        if w >= nx or h >= ny:
            continue
        own = np.zeros(R.shape, bool)
        own |= (R == r["region"])
        if r.get("shared"):  # open plan: every room named in this area shares it
            own |= (R == r["region"])
        So = _integral(own)
        Sc = _integral(occ)
        wl = _box_sum(Sw, w, h).astype(float)
        oc = _box_sum(Sc, w, h).astype(float)
        ow = _box_sum(So, w, h).astype(float)
        own_total = float(own.sum()) or 1.0
        if r.get("shared"):
            outside = w * h - ow                         # part of the box outside its own open area
            miss = 0.0 * ow
        else:
            outside = 0.0 * ow
            miss = own_total - ow                         # part of its own drawn area the box does not cover
        # hugging walls: wall cells in the 1-cell strip just outside each side
        P = np.pad(wall, 1)
        Sp = _integral(P)
        ey, ex = ny - h + 1, nx - w + 1
        # window [j, j+h) × [i, i+w) in the padded array is offset by +1
        def strip(dj0, dj1, di0, di1):
            # strip rows j+dj0 .. j+dj1, cols i+di0 .. i+di1 (padded coordinates)
            hh, ww = dj1 - dj0, di1 - di0
            return Sp[dj0 + hh: dj0 + hh + ey, di0 + ww: di0 + ww + ex] \
                - Sp[dj0: dj0 + ey, di0 + ww: di0 + ww + ex] \
                - Sp[dj0 + hh: dj0 + hh + ey, di0: di0 + ex] + Sp[dj0: dj0 + ey, di0: di0 + ex]
        left = strip(1, 1 + h, 0, 1)
        right = strip(1, 1 + h, w + 1, w + 2)
        below = strip(0, 1, 1, 1 + w)
        above = strip(h + 1, h + 2, 1, 1 + w)
        hug = (np.minimum(left, h) + np.minimum(right, h)) / h + (np.minimum(below, w) + np.minimum(above, w)) / w
        sx, sy = r.get("size_xy") or (r["lx"], r["ly"])
        px, py = ((r["lx"] + sx) / 2 - gx0) / st, ((r["ly"] + sy) / 2 - gy0) / st
        jj, ii = np.mgrid[0:ey, 0:ex]
        dist = np.hypot(ii + w / 2 - px, jj + h / 2 - py)
        cost = 4.0 * wl + (1.2 if r.get("shared") else 6.0) * oc + 2.5 * outside + 3.0 * miss - 90.0 * hug + 0.6 * dist
        j, i = np.unravel_index(int(np.argmin(cost)), cost.shape)
        r["x"], r["y"] = gx0 + i * st, gy0 + j * st
        occ[j:j + h, i:i + w] = True
        r["placed_by_walls"] = True


def carve(rooms: list[dict], k: float, notes: list[str]) -> None:
    """A small room standing in the corner of an open-plan room's box (sit-out in the hall, hall in the dining) makes
    that room an L. It is kept as TWO rectangles (same name, 'part 2') – never pushed away, never made smaller."""
    added: list[dict] = []
    for a in sorted(rooms, key=lambda q: q["w"] * q["d"]):
        if not a.get("placed_by_walls") or not a.get("shared"):
            continue
        for b in list(rooms):
            if b is a or b.get("lpart") or (b.get("shared") and not b.get("placed_by_walls")):
                continue
            if b.get("shared") and b["w"] * b["d"] < a["w"] * a["d"]:
                continue  # between two open-plan rooms the smaller one is carved around the bigger one
            ox0, ox1 = max(a["x"], b["x"]), min(a["x"] + a["w"], b["x"] + b["w"])
            oy0, oy1 = max(a["y"], b["y"]), min(a["y"] + a["d"], b["y"] + b["d"])
            ow, od = (ox1 - ox0) * k, (oy1 - oy0) * k
            if ow < 0.5 or od < 0.5 or ow * od > 0.4 * a["w"] * a["d"] * k * k:
                continue
            tol = 0.3 / k
            at_l, at_r = ox0 <= a["x"] + tol, ox1 >= a["x"] + a["w"] - tol
            at_b, at_t = oy0 <= a["y"] + tol, oy1 >= a["y"] + a["d"] - tol
            if not ((at_l or at_r) and (at_b or at_t)):
                continue
            # option 1: full-width piece on the free rows, narrow piece beside the obstacle;  option 2: the other way
            def mk(x, y, w, d):
                return {**a, "x": x, "y": y, "w": w, "d": d}
            if at_b:
                full = mk(a["x"], oy1, a["w"], a["y"] + a["d"] - oy1)
                rest_y, rest_d = a["y"], oy1 - a["y"]
            else:
                full = mk(a["x"], a["y"], a["w"], oy0 - a["y"])
                rest_y, rest_d = oy0, a["y"] + a["d"] - oy0
            rest = mk(ox1 if at_l else a["x"], rest_y, (a["x"] + a["w"] - ox1) if at_l else (ox0 - a["x"]), rest_d)
            if full["d"] * k < 2 or rest["w"] * k < 2:   # too thin – try the other way
                if at_l:
                    full = mk(ox1, a["y"], a["x"] + a["w"] - ox1, a["d"])
                    rest = mk(a["x"], oy1 if not at_b else a["y"], ox1 - a["x"] if False else ox0 - a["x"] if False else (ox1 - a["x"]) if False else a["w"] - full["w"],
                              (a["y"] + a["d"] - oy1) if at_b else (oy0 - a["y"]))
                else:
                    full = mk(a["x"], a["y"], ox0 - a["x"], a["d"])
                    rest = mk(ox0, oy1 if at_b else a["y"], a["w"] - full["w"], (a["y"] + a["d"] - oy1) if at_b else (oy0 - a["y"]))
                if full["w"] * k < 2 or rest["d"] * k < 2:
                    continue
            a.update(x=full["x"], y=full["y"], w=full["w"], d=full["d"], carved=True)
            rest["label"] = a["label"] + " (part 2)"
            rest["lpart"] = True
            rest["carved"] = False
            rest["rigid"] = False
            rest["placed_by_walls"] = False
            rest["shared"] = False
            rest["extra"] = []
            added.append(rest)
            notes.append(f"{a['label'].title()} is L-shaped here ({b['label'].title()} stands in its corner) – drawn as two "
                         f"rectangles that together keep the written size.")
            break
    rooms.extend(added)
