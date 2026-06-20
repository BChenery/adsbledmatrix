import pytest

from app.config import Settings
from hardware.led_config import calculate_matrix_dimensions


def test_u_mapper_default_dimensions():
    """Four 128x64 panels in a U-mapper chain produce 256x128."""
    assert calculate_matrix_dimensions(64, 128, 4, 1, "U-mapper") == (256, 128)


def test_u_mapper_with_rotate():
    """U-mapper may be chained with Rotate; dimensions stay the same."""
    assert calculate_matrix_dimensions(64, 128, 4, 1, "U-mapper;Rotate:180") == (256, 128)


def test_no_mapper_dimensions():
    """Without a mapper the logical size is the raw chain size."""
    assert calculate_matrix_dimensions(64, 128, 4, 1, "") == (512, 64)


def test_u_mapper_empty_string_is_no_mapper():
    """An empty or whitespace mapper is treated as no mapper."""
    assert calculate_matrix_dimensions(64, 128, 4, 1, "   ") == (512, 64)


def test_default_led_settings_match_pdf():
    """Default settings must match the PDF wiring diagram."""
    settings = Settings()
    assert settings.led_matrix_rows == 64
    assert settings.led_matrix_cols == 128
    assert settings.led_matrix_chain == 4
    assert settings.led_matrix_parallel == 1
    assert settings.led_matrix_pixel_mapper == "U-mapper"
    assert settings.led_matrix_row_address_type == 3
    assert settings.led_matrix_pwm_bits == 7
    assert settings.led_matrix_brightness == 70
    assert settings.led_matrix_gpio_slowdown == 4
