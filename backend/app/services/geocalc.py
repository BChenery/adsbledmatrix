import math
from typing import Optional, Tuple

EARTH_RADIUS_KM = 6371.0
EARTH_RADIUS_NM = 3440.065
EARTH_RADIUS_MI = 3958.8


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate great-circle distance in kilometers."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def calculate_bearing(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate bearing from point 1 to point 2 in degrees (0-360)."""
    dlon = math.radians(lon2 - lon1)
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    x = math.sin(dlon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(
        lat2_rad
    ) * math.cos(dlon)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def convert_distance(km: float, unit: str) -> float:
    if unit == "nm":
        return km * 0.539957
    if unit == "mi":
        return km * 0.621371
    return km


def convert_altitude(ft: Optional[float], unit: str) -> Optional[float]:
    if ft is None:
        return None
    if unit == "m":
        return ft * 0.3048
    return ft


def convert_speed(kts: Optional[float], unit: str) -> Optional[float]:
    if kts is None:
        return None
    if unit == "kmh":
        return kts * 1.852
    if unit == "mph":
        return kts * 1.15078
    return kts


def format_heading(heading: Optional[float]) -> str:
    if heading is None:
        return "---"
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    index = round(heading / 45) % 8
    return f"{directions[index]} ({heading:.0f}°)"
