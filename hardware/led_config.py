"""LED matrix hardware configuration for Raspberry Pi."""

# Panel arrangement: 4 panels in a chain = 512x64 (or 256x128 depending on wiring)
# For 512x256: typically 2 chains of 2 panels each, or 4 panels in a 2x2 arrangement

LED_MATRIX_CONFIG = {
    "rows": 64,
    "cols": 128,
    "chain_length": 4,  # 4 panels chained
    "parallel": 1,
    "hardware_mapping": "regular",  # or "adafruit-hat", "adafruit-hat-pwm"
    "pwm_bits": 11,
    "brightness": 100,
    "gpio_slowdown": 2,  # Increase to 2-4 for Pi 4
    "limit_refresh": 0,
    # Panel arrangement for 512x256 (4 panels in 2x2)
    # If panels are arranged as 2 wide x 2 tall:
    # "panel_width": 256,
    # "panel_height": 128,
}

# Alternative for 64x64 panels in 2x2 grid (256x128) with 2 parallel chains
LED_MATRIX_CONFIG_2x2 = {
    "rows": 64,
    "cols": 64,
    "chain_length": 2,
    "parallel": 2,
    "hardware_mapping": "regular",
    "pwm_bits": 11,
    "brightness": 100,
    "gpio_slowdown": 2,
}

# Alternative for 128x64 panels in 1x4 chain (512x64)
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
