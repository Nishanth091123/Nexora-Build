"""1.18 Irregular plots: any shape from the survey sketch, the setbacks per side, and the biggest building rectangle
that fits inside what is left.

Plot coordinates (feet): origin at the front-left corner, x along the road, y away from the road (same as the plan).
Ways to give the shape (plan["requirements"]["plot_shape"]):
  {"mode": "quad",   "sides": [front, right, rear, left], "diagonal": front-left → rear-right}
  {"mode": "angles", "sides": [s1, s2, …], "angles": [interior angle at the start of each side, degrees]}
  {"mode": "points", "points": [[x, y], …]}            – drawn / typed corner points, anti-clockwise from front-left
The first side is the road side unless "road_sides" lists others (corner plots). Nothing is guessed: a missing
diagonal / angle / side is asked for.
"""
from __future__ import annotations

import math


class PlotError(ValueError):
    def __init__(self, questions: list[str]):
        super().__init__("; ".join(questions))
        self.questions = questions


def _tri_point(a: tuple[float, float], b: tuple[float, float], ra: float, rb: float, left: bool) -> tuple[float, float]:
    """Point at distance ra from a and rb from b, on the left (or right) of a→b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy)
    if d <= 0 or ra + rb < d - 1e-6 or abs(ra - rb) > d + 1e-6:
        raise PlotError(["These side lengths and the diagonal cannot make a closed plot – please check the measurements."])
    x = (ra * ra - rb * rb + d * d) / (2 * d)
    h = math.sqrt(max(0.0, ra * ra - x * x))
    ux, uy = dx / d, dy / d
    nx, ny = (-uy, ux) if left else (uy, -ux)
    return a[0] + ux * x + nx * h, a[1] + uy * x + ny * h


def polygon(shape: dict) -> list[tuple[float, float]]:
    mode = shape.get("mode") or "quad"
    if mode == "points":
        pts = [(float(p[0]), float(p[1])) for p in shape.get("points") or []]
        if len(pts) < 3:
            raise PlotError(["Give at least 3 corner points of the plot."])
    elif mode == "quad":
        s = [shape.get("sides", [None] * 4)[i] if i < len(shape.get("sides") or []) else None for i in range(4)]
        names = ["front (road side)", "right side", "rear", "left side"]
        miss = [f"Length of the {names[i]}" for i, v in enumerate(s) if not v or float(v) <= 0]
        if not shape.get("diagonal"):
            miss.append("One diagonal (front-left corner to rear-right corner) – 4 sides alone do not fix the shape")
        if miss:
            raise PlotError(miss)
        f, r, b, l = (float(v) for v in s)
        dg = float(shape["diagonal"])
        A, B = (0.0, 0.0), (f, 0.0)
        C = _tri_point(A, B, dg, r, left=True)  # rear-right corner
        D = _tri_point(A, C, l, b, left=True)   # rear-left corner
        pts = [A, B, C, D]
    elif mode == "angles":
        sides = [float(v) for v in shape.get("sides") or []]
        ang = [float(v) for v in shape.get("angles") or []]
        if len(sides) < 3:
            raise PlotError(["Give every side length of the plot (at least 3)."])
        if len(ang) < len(sides) - 1:
            raise PlotError([f"Give the corner angles too ({len(sides) - 1} needed) – or use 'sides + diagonal'."])
        pts, x, y, head = [(0.0, 0.0)], 0.0, 0.0, 0.0
        for i, L in enumerate(sides[:-1]):
            x, y = x + L * math.cos(head), y + L * math.sin(head)
            pts.append((x, y))
            head += math.pi - math.radians(ang[i + 1] if i + 1 < len(ang) else ang[-1])
        gap = math.hypot(pts[-1][0] - 0, pts[-1][1] - 0)
        if abs(gap - sides[-1]) > max(0.5, 0.02 * sides[-1]):
            raise PlotError([f"The sides and angles do not close: the last side works out to {gap:.2f} ft, not {sides[-1]:g} ft – "
                             "please check the measurements."])
    else:
        raise PlotError(["Unknown plot shape mode"])
    # orient: first side along +x, polygon anti-clockwise
    (x0, y0), (x1, y1) = pts[0], pts[1]
    a = -math.atan2(y1 - y0, x1 - x0)
    ca, sa = math.cos(a), math.sin(a)
    pts = [((x - x0) * ca - (y - y0) * sa, (x - x0) * sa + (y - y0) * ca) for x, y in pts]
    if area_signed(pts) < 0:
        pts = [(x, -y) for x, y in pts]
    mx, my = min(p[0] for p in pts), min(p[1] for p in pts)
    return [(round(x - mx, 3), round(y - my, 3)) for x, y in pts]


def area_signed(pts) -> float:
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2


def info(pts) -> dict:
    n = len(pts)
    sides = [math.hypot(pts[(i + 1) % n][0] - pts[i][0], pts[(i + 1) % n][1] - pts[i][1]) for i in range(n)]
    ang = []
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        a1 = math.atan2(p0[1] - p1[1], p0[0] - p1[0])
        a2 = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        v = math.degrees((a1 - a2) % (2 * math.pi))
        ang.append(round(v, 1))
    A = abs(area_signed(pts))
    rect = all(abs(a - 90) < 1.0 for a in ang) and n == 4
    return {"sides_ft": [round(s, 2) for s in sides], "angles_deg": ang, "area_sqft": round(A, 1), "area_sqm": round(A * 0.09290304, 2),
            "area_cents": round(A / 435.6, 3), "perimeter_ft": round(sum(sides), 2), "w": round(max(p[0] for p in pts), 2),
            "d": round(max(p[1] for p in pts), 2), "rectangular": rect}


def _seg_dist(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _inside(px, py, pts) -> bool:
    c = False
    n = len(pts)
    for i in range(n):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        if (y1 > py) != (y2 > py) and px < (x2 - x1) * (py - y1) / (y2 - y1) + x1:
            c = not c
    return c


def edge_kinds(pts, road_sides: list[int] | None = None) -> list[str]:
    """road | side | rear for every edge. Edge 0 (the first side) is the road unless road_sides says otherwise."""
    road = set(road_sides or [0])
    n = len(pts)
    out = []
    for i in range(n):
        if i in road:
            out.append("road")
            continue
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        nx, ny = (y2 - y1), -(x2 - x1)  # outward normal (anti-clockwise polygon)
        L = math.hypot(nx, ny) or 1
        out.append("rear" if ny / L > 0.7 else "side")
    return out


def buildable(pts, setbacks_ft: dict, road_sides: list[int] | None = None, step: float = 0.5) -> dict:
    """Largest axis-aligned rectangle (x along the road) whose every point keeps the setback from every edge.
    setbacks_ft: {"front", "rear", "left", "right"} – left / right are used for side edges by their position."""
    kinds = edge_kinds(pts, road_sides)
    n = len(pts)
    W, D = max(p[0] for p in pts), max(p[1] for p in pts)
    cx = W / 2
    req = []
    for i in range(n):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        k = kinds[i]
        if k == "road":
            s = setbacks_ft.get("front", 0)
        elif k == "rear":
            s = setbacks_ft.get("rear", 0)
        else:
            s = setbacks_ft.get("left", 0) if (x1 + x2) / 2 < cx else setbacks_ft.get("right", 0)
        req.append(s)
    nx, ny = int(W / step) + 1, int(D / step) + 1
    ok = [[False] * nx for _ in range(ny)]
    for j in range(ny):
        py = j * step
        for i in range(nx):
            px = i * step
            if not _inside(px, py, pts):
                continue
            good = True
            for e in range(n):
                (ax, ay), (bx, by) = pts[e], pts[(e + 1) % n]
                if _seg_dist(px, py, ax, ay, bx, by) < req[e] - 1e-6:
                    good = False
                    break
            ok[j][i] = good
    # largest rectangle of buildable grid POINTS (histogram method on cells whose 4 corners are buildable)
    best = (0.0, 0, 0, 0, 0)
    h = [0] * (nx - 1)
    for j in range(ny - 1):
        for i in range(nx - 1):
            h[i] = h[i] + 1 if (ok[j][i] and ok[j][i + 1] and ok[j + 1][i] and ok[j + 1][i + 1]) else 0
        stack: list[int] = []
        for i in range(nx):
            cur = h[i] if i < nx - 1 else 0
            while stack and h[stack[-1]] >= cur:
                top = stack.pop()
                height = h[top]
                left = stack[-1] + 1 if stack else 0
                width = i - left
                area = width * height
                if height and width and area > best[0]:
                    best = (area, left, j - height + 1, width, height)
            stack.append(i)
    if not best[0]:
        raise PlotError(["After the setbacks nothing is left to build on this plot – check the sizes or the road side."])
    _, i0, j0, wc, hc = best
    return {"x": round(i0 * step, 2), "y": round(j0 * step, 2), "w": round(wc * step, 2), "d": round(hc * step, 2),
            "edge_kinds": kinds, "edge_setbacks_ft": [round(v, 2) for v in req]}


def plot_area_sqft(P: dict) -> float:
    if P.get("poly"):
        return abs(area_signed([tuple(p) for p in P["poly"]]))
    return P["w"] * P["d"]


def provided(P: dict, x0: float, y0: float, x1: float, y1: float) -> dict | None:
    """Open space kept from each kind of plot edge (irregular plot) – the smallest distance from the building."""
    pts = [tuple(p) for p in P.get("poly") or []]
    if not pts:
        return None
    kinds = P.get("edges") or edge_kinds(pts)
    cx = max(p[0] for p in pts) / 2
    rect = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    samples = [(x0 + (x1 - x0) * t / 20, y) for t in range(21) for y in (y0, y1)] + [(x, y0 + (y1 - y0) * t / 20) for t in range(21) for x in (x0, x1)]
    out = {"front": 1e9, "rear": 1e9, "left": 1e9, "right": 1e9}
    n = len(pts)
    for e in range(n):
        (ax, ay), (bx, by) = pts[e], pts[(e + 1) % n]
        dmin = min(_seg_dist(px, py, ax, ay, bx, by) for px, py in samples + rect)
        k = kinds[e] if e < len(kinds) else "side"
        key = "front" if k == "road" else "rear" if k == "rear" else ("left" if (ax + bx) / 2 < cx else "right")
        out[key] = min(out[key], dmin)
    return {k: round(v if v < 1e8 else 0.0, 2) for k, v in out.items()}


def draw_plot(d, P: dict) -> bool:
    """Plot boundary on a drawing: polygon with side lengths and boundary stones. False for a rectangular plot."""
    pts = [tuple(p) for p in P.get("poly") or []]
    if not pts:
        return False
    n = len(pts)
    from .sheets import ft_in
    for i in range(n):
        (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
        d.line(ax, ay, bx, by, "PLOT")
        L = math.hypot(bx - ax, by - ay)
        mx, my = (ax + bx) / 2, (ay + by) / 2
        nx, ny = (by - ay) / (L or 1), -(bx - ax) / (L or 1)  # outward
        d.text(mx + nx * 1.6, my + ny * 1.6, ft_in(L), 0.6, layer="DIM")
        d.rect(ax - 0.35, ay - 0.35, 0.7, 0.7, "PLOT", "#111111", 0)
    inf = info(pts)
    d.text(inf["w"] / 2, inf["d"] + 3.0, f"PLOT AREA {inf['area_sqft']:g} sq ft ({inf['area_sqm']:g} m², {inf['area_cents']:g} cents)", 0.7, layer="DIM")
    return True
