"""Mock LED matrix for development without hardware."""

import logging
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)

# Default dimensions match the backend config defaults
DEFAULT_WIDTH = 256   # 128 cols * 2 panels wide after U-mapper
DEFAULT_HEIGHT = 128  # 64 rows * 2 panels tall after U-mapper


class MockLEDMatrix:
    """Software-only mock of the LED matrix. Saves frames to disk for inspection."""

    is_hardware = False

    def __init__(self, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT):
        self.width = width
        self.height = height
        self._frame_count = 0
        self._last_frame: Image.Image | None = None
        logger.info(f"Mock LED matrix: {self.width}x{self.height}")

    def SetImage(self, image: Image.Image):
        """Match the rpi-rgb-led-matrix API."""
        self._last_frame = image.copy()
        self._frame_count += 1
        # Optionally save every N frames for debugging
        if self._frame_count % 300 == 0:  # Every ~10 seconds at 30fps
            debug_dir = Path("/tmp/adsbledmatrix-debug")
            debug_dir.mkdir(exist_ok=True)
            path = debug_dir / f"frame_{self._frame_count:06d}.png"
            image.save(path)
            logger.debug(f"Saved debug frame to {path}")

    def display(self, image: Image.Image):
        """Legacy alias for SetImage."""
        self.SetImage(image)

    def set_brightness(self, brightness: int):
        logger.debug(f"Mock brightness set to {brightness}")

    def clear(self):
        self._last_frame = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        logger.debug("Mock matrix cleared")

    def get_last_frame(self) -> Image.Image | None:
        return self._last_frame
