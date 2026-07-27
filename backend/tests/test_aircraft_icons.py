"""Tests for type-aware aircraft radar silhouettes."""

from app.services.aircraft_icons import (
    ICON_HEAVY,
    ICON_HELICOPTER,
    ICON_JET,
    ICON_JUMBO,
    ICON_LIGHT_GA,
    ICON_TURBOPROP,
    aircraft_icon_polygon,
    all_icon_classes,
    classify_aircraft_icon,
)


def test_classify_helicopter_by_type_code():
    assert classify_aircraft_icon("EC35") == ICON_HELICOPTER
    assert classify_aircraft_icon("R44") == ICON_HELICOPTER
    assert classify_aircraft_icon("B06") == ICON_HELICOPTER


def test_classify_helicopter_by_type_name():
    assert classify_aircraft_icon(None, "Airbus Helicopters H135") == ICON_HELICOPTER
    assert classify_aircraft_icon("ZZZZ", "twin-engine turboprop helicopter") == ICON_HELICOPTER


def test_classify_light_ga_cessna():
    assert classify_aircraft_icon("C172") == ICON_LIGHT_GA
    assert classify_aircraft_icon("C152") == ICON_LIGHT_GA
    assert classify_aircraft_icon("SR22") == ICON_LIGHT_GA


def test_classify_turboprop():
    assert classify_aircraft_icon("DH8D") == ICON_TURBOPROP
    assert classify_aircraft_icon("AT76") == ICON_TURBOPROP
    assert classify_aircraft_icon("PC12") == ICON_TURBOPROP
    assert classify_aircraft_icon("C208") == ICON_TURBOPROP


def test_classify_narrowbody_jet():
    # A320 / B738 should use the generic jet silhouette, distinct from GA/heavy.
    assert classify_aircraft_icon("A320") == ICON_JET
    assert classify_aircraft_icon("B738") == ICON_JET
    assert classify_aircraft_icon("A21N") == ICON_JET


def test_classify_heavy_widebody():
    assert classify_aircraft_icon("B77W") == ICON_HEAVY
    assert classify_aircraft_icon("B789") == ICON_HEAVY
    assert classify_aircraft_icon("A333") == ICON_HEAVY
    assert classify_aircraft_icon("A359") == ICON_HEAVY


def test_classify_jumbo():
    assert classify_aircraft_icon("B744") == ICON_JUMBO
    assert classify_aircraft_icon("A388") == ICON_JUMBO
    assert classify_aircraft_icon(None, "Boeing 747-400") == ICON_JUMBO


def test_classify_unknown_defaults_to_jet():
    assert classify_aircraft_icon(None, None) == ICON_JET
    assert classify_aircraft_icon("", "") == ICON_JET
    assert classify_aircraft_icon("XXXX") == ICON_JET


def test_classify_logo_fallback_kinds():
    from app.services.aircraft_icons import (
        LOGO_FALLBACK_AIRLINER,
        LOGO_FALLBACK_BIZJET,
        LOGO_FALLBACK_HELICOPTER,
        LOGO_FALLBACK_PROP,
        classify_logo_fallback,
        is_bizjet_type,
    )

    assert classify_logo_fallback("R44") == LOGO_FALLBACK_HELICOPTER
    assert classify_logo_fallback("EC35") == LOGO_FALLBACK_HELICOPTER
    assert classify_logo_fallback("C172") == LOGO_FALLBACK_PROP
    assert classify_logo_fallback("PC12") == LOGO_FALLBACK_PROP
    assert classify_logo_fallback("C25A", "Cessna Citation CJ2") == LOGO_FALLBACK_BIZJET
    assert classify_logo_fallback("GLF5") == LOGO_FALLBACK_BIZJET
    assert classify_logo_fallback("B738") == LOGO_FALLBACK_AIRLINER
    assert classify_logo_fallback("A320") == LOGO_FALLBACK_AIRLINER
    assert is_bizjet_type("C25A")
    assert is_bizjet_type("GLF4")
    assert not is_bizjet_type("B738")
    assert not is_bizjet_type("C172")


def test_polygons_differ_by_class():
    """Key families must produce visibly different silhouettes."""
    shapes = {
        cls: tuple(aircraft_icon_polygon(icon_class=cls))
        for cls in all_icon_classes()
    }
    # Every class has a unique polygon.
    assert len(set(shapes.values())) == len(shapes)

    # Jet nose is further forward than helicopter cabin tip (relative).
    jet_nose = min(y for _, y in shapes[ICON_JET])
    heli_nose = min(y for _, y in shapes[ICON_HELICOPTER])
    assert jet_nose < heli_nose

    # Heavy is wider than narrowbody jet.
    jet_width = max(x for x, _ in shapes[ICON_JET]) - min(x for x, _ in shapes[ICON_JET])
    heavy_width = max(x for x, _ in shapes[ICON_HEAVY]) - min(x for x, _ in shapes[ICON_HEAVY])
    assert heavy_width > jet_width

    # Jumbo has more vertices (engine nacelle detail) than jet.
    assert len(shapes[ICON_JUMBO]) > len(shapes[ICON_JET])


def test_polygon_from_type_code_matches_class():
    poly = aircraft_icon_polygon("C172")
    assert poly == aircraft_icon_polygon(icon_class=ICON_LIGHT_GA)
    poly = aircraft_icon_polygon("EC35")
    assert poly == aircraft_icon_polygon(icon_class=ICON_HELICOPTER)
