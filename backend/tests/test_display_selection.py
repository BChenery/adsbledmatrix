from types import SimpleNamespace

import pytest

from app.services.aircraft_interest import InterestResult
from app.services.display_selection import (
    EXIT_HYSTERESIS,
    MAX_PLAYLIST_SIZE,
    normalize_display_mode,
    resolve_playlist_ids,
    select_aircraft,
    select_layout_index,
)


def _ac(hex_code: str, distance_km: float, squawk=None):
    return SimpleNamespace(hex_code=hex_code, distance_km=distance_km, squawk=squawk)


POOL = [
    _ac("aaa111", 1.0),
    _ac("bbb222", 2.5),
    _ac("ccc333", 5.0),
    _ac("ddd444", 8.0),
    _ac("eee555", 12.0),
]


def test_normalize_cycle3_alias():
    assert normalize_display_mode("cycle3") == "cycle"
    assert normalize_display_mode("closest") == "closest"
    assert normalize_display_mode(None) == "closest"


def test_cycle_uses_first_n_of_pool():
    result = select_aircraft(
        POOL,
        display_mode="cycle",
        cycle_count=2,
        cycle_index=1,
        proximity_enabled=False,
        proximity_km=3.0,
    )
    assert result.mode == "cycle"
    assert result.aircraft.hex_code == "bbb222"
    assert result.cycle_index == 1


def test_cycle3_alias_behaves_as_cycle():
    result = select_aircraft(
        POOL,
        display_mode="cycle3",
        cycle_count=3,
        cycle_index=2,
        proximity_enabled=False,
        proximity_km=3.0,
    )
    assert result.mode == "cycle"
    assert result.aircraft.hex_code == "ccc333"


def test_proximity_overrides_cycle_when_inside_threshold():
    result = select_aircraft(
        POOL,
        display_mode="cycle",
        cycle_count=3,
        cycle_index=2,
        proximity_enabled=True,
        proximity_km=3.0,
    )
    assert result.focused is True
    assert result.mode == "proximity"
    assert result.aircraft.hex_code == "aaa111"


def test_proximity_does_not_fire_when_outside_threshold():
    far_pool = [
        _ac("aaa111", 10.0),
        _ac("bbb222", 12.0),
    ]
    result = select_aircraft(
        far_pool,
        display_mode="cycle",
        cycle_count=2,
        cycle_index=0,
        proximity_enabled=True,
        proximity_km=3.0,
    )
    assert result.focused is False
    assert result.mode == "cycle"
    assert result.aircraft.hex_code == "aaa111"


def test_hysteresis_keeps_focus_slightly_past_threshold():
    threshold = 3.0
    just_outside = threshold * 1.10  # still inside exit hysteresis
    pool = [_ac("aaa111", just_outside), _ac("bbb222", 8.0)]
    result = select_aircraft(
        pool,
        display_mode="cycle",
        cycle_count=2,
        cycle_index=1,
        proximity_enabled=True,
        proximity_km=threshold,
        currently_focused=True,
    )
    assert result.focused is True
    assert result.aircraft.hex_code == "aaa111"
    assert just_outside <= threshold * EXIT_HYSTERESIS


def test_hysteresis_releases_beyond_exit_threshold():
    threshold = 3.0
    beyond = threshold * EXIT_HYSTERESIS + 0.1
    pool = [_ac("aaa111", beyond), _ac("bbb222", 8.0)]
    result = select_aircraft(
        pool,
        display_mode="cycle",
        cycle_count=2,
        cycle_index=0,
        proximity_enabled=True,
        proximity_km=threshold,
        currently_focused=True,
    )
    assert result.focused is False
    assert result.mode == "cycle"


def test_closest_always_returns_nearest():
    result = select_aircraft(
        POOL,
        display_mode="closest",
        cycle_count=5,
        cycle_index=3,
        proximity_enabled=False,
        proximity_km=3.0,
    )
    assert result.mode == "closest"
    assert result.aircraft.hex_code == "aaa111"
    assert result.cycle_index == 0


def test_empty_pool_returns_none():
    result = select_aircraft(
        [],
        display_mode="cycle",
        cycle_count=3,
        cycle_index=0,
        proximity_enabled=True,
        proximity_km=3.0,
    )
    assert result.aircraft is None
    assert result.focused is False


def test_proximity_can_pick_aircraft_outside_cycle_pool():
    # Closest 3 are far; 4th is close — focus pool still sees it.
    pool = [
        _ac("far1", 20.0),
        _ac("far2", 21.0),
        _ac("far3", 22.0),
        _ac("close", 1.5),
    ]
    result = select_aircraft(
        pool,
        display_mode="cycle",
        cycle_count=3,
        cycle_index=0,
        proximity_enabled=True,
        proximity_km=3.0,
    )
    assert result.focused is True
    assert result.aircraft.hex_code == "close"


def test_select_layout_index_advance():
    assert select_layout_index(3, rotation_enabled=True, current_index=0, advance=True) == 1
    assert select_layout_index(3, rotation_enabled=True, current_index=2, advance=True) == 0
    assert select_layout_index(3, rotation_enabled=False, current_index=2, advance=True) == 0
    assert select_layout_index(0, rotation_enabled=True, current_index=1, advance=True) == 0


def test_interesting_beats_proximity():
    pool = [
        _ac("close", 1.0),
        _ac("rare", 12.0),
    ]
    interest = {
        "CLOSE": InterestResult(False, [], 0.0, None),
        "RARE": InterestResult(True, ["first_seen"], 400.0, "NEW"),
    }
    result = select_aircraft(
        pool,
        display_mode="closest",
        cycle_count=3,
        cycle_index=0,
        proximity_enabled=True,
        proximity_km=3.0,
        interesting_enabled=True,
        interest_by_hex=interest,
    )
    assert result.mode == "interesting"
    assert result.interesting is True
    assert result.aircraft.hex_code == "rare"
    assert result.interest_reason == "NEW"
    assert result.focused is False


def test_interesting_hold_keeps_hex():
    pool = [
        _ac("aaa", 2.0),
        _ac("bbb", 5.0),
    ]
    interest = {
        "AAA": InterestResult(True, ["rare"], 200.0, "RARE"),
        "BBB": InterestResult(True, ["first_seen"], 400.0, "NEW"),
    }
    result = select_aircraft(
        pool,
        display_mode="cycle",
        cycle_count=2,
        cycle_index=0,
        proximity_enabled=False,
        proximity_km=3.0,
        interesting_enabled=True,
        interest_by_hex=interest,
        currently_interesting_hex="aaa",
        interesting_hold_active=True,
    )
    assert result.mode == "interesting"
    assert result.aircraft.hex_code == "aaa"


def test_proximity_when_interesting_disabled():
    pool = [_ac("close", 1.0), _ac("rare", 12.0)]
    interest = {
        "RARE": InterestResult(True, ["first_seen"], 400.0, "NEW"),
    }
    result = select_aircraft(
        pool,
        display_mode="closest",
        cycle_count=3,
        cycle_index=0,
        proximity_enabled=True,
        proximity_km=3.0,
        interesting_enabled=False,
        interest_by_hex=interest,
    )
    assert result.mode == "proximity"
    assert result.aircraft.hex_code == "close"


def test_resolve_playlist_ids():
    assert resolve_playlist_ids([3, 1, 3, 2], 9) == [3, 1, 2]
    assert resolve_playlist_ids([], 5) == [5]
    assert resolve_playlist_ids(None, None) == []


def test_resolve_playlist_ids_caps_size():
    huge = list(range(1, MAX_PLAYLIST_SIZE + 10))
    assert resolve_playlist_ids(huge, None) == list(range(1, MAX_PLAYLIST_SIZE + 1))
