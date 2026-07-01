# P2 4-Panel Serpentine Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the project defaults and dimension logic so the display matches the PDF wiring (four 128×64 P2 panels in a single serpentine HUB75 chain, 256×128 logical display) and works after a friend runs `scripts/update.sh`.

**Architecture:** Update `backend/app/config.py` defaults to the PDF values; add a `calculate_matrix_dimensions` helper in `hardware/led_config.py` that knows the U-mapper halves the chain vertically; make both `hardware/led_matrix.py` and `backend/app/services/display_engine.py` use the logical (post-mapper) dimensions instead of the raw chain size; update docs and the env example.

**Tech Stack:** Python 3.13, Pydantic Settings, Pillow, rpi-rgb-led-matrix Python bindings, pytest.

---

## File map

| File | Responsibility |
|---|---|
| `hardware/led_config.py` | Presets and the new `calculate_matrix_dimensions` helper. |
| `backend/app/config.py` | Pydantic settings defaults for all LED matrix options. |
| `hardware/led_matrix.py` | Real matrix wrapper; must report actual mapped width/height. |
| `hardware/mock_led.py` | Software-only matrix fallback; default size must match new default. |
| `backend/app/services/display_engine.py` | Render loop; must render at logical display size. |
| `backend/tests/test_led_config.py` | New unit tests for dimension helper and config defaults. |
| `.env.example` | Example environment variables for the new default layout. |
| `docs/SETUP.md` | Hardware wiring and configuration documentation. |

---

## Task 1: Add dimension helper and tests

**Files:**
- Modify: `hardware/led_config.py`
- Create: `backend/tests/test_led_config.py`

- [ ] **Step 1: Add `calculate_matrix_dimensions` to `hardware/led_config.py`**

```python
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
```

Add the function near the top of `hardware/led_config.py`, after the module docstring and before the config dictionaries.

- [ ] **Step 2: Create `backend/tests/conftest.py` to add the project root to `sys.path`**

```python
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"

for path in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)
```

- [ ] **Step 3: Create the test file `backend/tests/test_led_config.py`**

```python
import pytest

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
```

- [ ] **Step 4: Run the new tests and confirm they pass**

Run:
```bash
cd /home/bchen/Github/adsbledmatrix/backend
. .venv/bin/activate && pytest tests/test_led_config.py -v
```

Expected output:
```
tests/test_led_config.py::test_u_mapper_default_dimensions PASSED
tests/test_led_config.py::test_u_mapper_with_rotate PASSED
tests/test_led_config.py::test_no_mapper_dimensions PASSED
tests/test_led_config.py::test_u_mapper_empty_string_is_no_mapper PASSED
```

- [ ] **Step 5: Commit**

```bash
git add hardware/led_config.py backend/tests/conftest.py backend/tests/test_led_config.py
git commit -m "feat: add calculate_matrix_dimensions helper for U-mapper layouts"
```

---

## Task 2: Update config defaults

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Replace the LED matrix defaults block**

In `backend/app/config.py`, replace the existing Display section comment and defaults with:

```python
    # Display
    # Default is a 256x128 display made of four 128x64 P2 panels wired in a
    # single HUB75 chain with a serpentine (U-mapper) bottom row:
    #
    #   Panel 1 (UL) -> Panel 2 (UR) -> Panel 3 (BR) -> Panel 4 (BL)
    #
    # Total logical display: 256x128 pixels.
    # This requires a single-channel HUB75 adapter board and an external 5V PSU.
    led_matrix_rows: int = 64
    led_matrix_cols: int = 128
    led_matrix_chain: int = 4
    led_matrix_parallel: int = 1
    led_matrix_hardware_mapping: str = "regular"
    led_matrix_pixel_mapper: str = "U-mapper"
    led_matrix_row_address_type: int = 3
    led_matrix_multiplexing: int = 0
    led_matrix_panel_type: str = ""  # e.g. "FM6126A"
    led_matrix_pwm_bits: int = 7
    led_matrix_brightness: int = 70
    led_matrix_gpio_slowdown: int = 4
    led_matrix_limit_refresh: int = 0
    led_matrix_flip_vertical: bool = True
```

- [ ] **Step 2: Add a test for default settings**

Append to `backend/tests/test_led_config.py`:

```python
from app.config import Settings


def test_default_led_settings_match_pdf():
    """Default settings must match the PDF wiring diagram."""
    settings = Settings()
    assert settings.led_matrix_rows == 64
    assert settings.led_matrix_cols == 128
    assert settings.led_matrix_chain == 4
    assert settings.led_matrix_parallel == 1
    assert settings.led_matrix_pixel_mapper == "U-mapper"
    assert settings.led_matrix_row_address_type == 0
    assert settings.led_matrix_pwm_bits == 7
    assert settings.led_matrix_brightness == 70
    assert settings.led_matrix_gpio_slowdown == 4
    assert settings.led_matrix_flip_vertical is True
```

- [ ] **Step 3: Run the test and confirm it passes**

Run:
```bash
cd /home/bchen/Github/adsbledmatrix/backend
pytest tests/test_led_config.py -v
```

Expected: all tests pass, including `test_default_led_settings_match_pdf`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/tests/test_led_config.py
git commit -m "feat: set LED matrix defaults to P2 4-panel serpentine layout"
```

---

## Task 3: Update hardware presets

**Files:**
- Modify: `hardware/led_config.py`

- [ ] **Step 1: Replace `LED_MATRIX_CONFIG` with the new default**

```python
LED_MATRIX_CONFIG = {
    "rows": 64,
    "cols": 128,
    "chain_length": 4,
    "parallel": 1,
    "hardware_mapping": "regular",
    "pixel_mapper": "U-mapper",
    "pwm_bits": 7,
    "brightness": 70,
    "gpio_slowdown": 4,
}
```

- [ ] **Step 2: Remove the 4x4 preset**

Delete the entire `LED_MATRIX_CONFIG_4x4` dictionary and its comment block.

- [ ] **Step 3: Keep `LED_MATRIX_CONFIG_1x4` as a reference**

Leave `LED_MATRIX_CONFIG_1x4` unchanged (it is a useful reference for a single-row 512x64 layout).

- [ ] **Step 4: Commit**

```bash
git add hardware/led_config.py
git commit -m "feat: update hardware presets for P2 serpentine layout"
```

---

## Task 4: Use actual matrix dimensions in `hardware/led_matrix.py`

**Files:**
- Modify: `hardware/led_matrix.py`

- [ ] **Step 1: Import the helper**

At the top of `hardware/led_matrix.py`, add:

```python
from hardware.led_config import calculate_matrix_dimensions
```

- [ ] **Step 2: Set initial dimensions from the helper, then override with real matrix size**

In `LEDMatrix.__init__`, replace:

```python
self.width = settings.led_matrix_cols * settings.led_matrix_chain
self.height = settings.led_matrix_rows * settings.led_matrix_parallel
```

with:

```python
self.width, self.height = calculate_matrix_dimensions(
    settings.led_matrix_rows,
    settings.led_matrix_cols,
    settings.led_matrix_chain,
    settings.led_matrix_parallel,
    settings.led_matrix_pixel_mapper,
)
```

Then, after `self.matrix = RGBMatrix(options=options)`, add:

```python
                self.width = self.matrix.width
                self.height = self.matrix.height
                logger.info(
                    f"LED matrix initialized: {self.width}x{self.height}"
                )
```

Remove the old `logger.info` block that logged before the matrix was created.

- [ ] **Step 3: Commit**

```bash
git add hardware/led_matrix.py
git commit -m "fix: report actual mapped dimensions from LEDMatrix"
```

---

## Task 5: Update mock matrix default size

**Files:**
- Modify: `hardware/mock_led.py`

- [ ] **Step 1: Update the default constants**

Replace:

```python
DEFAULT_WIDTH = 512   # 128 cols * 4 chain
DEFAULT_HEIGHT = 256  # 64 rows * 4 parallel
```

with:

```python
DEFAULT_WIDTH = 256   # 128 cols * 2 panels wide after U-mapper
DEFAULT_HEIGHT = 128  # 64 rows * 2 panels tall after U-mapper
```

- [ ] **Step 2: Commit**

```bash
git add hardware/mock_led.py
git commit -m "fix: update mock matrix default to 256x128"
```

---

## Task 6: Fix render dimensions in display engine

**Files:**
- Modify: `backend/app/services/display_engine.py`

- [ ] **Step 1: Import the helper**

At the top of `backend/app/services/display_engine.py`, add:

```python
from hardware.led_config import calculate_matrix_dimensions
```

- [ ] **Step 2: Calculate logical dimensions before creating the matrix**

In `DisplayEngine.__init__`, replace:

```python
self.width = settings.led_matrix_cols * settings.led_matrix_chain
self.height = settings.led_matrix_rows * settings.led_matrix_parallel
```

with:

```python
self.width, self.height = calculate_matrix_dimensions(
    settings.led_matrix_rows,
    settings.led_matrix_cols,
    settings.led_matrix_chain,
    settings.led_matrix_parallel,
    settings.led_matrix_pixel_mapper,
)
```

- [ ] **Step 3: Sync display engine dimensions with the matrix object after init**

After:

```python
from hardware import create_matrix
self._matrix = create_matrix(self.width, self.height)
```

add:

```python
        self.width = getattr(self._matrix, "width", self.width)
        self.height = getattr(self._matrix, "height", self.height)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/display_engine.py
git commit -m "fix: render at logical U-mapper dimensions in display engine"
```

---

## Task 7: Add pixel mapper to diagnostics

**Files:**
- Modify: `backend/app/services/display_engine.py`

- [ ] **Step 1: Extend `get_diagnostics`**

In the returned dict, add:

```python
            "pixel_mapper": settings.led_matrix_pixel_mapper,
            "row_address_type": settings.led_matrix_row_address_type,
            "multiplexing": settings.led_matrix_multiplexing,
            "pwm_bits": settings.led_matrix_pwm_bits,
            "gpio_slowdown": settings.led_matrix_gpio_slowdown,
```

(Only `pixel_mapper` is strictly new; the others make remote troubleshooting easier.)

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/display_engine.py
git commit -m "feat: expose more LED matrix settings in diagnostics"
```

---

## Task 8: Update `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Replace the LED matrix section**

Replace the existing LED matrix lines with:

```bash
ADSB_LED_MATRIX_ROWS=64
ADSB_LED_MATRIX_COLS=128
ADSB_LED_MATRIX_CHAIN=4
ADSB_LED_MATRIX_PARALLEL=1
ADSB_LED_MATRIX_PIXEL_MAPPER=U-mapper
ADSB_LED_MATRIX_ROW_ADDRESS_TYPE=0
ADSB_LED_MATRIX_PWM_BITS=7
ADSB_LED_MATRIX_BRIGHTNESS=70
ADSB_LED_MATRIX_GPIO_SLOWDOWN=4
ADSB_LED_MATRIX_FLIP_VERTICAL=true
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: update .env.example for P2 serpentine layout"
```

---

## Task 9: Update `docs/SETUP.md`

**Files:**
- Modify: `docs/SETUP.md`

- [ ] **Step 1: Update the parts list**

Replace the generic RGB panel item with:

```markdown
- 4× P2 128×64 RGB LED Matrix panels (256×128 mm each)
- Single-channel HUB75 adapter board for Raspberry Pi (e.g. AliExpress "Conversion board for Raspberry Pi to HUB75")
- External 5 V power supply (10 A+ recommended for 4 panels)
```

- [ ] **Step 2: Update the panel arrangement section**

Replace the existing "Panel Arrangement" section with:

```markdown
### Panel Arrangement

Default configuration is **256×128** using four 128×64 panels wired in a single
serpentine HUB75 chain:

```
Panel 1 (UL) ──► Panel 2 (UR)
                       │
                       ▼
Panel 4 (BL) ◄── Panel 3 (BR)
```

- `rows=64`, `cols=128`, `chain=4`, `parallel=1`
- `hardware_mapping=regular` (matches the single-channel adapter pinout)
- `pixel_mapper=U-mapper` (handles the right-to-left bottom row)
- `row_address_type=0` for direct row addressing (these P2 panels are not ABC-decoded)
- `flip_vertical=true` because the panels are mounted with the HUB75 input at the bottom, swapping the top and bottom panel rows

Set these environment variables in `/opt/adsbledmatrix/.env`:

```bash
ADSB_LED_MATRIX_ROWS=64
ADSB_LED_MATRIX_COLS=128
ADSB_LED_MATRIX_CHAIN=4
ADSB_LED_MATRIX_PARALLEL=1
ADSB_LED_MATRIX_PIXEL_MAPPER=U-mapper
ADSB_LED_MATRIX_HARDWARE_MAPPING=regular
ADSB_LED_MATRIX_ROW_ADDRESS_TYPE=0
ADSB_LED_MATRIX_PWM_BITS=7
ADSB_LED_MATRIX_BRIGHTNESS=70
ADSB_LED_MATRIX_GPIO_SLOWDOWN=4
ADSB_LED_MATRIX_FLIP_VERTICAL=true
```

> Note: some guides mention `--led-sba=1` for serpentine wiring. The standard
> `hzeller/rpi-rgb-led-matrix` library does not have this flag; the `U-mapper`
> option performs the same function.

> If the image appears split with the bottom half at the top, `flip_vertical` is wrong for your mounting. Set `ADSB_LED_MATRIX_FLIP_VERTICAL=false` and restart the service.
```

- [ ] **Step 3: Update the LED matrix troubleshooting example**

Replace the "Test LED matrix directly" Python snippet with:

```python
from rgbmatrix import RGBMatrix, RGBMatrixOptions
options = RGBMatrixOptions()
options.rows = 64
options.cols = 128
options.chain_length = 4
options.parallel = 1
options.hardware_mapping = "regular"
options.pixel_mapper_config = "U-mapper"
options.row_address_type = 0
options.pwm_bits = 7
options.brightness = 70
options.gpio_slowdown = 4
matrix = RGBMatrix(options=options)
matrix.Fill(255, 0, 0)
print(f"Matrix size: {matrix.width}x{matrix.height}")
```

- [ ] **Step 4: Commit**

```bash
git add docs/SETUP.md
git commit -m "docs: rewrite setup guide for P2 4-panel serpentine wiring"
```

---

## Task 10: Full test run and mock verification

**Files:**
- No file changes; verification only.

- [ ] **Step 1: Run the full backend test suite**

```bash
cd /home/bchen/Github/adsbledmatrix/backend
pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Start the app in mock mode and check diagnostics**

```bash
cd /home/bchen/Github/adsbledmatrix/backend
ADSB_MOCK_AIRCRAFT=true uvicorn app.main:app --host 0.0.0.0 --port 8080
```

In another terminal:

```bash
curl -s http://localhost:8080/api/diagnostics | python3 -m json.tool
```

Expected JSON contains:

```json
{
  "width": 256,
  "height": 128,
  "rows": 64,
  "cols": 128,
  "chain": 4,
  "parallel": 1,
  "pixel_mapper": "U-mapper",
  "row_address_type": 0,
  "multiplexing": 0,
  "pwm_bits": 7,
  "brightness": 70,
  "gpio_slowdown": 4,
  "flip_vertical": true
}
```

- [ ] **Step 3: Commit any final fixes**

If any fixes were required, commit them with a clear message.

---

## Spec coverage check

| Spec requirement | Implementing task |
|---|---|
| New default LED settings from PDF | Task 2 |
| Correct 256×128 logical dimensions | Tasks 1, 4, 5, 6 |
| U-mapper default | Tasks 2, 3 |
| `flip_vertical=true` for bottom-fed HUB75 wiring | Tasks 2, 8, 9 |
| No `--led-sba` support | Note in Task 9 docs |
| Updated `.env.example` | Task 8 |
| Updated `docs/SETUP.md` | Task 9 |
| Diagnostics include mapper/settings | Task 7 |
| Tests for dimensions and defaults | Tasks 1, 2 |
| Mock-mode verification | Task 10 |

---

## Placeholder scan

No TBD/TODO placeholders. All code blocks contain complete, runnable content. All commands include expected output.
