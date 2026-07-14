"""Score live aircraft for site-local interest (rarity, first-seen, emergencies)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional, Sequence

EMERGENCY_SQUAWKS = frozenset({"7500", "7600", "7700"})

# Score bands: higher wins when multiple interesting aircraft are present.
SCORE_EMERGENCY = 1000.0
SCORE_FIRST_SEEN = 400.0
SCORE_LONG_ABSENT = 300.0
SCORE_RARE = 200.0

DEFAULT_RARE_SIGHTINGS = 3
DEFAULT_ABSENT_DAYS = 30
DEFAULT_WARMUP_DAYS = 7
DEFAULT_WARMUP_HEXES = 50


@dataclass(frozen=True)
class HistorySnapshot:
    """In-memory view of one hex's local sighting history."""

    hex_code: str
    sightings: int = 1
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    last_visit_start: Optional[datetime] = None
    # Gap in days between previous visit end and current visit start (0 if unknown/first).
    prior_gap_days: float = 0.0


@dataclass
class InterestResult:
    is_interesting: bool
    reasons: list[str] = field(default_factory=list)
    score: float = 0.0
    primary_reason: Optional[str] = None  # EMERGENCY | NEW | RARE | RETURN


@dataclass
class SiteBaseline:
    """Site-wide warmup state for learned (non-emergency) alerts."""

    earliest_first_seen: Optional[datetime] = None
    unique_hexes: int = 0


def is_emergency_squawk(squawk: Optional[str]) -> bool:
    if not squawk:
        return False
    return str(squawk).strip() in EMERGENCY_SQUAWKS


def is_warmup(
    baseline: SiteBaseline,
    *,
    now: Optional[datetime] = None,
    warmup_days: int = DEFAULT_WARMUP_DAYS,
    warmup_hexes: int = DEFAULT_WARMUP_HEXES,
) -> bool:
    """True until either enough unique hexes or enough calendar age.

    Warmup ends when ``unique_hexes >= warmup_hexes`` **or**
    ``age >= warmup_days`` (whichever comes first). Empty sites stay warm.
    """
    now = now or datetime.utcnow()
    hex_target = max(1, int(warmup_hexes))
    day_target = max(0, int(warmup_days))

    if baseline.unique_hexes >= hex_target:
        return False
    if baseline.earliest_first_seen is not None:
        age = now - baseline.earliest_first_seen
        if age >= timedelta(days=day_target):
            return False
    # No history yet, or still below both thresholds.
    if baseline.unique_hexes == 0 and baseline.earliest_first_seen is None:
        return True
    return True


def score_aircraft(
    *,
    hex_code: str,
    squawk: Optional[str] = None,
    distance_km: Optional[float] = None,
    history: Optional[HistorySnapshot] = None,
    baseline: Optional[SiteBaseline] = None,
    rare_sightings: int = DEFAULT_RARE_SIGHTINGS,
    absent_days: int = DEFAULT_ABSENT_DAYS,
    warmup_days: int = DEFAULT_WARMUP_DAYS,
    warmup_hexes: int = DEFAULT_WARMUP_HEXES,
    now: Optional[datetime] = None,
) -> InterestResult:
    """Return interest flags/score for one aircraft at this site."""
    now = now or datetime.utcnow()
    reasons: list[str] = []
    score = 0.0

    if is_emergency_squawk(squawk):
        reasons.append("emergency")
        score += SCORE_EMERGENCY

    warming = is_warmup(
        baseline or SiteBaseline(),
        now=now,
        warmup_days=warmup_days,
        warmup_hexes=warmup_hexes,
    )

    if not warming:
        sightings = history.sightings if history is not None else 0
        # First visit at this site (no row yet, or only the current visit).
        if history is None or sightings <= 1:
            reasons.append("first_seen")
            score += SCORE_FIRST_SEEN
        else:
            rare_threshold = max(1, int(rare_sightings))
            if sightings < rare_threshold:
                reasons.append("rare")
                score += SCORE_RARE

            gap = history.prior_gap_days if history is not None else 0.0
            if gap >= float(max(1, int(absent_days))):
                reasons.append("long_absent")
                score += SCORE_LONG_ABSENT

    # Nearer aircraft wins ties within the same band.
    if distance_km is not None and score > 0:
        score += max(0.0, 50.0 - float(distance_km)) * 0.01

    primary = None
    if "emergency" in reasons:
        primary = "EMERGENCY"
    elif "first_seen" in reasons:
        primary = "NEW"
    elif "long_absent" in reasons:
        primary = "RETURN"
    elif "rare" in reasons:
        primary = "RARE"

    return InterestResult(
        is_interesting=bool(reasons),
        reasons=reasons,
        score=score,
        primary_reason=primary,
    )


def pick_most_interesting(
    candidates: Sequence[tuple[Any, InterestResult]],
) -> Optional[tuple[Any, InterestResult]]:
    """Pick highest-score interesting aircraft; distance already folded into score."""
    interesting = [(ac, res) for ac, res in candidates if res.is_interesting]
    if not interesting:
        return None
    interesting.sort(key=lambda pair: pair[1].score, reverse=True)
    return interesting[0]
