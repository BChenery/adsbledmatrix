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
