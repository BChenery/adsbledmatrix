# Design: P2 4-Panel Serpentine Wiring Support

**Date:** 2026-06-20
**Status:** Approved

## Background

The project has a new hardware target documented in `New Wiring diagram and setup.pdf`. The display consists of four P2 128×64 RGB LED panels wired in a single HUB75 chain with a serpentine bottom row. This is materially different from the previous default of four 64×64 panels arranged as `chain=2, parallel=2`.

The friend's Raspberry Pi is installed from this repository using `scripts/install.sh` and updated with `scripts/update.sh`. The Pi is a clean install with no custom `.env` overrides to preserve.

## Hardware target

- 4× P2 indoor panels, each 128×64 pixels, 256×128 mm physical size
- Total logical display: **256×128 pixels**
- Electrical chain: Pi → Panel 1 (upper-left) → Panel 2 (upper-right) → Panel 3 (bottom-right) → Panel 4 (bottom-left)
- Single-channel HUB75 adapter board connected to the Pi 4 GPIO header
- Panels powered from an external 5 V supply, not from the Pi

Front view:
```
┌─────────┬─────────┐
│ Panel 1 │ Panel 2 │
│  UL     │  UR     │
├─────────┼─────────┤
│ Panel 4 │ Panel 3 │
│  BL     │  BR     │
└─────────┴─────────┘
```

Data flows left-to-right on the top row and right-to-left on the bottom row (serpentine).

## Required `rpi-rgb-led-matrix` settings

| Flag / option | Value | Reason |
|---|---|---|
| `--led-rows` | 64 | Panel height |
| `--led-cols` | 128 | Panel width |
| `--led-chain` | 4 | Four panels in one chain |
| `--led-parallel` | 1 | Single-channel adapter board |
| `--led-pixel-mapper` | `U-mapper` | Arranges chain into 2×2 serpentine grid |
| `--led-row-addr-type` | 3 | ABC-addressed panels (1/32 scan) |
| `--led-slowdown-gpio` | 4 | Pi 4 + 4 panels |
| `--led-multiplexing` | 0 | Standard P2 panels |
| `--led-pwm-bits` | 7 | Reduce flicker on long chain |
| `--led-brightness` | 70 | Indoor brightness |
| `--led-flip-vertical` | `true` | Swap top/bottom panel rows for bottom-fed HUB75 wiring |
| `--led-rgb-sequence` | `BGR` | P2 panels wire colour channels as BGR |

### Note on `--led-sba`

The PDF mentions `--led-sba=1` (serpentine bottom arrangement). This flag is **not present** in the standard `hzeller/rpi-rgb-led-matrix` library that the installer clones. The serpentine bottom row is handled by the `U-mapper`, so this project will **not** add an `sba` option.

## Goals

1. Make the PDF wiring the default project configuration.
2. Fix the display dimension calculation so the rendering canvas matches the real 256×128 output instead of the raw 512×64 chain size.
3. Update documentation and environment examples so a clean install or `update.sh` run produces a working display.
4. Keep the code simple — no profile/preset system is required because this is the only supported hardware layout.

## Proposed changes

### 1. `backend/app/config.py`

Update the `Settings` class defaults:

```python
led_matrix_rows: int = 64
led_matrix_cols: int = 128
led_matrix_chain: int = 4
led_matrix_parallel: int = 1
led_matrix_hardware_mapping: str = "regular"
led_matrix_pixel_mapper: str = "U-mapper"
led_matrix_row_address_type: int = 3
led_matrix_multiplexing: int = 0
led_matrix_panel_type: str = ""
led_matrix_pwm_bits: int = 7
led_matrix_brightness: int = 70
led_matrix_gpio_slowdown: int = 4
led_matrix_limit_refresh: int = 0
led_matrix_flip_vertical: bool = True
led_matrix_rgb_sequence: str = "BGR"
```

Update the comment block above these settings to describe the P2 4-panel serpentine layout, including that `flip_vertical` compensates for the bottom-fed HUB75 input and `rgb_sequence=BGR` matches the target panels' colour channel wiring.

### 2. Display dimension calculation

Introduce a helper in `hardware/led_config.py`:

```python
def calculate_matrix_dimensions(rows: int, cols: int, chain: int, parallel: int, pixel_mapper: str) -> tuple[int, int]:
    """Return the logical display width and height after applying a pixel mapper."""
    if pixel_mapper.strip().startswith("U-mapper"):
        # U-mapper folds the chain in half vertically.
        return cols * (chain // 2), rows * 2 * parallel
    return cols * chain, rows * parallel
```

Use this helper in:
- `backend/app/services/display_engine.py` to set the initial render size.
- `hardware/led_matrix.py`: after creating `RGBMatrix`, override `self.width` / `self.height` with `matrix.width` / `matrix.height`.
- `hardware/mock_led.py`: default to 256×128 and accept width/height from the caller.

### 3. `hardware/led_config.py`

- Make `LED_MATRIX_CONFIG` match the new defaults.
- Keep `LED_MATRIX_CONFIG_1x4` as a named reference for the 512×64 single-row layout.
- Remove `LED_MATRIX_CONFIG_4x4` because it requires a Compute Module / active adapter board and is not the target hardware.

### 4. `.env.example`

Update the LED variables to the new defaults:

```bash
ADSB_LED_MATRIX_ROWS=64
ADSB_LED_MATRIX_COLS=128
ADSB_LED_MATRIX_CHAIN=4
ADSB_LED_MATRIX_PARALLEL=1
ADSB_LED_MATRIX_PIXEL_MAPPER=U-mapper
ADSB_LED_MATRIX_ROW_ADDRESS_TYPE=3
ADSB_LED_MATRIX_PWM_BITS=7
ADSB_LED_MATRIX_BRIGHTNESS=70
ADSB_LED_MATRIX_GPIO_SLOWDOWN=4
ADSB_LED_MATRIX_FLIP_VERTICAL=true
ADSB_LED_MATRIX_RGB_SEQUENCE=BGR
```

### 5. `docs/SETUP.md`

Rewrite the "Hardware Assembly" and "Panel Arrangement" sections:
- Parts list updated for P2 128×64 panels and single-channel HUB75 adapter.
- Diagram showing Panel 1 → Panel 2 → Panel 3 → Panel 4 chain.
- Environment variable snippet for `/opt/adsbledmatrix/.env`.
- Note explaining that `--led-sba` is omitted because `U-mapper` handles serpentine wiring in the standard library.

### 6. `scripts/install.sh` and `scripts/update.sh`

No changes to the install/update mechanics are required because the service reads defaults from `config.py`. Optional additions:
- `update.sh` can print the active LED dimensions after restart by importing `app.config.settings`.

## Verification

### Automated tests

Add or update tests in `backend/tests/`:

1. `calculate_matrix_dimensions()` returns 256×128 for the new default settings.
2. `calculate_matrix_dimensions()` returns 512×64 for a no-mapper chain of four 128×64 panels.
3. Settings instantiation produces the new defaults when no env vars are set.

### Local mock run

```bash
cd backend
ADSB_MOCK_AIRCRAFT=true uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Confirm via `/api/diagnostics` that `width: 256`, `height: 128`, `pixel_mapper: U-mapper`.

### On the Pi

After your friend runs:

```bash
sudo bash /opt/adsbledmatrix/scripts/update.sh
```

Verify:

```bash
sudo journalctl -u adsbledmatrix -f
# Should show "LED matrix initialized: 256x128"

# Or via API:
curl http://adsb-display.local/api/diagnostics | python3 -m json.tool
# Expected: width 256, height 128, pixel_mapper U-mapper, rows 64, cols 128, chain 4, parallel 1, flip_vertical true, rgb_sequence BGR
```

## Out of scope

- Support for the old 64×64 2×2 layout as a default. It can still be achieved by setting env vars, but it is no longer the default.
- Adding `--led-sba` support (non-standard flag).
- A profile/preset selector UI.
