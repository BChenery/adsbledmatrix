"""LED matrix hardware wrapper using rpi-rgb-led-matrix."""

import logging
import os
from typing import Optional
from PIL import Image

try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
    HAS_MATRIX = True
except ImportError:
    HAS_MATRIX = False

from app.config import settings

logger = logging.getLogger(__name__)


class LEDMatrix:
    """Wrapper for the RGB LED matrix."""

    is_hardware = True

    def __init__(self):
        self.matrix: Optional[RGBMatrix] = None
        self.width = settings.led_matrix_cols * settings.led_matrix_chain
        self.height = settings.led_matrix_rows * settings.led_matrix_parallel

        if HAS_MATRIX:
            try:
                options = RGBMatrixOptions()
                options.rows = settings.led_matrix_rows
                options.cols = settings.led_matrix_cols
                options.chain_length = settings.led_matrix_chain
                options.parallel = settings.led_matrix_parallel
                options.hardware_mapping = settings.led_matrix_hardware_mapping
                if settings.led_matrix_pixel_mapper:
                    options.pixel_mapper_config = settings.led_matrix_pixel_mapper
                if settings.led_matrix_row_address_type != 0:
                    options.row_address_type = settings.led_matrix_row_address_type
                if settings.led_matrix_multiplexing != 0:
                    options.multiplexing = settings.led_matrix_multiplexing
                if settings.led_matrix_panel_type:
                    try:
                        options.panel_type = settings.led_matrix_panel_type
                    except Exception as e:
                        logger.warning(
                            f"Panel type '{settings.led_matrix_panel_type}' not supported by this "
                            f"rpi-rgb-led-matrix build: {e}"
                        )
                options.pwm_bits = settings.led_matrix_pwm_bits
                options.brightness = settings.led_matrix_brightness
                options.gpio_slowdown = settings.led_matrix_gpio_slowdown
                if settings.led_matrix_limit_refresh > 0:
                    options.limit_refresh_rate_hz = settings.led_matrix_limit_refresh

                # SPWM options only exist in the PWM fork of rpi-rgb-led-matrix.
                # Set them defensively so the same code works with the main library.
                for spwm_attr in (
                    "spwm_row_address_type",
                    "spwm_register_config",
                    "spwm_scan_rows",
                ):
                    if hasattr(options, spwm_attr):
                        setattr(options, spwm_attr, getattr(settings, f"led_matrix_{spwm_attr}"))
                    else:
                        logger.debug(f"RGBMatrixOptions does not support {spwm_attr}")

                if settings.led_matrix_led_rgb_sequence and settings.led_matrix_led_rgb_sequence != "RGB":
                    if hasattr(options, "led_rgb_sequence"):
                        options.led_rgb_sequence = settings.led_matrix_led_rgb_sequence
                    else:
                        logger.debug("RGBMatrixOptions does not support led_rgb_sequence")

                # rpi-rgb-led-matrix needs root to initialise GPIO timing, then
                # drops privileges. Make sure it drops back to the service user
                # so file permissions remain correct.
                if os.geteuid() == 0:
                    options.drop_privileges = True
                    options.drop_priv_user = "adsb"
                    options.drop_priv_group = "adsb"

                self.matrix = RGBMatrix(options=options)
                logger.info(
                    f"LED matrix initialized: {self.width}x{self.height}"
                )
            except Exception as e:
                logger.error(f"Failed to initialize LED matrix: {e}")
                self.matrix = None
        else:
            logger.warning(
                "rpi-rgb-led-matrix not available. Running in mock mode."
            )

    def display(self, image: Image.Image):
        """Display a PIL Image on the LED matrix."""
        if self.matrix is None:
            return
        # Ensure image is correct size
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height), Image.LANCZOS)
        self.matrix.SetImage(image)
        self._last_frame = image.copy()

    def SetImage(self, image: Image.Image):
        """Alias for display() — matches rpi-rgb-led-matrix API."""
        self.display(image)

    def get_last_frame(self) -> Optional[Image.Image]:
        """Return the last frame displayed (for preview endpoints)."""
        return self._last_frame.copy() if self._last_frame is not None else None

    def set_brightness(self, brightness: int):
        """Set matrix brightness (0-100)."""
        if self.matrix:
            self.matrix.brightness = max(0, min(100, brightness))

    def clear(self):
        """Clear the matrix."""
        if self.matrix:
            self.matrix.Clear()
