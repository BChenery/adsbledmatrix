"""LED matrix hardware configuration for Raspberry Pi."""


def calculate_matrix_dimensions(
    rows: int,
    cols: int,
    chain: int,
    parallel: int,
    pixel_mapper: str,
) -> tuple[int, int]:
    """Return the logical display width and height after applying a pixel mapper.

    This assumes the standard single-chain U-mapper layout used by this
    project: the chain is folded in half vertically, forming a 2-row grid.
    """
    mapper = (pixel_mapper or "").strip()
    if mapper.startswith("U-mapper"):
        return cols * (chain // 2), rows * 2 * parallel
    return cols * chain, rows * parallel


# Default arrangement: 256x128 using four 64x64 panels (2 wide x 2 tall).
# rpi-rgb-led-matrix supports up to 3 parallel chains on a standard 40-pin Pi.
# Larger 512x256 arrangements need a Compute Module or an active adapter board.

LED_MATRIX_CONFIG = {
    "rows": 64,
    "cols": 64,
    "chain_length": 2,   # 2 panels wide
    "parallel": 2,       # 2 panels tall
    "hardware_mapping": "regular",  # or "adafruit-hat", "adafruit-hat-pwm"
    "pwm_bits": 11,
    "brightness": 100,
    "gpio_slowdown": 2,  # Increase to 2-4 for Pi 4
    "limit_refresh": 0,
}

# 512x256 arrangement using sixteen 128x64 panels (4 wide x 4 tall).
# NOTE: This requires a Raspberry Pi Compute Module or an active adapter board
# that provides 4+ parallel chains. It will NOT work on a standard Pi 4.
LED_MATRIX_CONFIG_4x4 = {
    "rows": 64,
    "cols": 128,
    "chain_length": 4,
    "parallel": 4,
    "hardware_mapping": "regular",
    "pwm_bits": 11,
    "brightness": 100,
    "gpio_slowdown": 2,
}

# 128x64 panels in a single 1x4 chain (512x64)
LED_MATRIX_CONFIG_1x4 = {
    "rows": 64,
    "cols": 128,
    "chain_length": 4,
    "parallel": 1,
    "hardware_mapping": "regular",
    "pwm_bits": 11,
    "brightness": 100,
    "gpio_slowdown": 2,
}
