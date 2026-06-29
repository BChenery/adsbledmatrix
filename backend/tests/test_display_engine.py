import pytest
from app.services.display_engine import DisplayEngine


@pytest.fixture
def engine():
    """Return a DisplayEngine using the inline mock matrix fallback."""
    return DisplayEngine()


@pytest.mark.asyncio
async def test_draw_radar_positions_aircraft_dot(engine):
    """Aircraft due north at half the range should appear at the top centre of the radar."""
    from unittest.mock import MagicMock
    from app.services.display_engine import RenderContext
    from PIL import Image, ImageDraw

    element = MagicMock()
    element.element_type = 'radar'
    element.x = 0
    element.y = 0
    element.width = 100
    element.height = 100
    element.range_km = 20
    element.ring_color = '#333333'
    element.dot_color = '#ff0000'
    element.user_dot_color = '#00ff00'
    element.show_rings = True
    element.show_ticks = True
    element.bg_color = None

    aircraft = MagicMock()
    aircraft.distance_km = 10.0
    aircraft.bearing = 0.0  # North

    ctx = RenderContext(aircraft=aircraft)

    img = Image.new('RGB', (100, 100), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    engine._draw_radar(draw, img, element, ctx)

    # North at half range in a 100x100 box: dot should be near (50, 25)
    red_pixels = [
        (px, py)
        for px in range(48, 53)
        for py in range(23, 28)
        if img.getpixel((px, py)) == (255, 0, 0)
    ]
    assert red_pixels, "Expected at least one red pixel near the radar dot centre"


def test_brightness_defaults_to_settings(engine):
    from app.config import settings
    assert engine.get_brightness() == settings.led_matrix_brightness


def test_set_brightness_clamps_and_updates(engine):
    engine.set_brightness(150)
    assert engine.get_brightness() == 100

    engine.set_brightness(-10)
    assert engine.get_brightness() == 0

    engine.set_brightness(45)
    assert engine.get_brightness() == 45
