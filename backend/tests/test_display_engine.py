import pytest
from app.services.display_engine import DisplayEngine


def _count_non_black_pixels(img):
    """Count pixels that are not exactly black."""
    return sum(1 for px in img.get_flattened_data() if px != (0, 0, 0))


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


def test_time_window_detection(engine):
    """Window detection works for both same-day and wrap-around intervals."""
    from unittest.mock import patch
    from datetime import time, datetime, date

    with patch("app.services.display_engine.datetime") as mock_dt:
        mock_dt.strptime = datetime.strptime
        mock_dt.now.return_value = datetime.combine(date.today(), time(23, 30))
        assert engine._is_in_time_window("22:00", "06:00") is True

        mock_dt.now.return_value = datetime.combine(date.today(), time(3, 0))
        assert engine._is_in_time_window("22:00", "06:00") is True

        mock_dt.now.return_value = datetime.combine(date.today(), time(12, 0))
        assert engine._is_in_time_window("22:00", "06:00") is False

        mock_dt.now.return_value = datetime.combine(date.today(), time(2, 0))
        assert engine._is_in_time_window("22:00", "23:00") is False


def test_time_window_uses_configured_timezone(engine):
    """When a timezone is supplied, the window is evaluated in that timezone."""
    from unittest.mock import patch
    from datetime import time, datetime, date
    from zoneinfo import ZoneInfo

    with patch("app.services.display_engine.datetime") as mock_dt:
        mock_dt.strptime = datetime.strptime
        # 05:14 in the user's timezone should be inside a 19:00-06:00 sleep window.
        mock_dt.now.return_value = datetime.combine(date.today(), time(5, 14))
        assert engine._is_in_time_window("19:00", "06:00", "America/Los_Angeles") is True
        mock_dt.now.assert_called_with(ZoneInfo("America/Los_Angeles"))

        # 15:00 should be outside the same window.
        mock_dt.now.return_value = datetime.combine(date.today(), time(15, 0))
        assert engine._is_in_time_window("19:00", "06:00", "America/Los_Angeles") is False


def test_sleep_window_blanks_display(engine):
    """Sleep window clears the matrix and stops rendering."""
    from unittest.mock import MagicMock, patch
    from datetime import datetime, date, time

    config = MagicMock()
    config.night_mode = False
    config.sleep_mode = True
    config.sleep_mode_start = "23:00"
    config.sleep_mode_end = "06:00"

    engine._night_mode_active = False
    engine._matrix = MagicMock()

    with patch("app.services.display_engine.datetime") as mock_dt:
        mock_dt.strptime = datetime.strptime
        mock_dt.now.return_value = datetime.combine(date.today(), time(0, 30))
        assert engine._handle_night_mode(config) is True
        engine._matrix.clear.assert_called_once()
        assert engine._night_mode_active is True


def test_sleep_window_overrides_dim_window(engine):
    """If sleep and dim windows overlap, sleep takes precedence."""
    from unittest.mock import MagicMock, patch
    from datetime import datetime, date, time

    config = MagicMock()
    config.night_mode = True
    config.night_mode_start = "22:00"
    config.night_mode_end = "07:00"
    config.sleep_mode = True
    config.sleep_mode_start = "23:00"
    config.sleep_mode_end = "06:00"

    engine._night_mode_active = False
    engine._matrix = MagicMock()

    with patch("app.services.display_engine.datetime") as mock_dt:
        mock_dt.strptime = datetime.strptime
        mock_dt.now.return_value = datetime.combine(date.today(), time(0, 30))
        assert engine._handle_night_mode(config) is True
        engine._matrix.clear.assert_called_once()


def test_draw_text_clips_to_box_width(engine):
    """Long text must not render past the declared box width."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (100, 32), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    engine._draw_text(draw, 10, 0, 40, "VERYLONGCALLSIGN", (255, 255, 255), None, 16)

    # No non-black pixel may appear beyond x=50 (10 + 40).
    pixels = img.load()
    for py in range(32):
        for px in range(50, 100):
            assert pixels[px, py] == (0, 0, 0), f"text overflow at ({px},{py})"


def test_draw_text_keeps_short_text_inside_box(engine):
    """Short text should render normally inside its box."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (100, 32), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    engine._draw_text(draw, 0, 0, 100, "ABC", (255, 255, 255), None, 16)

    bbox = img.getbbox()
    assert bbox is not None
    assert bbox[2] <= 100


def test_draw_text_clips_to_box_height(engine):
    """An oversized font must not render past the declared box height."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (100, 64), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Font size 24 in a 14px-tall box will overflow without clipping.
    engine._draw_text(draw, 0, 10, 100, "ALT: 145", (255, 255, 255), None, 24, height=14)

    # No non-black pixel may appear below y=24 (10 + 14).
    pixels = img.load()
    for py in range(24, 64):
        for px in range(100):
            assert pixels[px, py] == (0, 0, 0), f"text overflow below box at ({px},{py})"


def test_distance_bar_does_not_draw_label_below_bar(engine):
    """The distance bar must not render its value label below the bar area."""
    from unittest.mock import MagicMock
    from app.services.display_engine import RenderContext
    from PIL import Image, ImageDraw

    aircraft = MagicMock()
    aircraft.distance_km = 12.5

    ctx = RenderContext(aircraft=aircraft)

    img = Image.new("RGB", (256, 128), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    engine._draw_distance_bar(draw, 4, 118, 248, 6, ctx, (0, 212, 255))

    # The area below the bar (y >= 126, where the old label was drawn) must remain black.
    pixels = img.load()
    for py in range(126, 128):
        for px in range(256):
            assert pixels[px, py] == (0, 0, 0), f"non-black pixel below bar at ({px},{py})"


def test_draw_radar_plane_symbol_rotates_with_heading(engine):
    """A plane symbol at due north with heading 90° (east) should point right."""
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
    element.use_plane_symbol = True

    aircraft = MagicMock()
    aircraft.distance_km = 10.0
    aircraft.bearing = 0.0  # North
    aircraft.heading = 90.0  # East

    ctx = RenderContext(aircraft=aircraft)

    img = Image.new('RGB', (100, 100), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    engine._draw_radar(draw, img, element, ctx)

    # The aircraft is at (50, 26). With heading 90° the nose should be to the right,
    # well outside the original 7×7 dot (which only reaches x=53).
    red_pixels_east = [
        (px, py)
        for px in range(54, 58)
        for py in range(24, 29)
        if img.getpixel((px, py)) == (255, 0, 0)
    ]
    assert red_pixels_east, "Expected red plane pixels east of the aircraft position"

    # Confirm no red pixel where the unrotated nose would be; the plane has rotated east.
    assert img.getpixel((50, 22)) == (0, 0, 0), "Expected no red pixel at the unrotated nose position"


def test_draw_radar_plane_symbol_disabled_uses_dot(engine):
    """When use_plane_symbol is False the renderer should fall back to the dot."""
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
    element.use_plane_symbol = False

    aircraft = MagicMock()
    aircraft.distance_km = 10.0
    aircraft.bearing = 0.0
    aircraft.heading = 90.0

    ctx = RenderContext(aircraft=aircraft)

    img = Image.new('RGB', (100, 100), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    engine._draw_radar(draw, img, element, ctx)

    # The original dot is rendered near (50, 26).
    assert img.getpixel((50, 26)) == (255, 0, 0), "Expected red dot at aircraft position"

    # No plane nose should appear east of the dot.
    red_pixels_east = [
        (px, py)
        for px in range(54, 58)
        for py in range(24, 29)
        if img.getpixel((px, py)) == (255, 0, 0)
    ]
    assert not red_pixels_east, "Did not expect plane pixels east of the aircraft position"


def test_draw_radar_plane_symbol_falls_back_when_no_heading(engine):
    """When the aircraft has no heading the renderer should fall back to the dot."""
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
    element.use_plane_symbol = True

    aircraft = MagicMock()
    aircraft.distance_km = 10.0
    aircraft.bearing = 0.0
    aircraft.heading = None

    ctx = RenderContext(aircraft=aircraft)

    img = Image.new('RGB', (100, 100), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    engine._draw_radar(draw, img, element, ctx)

    # The original dot is rendered near (50, 26).
    assert img.getpixel((50, 26)) == (255, 0, 0), "Expected red dot at aircraft position"

    # No plane nose should appear east of the dot.
    red_pixels_east = [
        (px, py)
        for px in range(54, 58)
        for py in range(24, 29)
        if img.getpixel((px, py)) == (255, 0, 0)
    ]
    assert not red_pixels_east, "Did not expect plane pixels east of the aircraft position"


def test_vertical_rate_uses_custom_font_size(engine):
    """A larger explicit font_size should render more text pixels than the default."""
    from unittest.mock import MagicMock
    from app.services.display_engine import RenderContext
    from PIL import Image, ImageDraw

    aircraft = MagicMock()
    aircraft.vertical_rate = 1200

    ctx = RenderContext(aircraft=aircraft)

    element_small = MagicMock()
    element_small.element_type = 'vertical_rate'
    element_small.font_size = 12
    element_small.font_family = None

    element_large = MagicMock()
    element_large.element_type = 'vertical_rate'
    element_large.font_size = 24
    element_large.font_family = None

    img_small = Image.new('RGB', (64, 32), (0, 0, 0))
    draw_small = ImageDraw.Draw(img_small)
    engine._draw_vertical_rate(draw_small, 0, 0, 64, 32, element_small, ctx, (255, 255, 255))

    img_large = Image.new('RGB', (64, 32), (0, 0, 0))
    draw_large = ImageDraw.Draw(img_large)
    engine._draw_vertical_rate(draw_large, 0, 0, 64, 32, element_large, ctx, (255, 255, 255))

    small_pixels = _count_non_black_pixels(img_small)
    large_pixels = _count_non_black_pixels(img_large)

    assert small_pixels > 0, "Expected the small font to render some text"
    assert large_pixels > small_pixels, (
        f"Expected larger font_size to render more pixels, got {large_pixels} <= {small_pixels}"
    )


def test_draw_image_thresholds_alpha_fringe(engine, tmp_path):
    """Semi-transparent coloured edge pixels should be removed, not drawn as dots."""
    from unittest.mock import MagicMock
    from PIL import Image
    from app.services.display_engine import RenderContext

    # Create a 32x32 image: yellow shape on transparent background with
    # semi-transparent red fringe pixels around the edge.
    logo = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for y in range(8, 24):
        for x in range(8, 24):
            logo.putpixel((x, y), (255, 255, 0, 255))
    for y in range(7, 25):
        for x in range(7, 25):
            if logo.getpixel((x, y))[3] == 0:
                logo.putpixel((x, y), (255, 0, 0, 10))
    logo_path = tmp_path / "fringe_logo.png"
    logo.save(logo_path)

    element = MagicMock()
    element.image_path = str(logo_path)

    ctx = RenderContext()
    img = Image.new("RGB", (32, 32), (0, 0, 0))
    engine._draw_image(img, 0, 0, 32, 32, element, ctx)

    red_pixels = [px for px in img.getdata() if px == (255, 0, 0)]
    assert not red_pixels, "Expected semi-transparent red fringe to be removed"
