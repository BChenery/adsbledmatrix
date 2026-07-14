from datetime import datetime, timedelta

from app.services.aircraft_interest import (
    HistorySnapshot,
    SiteBaseline,
    is_warmup,
    score_aircraft,
    pick_most_interesting,
    warmup_status,
)


def _ready_baseline(now: datetime) -> SiteBaseline:
    return SiteBaseline(
        earliest_first_seen=now - timedelta(days=50),
        unique_hexes=100,
    )


def test_emergency_always_interesting_during_warmup():
    now = datetime.utcnow()
    cold = SiteBaseline(earliest_first_seen=now, unique_hexes=1)
    res = score_aircraft(
        hex_code="ABC123",
        squawk="7700",
        distance_km=10.0,
        history=None,
        baseline=cold,
        now=now,
    )
    assert res.is_interesting
    assert "emergency" in res.reasons
    assert res.primary_reason == "EMERGENCY"


def test_first_seen_suppressed_during_warmup():
    now = datetime.utcnow()
    cold = SiteBaseline(earliest_first_seen=now, unique_hexes=1)
    res = score_aircraft(
        hex_code="NEW001",
        squawk="1200",
        distance_km=5.0,
        history=None,
        baseline=cold,
        now=now,
    )
    assert not res.is_interesting


def test_first_seen_suppressed_with_many_hexes_before_days():
    """Busy sites must not treat every plane as NEW before the day baseline."""
    now = datetime.utcnow()
    busy_but_young = SiteBaseline(
        earliest_first_seen=now - timedelta(days=3),
        unique_hexes=500,
    )
    res = score_aircraft(
        hex_code="NEW001",
        squawk=None,
        distance_km=5.0,
        history=None,
        baseline=busy_but_young,
        warmup_days=45,
        warmup_hexes=50,
        now=now,
    )
    assert not res.is_interesting


def test_first_seen_after_warmup():
    now = datetime.utcnow()
    res = score_aircraft(
        hex_code="NEW001",
        squawk=None,
        distance_km=5.0,
        history=None,
        baseline=_ready_baseline(now),
        now=now,
    )
    assert res.is_interesting
    assert "first_seen" in res.reasons
    assert res.primary_reason == "NEW"


def test_rare_by_sightings():
    now = datetime.utcnow()
    hist = HistorySnapshot(
        hex_code="RARE01",
        sightings=2,
        first_seen=now - timedelta(days=10),
        last_seen=now - timedelta(hours=1),
        prior_gap_days=0.0,
    )
    res = score_aircraft(
        hex_code="RARE01",
        history=hist,
        baseline=_ready_baseline(now),
        rare_sightings=3,
        now=now,
    )
    assert res.is_interesting
    assert "rare" in res.reasons
    assert res.primary_reason == "RARE"


def test_regular_not_interesting():
    now = datetime.utcnow()
    hist = HistorySnapshot(
        hex_code="REG001",
        sightings=20,
        first_seen=now - timedelta(days=40),
        last_seen=now - timedelta(hours=2),
        prior_gap_days=0.5,
    )
    res = score_aircraft(
        hex_code="REG001",
        history=hist,
        baseline=_ready_baseline(now),
        rare_sightings=3,
        absent_days=30,
        now=now,
    )
    assert not res.is_interesting


def test_long_absent_30_days():
    now = datetime.utcnow()
    hist = HistorySnapshot(
        hex_code="RET001",
        sightings=10,
        first_seen=now - timedelta(days=50),
        last_seen=now,
        last_visit_start=now,
        prior_gap_days=35.0,
    )
    res = score_aircraft(
        hex_code="RET001",
        history=hist,
        baseline=_ready_baseline(now),
        rare_sightings=3,
        absent_days=30,
        now=now,
    )
    assert res.is_interesting
    assert "long_absent" in res.reasons
    assert res.primary_reason == "RETURN"


def test_warmup_requires_both_days_and_hexes():
    now = datetime.utcnow()
    aged_few = SiteBaseline(
        earliest_first_seen=now - timedelta(days=50),
        unique_hexes=3,
    )
    young_many = SiteBaseline(
        earliest_first_seen=now - timedelta(days=8),
        unique_hexes=200,
    )
    ready = SiteBaseline(
        earliest_first_seen=now - timedelta(days=45),
        unique_hexes=50,
    )
    assert is_warmup(aged_few, now=now, warmup_days=45, warmup_hexes=50)
    assert is_warmup(young_many, now=now, warmup_days=45, warmup_hexes=50)
    assert not is_warmup(ready, now=now, warmup_days=45, warmup_hexes=50)


def test_warmup_status_progress():
    now = datetime.utcnow()
    baseline = SiteBaseline(
        earliest_first_seen=now - timedelta(days=15),
        unique_hexes=20,
    )
    status = warmup_status(baseline, now=now, warmup_days=45, warmup_hexes=50)
    assert status.learning
    assert status.age_days == 15
    assert status.days_remaining == 30
    assert status.hexes_remaining == 30
    assert status.as_dict()["learning"] is True


def test_pick_most_interesting_prefers_emergency():
    from types import SimpleNamespace
    from app.services.aircraft_interest import InterestResult

    a = SimpleNamespace(hex_code="aaa")
    b = SimpleNamespace(hex_code="bbb")
    candidates = [
        (a, InterestResult(True, ["first_seen"], 400.0, "NEW")),
        (b, InterestResult(True, ["emergency"], 1000.0, "EMERGENCY")),
    ]
    picked = pick_most_interesting(candidates)
    assert picked is not None
    assert picked[0].hex_code == "bbb"
