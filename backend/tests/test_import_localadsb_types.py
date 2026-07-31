"""Unit tests for aircraft type resolution in import_localadsb."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from import_localadsb import (  # noqa: E402
    _icao_from_variant,
    _resolve_type_and_model,
)


TYPE_NAMES = {
    "A21N": "Airbus A321neo",
    "A20N": "Airbus A320neo",
    "B190": "Beechcraft 1900",
    "B738": "Boeing 737-800",
}


def test_icao_from_variant_a321neo():
    assert _icao_from_variant("A321-251NX", TYPE_NAMES) == "A21N"
    assert _icao_from_variant("A321-251NX(ACF)", TYPE_NAMES) == "A21N"
    assert _icao_from_variant("A21N", TYPE_NAMES) == "A21N"


def test_resolve_prefers_fleet_over_stale_registry():
    # VH-OYV style: registry wrongly B190, fleet A21N, AU A21N + A321-251NX
    type_code, model, mfr = _resolve_type_and_model(
        registry_type="B190",
        variant="A321-251NX",
        fleet_type="A21N",
        au_type="A21N",
        au_model="A321-251NX",
        au_manufacturer="AIRBUS",
        type_names=TYPE_NAMES,
    )
    assert type_code == "A21N"
    assert model == "A321-251NX"
    assert mfr == "Airbus"


def test_resolve_falls_back_to_variant_when_no_fleet():
    type_code, model, mfr = _resolve_type_and_model(
        registry_type="B190",
        variant="A321-251NX",
        fleet_type=None,
        au_type=None,
        au_model=None,
        au_manufacturer=None,
        type_names=TYPE_NAMES,
    )
    assert type_code == "A21N"
    assert model == "Airbus A321neo" or model == "A321-251NX"
    assert mfr == "Airbus"


def test_resolve_uses_registry_when_nothing_better():
    type_code, model, mfr = _resolve_type_and_model(
        registry_type="B738",
        variant=None,
        fleet_type=None,
        au_type=None,
        au_model=None,
        au_manufacturer=None,
        type_names=TYPE_NAMES,
    )
    assert type_code == "B738"
    assert model == "Boeing 737-800"
    assert mfr == "Boeing"
