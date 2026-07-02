#!/usr/bin/env python3
"""Generate default_layouts.json from the project design system."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "default_layouts.json"

W, H = 256, 128
M = 4  # safe margin

PALETTE = {
    "primary": "#00d4ff",
    "secondary": "#a0aec0",
    "accent": "#ffb347",
    "positive": "#4ade80",
    "negative": "#f87171",
    "muted": "#334155",
    "white": "#ffffff",
}


def elem(
    element_type: str,
    x: int,
    y: int,
    width: int,
    height: int,
    **kwargs: Any,
) -> Dict[str, Any]:
    out = {
        "element_type": element_type,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "z_index": kwargs.pop("z_index", 0),
    }
    for key, value in kwargs.items():
        if value is not None:
            out[key] = value
    return out


def text(x, y, w, h, text, *, font_size=16, color=PALETTE["secondary"], z_index=0, **kw):
    return elem(
        "text", x, y, w, h,
        format_str=text,
        font_size=font_size,
        color=color,
        z_index=z_index,
        **kw,
    )


def data_field(x, y, w, h, field, *, fmt=None, font_size=16, color=PALETTE["secondary"], z_index=0, **kw):
    return elem(
        "data_field", x, y, w, h,
        data_field=field,
        format_str=fmt or "{" + field + "}",
        font_size=font_size,
        color=color,
        z_index=z_index,
        **kw,
    )


def image(x, y, w, h, *, z_index=0, show_if=None):
    return elem("image", x, y, w, h, z_index=z_index, show_if=show_if)


def heading_arrow(x, y, w, h, *, color=PALETTE["positive"], z_index=0):
    return elem("heading_arrow", x, y, w, h, color=color, z_index=z_index)


def vertical_rate(x, y, w, h, *, color=PALETTE["secondary"], z_index=0):
    return elem("vertical_rate", x, y, w, h, color=color, z_index=z_index)


def distance_bar(x=4, y=118, w=248, h=6, *, color=PALETTE["primary"], z_index=0):
    return elem("distance_bar", x, y, w, h, color=color, z_index=z_index)


def aircraft_list(x, y, w, h, *, columns, max_rows=5, row_height=22, show_header=True, color=PALETTE["secondary"], z_index=0):
    return elem(
        "aircraft_list", x, y, w, h,
        color=color,
        extra={
            "columns": columns,
            "max_rows": max_rows,
            "row_height": row_height,
            "show_header": show_header,
        },
        z_index=z_index,
    )


def shape_rect(x, y, w, h, *, color=PALETTE["muted"], z_index=0):
    return elem("shape", x, y, w, h, color=color, extra={"shape_type": "rectangle"}, z_index=z_index)


def shape_line(x1, y1, x2, y2, *, color=PALETTE["muted"], width=1, z_index=0):
    return elem(
        "shape", x1, y1, x2 - x1, y2 - y1,
        color=color,
        extra={"shape_type": "line", "width": width},
        z_index=z_index,
    )


def flight_card(name: str, description: str, variant: str = "full") -> Dict[str, Any]:
    """Single-aircraft layout with logo, callsign, route, stats, and distance bar."""
    elements = [
        image(4, 4, 48, 48, show_if="has_logo"),
        data_field(60, 4, 130, 36, "callsign", font_size=32, color=PALETTE["primary"]),
    ]

    if variant in ("full", "tracker"):
        elements.extend([
            data_field(196, 4, 56, 28, "route", fmt="{route}", font_size=24, color=PALETTE["accent"]),
            data_field(196, 36, 56, 36, "distance", fmt="{distance}", font_size=32, color=PALETTE["accent"]),
            data_field(60, 42, 130, 16, "registration", fmt="{registration} · {type_code}", font_size=12, color=PALETTE["secondary"]),
            heading_arrow(204, 42, 48, 48),
        ])
    elif variant == "pilot":
        elements.extend([
            heading_arrow(180, 4, 72, 72),
            data_field(4, 44, 78, 20, "altitude", fmt="ALT: {altitude}", font_size=16),
            data_field(90, 44, 78, 20, "ground_speed", fmt="SPD: {ground_speed}", font_size=16),
            data_field(176, 44, 76, 20, "heading", fmt="HDG: {heading}", font_size=16),
            data_field(4, 70, 120, 28, "distance", fmt="{distance}", font_size=24, color=PALETTE["accent"]),
            vertical_rate(130, 74, 100, 16),
        ])
    elif variant == "type_speed":
        elements.extend([
            data_field(4, 44, 120, 36, "type_code", fmt="{type_code}", font_size=32, color=PALETTE["accent"]),
            data_field(140, 44, 112, 28, "ground_speed", fmt="{ground_speed} kts", font_size=24, color=PALETTE["accent"]),
            data_field(140, 76, 112, 28, "altitude", fmt="{altitude} ft", font_size=24),
        ])

    if variant in ("full", "tracker"):
        elements.extend([
            data_field(4, 66, 78, 20, "altitude", fmt="ALT: {altitude}", font_size=16),
            data_field(90, 66, 78, 20, "ground_speed", fmt="SPD: {ground_speed}", font_size=16),
            data_field(176, 66, 76, 20, "heading", fmt="HDG: {heading}", font_size=16),
            vertical_rate(4, 92, 100, 16),
        ])

    elements.append(distance_bar())
    return {"name": name, "description": description, "width": W, "height": H, "is_default": False, "elements": elements}


def brand_hero(name: str, description: str, large_distance: bool = False) -> Dict[str, Any]:
    elements = [
        image(4, 14, 100, 100),
        data_field(120, 20, 132, 36, "callsign", font_size=32, color=PALETTE["primary"]),
        data_field(120, 60, 132, 28, "route", fmt="{route}", font_size=24, color=PALETTE["accent"]),
    ]
    if large_distance:
        elements.append(data_field(120, 88, 132, 32, "distance", fmt="{distance}", font_size=24, color=PALETTE["accent"]))
    else:
        elements.append(data_field(120, 92, 132, 20, "distance", fmt="{distance} km", font_size=16, color=PALETTE["accent"]))
    elements.append(distance_bar())
    return {"name": name, "description": description, "width": W, "height": H, "is_default": False, "elements": elements}


def route_focus() -> Dict[str, Any]:
    return {
        "name": "Route Focus",
        "description": "Route text is the hero with supporting flight details",
        "width": W,
        "height": H,
        "is_default": False,
        "elements": [
            image(220, 4, 32, 32, show_if="has_logo"),
            data_field(4, 4, 200, 36, "callsign", font_size=32, color=PALETTE["primary"]),
            data_field(4, 42, 248, 36, "route", fmt="{origin} → {destination}", font_size=32, color=PALETTE["accent"]),
            data_field(4, 86, 78, 20, "altitude", fmt="ALT: {altitude}", font_size=16),
            data_field(90, 86, 78, 20, "ground_speed", fmt="SPD: {ground_speed}", font_size=16),
            data_field(176, 86, 76, 20, "heading", fmt="HDG: {heading}", font_size=16),
            distance_bar(),
        ],
    }


def minimal() -> Dict[str, Any]:
    return {
        "name": "Minimal",
        "description": "Just the essentials: callsign and distance",
        "width": W,
        "height": H,
        "is_default": False,
        "elements": [
            data_field(4, 26, 248, 36, "callsign", font_size=32, color=PALETTE["primary"]),
            data_field(4, 68, 248, 36, "distance", fmt="{distance} km", font_size=32, color=PALETTE["accent"]),
        ],
    }


def idle_scanning() -> Dict[str, Any]:
    return {
        "name": "Idle / Scanning",
        "description": "Shown when no aircraft are in range",
        "width": W,
        "height": H,
        "is_default": False,
        "elements": [
            data_field(180, 4, 72, 16, "current_time", fmt="{current_time}", font_size=12, color=PALETTE["secondary"]),
            elem("radar_blip", 78, 24, 100, 80, color=PALETTE["primary"]),
            text(4, 106, 248, 18, "Scanning for aircraft...", font_size=14, color=PALETTE["white"]),
        ],
    }


def airport_board() -> Dict[str, Any]:
    return {
        "name": "Airport Board",
        "description": "Full-width flight board showing closest aircraft in a table",
        "width": W,
        "height": H,
        "is_default": False,
        "elements": [
            aircraft_list(
                4, 4, 248, 120,
                columns=["callsign", "origin", "destination", "altitude", "ground_speed", "distance"],
                max_rows=5,
                row_height=20,
                show_header=True,
            ),
        ],
    }


def close_encounters() -> Dict[str, Any]:
    return {
        "name": "Close Encounters",
        "description": "Minimal list of closest aircraft ordered by distance",
        "width": W,
        "height": H,
        "is_default": False,
        "elements": [
            text(4, 4, 200, 18, "CLOSEST AIRCRAFT", font_size=14, color=PALETTE["primary"]),
            aircraft_list(
                4, 22, 248, 100,
                columns=["callsign", "route", "distance"],
                max_rows=5,
                row_height=20,
                show_header=False,
            ),
        ],
    }


def split_detail_list() -> Dict[str, Any]:
    return {
        "name": "Split Detail + List",
        "description": "Left panel shows detailed aircraft info, right panel lists closest flights",
        "width": W,
        "height": H,
        "is_default": False,
        "elements": [
            image(4, 4, 40, 40, show_if="has_logo"),
            data_field(50, 4, 115, 28, "callsign", font_size=24, color=PALETTE["primary"]),
            data_field(50, 34, 115, 16, "route", fmt="{route}", font_size=12, color=PALETTE["accent"]),
            data_field(4, 54, 78, 16, "altitude", fmt="ALT: {altitude}", font_size=12),
            data_field(90, 54, 78, 16, "ground_speed", fmt="SPD: {ground_speed}", font_size=12),
            data_field(4, 74, 78, 16, "heading", fmt="HDG: {heading}", font_size=12),
            data_field(90, 74, 78, 16, "distance", fmt="{distance} km", font_size=12, color=PALETTE["accent"]),
            heading_arrow(122, 64, 44, 44),
            distance_bar(4, 118, 162, 6),
            shape_line(174, 4, 174, 118, color=PALETTE["muted"]),
            aircraft_list(
                178, 4, 74, 112,
                columns=["callsign", "distance"],
                max_rows=5,
                row_height=22,
                show_header=False,
                color=PALETTE["secondary"],
            ),
        ],
    }


def data_dump() -> Dict[str, Any]:
    return {
        "name": "Data Dump",
        "description": "Maximum info density: every field visible at once",
        "width": W,
        "height": H,
        "is_default": False,
        "elements": [
            data_field(4, 4, 120, 36, "callsign", font_size=32, color=PALETTE["primary"]),
            data_field(130, 4, 122, 16, "registration", fmt="{registration} · {type_code}", font_size=12),
            data_field(130, 22, 122, 16, "operator_icao", fmt="{operator_icao}", font_size=12),
            data_field(4, 44, 120, 18, "route", fmt="{origin} → {destination}", font_size=14, color=PALETTE["accent"]),
            data_field(4, 64, 78, 16, "altitude", fmt="ALT: {altitude}", font_size=12),
            data_field(90, 64, 78, 16, "ground_speed", fmt="SPD: {ground_speed}", font_size=12),
            data_field(176, 64, 76, 16, "heading", fmt="HDG: {heading}", font_size=12),
            data_field(4, 84, 100, 16, "distance", fmt="DIST: {distance}", font_size=12, color=PALETTE["accent"]),
            vertical_rate(110, 84, 80, 16),
            heading_arrow(210, 70, 40, 40),
            distance_bar(),
        ],
    }


def build_layouts() -> List[Dict[str, Any]]:
    return [
        {**flight_card("Aviation Enthusiast", "Full aircraft details with callsign, altitude, speed, heading, and distance", "full"), "is_default": True},
        flight_card("Flight Tracker", "Brand-focused layout with airline logo, route, and key flight stats", "tracker"),
        flight_card("Pilot View", "Giant callsign and heading arrow with key stats stacked", "pilot"),
        flight_card("Type & Speed", "Aircraft type code hero with speed and altitude side-by-side", "type_speed"),
        brand_hero("Airline Brand", "Large airline logo with minimal flight info"),
        brand_hero("Logo & Distance", "Giant logo and massive distance number for quick scanning", large_distance=True),
        route_focus(),
        minimal(),
        idle_scanning(),
        airport_board(),
        close_encounters(),
        split_detail_list(),
        data_dump(),
    ]


def main():
    layouts = build_layouts()
    OUTPUT_PATH.write_text(json.dumps(layouts, indent=2) + "\n")
    print(f"Wrote {len(layouts)} layouts to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
