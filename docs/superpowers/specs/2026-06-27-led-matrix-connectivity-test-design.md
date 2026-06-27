# LED Matrix Connectivity Test — Design

**Date:** 2026-06-27  
**Status:** Approved  
**Scope:** Get a visible test pattern on the 512×256 RGB LED matrix connected to the Raspberry Pi at `10.0.0.24`. Installer and documentation updates are explicitly out of scope for this task.

---

## 1. Goal

Make the LED matrix display the built-in red/green/blue test pattern by correcting the software configuration to match the physical hardware.

Success criteria:
- `curl -X POST http://10.0.0.24:8080/api/display/test` causes the matrix to flash red, then green, then blue.
- The matrix remains usable by the display engine afterwards.

---

## 2. Hardware Context

| Item | Value |
|------|-------|
| Host | Raspberry Pi at `10.0.0.24` |
| Driver board | Electrodragon HUB75 adapter (exact variant unknown) |
| Panels | 4 × 256×128 RGB HUB75 panels |
| Wiring | U-shaped ribbon chain |
| Logical arrangement | 512×256 (2 panels wide × 2 panels tall) |
| Panel chipset | SM16380SH (from existing `/opt/adsbledmatrix/.env`) |
| SPI | Enabled (`/dev/spidev0.0`, `/dev/spidev0.1` present) |
| Library | `rpi-rgb-led-matrix` installed in `/opt/adsbledmatrix/venv` |

The current `.env` is configured for 64×128 panels with an Adafruit HAT mapping, which is why the matrix is blank.

---

## 3. Configuration Changes

Update `/opt/adsbledmatrix/.env` to:

```bash
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
```

Rationale:
- `rows=128`, `cols=256`, `chain=4`, `parallel=1`, `U-mapper` describe four 256×128 panels chained in a U-shape to produce 512×256.
- `hardware_mapping=electrodragon` matches the Electrodragon driver board GPIO mapping.
- `panel_type=sm16380sh` and the three `SPWM_*` values are carried over from the existing `.env` because the panels use that chipset.
- Brightness is kept at 70 to avoid overloading the power supply during initial testing.

---

## 4. Code Changes

The backend currently ignores the three `SPWM_*` environment variables because they are not declared in `backend/app/config.py` and are not applied in `hardware/led_matrix.py`.

### 4.1 `backend/app/config.py`

Add three new settings after the existing LED matrix options:

```python
led_matrix_spwm_row_address_type: int = 0
led_matrix_spwm_register_config: int = -1
led_matrix_spwm_scan_rows: int = 0
```

### 4.2 `hardware/led_matrix.py`

After the existing conditional options, pass the new values to `RGBMatrixOptions`:

```python
options.spwm_row_address_type = settings.led_matrix_spwm_row_address_type
options.spwm_register_config = settings.led_matrix_spwm_register_config
options.spwm_scan_rows = settings.led_matrix_spwm_scan_rows
```

These options are confirmed to exist in the installed `rpi-rgb-led-matrix` build.

---

## 5. Verification Plan

1. Apply the code changes on the Pi (edit repo files in `/opt/adsbledmatrix`).
2. Rewrite `/opt/adsbledmatrix/.env` with the values in Section 3.
3. Restart the service:
   ```bash
   sudo systemctl restart adsbledmatrix
   ```
4. Trigger the test pattern:
   ```bash
   curl -X POST http://10.0.0.24:8080/api/display/test
   ```
5. Observe the matrix. Expected result: red, then green, then blue full-screen flashes.
6. If the matrix remains blank, run a direct Python fill test with different combinations of `hardware_mapping`, `row_address_type`, and `panel_type` until pixels appear.

---

## 6. Out of Scope

- Updating `scripts/install.sh` or other installer logic.
- Adding documentation beyond this spec.
- Building a config generator or wizard.
- Refactoring the display engine or layout rendering.

These will be handled in a follow-up task once the matrix is proven to work.

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Electrodragon variant uses a different mapping | Try `hardware_mapping=electrodragon` first; fallback to `regular` or `adafruit-hat` if blank. |
| SM16380SH needs different SPWM/row-address settings | Iterate on `row_address_type` (0–5) and `spwm_*` values using a direct Python script. |
| Power supply cannot drive full matrix at 70% brightness | If flickering or reset occurs, reduce `ADSB_LED_MATRIX_BRIGHTNESS` and check power wiring. |
| rpi-rgb-led-matrix needs root for GPIO timing | Service already runs as `root`; direct tests must also run as root. |
