"""WMO weather-code → LED icon category, plus PIL renderers for the matrix."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional, Tuple

from PIL import Image, ImageDraw

# Coarse icon buckets used by layouts and the renderer.
ICON_CLEAR = "clear"
ICON_PARTLY = "partly_cloudy"
ICON_CLOUDY = "cloudy"
ICON_FOG = "fog"
ICON_DRIZZLE = "drizzle"
ICON_RAIN = "rain"
ICON_SNOW = "snow"
ICON_THUNDER = "thunder"
ICON_UNKNOWN = "unknown"

# Palette tuned for low-res RGB LED panels.
_YELLOW = (255, 204, 0)
_ORANGE = (255, 160, 32)
_WHITE = (240, 240, 245)
_CLOUD = (180, 190, 205)
_CLOUD_DARK = (120, 130, 150)
_CYAN = (0, 200, 255)
_BLUE = (64, 140, 255)
_GRAY = (160, 170, 180)
_PURPLE = (160, 100, 255)
_BOLT = (255, 230, 80)


def weather_icon_key(weather_code: Optional[int]) -> str:
    """Map Open-Meteo / WMO weather code to an icon key."""
    if weather_code is None:
        return ICON_UNKNOWN
    try:
        code = int(weather_code)
    except (TypeError, ValueError):
        return ICON_UNKNOWN

    if code == 0:
        return ICON_CLEAR
    if code == 1:
        return ICON_PARTLY
    if code == 2:
        return ICON_PARTLY
    if code == 3:
        return ICON_CLOUDY
    if code in (45, 48):
        return ICON_FOG
    if 51 <= code <= 57:
        return ICON_DRIZZLE
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return ICON_RAIN
    if code in (71, 73, 75, 77, 85, 86):
        return ICON_SNOW
    if code in (95, 96, 99):
        return ICON_THUNDER
    return ICON_UNKNOWN


def _scale(points, s: float, ox: float = 0.0, oy: float = 0.0):
    return [(ox + x * s, oy + y * s) for x, y in points]


def _draw_sun(draw: ImageDraw.Draw, cx: float, cy: float, r: float) -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_YELLOW)
    # Rays
    for dx, dy in (
        (0, -1),
        (0, 1),
        (-1, 0),
        (1, 0),
        (0.7, 0.7),
        (0.7, -0.7),
        (-0.7, 0.7),
        (-0.7, -0.7),
    ):
        x1 = cx + dx * r * 1.25
        y1 = cy + dy * r * 1.25
        x2 = cx + dx * r * 1.75
        y2 = cy + dy * r * 1.75
        draw.line([(x1, y1), (x2, y2)], fill=_ORANGE, width=max(1, int(r * 0.22)))


def _draw_cloud(
    draw: ImageDraw.Draw,
    cx: float,
    cy: float,
    scale: float,
    fill=_CLOUD,
) -> None:
    # Three overlapping ellipses + body — reads as a cloud at low res.
    draw.ellipse(
        [cx - 10 * scale, cy - 4 * scale, cx + 2 * scale, cy + 8 * scale],
        fill=fill,
    )
    draw.ellipse(
        [cx - 4 * scale, cy - 8 * scale, cx + 8 * scale, cy + 4 * scale],
        fill=fill,
    )
    draw.ellipse(
        [cx + 0 * scale, cy - 3 * scale, cx + 12 * scale, cy + 8 * scale],
        fill=fill,
    )
    draw.ellipse(
        [cx - 8 * scale, cy + 1 * scale, cx + 10 * scale, cy + 10 * scale],
        fill=fill,
    )


def _draw_rain_drops(
    draw: ImageDraw.Draw, cx: float, cy: float, scale: float, count: int = 3
) -> None:
    for i in range(count):
        x = cx - 6 * scale + i * 6 * scale
        y0 = cy + 8 * scale
        y1 = y0 + 6 * scale
        draw.line([(x, y0), (x - 1.5 * scale, y1)], fill=_CYAN, width=max(1, int(scale)))


def _draw_snow_flakes(
    draw: ImageDraw.Draw, cx: float, cy: float, scale: float
) -> None:
    for i, (ox, oy) in enumerate(((-6, 8), (0, 10), (6, 8))):
        x = cx + ox * scale
        y = cy + oy * scale
        r = 1.6 * scale
        draw.ellipse([x - r, y - r, x + r, y + r], fill=_WHITE)
        if i == 1:
            draw.line([(x - 3 * scale, y), (x + 3 * scale, y)], fill=_WHITE, width=1)
            draw.line([(x, y - 3 * scale), (x, y + 3 * scale)], fill=_WHITE, width=1)


def _draw_bolt(draw: ImageDraw.Draw, cx: float, cy: float, scale: float) -> None:
    pts = [
        (cx - 1 * scale, cy + 4 * scale),
        (cx + 3 * scale, cy + 4 * scale),
        (cx - 1 * scale, cy + 11 * scale),
        (cx + 5 * scale, cy + 11 * scale),
        (cx - 2 * scale, cy + 20 * scale),
        (cx + 1 * scale, cy + 12 * scale),
        (cx - 4 * scale, cy + 12 * scale),
    ]
    draw.polygon(pts, fill=_BOLT)


def render_weather_icon(
    key: str,
    size: int = 48,
    color: Optional[Tuple[int, int, int]] = None,
) -> Image.Image:
    """Render a weather icon into an RGBA image of the requested pixel size."""
    size = max(8, int(size))
    # Draw at fixed 32px artboard then scale — keeps shapes consistent.
    base = 32
    img = Image.new("RGBA", (base, base), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    accent = color or _WHITE

    k = (key or ICON_UNKNOWN).lower().strip()
    if k == ICON_CLEAR:
        _draw_sun(draw, 16, 16, 7)
    elif k == ICON_PARTLY:
        _draw_sun(draw, 11, 11, 5.5)
        _draw_cloud(draw, 14, 16, 0.95, fill=_CLOUD)
    elif k == ICON_CLOUDY:
        _draw_cloud(draw, 12, 12, 1.05, fill=_CLOUD_DARK)
        _draw_cloud(draw, 14, 14, 1.0, fill=_CLOUD)
    elif k == ICON_FOG:
        for i, y in enumerate((10, 15, 20, 25)):
            w = 18 if i % 2 == 0 else 14
            x0 = 7 if i % 2 == 0 else 9
            draw.line([(x0, y), (x0 + w, y)], fill=_GRAY, width=2)
    elif k == ICON_DRIZZLE:
        _draw_cloud(draw, 12, 10, 0.95, fill=_CLOUD)
        _draw_rain_drops(draw, 16, 12, 0.85, count=2)
    elif k == ICON_RAIN:
        _draw_cloud(draw, 12, 9, 1.0, fill=_CLOUD_DARK)
        _draw_rain_drops(draw, 16, 12, 1.0, count=3)
        # Extra heavy drop
        draw.line([(22, 22), (20, 28)], fill=_BLUE, width=2)
    elif k == ICON_SNOW:
        _draw_cloud(draw, 12, 9, 1.0, fill=_CLOUD)
        _draw_snow_flakes(draw, 16, 12, 1.0)
    elif k == ICON_THUNDER:
        _draw_cloud(draw, 11, 8, 1.0, fill=_PURPLE)
        _draw_bolt(draw, 14, 10, 0.85)
    else:
        # Unknown: simple "?"-like mark
        draw.ellipse([8, 6, 24, 22], outline=accent, width=2)
        draw.line([(16, 24), (16, 28)], fill=accent, width=2)

    if size != base:
        img = img.resize((size, size), Image.NEAREST)
    return img


@lru_cache(maxsize=64)
def cached_weather_icon(key: str, size: int) -> Image.Image:
    """Cached copy-safe icon; callers should .copy() before mutating."""
    return render_weather_icon(key, size=size)
