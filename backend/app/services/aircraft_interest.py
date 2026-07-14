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
# Baseline must age in before NEW/RARE/RETURN fire — otherwise every unfamiliar
# hex looks "special" and the matrix flashes yellow constantly.
DEFAULT_WARMUP_DAYS = 45
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


@dataclass(frozen=True)
class WarmupStatus:
    """Progress toward a usable local regularity baseline."""

    learning: bool
    warmup_days: int
    warmup_hexes: int
    unique_hexes: int
    age_days: float
    days_remaining: float
    hexes_remaining: int
    earliest_first_seen: Optional[datetime] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "learning": self.learning,
            "warmup_days": self.warmup_days,
            "warmup_hexes": self.warmup_hexes,
            "unique_hexes": self.unique_hexes,
            "age_days": round(self.age_days, 2),
            "days_remaining": round(self.days_remaining, 2),
            "hexes_remaining": self.hexes_remaining,
            "earliest_first_seen": (
                self.earliest_first_seen.isoformat() if self.earliest_first_seen else None
            ),
        }


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
    """True until both calendar age and unique-hex sample size are met.

    Learned alerts (NEW / RARE / RETURN) stay off while learning. Emergencies
    still score during warmup. Empty sites stay learning.
    """
    now = now or datetime.utcnow()
    hex_target = max(1, int(warmup_hexes))
    day_target = max(0, int(warmup_days))

    if baseline.unique_hexes == 0 and baseline.earliest_first_seen is None:
        return True

    age_ok = False
    if day_target == 0:
        age_ok = True
    elif baseline.earliest_first_seen is not None:
        age = now - baseline.earliest_first_seen
        age_ok = age >= timedelta(days=day_target)

    hexes_ok = baseline.unique_hexes >= hex_target
    return not (age_ok and hexes_ok)


def warmup_status(
    baseline: SiteBaseline,
    *,
    now: Optional[datetime] = None,
    warmup_days: int = DEFAULT_WARMUP_DAYS,
    warmup_hexes: int = DEFAULT_WARMUP_HEXES,
) -> WarmupStatus:
    """Return learning progress for UI/API."""
    now = now or datetime.utcnow()
    day_target = max(0, int(warmup_days))
    hex_target = max(1, int(warmup_hexes))
    unique = int(baseline.unique_hexes or 0)

    if baseline.earliest_first_seen is not None:
        age_days = max(0.0, (now - baseline.earliest_first_seen).total_seconds() / 86400.0)
    else:
        age_days = 0.0

    return WarmupStatus(
        learning=is_warmup(
            baseline,
            now=now,
            warmup_days=day_target,
            warmup_hexes=hex_target,
        ),
        warmup_days=day_target,
        warmup_hexes=hex_target,
        unique_hexes=unique,
        age_days=age_days,
        days_remaining=max(0.0, float(day_target) - age_days),
        hexes_remaining=max(0, hex_target - unique),
        earliest_first_seen=baseline.earliest_first_seen,
    )


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
