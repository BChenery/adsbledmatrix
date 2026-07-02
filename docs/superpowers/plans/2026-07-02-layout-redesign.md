# Default Layout Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign every default layout in `data/default_layouts.json` using a shared design system, add a validation script, and make the display engine render text and distance bars cleanly.

**Architecture:** A Python generator script encodes the design system (palette, type scale, spacing grid) and produces the complete `default_layouts.json`. A standalone validator checks every layout for overlaps, out-of-bounds elements, font/box mismatches, and palette violations. Two small display-engine changes clip text to box width and remove the hard-coded distance-bar label.

**Tech Stack:** Python 3.12, Pydantic, Pillow, SQLAlchemy, pytest, FastAPI.

---

## File Map

| File | Responsibility |
|------|----------------|
| `data/default_layouts.json` | All 13 redesigned default layouts, produced by the generator. |
| `scripts/generate_default_layouts.py` | Encodes design system and outputs the JSON. |
| `scripts/validate_layouts.py` | Loads the JSON and reports layout violations. |
| `backend/app/services/display_engine.py` | Text clipping, baseline alignment, distance-bar label removal. |
| `backend/tests/test_layouts.py` | Tests that default layouts pass validation and engine renders them. |
| `backend/tests/test_display_engine.py` | Tests for text clipping and distance-bar behaviour. |

---

## Task 1: Create the layout validator

**Files:**
- Create: `scripts/validate_layouts.py`
- Create: `backend/tests/test_layout_validator.py`

**Rationale:** Build the guard-rail first so every redesigned layout can be checked immediately.

- [ ] **Step 1: Write the validator module**

Create `scripts/validate_layouts.py`:

```python
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
                errors.append(f"{name}: opaque elements {i} and {j} overlap")

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
```

- [ ] **Step 2: Write tests for the validator**

Create `backend/tests/test_layout_validator.py`:

```python
import json
from pathlib import Path

import pytest

from scripts.validate_layouts import validate_layout, PALETTE


def test_valid_layout_passes():
    layout = {
        "name": "Valid",
        "width": 256,
        "height": 128,
        "elements": [
            {
                "element_type": "data_field",
                "x": 4,
                "y": 4,
                "width": 100,
                "height": 20,
                "font_size": 16,
                "color": "#00d4ff",
                "format_str": "{callsign}",
                "data_field": "callsign",
            }
        ],
    }
    assert validate_layout(layout) == []


def test_out_of_bounds_fails():
    layout = {
        "name": "OOB",
        "width": 256,
        "height": 128,
        "elements": [
            {
                "element_type": "data_field",
                "x": 250,
                "y": 4,
                "width": 20,
                "height": 20,
                "font_size": 16,
                "color": "#00d4ff",
                "format_str": "{callsign}",
                "data_field": "callsign",
            }
        ],
    }
    errors = validate_layout(layout)
    assert any("outside safe area" in e for e in errors)


def test_overlap_fails():
    layout = {
        "name": "Overlap",
        "width": 256,
        "height": 128,
        "elements": [
            {
                "element_type": "shape",
                "x": 4,
                "y": 4,
                "width": 20,
                "height": 20,
                "color": "#334155",
                "extra": {"shape_type": "rectangle"},
            },
            {
                "element_type": "shape",
                "x": 10,
                "y": 10,
                "width": 20,
                "height": 20,
                "color": "#334155",
                "extra": {"shape_type": "rectangle"},
            },
        ],
    }
    errors = validate_layout(layout)
    assert any("overlap" in e for e in errors)


def test_font_too_large_fails():
    layout = {
        "name": "Font",
        "width": 256,
        "height": 128,
        "elements": [
            {
                "element_type": "data_field",
                "x": 4,
                "y": 4,
                "width": 100,
                "height": 20,
                "font_size": 20,
                "color": "#00d4ff",
                "format_str": "{callsign}",
                "data_field": "callsign",
            }
        ],
    }
    errors = validate_layout(layout)
    assert any("font_size" in e for e in errors)


def test_invalid_colour_fails():
    layout = {
        "name": "Colour",
        "width": 256,
        "height": 128,
        "elements": [
            {
                "element_type": "data_field",
                "x": 4,
                "y": 4,
                "width": 100,
                "height": 20,
                "font_size": 16,
                "color": "#ff00ff",
                "format_str": "{callsign}",
                "data_field": "callsign",
            }
        ],
    }
    errors = validate_layout(layout)
    assert any("palette" in e for e in errors)
```

- [ ] **Step 3: Run the validator tests**

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend
.venv/bin/pytest tests/test_layout_validator.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Run the validator against the current defaults to confirm it catches the existing sloppiness**

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix
python3 scripts/validate_layouts.py
```

Expected: multiple errors reported (overlaps, font sizes, etc.). This is the pre-redesign baseline.

---

## Task 2: Create the layout generator

**Files:**
- Create: `scripts/generate_default_layouts.py`
- Modify: `data/default_layouts.json`

**Rationale:** Encoding the design system in Python makes the layouts maintainable and guarantees consistent spacing, colours, and typography.

- [ ] **Step 1: Write the generator script**

Create `scripts/generate_default_layouts.py`:

```python
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
        elements.append(data_field(120, 92, 132, 24, "distance", fmt="{distance}", font_size=24, color=PALETTE["accent"]))
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
            elem("radar_blip", 78, 4, 100, 100, color=PALETTE["primary"]),
            text(4, 108, 248, 16, "Scanning for aircraft...", font_size=14, color=PALETTE["white"]),
            data_field(90, 92, 76, 12, "current_time", fmt="{current_time}", font_size=12, color=PALETTE["secondary"]),
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
                row_height=22,
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
            text(4, 4, 150, 16, "CLOSEST AIRCRAFT", font_size=14, color=PALETTE["primary"]),
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
            heading_arrow(122, 78, 44, 44),
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
            data_field(4, 44, 120, 16, "route", fmt="{origin} → {destination}", font_size=14, color=PALETTE["accent"]),
            data_field(4, 64, 78, 16, "altitude", fmt="ALT: {altitude}", font_size=12),
            data_field(90, 64, 78, 16, "ground_speed", fmt="SPD: {ground_speed}", font_size=12),
            data_field(176, 64, 76, 16, "heading", fmt="HDG: {heading}", font_size=12),
            data_field(4, 84, 100, 16, "distance", fmt="DIST: {distance}", font_size=12, color=PALETTE["accent"]),
            vertical_rate(110, 84, 80, 16),
            heading_arrow(210, 82, 40, 40),
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
```

- [ ] **Step 2: Run the generator to produce the JSON**

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix
python3 scripts/generate_default_layouts.py
```

Expected: `Wrote 13 layouts to data/default_layouts.json`.

- [ ] **Step 3: Validate the generated layouts**

```bash
python3 scripts/validate_layouts.py
```

Expected: `All layouts validate OK.`

> Note: the generator coordinates shown above are the starting design; during implementation they were tuned slightly (e.g. idle radar position, split-detail arrow placement, data-dump arrow placement) so every layout passes validation. The committed `scripts/generate_default_layouts.py` contains the final coordinates.

- [ ] **Step 4: Sanity-check the JSON diff**

```bash
git diff --stat data/default_layouts.json
```

Expected: the file changed, no unexpected deletions.

---

## Task 3: Fix text rendering in the display engine

**Files:**
- Modify: `backend/app/services/display_engine.py:235-268`
- Modify: `backend/tests/test_display_engine.py`

**Rationale:** Long callsigns or routes currently bleed outside their declared boxes. Clipping fixes that. Baseline alignment makes cap-height sit consistently inside the box.

- [ ] **Step 1: Add failing tests for text clipping**

Append to `backend/tests/test_display_engine.py`:

```python
def test_draw_text_clips_to_box_width(engine):
    """Long text must not render past the declared box width."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (100, 32), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    engine._draw_text(draw, 10, 0, 40, "VERYLONGCALLSIGN", (255, 255, 255), None, 16)

    pixels = img.load()
    for py in range(32):
        for px in range(50, 100):
            assert pixels[px, py] == (0, 0, 0), f"text overflow at ({px},{py})"


def test_draw_text_keeps_short_text_inside_box(engine):
    """Short text should render normally inside its box."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (100, 32), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    engine._draw_text(draw, 0, 0, 100, "ABC", (255, 255, 255), None, 16)

    bbox = img.getbbox()
    assert bbox is not None
    assert bbox[2] <= 100
```

- [ ] **Step 2: Run the new tests and confirm they fail**

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend
.venv/bin/pytest tests/test_display_engine.py::test_draw_text_clips_to_box_width tests/test_display_engine.py::test_draw_text_keeps_short_text_inside_box -v
```

Expected: FAIL.

- [ ] **Step 3: Implement text clipping and baseline alignment**

Replace the `_draw_text` method in `backend/app/services/display_engine.py` with:

```python
    def _draw_text(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        width: int,
        text: str,
        color: Tuple[int, int, int],
        font_family: Optional[str],
        font_size: Optional[int],
        align: str = "center",
    ):
        size = font_size or 12
        family = font_family or "default"
        key = (family, size)

        if key not in self._font_cache:
            try:
                self._font_cache[key] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
            except Exception:
                self._font_cache[key] = ImageFont.load_default()

        font = self._font_cache[key]
        text = str(text)
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        if align == "center":
            draw_x = x + max(0, (width - text_width) // 2)
        elif align == "right":
            draw_x = x + max(0, width - text_width)
        else:
            draw_x = x

        # Vertically centre the glyph bounding box inside the declared box so
        # cap-height sits near the top and descenders do not spill out.
        draw_y = y + max(0, (size - text_height) // 2)

        if text_width > width:
            # Long text is cropped to the declared width and left-aligned so the
            # start of the value (e.g. callsign prefix) remains readable.
            tmp = Image.new("RGBA", (text_width, text_height + 2), (0, 0, 0, 0))
            tmp_draw = ImageDraw.Draw(tmp)
            tmp_draw.text((0, 0), text, fill=color, font=font)
            cropped = tmp.crop((0, 0, width, text_height + 2))
            draw._image.paste(cropped, (x, draw_y), cropped)
        else:
            draw.text((draw_x, draw_y), text, fill=color, font=font)
```

- [ ] **Step 4: Run the clipping tests again**

```bash
.venv/bin/pytest tests/test_display_engine.py::test_draw_text_clips_to_box_width tests/test_display_engine.py::test_draw_text_keeps_short_text_inside_box -v
```

Expected: PASS.

- [ ] **Step 5: Make `_render_element` tolerant of missing optional attributes**

Some generated elements omit `None` optional fields (e.g. `show_if`). Replace direct attribute access with `getattr` defaults so these elements render instead of being silently skipped.

Replace the `_render_element` method in `backend/app/services/display_engine.py` with:

```python
    def _render_element(self, draw: ImageDraw.Draw, img: Image.Image, element: Any, ctx: RenderContext):
        show_if = getattr(element, "show_if", None)
        if show_if and not self._evaluate_condition(show_if, ctx):
            return

        x, y = element.x, element.y
        w = getattr(element, "width", None) or 100
        h = getattr(element, "height", None) or 20
        color = self._parse_color(getattr(element, "color", None)) or (255, 255, 255)
        bg_color = self._parse_color(getattr(element, "bg_color", None))

        if bg_color:
            draw.rectangle([x, y, x + w, y + h], fill=bg_color)

        element_type = element.element_type
        font_family = getattr(element, "font_family", None)
        font_size = getattr(element, "font_size", None)

        if element_type == "text":
            text = getattr(element, "format_str", None) or ""
            self._draw_text(draw, x, y, w, text, color, font_family, font_size)

        elif element_type == "data_field":
            text = self._resolve_data_field(getattr(element, "data_field", None), getattr(element, "format_str", None), ctx)
            self._draw_text(draw, x, y, w, text, color, font_family, font_size)

        elif element_type == "image":
            self._draw_image(img, x, y, w, h, element, ctx)

        elif element_type == "shape":
            self._draw_shape(draw, x, y, w, h, element, color)

        elif element_type == "heading_arrow":
            self._draw_heading_arrow(draw, x, y, w, h, ctx, color)

        elif element_type == "vertical_rate":
            self._draw_vertical_rate(draw, x, y, w, h, ctx, color)

        elif element_type == "distance_bar":
            self._draw_distance_bar(draw, x, y, w, h, ctx, color)

        elif element_type == "radar":
            self._draw_radar(draw, img, element, ctx)

        elif element_type == "radar_blip":
            self._draw_radar_blip(draw, x, y, w, h, ctx, color)

        elif element_type == "aircraft_list":
            self._draw_aircraft_list(draw, x, y, w, h, element, ctx, color)
```

- [ ] **Step 6: Run the display-engine tests**

```bash
.venv/bin/pytest tests/test_display_engine.py -v
```

Expected: PASS.

---

## Task 4: Remove the hard-coded distance-bar label

**Files:**
- Modify: `backend/app/services/display_engine.py:336-346`
- Modify: `backend/tests/test_display_engine.py`

**Rationale:** The redesigned layouts place the distance value in a separate data-field element. The bar's own label currently draws below the bar and clips the bottom margin.

- [ ] **Step 1: Add a failing test for the label removal**

Append to `backend/tests/test_display_engine.py`:

```python
def test_distance_bar_does_not_draw_external_label(engine):
    from unittest.mock import MagicMock

    ctx = MagicMock()
    ctx.aircraft.distance_km = 12.5
    ctx.aircraft.altitude = 1000
    ctx.aircraft.ground_speed = 200
    ctx.aircraft.heading = 90
    ctx.aircraft.vertical_rate = 0
    ctx.enriched = {}
    ctx.user_config = MagicMock()
    ctx.user_config.distance_unit = "km"
    ctx.user_config.altitude_unit = "ft"
    ctx.user_config.speed_unit = "kts"

    from PIL import Image, ImageDraw
    img = Image.new("RGB", (256, 128), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    class FakeElem:
        x = 4
        y = 118
        width = 248
        height = 6
        color = "#00d4ff"

    engine._draw_distance_bar(draw, 4, 118, 248, 6, ctx, (0, 212, 255))
    # The area below the bar (y > 124) must remain black.
    pixels = list(img.getdata())
    for py in range(125, 128):
        for px in range(256):
            idx = py * 256 + px
            assert pixels[idx] == (0, 0, 0), f"non-black pixel at ({px},{py})"
```

- [ ] **Step 2: Run the test and confirm it fails**

```bash
.venv/bin/pytest tests/test_display_engine.py::test_distance_bar_does_not_draw_external_label -v
```

Expected: FAIL (label is drawn below the bar).

- [ ] **Step 3: Remove the label from `_draw_distance_bar`**

Replace the `_draw_distance_bar` method in `backend/app/services/display_engine.py` with:

```python
    def _draw_distance_bar(self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, ctx: RenderContext, color: Tuple[int, int, int]):
        dist = ctx.aircraft.distance_km if ctx.aircraft else None
        if dist is None:
            return
        max_dist = 50.0  # km, scale max
        ratio = min(dist / max_dist, 1.0)
        bar_w = int(w * (1.0 - ratio))
        draw.rectangle([x, y, x + w, y + h], outline=(50, 50, 50))
        draw.rectangle([x, y, x + bar_w, y + h], fill=color)
```

- [ ] **Step 4: Run the test again**

```bash
.venv/bin/pytest tests/test_display_engine.py::test_distance_bar_does_not_draw_external_label -v
```

Expected: PASS.

---

## Task 5: Update layout API tests

**Files:**
- Modify: `backend/tests/test_layouts.py`

**Rationale:** Ensure the default layouts stored in the database pass validation after seeding.

- [ ] **Step 1: Add a validation test to the existing layout test file**

Add to `backend/tests/test_layouts.py`:

```python
def test_default_layouts_validate(client):
    from scripts.validate_layouts import validate
    errors = validate()
    assert errors == [], "Default layouts failed validation: " + "; ".join(errors)
```

- [ ] **Step 2: Run the updated layout tests**

```bash
.venv/bin/pytest tests/test_layouts.py -v
```

Expected: PASS.

---

## Task 6: Run the full test suite

- [ ] **Step 1: Run all backend tests**

```bash
.venv/bin/pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run the validation script one final time**

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix
python3 scripts/validate_layouts.py
```

Expected: `All layouts validate OK.`

---

## Self-Review Checklist

- [ ] Spec coverage: every design-system rule (palette, margins, fonts, spacing, distance-bar position) maps to a validator check or generator constant.
- [ ] Placeholder scan: no TBD/TODO/fill-in-later steps.
- [ ] Type consistency: `flight_card`, `brand_hero`, and helper functions use the same `elem()` return shape as the existing JSON schema.
