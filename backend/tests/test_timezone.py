from app.services.timezone import timezone_for_location


def test_timezone_for_location_known_cities():
    assert timezone_for_location(-33.8568, 151.2153) == "Australia/Sydney"
    assert timezone_for_location(51.5074, -0.1278) == "Europe/London"
    assert timezone_for_location(40.7128, -74.0060) == "America/New_York"


def test_timezone_for_location_invalid_returns_none():
    assert timezone_for_location(None, 151.0) is None
    assert timezone_for_location(0.0, None) is None
