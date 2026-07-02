#!/usr/bin/env python3
"""Validate default layouts against the project design system."""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LAYOUTS_PATH = PROJECT_ROOT / "data" / "default_layouts.json"

CANVAS_WIDTH = 256
CANVAS_HEIGHT = 128
SAFE_MARGIN = 4

PALETTE = {
    "#000000",
    "#00d4ff",
    "#a0aec0",
    "#ffb347",
    "#4ade80",
    "#f87171",
    "#334155",
    "#ffffff",
}

REQUIRED_FIELDS = {
    "text": ["format_str"],
    "data_field": ["format_str", "data_field"],
    "image": [],
    "shape": ["extra"],
    "heading_arrow": [],
    "vertical_rate": [],
    "distance_bar": [],
    "radar": [],
    "radar_blip": [],
    "aircraft_list": ["extra"],
}


def load_layouts(path: Path = LAYOUTS_PATH) -> List[Dict[str, Any]]:
    with open(path) as f:
        return json.load(f)


def bbox(element: Dict[str, Any]) -> Tuple[int, int, int, int]:
    x = element["x"]
    y = element["y"]
    w = element.get("width") or 0
    h = element.get("height") or 0
    return x, y, x + w, y + h


def overlaps(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    ax1, ay1, ax2, ay2 = bbox(a)
    bx1, by1, bx2, by2 = bbox(b)
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


def validate_layout(layout: Dict[str, Any]) -> List[str]:
    errors = []
    name = layout.get("name", "<unnamed>")
    width = layout.get("width", CANVAS_WIDTH)
    height = layout.get("height", CANVAS_HEIGHT)

    if width != CANVAS_WIDTH or height != CANVAS_HEIGHT:
        errors.append(f"{name}: layout dimensions {width}x{height} != {CANVAS_WIDTH}x{CANVAS_HEIGHT}")

    elements = layout.get("elements", [])
    for i, elem in enumerate(elements):
        prefix = f"{name}[{i}]"
        x, y = elem.get("x"), elem.get("y")
        w = elem.get("width") or 0
        h = elem.get("height") or 0
        elem_type = elem.get("element_type", "<missing>")

        if x is None or y is None:
            errors.append(f"{prefix}: missing x/y")
            continue

        if x < SAFE_MARGIN or y < SAFE_MARGIN or x + w > width - SAFE_MARGIN or y + h > height - SAFE_MARGIN:
            errors.append(
                f"{prefix}: box ({x},{y},{w},{h}) outside safe area "
                f"({SAFE_MARGIN}-{width - SAFE_MARGIN}, {SAFE_MARGIN}-{height - SAFE_MARGIN})"
            )

        font_size = elem.get("font_size")
        if font_size and h and font_size > h - 4:
            errors.append(f"{prefix}: font_size {font_size} exceeds box height {h} - 4")

        color = elem.get("color")
        bg_color = elem.get("bg_color")
        ring_color = elem.get("ring_color")
        dot_color = elem.get("dot_color")
        user_dot_color = elem.get("user_dot_color")
        for field, value in [
            ("color", color),
            ("bg_color", bg_color),
            ("ring_color", ring_color),
            ("dot_color", dot_color),
            ("user_dot_color", user_dot_color),
        ]:
            if value and value not in PALETTE:
                errors.append(f"{prefix}: {field} {value} not in approved palette")

        required = REQUIRED_FIELDS.get(elem_type)
        if required is None:
            errors.append(f"{prefix}: unknown element_type {elem_type}")
        else:
            for field in required:
                if not elem.get(field):
                    errors.append(f"{prefix}: missing required field {field} for {elem_type}")

    for i in range(len(elements)):
        for j in range(i + 1, len(elements)):
            a, b = elements[i], elements[j]
            # Images and solid backgrounds are opaque; text/data over images is allowed.
            opaque = {"image", "shape", "radar", "radar_blip", "distance_bar", "heading_arrow"}
            a_opaque = a.get("element_type") in opaque
            b_opaque = b.get("element_type") in opaque
            if a_opaque and b_opaque and overlaps(a, b):
                errors.append(f"{name}: opaque elements {i} ({a.get('element_type')}) and {j} ({b.get('element_type')}) overlap")

    return errors


def validate(path: Path = LAYOUTS_PATH) -> List[str]:
    all_errors = []
    for layout in load_layouts(path):
        all_errors.extend(validate_layout(layout))
    return all_errors


def main() -> int:
    errors = validate()
    if errors:
        print(f"Validation failed with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("All layouts validate OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
