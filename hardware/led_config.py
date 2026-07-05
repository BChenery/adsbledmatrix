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
    if rows <= 0 or cols <= 0 or chain <= 0 or parallel <= 0:
        raise ValueError("rows, cols, chain, and parallel must be positive")
    mapper = (pixel_mapper or "").strip()
    if mapper.startswith("U-mapper"):
        if chain % 2 != 0:
            raise ValueError("U-mapper requires an even chain length")
        return cols * (chain // 2), rows * 2 * parallel
    return cols * chain, rows * parallel


# Default arrangement: 256x128 using four 128x64 P2 panels wired in a single
# HUB75 chain with a serpentine (U-mapper) bottom row.
#
#   Panel 1 (UL) -> Panel 2 (UR) -> Panel 3 (BR) -> Panel 4 (BL)
#
# Total logical display: 256x128 pixels.
# This requires a single-channel HUB75 adapter board and an external 5V PSU.

LED_MATRIX_CONFIG = {
    "rows": 64,
    "cols": 128,
    "chain_length": 4,
    "parallel": 1,
    "hardware_mapping": "regular",
    "pixel_mapper": "U-mapper",
    "row_address_type": 0,
    "pwm_bits": 7,
    "brightness": 70,
    "gpio_slowdown": 5,
    "limit_refresh": 0,
    "flip_vertical": True,
    "rgb_sequence": "BGR",
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
