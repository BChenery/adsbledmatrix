"""Hardware matrix factory — returns real LED matrix or mock fallback."""

import logging
from typing import Optional
from PIL import Image

logger = logging.getLogger(__name__)


def create_matrix(width: int, height: int):
    """Try to initialise the real LED matrix, falling back to mock on failure.

    Uses lazy imports so that importing this module does not trigger
    side-effects in ``hardware.led_matrix`` (which creates a singleton).
    """
    try:
        from hardware.led_matrix import LEDMatrix

        matrix = LEDMatrix()
        if matrix.matrix is not None:
            logger.info("Using real LED matrix")
            return matrix
        logger.warning("LEDMatrix initialised but internal matrix is None, using mock")
    except Exception as exc:
        logger.warning(f"Could not initialise LEDMatrix ({exc}), using mock")

    try:
        from hardware.mock_led import MockLEDMatrix

        return MockLEDMatrix(width=width, height=height)
    except Exception as exc:
        logger.warning(f"Could not import MockLEDMatrix ({exc}), using inline mock")

    # Absolute last resort — same API, no external deps
    return _InlineMockLEDMatrix(width=width, height=height)


class _InlineMockLEDMatrix:
    """Fallback mock when even ``hardware.mock_led`` is unavailable."""

    is_hardware = False

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._frame_count = 0
        self._last_frame: Optional[Image.Image] = None
        logger.info(f"Inline mock LED matrix: {self.width}x{self.height}")

    def SetImage(self, image: Image.Image):
        self._last_frame = image.copy()
        self._frame_count += 1
        if self._frame_count % 300 == 0:  # Every ~10 seconds at 30fps
            from pathlib import Path

            debug_dir = Path("/tmp/adsbledmatrix-debug")
            debug_dir.mkdir(exist_ok=True)
            path = debug_dir / f"frame_{self._frame_count:06d}.png"
            image.save(path)
            logger.debug(f"Saved debug frame to {path}")

    def display(self, image: Image.Image):
        self.SetImage(image)

    def set_brightness(self, brightness: int):
        logger.debug(f"Mock brightness set to {brightness}")

    def clear(self):
        self._last_frame = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        logger.debug("Mock matrix cleared")

    def get_last_frame(self) -> Optional[Image.Image]:
        return self._last_frame
