"""1.23 – read the plot and the setbacks that are WRITTEN on the drawing sheet
(e.g. "30'-0" X 40'-0"", "PLOT AREA : 1200 SQ.FT", "SETBACKS : FRONT 5'-0" | REAR 3'-0" | SIDES 2'-0" EACH",
"11'-0" WIDE ROAD (NORTH SIDE)"). Nothing is guessed: a value is returned only when it is written."""
from __future__ import annotations

import re

_FT = r"(\d+(?:\.\d+)?)\s*(?:'|’|ft)\s*(?:-?\s*(\d+(?:\.\d+)?)\s*(?:\"|”|''|in)?)?"


def _ft(m: re.Match, i: int = 1) -> float:
    return float(m.group(i)) + (float(m.group(i + 1)) / 12 if m.group(i + 1) else 0.0)


def read_sheet(texts: list) -> dict:
    """texts: list of strings (or dicts with "text"). Returns {plot:{w,d}, setbacks:{front,rear,left,right}, road_ft, facing}."""
    lines = [(t["text"] if isinstance(t, dict) else str(t)).replace("’", "'").replace("”", '"') for t in texts]
    blob = "\n".join(lines)
    out: dict = {}
    plot = None
    area = re.search(r"PLOT\s*AREA\s*[:=]?\s*(\d{3,6})", blob, re.I)
    wtxt = re.search(_FT + r"\s*\(?\s*PLOT\s*WIDTH", blob, re.I)
    for ln in lines:  # "30'-0" X 40'-0"" – accepted as the PLOT only when the sheet confirms it (area or plot-width text)
        m = re.search(_FT + r"\s*[xX×]\s*" + _FT, ln)
        if not m or re.search(r"bedroom|kitchen|toilet|hall|dining|parking|sit|room", ln, re.I):
            continue
        a_, b_ = _ft(m, 1), _ft(m, 3)
        ok = bool(area and abs(a_ * b_ - float(area.group(1))) <= 0.02 * float(area.group(1)))
        ok = ok or bool(wtxt and abs(_ft(wtxt) - a_) < 0.05 and b_ >= 8)
        if ok:
            plot = (a_, b_)
            break
    w = re.search(_FT + r"\s*\(?\s*PLOT\s*WIDTH", blob, re.I)
    d = re.search(_FT + r"\s*\(?\s*PLOT\s*DEPTH", blob, re.I)
    if w and d:
        plot = (_ft(w), _ft(d))
    if plot and plot[0] >= 8 and plot[1] >= 8:
        out["plot"] = {"w": round(plot[0], 2), "d": round(plot[1], 2)}
    sb: dict = {}
    for key, pat in (("front", r"FRONT"), ("rear", r"REAR"), ("left", r"LEFT"), ("right", r"RIGHT")):
        mm = re.search(pat + r"\s*(?:SET\s*BACK)?\s*[:=]?\s*" + _FT, blob, re.I)
        if mm:
            sb[key] = round(_ft(mm), 2)
    mm = re.search(r"SIDES?\s*(?:SET\s*BACK)?\s*[:=]?\s*" + _FT, blob, re.I)
    if mm:
        sb.setdefault("left", round(_ft(mm), 2))
        sb.setdefault("right", round(_ft(mm), 2))
    if sb:
        out["setbacks"] = sb
    mm = re.search(_FT + r"\s*WIDE\s*ROAD", blob, re.I) or re.search(r"ROAD\s*[:=]?\s*" + _FT + r"\s*WIDE", blob, re.I)
    if mm:
        out["road_ft"] = round(_ft(mm), 2)
    mm = re.search(r"(NORTH|SOUTH|EAST|WEST)(?:\s*-?\s*(EAST|WEST))?\s*FACING", blob, re.I)
    if mm:
        out["facing"] = (mm.group(1) + ("-" + mm.group(2) if mm.group(2) else "")).lower()
    return out
