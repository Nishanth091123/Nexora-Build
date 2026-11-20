"""1.27.1 – "compact" generator for small single-floor plots: NO passage at all.

      ┌──────────────┬───────┐   front row : hall  + staircase (stair opens from the hall)
      │     hall     │ stair │
      ├────────┬─────┴──┬────┤   middle row: kitchen | dining | common toilet  (dining is the hub)
      │kitchen │ dining │ CT │
      ├────────┴─┬──────┴────┤   rear row  : bedrooms side by side, each with its attached toilet (+ dress);
      │ bedroom1 │ bedroom2  │   both bedroom doors open from the dining
      │ toilet   │ toilet    │
      └──────────┴───────────┘

Every room opens from the hall or the dining (PASS rooms) by construction – no passage cell, so no area is lost to
one. Only what the user chose is placed; anything it cannot place raises LayoutError and the caller falls back to the
spine generator. 4 variants: mirrored, and kitchen / dining swapped.
"""
from __future__ import annotations

from .layout import LayoutError, NAMES, r2
from .spine import _mk

STAIR_W, STAIR_D = 7.5, 11.0
TOIL_D, TOIL_W = 6.0, 5.5
MIN_BED_AREA, MIN_BED_W, MIN_BED_D = 100.0, 9.5, 8.5


def build(lv: dict, bw: float, bd: float, multi: bool, k: int) -> tuple[list[dict], dict]:
    nm = lv.get("name", "Floor")
    beds = int(lv.get("bedrooms") or 0)
    att = int(lv.get("attached_toilets") or 0)
    ct = int(lv.get("common_toilets") or 0)
    if lv.get("parking_car") or lv.get("parking_bike") or lv.get("lounge") or lv.get("pooja") or lv.get("stilt") \
            or not lv.get("hall") or not lv.get("kitchen") or not lv.get("dining") or beds not in (1, 2) or ct > 1 \
            or att > beds or k >= 4:
        raise LayoutError([f"{nm}: compact layout is not used for these rooms."])
    mirror, swap = bool(k & 1), bool(k & 2)
    hd = STAIR_D if multi else 12.0
    best = None
    for md in (9.5, 10.0, 10.5, 9.0):
        rd = r2(bd - hd - md)
        body = rd - (TOIL_D if att else 0.0)
        bwid = bw / beds
        if body >= MIN_BED_D and bwid >= MIN_BED_W and body * bwid >= MIN_BED_AREA:
            best = (md, rd)
            break
    if not best:
        raise LayoutError([f"{nm}: bedrooms would be too small in a compact layout."])
    md, rd = best
    # middle row widths
    ctw = 5.3 if ct else 0.0
    kw = 8.0
    dw = r2(bw - kw - ctw)
    if dw < 8.0:
        raise LayoutError([f"{nm}: plot too narrow for kitchen + dining in a compact layout."])
    rooms: list[dict] = []
    cn: dict = {}
    X = (lambda x, w: r2(bw - x - w)) if mirror else (lambda x, w: r2(x))
    # front row: hall + stair (stair on the right, left when mirrored)
    sw = STAIR_W if multi else 0.0
    _mk(rooms, cn, "hall", NAMES["hall"], X(0, bw - sw), 0, bw - sw, hd)
    if multi:
        _mk(rooms, cn, "stair", NAMES["stair"], X(bw - sw, sw), 0, sw, hd)
    # middle row: kitchen | dining | common toilet  (swap → dining | kitchen | …  with the toilet beside the dining)
    y = hd
    if swap:
        order = [("dining", dw), ("kitchen", kw)] + ([("common_toilet", ctw)] if ct else [])
        if ct:  # keep the toilet next to the dining
            order = [("kitchen", kw), ("dining", dw), ("common_toilet", ctw)][::-1]
    else:
        order = [("kitchen", kw), ("dining", dw)] + ([("common_toilet", ctw)] if ct else [])
    x = 0.0
    for kind, w in order:
        _mk(rooms, cn, kind, NAMES[kind], X(x, w), y, w, md)
        x += w
    # rear row: bedrooms
    y = hd + md
    bwid = r2(bw / beds)
    for i in range(beds):
        w = bwid if i < beds - 1 else r2(bw - bwid * (beds - 1))
        xx = X(i * bwid, w)
        kind = "master" if i == 0 else "bedroom"
        if i < att:
            bdp = r2(rd - TOIL_D)
            b = _mk(rooms, cn, kind, NAMES[kind], xx, y, w, bdp)
            tw = min(TOIL_W, w)
            outer_left = (xx <= 0.05) if not mirror else (xx + w >= bw - 0.05)
            # toilet at the outer-wall corner, dress beside it
            tx = xx if (xx <= 0.05) else r2(xx + w - tw)
            _mk(rooms, cn, "toilet", "Attached Toilet", tx, y + bdp, tw, TOIL_D, parent=b["id"])
            if w - tw >= 3.0:
                dx = r2(xx + tw) if tx == xx else xx
                _mk(rooms, cn, "dress", NAMES["dress"], dx, y + bdp, w - tw, TOIL_D, parent=b["id"])
        else:
            _mk(rooms, cn, kind, NAMES[kind], xx, y, w, rd)
    info = {"spine": False, "compact": True, "Wf": bw, "Du": bd, "hd": hd, "dd": md, "y_rear": hd + md,
            "sy": 0.0 if multi else None, "stair_side": None, "k": k}
    return rooms, info
