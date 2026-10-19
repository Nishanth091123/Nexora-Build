"""Find rooms in a line drawing: closed areas (bounded by wall / room lines) that contain a room label.

Works the same for DXF and vector PDF:
  segments (axis-aligned lines) → snapped grid → flood fill of grid cells not separated by a line →
  the region under each room label = that room (its bounding box).
Thin regions between double wall lines carry no label and are ignored.
Units are whatever the caller uses; conversion to feet happens later.
"""
from __future__ import annotations

import bisect
import re
from collections import deque

ROOM_WORDS = [
    ("master", "bedroom"), ("bedroom", "bedroom"), ("bed room", "bedroom"), ("bed", "bedroom"), ("b.r", "bedroom"), ("guest", "bedroom"), ("kids", "bedroom"),
    ("children", "bedroom"), ("k.b.r", "bedroom"), ("m.b.r", "bedroom"),
    ("kitchen", "kitchen"), ("kit", "kitchen"), ("cook", "kitchen"),
    ("toilet", "toilet"), ("bath", "toilet"), ("wc", "toilet"), ("w.c", "toilet"), ("t&b", "toilet"),
    ("restroom", "toilet"), ("powder", "toilet"),
    ("living", "hall"), ("hall", "hall"), ("drawing", "hall"), ("lounge", "lounge"), ("family", "lounge"),
    ("dining", "dining"), ("pooja", "pooja"), ("puja", "pooja"), ("prayer", "pooja"),
    ("stair", "stair"), ("staircase", "stair"), ("lift", "stair"),
    ("parking", "parking"), ("car", "parking"), ("portico", "parking"), ("garage", "parking"),
    ("store", "store"), ("utility", "utility"), ("wash", "utility"),
    ("sit out", "sitout"), ("sitout", "sitout"), ("verandah", "sitout"), ("veranda", "sitout"),
    ("balcony", "balcony"), ("terrace", "terrace"), ("open", "terrace"),
    ("passage", "passage"), ("lobby", "passage"), ("corridor", "passage"), ("foyer", "passage"),
    ("dress", "dress"), ("wardrobe", "dress"), ("study", "bedroom"), ("office", "bedroom"),
]
NOT_ROOM = re.compile(r"^(n|north|scale|plan|ground floor|first floor|second floor|site plan|road|\d+(\.\d+)?)$", re.I)


def room_type(text: str) -> str | None:
    t = " " + re.sub(r"[^a-z.&' ]", " ", text.lower()) + " "
    t = re.sub(r"\s+", " ", t)
    for word, typ in ROOM_WORDS:
        if len(word) <= 3:
            if re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", t):
                return typ
        elif word in t:
            return typ
    return None


# sizes written like 12'0"x10'6"  /  12'x10'  /  3.60 x 3.00  /  3600x3000  /  12X10
SIZE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:'|ft|’)?\s*(?:-?\s*(\d+(?:\.\d+)?)\s*(?:\"|”|''|in))?\s*[x×X*]\s*"
    r"(\d+(?:\.\d+)?)\s*(?:'|ft|’)?\s*(?:-?\s*(\d+(?:\.\d+)?)\s*(?:\"|”|''|in))?")


def parse_size(text: str) -> tuple[float, float, str] | None:
    """Return (a, b, unit_hint) from a size text; unit_hint 'ft' when feet marks or small numbers."""
    m = SIZE_RE.search(text.replace("’", "'").replace("”", '"'))
    if not m:
        return None
    a = float(m.group(1)) + (float(m.group(2)) / 12 if m.group(2) else 0)
    b = float(m.group(3)) + (float(m.group(4)) / 12 if m.group(4) else 0)
    raw = m.group(0)
    if "'" in raw or "ft" in raw or '"' in raw:
        hint = "ft"
    elif a >= 300 or b >= 300:
        hint = "mm"
    elif "." in raw and a < 15 and b < 15:
        hint = "m"
    else:
        hint = "ft?"
    return a, b, hint


def to_ft(v: float, hint: str) -> float:
    return {"mm": v / 304.8, "cm": v / 30.48, "m": v / 0.3048}.get(hint.rstrip("?"), v)


def _cluster(values: list[float], tol: float) -> list[float]:
    vals = sorted(values)
    out: list[float] = []
    group: list[float] = []
    for v in vals:
        if group and v - group[-1] > tol:
            out.append(sum(group) / len(group))
            group = []
        group.append(v)
    if group:
        out.append(sum(group) / len(group))
    return out


def find_regions(segments: list[tuple[float, float, float, float]], labels: list[dict],
                 max_lines: int = 450) -> tuple[list[dict], list[dict]]:
    """segments: (x1,y1,x2,y2) in drawing units (y up). labels: {"text","x","y"}.
    Returns (rooms, unplaced_labels). Each room: {label, x, y, w, d, cells} in drawing units."""
    axis = []
    for x1, y1, x2, y2 in segments:
        if abs(x1 - x2) < 1e-9 and abs(y1 - y2) < 1e-9:
            continue
        if abs(y1 - y2) <= abs(x2 - x1) * 0.02:
            axis.append(("h", (y1 + y2) / 2, min(x1, x2), max(x1, x2)))
        elif abs(x1 - x2) <= abs(y2 - y1) * 0.02:
            axis.append(("v", (x1 + x2) / 2, min(y1, y2), max(y1, y2)))
    if not axis:
        return [], labels
    xs_all = [a[2] for a in axis if a[0] == "h"] + [a[3] for a in axis if a[0] == "h"] + [a[1] for a in axis if a[0] == "v"]
    ys_all = [a[2] for a in axis if a[0] == "v"] + [a[3] for a in axis if a[0] == "v"] + [a[1] for a in axis if a[0] == "h"]
    ext = max(max(xs_all) - min(xs_all), max(ys_all) - min(ys_all)) or 1.0
    # drop tiny segments (furniture, hatching, text strokes)
    axis = [a for a in axis if a[3] - a[2] >= ext * 0.012]
    tol = ext * 0.0025
    for _ in range(6):
        xs = _cluster([a[1] for a in axis if a[0] == "v"] + [a[2] for a in axis if a[0] == "h"] + [a[3] for a in axis if a[0] == "h"], tol)
        ys = _cluster([a[1] for a in axis if a[0] == "h"] + [a[2] for a in axis if a[0] == "v"] + [a[3] for a in axis if a[0] == "v"], tol)
        if len(xs) <= max_lines and len(ys) <= max_lines:
            break
        tol *= 1.8
    if len(xs) < 2 or len(ys) < 2:
        return [], labels

    def idx(arr, v):
        lo, hi = 0, len(arr) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if arr[mid] < v:
                lo = mid + 1
            else:
                hi = mid
        best = lo
        if lo > 0 and abs(arr[lo - 1] - v) < abs(arr[lo] - v):
            best = lo - 1
        return best

    nx, ny = len(xs) - 1, len(ys) - 1
    # blocked[v][i][j]: vertical boundary at xs[i] between cell row j ; blockedh at ys[j] col i
    vblock = [[False] * ny for _ in range(nx + 1)]
    hblock = [[False] * (ny + 1) for _ in range(nx)]
    for kind, c, a0, a1 in axis:
        if kind == "v":
            i = idx(xs, c)
            j0, j1 = idx(ys, a0), idx(ys, a1)
            for j in range(j0, j1):
                vblock[i][j] = True
        else:
            j = idx(ys, c)
            i0, i1 = idx(xs, a0), idx(xs, a1)
            for i in range(i0, i1):
                hblock[i][j] = True
    region = [[-1] * ny for _ in range(nx)]
    regions: list[dict] = []
    for si in range(nx):
        for sj in range(ny):
            if region[si][sj] >= 0:
                continue
            rid = len(regions)
            q = deque([(si, sj)])
            region[si][sj] = rid
            cells, touches = 0, False
            mnx, mny, mxx, mxy = si, sj, si, sj
            while q:
                i, j = q.popleft()
                cells += 1
                mnx, mny, mxx, mxy = min(mnx, i), min(mny, j), max(mxx, i), max(mxy, j)
                if i == 0 or j == 0 or i == nx - 1 or j == ny - 1:
                    touches = True
                for di, dj, blocked in ((1, 0, vblock[i + 1][j] if i + 1 <= nx else True),
                                        (-1, 0, vblock[i][j]), (0, 1, hblock[i][j + 1] if j + 1 <= ny else True),
                                        (0, -1, hblock[i][j])):
                    ni, nj = i + di, j + dj
                    if 0 <= ni < nx and 0 <= nj < ny and not blocked and region[ni][nj] < 0:
                        region[ni][nj] = rid
                        q.append((ni, nj))
            area = sum((xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j]) for i in range(mnx, mxx + 1) for j in range(mny, mxy + 1)
                       if region[i][j] == rid)
            bb_area = (xs[mxx + 1] - xs[mnx]) * (ys[mxy + 1] - ys[mny])
            regions.append({"x": xs[mnx], "y": ys[mny], "w": xs[mxx + 1] - xs[mnx], "d": ys[mxy + 1] - ys[mny],
                            "outside": touches, "fill": area / bb_area if bb_area else 0})
    rooms, unplaced = [], []
    used: dict[int, dict] = {}
    for lb in labels:
        if not (xs[0] <= lb["x"] <= xs[-1] and ys[0] <= lb["y"] <= ys[-1]):
            unplaced.append(lb)
            continue
        i = max(0, min(nx - 1, bisect.bisect_right(xs, lb["x"]) - 1))
        j = max(0, min(ny - 1, bisect.bisect_right(ys, lb["y"]) - 1))
        rid = region[i][j]
        rg = regions[rid]
        if rg["outside"] and rg["w"] * rg["d"] > ext * ext * 0.5:
            unplaced.append(lb)
            continue
        if rid in used:  # second label in the same area (e.g. size text) – attach to the first
            used[rid].setdefault("extra", []).append(lb["text"])
            continue
        room = {"label": lb["text"], "x": rg["x"], "y": rg["y"], "w": rg["w"], "d": rg["d"],
                "rectangular": rg["fill"] > 0.92, "region": rid}
        used[rid] = room
        rooms.append(room)
    return rooms, unplaced


def tidy(rooms: list[dict], tol: float = 1.0) -> list[dict]:
    """Align room edges that are within tol (feet) – closes wall-thickness gaps and small overlaps."""
    if not rooms:
        return rooms
    for axis, (p, s) in (("x", ("x", "w")), ("y", ("y", "d"))):
        edges = []
        for k, r in enumerate(rooms):
            edges.append((r[p], k, 0))
            edges.append((r[p] + r[s], k, 1))
        edges.sort()
        groups, cur = [], [edges[0]]
        for e in edges[1:]:
            if e[0] - cur[-1][0] <= tol and not any(c[1] == e[1] for c in cur):
                cur.append(e)
            else:
                groups.append(cur)
                cur = [e]
        groups.append(cur)
        newpos: dict[tuple[int, int], float] = {}
        for g in groups:
            v = round((sum(e[0] for e in g) / len(g)) * 4) / 4
            for e in g:
                newpos[(e[1], e[2])] = v
        for k, r in enumerate(rooms):
            a, b = newpos[(k, 0)], newpos[(k, 1)]
            if b - a >= 2:
                r[p], r[s] = a, round((b - a) * 4) / 4
    return rooms


def find_north(texts: list[dict], segs: list[tuple[float, float, float, float]]) -> float | None:
    """North arrow: a text 'N' / 'NORTH' with a line whose one end is close to it.
    Returns the arrow direction in degrees clockwise from 'up' (y up), or None."""
    cands = [t for t in texts if t["text"].strip().upper() in ("N", "NORTH", "N↑", "↑N")]
    if not cands or not segs:
        return None
    xs = [v for s in segs for v in (s[0], s[2])]
    ys = [v for s in segs for v in (s[1], s[3])]
    ext = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    best = None
    for t in cands:
        reach = max(float(t.get("h") or 0) * 4, ext * 0.06)
        for x1, y1, x2, y2 in segs:
            L = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            if L < ext * 0.01 or L > ext * 0.25:
                continue
            for (nx, ny), (fx, fy) in (((x1, y1), (x2, y2)), ((x2, y2), (x1, y1))):
                d = ((nx - t["x"]) ** 2 + (ny - t["y"]) ** 2) ** 0.5
                if d <= reach and ((fx - t["x"]) ** 2 + (fy - t["y"]) ** 2) ** 0.5 > d + L * 0.5:
                    score = d / (L + 1e-9)
                    if best is None or score < best[0]:
                        best = (score, nx - fx, ny - fy)
    if not best:
        return None
    import math
    ang = (math.degrees(math.atan2(best[1], best[2])) + 360) % 360
    return round(ang / 5) * 5 % 360
