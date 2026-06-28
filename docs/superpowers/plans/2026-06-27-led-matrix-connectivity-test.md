# LED Matrix Connectivity Test — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the 512×256 LED matrix display the built-in test pattern by correcting the driver configuration and exposing the missing SPWM options.

**Architecture:** Add the three `SPWM_*` settings to the Pydantic settings object in `backend/app/config.py`, pass them through `hardware/led_matrix.py` to `RGBMatrixOptions`, then update the Pi's `.env` with the correct panel geometry and Electrodragon mapping.

**Tech Stack:** Python 3.13, Pydantic Settings, `rpi-rgb-led-matrix`, systemd, FastAPI.

---

## File mapping

| File | Responsibility |
|------|----------------|
| `backend/app/config.py` | Declares all environment-driven LED matrix settings, including the new SPWM options. |
| `hardware/led_matrix.py` | Translates settings into `RGBMatrixOptions` for the C++ driver. |
| `backend/tests/test_config.py` | New test file — verifies SPWM env vars are parsed into `Settings`. |
| `/opt/adsbledmatrix/.env` (on Pi) | Runtime configuration for the installed service. |

---

## Task 1: Add SPWM settings to backend config

**Files:**
- Modify: `backend/app/config.py:44-47`

- [ ] **Step 1: Add the three new settings after `led_matrix_limit_refresh`**

```python
    led_matrix_spwm_row_address_type: int = 0
    led_matrix_spwm_register_config: int = -1
    led_matrix_spwm_scan_rows: int = 0
```

Place them immediately after:

```python
    led_matrix_limit_refresh: int = 0
```

- [ ] **Step 2: Verify the file imports and env prefix are unchanged**

`env_prefix = "ADSB_"` must still be set in the `Config` class so `ADSB_LED_MATRIX_SPWM_*` variables are picked up.

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(config): expose SPWM LED matrix settings"
```

---

## Task 2: Pass SPWM options to the matrix driver

**Files:**
- Modify: `hardware/led_matrix.py:44-49`

- [ ] **Step 1: Insert SPWM option assignments after `limit_refresh_rate_hz`**

After:

```python
                if settings.led_matrix_limit_refresh > 0:
                    options.limit_refresh_rate_hz = settings.led_matrix_limit_refresh
```

Add:

```python
                options.spwm_row_address_type = settings.led_matrix_spwm_row_address_type
                options.spwm_register_config = settings.led_matrix_spwm_register_config
                options.spwm_scan_rows = settings.led_matrix_spwm_scan_rows
```

- [ ] **Step 2: Commit**

```bash
git add hardware/led_matrix.py
git commit -m "feat(led_matrix): pass SPWM options to rpi-rgb-led-matrix"
```

---

## Task 3: Add a config parsing test

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: Create the test package file**

```bash
mkdir -p backend/tests
touch backend/tests/__init__.py
```

- [ ] **Step 2: Write the test**

```python
import os
from unittest.mock import patch


def test_spwm_settings_parsed_from_env():
    env = {
        "ADSB_LED_MATRIX_SPWM_ROW_ADDRESS_TYPE": "1",
        "ADSB_LED_MATRIX_SPWM_REGISTER_CONFIG": "-1",
        "ADSB_LED_MATRIX_SPWM_SCAN_ROWS": "0",
    }
    with patch.dict(os.environ, env, clear=False):
        # Import inside the patched environment
        from app.config import Settings

        settings = Settings()
        assert settings.led_matrix_spwm_row_address_type == 1
        assert settings.led_matrix_spwm_register_config == -1
        assert settings.led_matrix_spwm_scan_rows == 0
```

- [ ] **Step 3: Run the test and expect it to pass**

```bash
cd backend
/opt/adsbledmatrix/venv/bin/pytest tests/test_config.py -v
```

Expected output includes:

```
test_config.py::test_spwm_settings_parsed_from_env PASSED
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/__init__.py backend/tests/test_config.py
git commit -m "test(config): verify SPWM env vars are parsed"
```

---

## Task 4: Update the Pi runtime configuration

**Files:**
- Modify: `/opt/adsbledmatrix/.env` (on the Pi at `10.0.0.24`)

- [ ] **Step 1: Back up the existing `.env`**

```bash
ssh adsb@10.0.0.24 "cp /opt/adsbledmatrix/.env /opt/adsbledmatrix/.env.bak.$(date +%Y%m%d%H%M%S)"
```

- [ ] **Step 2: Write the new `.env` contents**

Use `ssh` to overwrite the file:

```bash
ssh adsb@10.0.0.24 "cat > /opt/adsbledmatrix/.env" <<'EOF'
ADSB_LED_MATRIX_ROWS=128
ADSB_LED_MATRIX_COLS=256
ADSB_LED_MATRIX_CHAIN=4
ADSB_LED_MATRIX_PARALLEL=1
ADSB_LED_MATRIX_PIXEL_MAPPER=U-mapper
ADSB_LED_MATRIX_HARDWARE_MAPPING=electrodragon
ADSB_LED_MATRIX_PANEL_TYPE=sm16380sh
ADSB_LED_MATRIX_ROW_ADDRESS_TYPE=3
ADSB_LED_MATRIX_BRIGHTNESS=70
ADSB_LED_MATRIX_PWM_BITS=7
ADSB_LED_MATRIX_GPIO_SLOWDOWN=4
ADSB_LED_MATRIX_SPWM_ROW_ADDRESS_TYPE=1
ADSB_LED_MATRIX_SPWM_REGISTER_CONFIG=-1
ADSB_LED_MATRIX_SPWM_SCAN_ROWS=0
EOF
```

- [ ] **Step 3: Verify the file on the Pi**

```bash
ssh adsb@10.0.0.24 "cat /opt/adsbledmatrix/.env"
```

Expected: the eleven lines above, no `ADSB_LED_MATRIX_HARDWARE_MAPPING=adafruit-hat` and no `ADSB_LED_MATRIX_SPWM_*` duplicates.

---

## Task 5: Deploy code changes to the Pi and restart the service

- [ ] **Step 1: Push or copy the updated repo files to the Pi**

If the repo on the Pi is on the `main` branch and pulling is acceptable:

```bash
git push origin main
ssh adsb@10.0.0.24 "cd /opt/adsbledmatrix && git pull"
```

If the local repo is not the remote, copy only the changed files:

```bash
scp backend/app/config.py hardware/led_matrix.py adsb@10.0.0.24:/opt/adsbledmatrix/
# For nested paths:
scp backend/app/config.py adsb@10.0.0.24:/opt/adsbledmatrix/backend/app/config.py
scp hardware/led_matrix.py adsb@10.0.0.24:/opt/adsbledmatrix/hardware/led_matrix.py
```

- [ ] **Step 2: Restart the service**

```bash
ssh adsb@10.0.0.24 "sudo systemctl restart adsbledmatrix"
```

- [ ] **Step 3: Check the service is healthy**

```bash
ssh adsb@10.0.0.24 "sudo systemctl status adsbledmatrix --no-pager"
```

Expected: `Active: active (running)`.

- [ ] **Step 4: Verify the API health endpoint**

```bash
curl http://10.0.0.24:8080/api/health
```

Expected: JSON response with status `ok`.

---

## Task 6: Run the LED matrix test pattern

- [ ] **Step 1: Trigger the test endpoint**

```bash
curl -X POST http://10.0.0.24:8080/api/display/test
```

- [ ] **Step 2: Observe the matrix**

The matrix should flash:
1. Full red for ~1 second
2. Full green for ~1 second
3. Full blue for ~1 second

- [ ] **Step 3: Check application logs if the matrix is still blank**

```bash
ssh adsb@10.0.0.24 "sudo journalctl -u adsbledmatrix -n 100 --no-pager"
```

Look for errors such as:
- `Failed to initialize LED matrix`
- GPIO permission errors
- `rgbmatrix` import errors

---

## Task 7: Iterate if the matrix remains blank

If Task 6 shows no pixels, try the following in order. After each change, restart the service and re-run the test pattern.

- [ ] **Step 1: Try `hardware_mapping=regular` as a fallback**

Edit `/opt/adsbledmatrix/.env`:

```bash
ADSB_LED_MATRIX_HARDWARE_MAPPING=regular
```

Restart and test.

- [ ] **Step 2: Try alternate `row_address_type` values**

Edit `/opt/adsbledmatrix/.env` and cycle through `0`, `1`, `2`, `4`, `5`:

```bash
ADSB_LED_MATRIX_ROW_ADDRESS_TYPE=0
```

Restart and test after each value.

- [ ] **Step 3: Try direct Python fill test bypassing the service**

On the Pi, run as root:

```bash
sudo /opt/adsbledmatrix/venv/bin/python3 - <<'PY'
from rgbmatrix import RGBMatrix, RGBMatrixOptions
options = RGBMatrixOptions()
options.rows = 128
options.cols = 256
options.chain_length = 4
options.parallel = 1
options.hardware_mapping = "electrodragon"
options.pixel_mapper_config = "U-mapper"
options.panel_type = "sm16380sh"
options.row_address_type = 3
options.pwm_bits = 7
options.brightness = 70
options.gpio_slowdown = 4
options.spwm_row_address_type = 1
options.spwm_register_config = -1
options.spwm_scan_rows = 0
matrix = RGBMatrix(options=options)
matrix.Fill(255, 0, 0)
import time
time.sleep(2)
matrix.Fill(0, 255, 0)
time.sleep(2)
matrix.Fill(0, 0, 255)
time.sleep(2)
matrix.Clear()
PY
```

If this works but the service does not, the issue is in the service layer. If this also fails, the issue is wiring, power, or a driver-board-specific mapping.

- [ ] **Step 4: Reduce brightness to rule out power issues**

```bash
ADSB_LED_MATRIX_BRIGHTNESS=30
```

Restart and test.

---

## Task 8: Record the final working config

- [ ] **Step 1: Save a copy of the working `.env`**

```bash
ssh adsb@10.0.0.24 "cp /opt/adsbledmatrix/.env /opt/adsbledmatrix/.env.working"
```

- [ ] **Step 2: Commit any remaining local code changes**

```bash
git status
git add -A
git commit -m "feat: support Electrodragon 512x256 LED matrix config"
```

---

## Self-review checklist

- [ ] **Spec coverage:** The spec required exposing SPWM settings, updating `.env`, and running the test pattern. Tasks 1–3 cover code changes, Task 4 covers `.env`, Tasks 5–6 cover verification, and Task 7 covers iteration if needed.
- [ ] **Placeholder scan:** No TBDs, TODOs, or vague instructions. Each step shows exact code or exact commands.
- [ ] **Type consistency:** Setting names match across `config.py`, `led_matrix.py`, and the test (`led_matrix_spwm_row_address_type`, `led_matrix_spwm_register_config`, `led_matrix_spwm_scan_rows`).
