"""Tamil Nadu setbacks – TNCDBR 2019, Rule 35(1)(a).

Applies to residential buildings up to 16 dwelling units (and small non-residential uses
up to 300 m²), height up to 12 m (GF+2 / Stilt+3; 9 m in EWS areas).
Source text: Tamil Nadu Combined Development and Building Rules, 2019, Section 35(1)(a).
Always show "verify with local authority" – local bodies can add conditions.
"""
from __future__ import annotations

FT = 0.3048  # m per ft
PLINTH_M = 0.45

AREA_TYPES = {"other": "Other areas", "cba": "Continuous Building Area (CBA)", "ews": "EWS area"}


def front_by_road(road_m: float, area_type: str = "other") -> float:
    if area_type == "cba":
        return 1.5
    if area_type == "ews":
        return 1.0
    if road_m <= 9.0:
        return 1.5
    if road_m <= 18.0:
        return 3.0
    if road_m <= 30.5:
        return 4.5
    return 6.0


def building_height_m(levels: int, floor_height_ft: float) -> float:
    return round(PLINTH_M + levels * floor_height_ft * FT, 2)


class SetbackError(ValueError):
    pass


def tn_setbacks(plot_w_ft: float, plot_d_ft: float, road_width_m: float, levels: int, floor_height_ft: float = 10,
                area_type: str = "other", corner: bool = False, side_road_width_m: float | None = None,
                one_side: str = "left") -> dict:
    """Return setbacks in metres and feet plus the buildable rectangle (feet).

    plot_w_ft = frontage along the road, plot_d_ft = depth away from the road.
    one_side = which side keeps the setback when the rule says "1 m on one side" ("left" / "right").
    """
    if area_type not in AREA_TYPES:
        raise SetbackError("area_type must be other, cba or ews")
    if plot_w_ft <= 0 or plot_d_ft <= 0:
        raise SetbackError("Plot size must be positive")
    if road_width_m is None or road_width_m <= 0:
        raise SetbackError("Abutting road width is needed for the front setback")
    h = building_height_m(levels, floor_height_ft)
    max_h = 9.0 if area_type == "ews" else 12.0
    notes = [f"TNCDBR 2019 Rule 35(1)(a) – {AREA_TYPES[area_type]}; building height ≈ {h} m "
             f"({levels} floor{'s' if levels > 1 else ''} × {floor_height_ft:g} ft + plinth)."]
    if h > max_h:
        raise SetbackError(f"Building height {h} m exceeds {max_h} m allowed under Rule 35(1)(a) – "
                           f"this needs special/multi-storey building rules (not supported yet).")
    width_m = plot_w_ft * FT

    front = front_by_road(road_width_m, area_type)
    notes.append(f"Front {front} m for a {road_width_m:g} m road.")

    left = right = rear = 0.0
    if area_type == "cba":
        notes.append("CBA: side and rear setbacks nil.")
    else:
        if h <= 7.0:
            rear = 0.0
            if width_m <= 9.0:
                left, right = (1.0, 0.0) if one_side == "left" else (0.0, 1.0)
                notes.append("Height ≤ 7 m, plot width ≤ 9 m: side 1 m on one side, rear nil.")
            else:
                left = right = 1.0
                notes.append("Height ≤ 7 m, plot width > 9 m: side 1 m on both sides, rear nil.")
        else:
            rear = 1.5
            if width_m <= 6.0:
                left, right = (1.0, 0.0) if one_side == "left" else (0.0, 1.0)
                notes.append("Height 7–12 m, plot width ≤ 6 m: side 1 m on one side, rear 1.5 m.")
            elif width_m <= 9.0:
                left, right = (1.5, 0.0) if one_side == "left" else (0.0, 1.5)
                notes.append("Height 7–12 m, plot width 6–9 m: side 1.5 m on one side, rear 1.5 m.")
            else:
                left = right = 1.5
                notes.append("Height 7–12 m, plot width > 9 m: side 1.5 m on both sides, rear 1.5 m.")

    if corner:
        srw = side_road_width_m or road_width_m
        side_front = front_by_road(srw, area_type)
        # the side road is taken on the side that has (or would have) the side setback
        if one_side == "left":
            left = max(left, side_front)
        else:
            right = max(right, side_front)
        notes.append(f"Corner plot: front setback rule ({side_front} m) also applied on the {one_side} side road.")

    m = {"front": front, "rear": rear, "left": left, "right": right}
    ft = {k: round(v / FT, 2) for k, v in m.items()}
    bw = round(plot_w_ft - ft["left"] - ft["right"], 2)
    bd = round(plot_d_ft - ft["front"] - ft["rear"], 2)
    if bw < 10 or bd < 15:
        raise SetbackError(f"After setbacks only {bw:.1f} × {bd:.1f} ft remains – too small for a house.")
    notes.append("Verify with the local body / DTCP / CMDA before construction – local conditions can differ.")
    return {
        "rule": "TNCDBR 2019 Rule 35(1)(a)", "area_type": area_type, "road_width_m": road_width_m,
        "corner": corner, "height_m": h, "max_height_m": max_h,
        "m": m, "ft": ft,
        "buildable": {"x": ft["left"], "y": ft["front"], "w": bw, "d": bd},
        "plot": {"w": plot_w_ft, "d": plot_d_ft},
        "coverage_pct": round(100 * bw * bd / (plot_w_ft * plot_d_ft), 1),
        "notes": notes,
    }
