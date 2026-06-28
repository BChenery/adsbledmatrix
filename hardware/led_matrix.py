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
                    options.panel_type = settings.led_matrix_panel_type
                options.pwm_bits = settings.led_matrix_pwm_bits
                options.brightness = settings.led_matrix_brightness
                options.gpio_slowdown = settings.led_matrix_gpio_slowdown
                if settings.led_matrix_limit_refresh > 0:
                    options.limit_refresh_rate_hz = settings.led_matrix_limit_refresh

                # rpi-rgb-led-matrix needs root to initialise GPIO timing, then
                # drops privileges. Make sure it drops back to the service user
                # so file permissions remain correct.
                if os.geteuid() == 0:
                    options.drop_privileges = True
                    options.drop_priv_user = "adsb"
                    options.drop_priv_group = "adsb"

                self.matrix = RGBMatrix(options=options)
                # Pixel mappers such as U-mapper change the logical canvas size
                # (e.g. 4x 128x64 panels become 256x128 rather than 512x64).
                # Use the matrix's reported dimensions so downstream renderers
                # produce images that match the physical layout.
                self.width = self.matrix.width
                self.height = self.matrix.height
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
