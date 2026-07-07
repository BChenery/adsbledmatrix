from typing import Optional
from timezonefinder import TimezoneFinder

_tz_finder: Optional[TimezoneFinder] = None


def _get_finder() -> TimezoneFinder:
    global _tz_finder
    if _tz_finder is None:
        _tz_finder = TimezoneFinder()
    return _tz_finder


def timezone_for_location(latitude: Optional[float], longitude: Optional[float]) -> Optional[str]:
    """Return the IANA timezone name for a lat/long, or None if unavailable."""
    if latitude is None or longitude is None:
        return None
    try:
        return _get_finder().timezone_at(lat=latitude, lng=longitude)
    except Exception:
        return None
