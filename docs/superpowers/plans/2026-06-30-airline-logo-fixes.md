# Airline Logo Mapping Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix airline logo selection so QantasLink shows Qantas, Jetstar/Singapore Airlines/Qantas use high-quality Radarbox logos, Royal Flying Doctor Service callsigns show the RFDS logo, and Australian-registered private aircraft do not show foreign airline logos.

**Architecture:** Keep the existing `LogoManager.logo_path_for_aircraft` entry point but (a) prefer Radarbox over FlightAware when downloading/importing logos, (b) pass aircraft registration into logo resolution so ambiguous callsign prefixes (e.g. `FD`) and bad operator data (e.g. `VH-SZS` → SAS) can be corrected, (c) ship a local RFDS logo for aircraft whose registration or callsign identifies them as RFDS.

**Tech Stack:** Python 3, Pillow, httpx, FastAPI, pytest.

---

## Methodical issue list and root causes

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | Singapore Airlines shows "SIA" text in a yellow circle | Local `SIA.png` was downloaded from FlightAware (text placeholder). | Prefer Radarbox source; re-download `SIA.png`. |
| 2 | Qantas shows "QFA" text in a red triangle | Local `QFA.png` is a low-quality FlightAware placeholder. | Prefer Radarbox source; re-download `QFA.png`. |
| 3 | Jetstar not showing the Jetstar logo | Local `JST.png` is a fallback placeholder with "JST" text. | Prefer Radarbox source; re-download `JST.png`. |
| 4 | QLK flight numbers don't always show Qantas logo | Once QFA.png is fixed, the existing `QLK → QFA` alias works. No code change beyond Issue 2. | Verify via test. |
| 5 | RFDS callsigns beginning with `FD` show Air Asia logo | `FD` is Thai AirAsia's IATA code in `airlines.csv`, so `FDxxx` resolves to `AIQ`. | Disambiguate `FD` by registration: `VH-` → RFDS, `HS-` → Thai AirAsia; add local `RFDS.png`. |
| 6 | `VH-SZS` shows SAS logo | `localadsb` aircraft DB has wrong `operator_icao` (SAS) for this VH-registered private aircraft. | For `VH-` registrations, only allow Australian airline ICAOs; otherwise fall back to `UNKNOWN.png`. |

## Files touched

- `backend/app/services/logo_manager.py` — source priority, FD disambiguation, VH- sanity check.
- `backend/app/services/display_engine.py` — pass registration to `logo_path_for_aircraft`.
- `backend/app/services/aircraft_db.py` — pass registration from enrichment to logo lookup.
- `backend/tests/test_logo_manager.py` — new tests for Radarbox priority, FD/VH- logic.
- `data/airline_logos/RFDS.png` — new local logo.
- `data/airline_logos/SIA.png`, `QFA.png`, `JST.png` — replaced from Radarbox source.
- `scripts/download_logo_pack.py` — swap source priority to Radarbox first.

---

## Task 1: Prefer Radarbox over FlightAware when downloading logos

**Files:**
- Modify: `backend/app/services/logo_manager.py:175-183`
- Modify: `backend/app/services/logo_manager.py:282-283`
- Modify: `scripts/download_logo_pack.py:47-49`

- [ ] **Step 1: Swap URL order in `_download_logo`**

```python
        urls = []
        # Primary: Radarbox (higher-quality logos, e.g. Singapore Airlines bird)
        urls.append(f"https://raw.githubusercontent.com/Jxck-S/airline-logos/main/radarbox_logos/{icao}.png")
        # Secondary: FlightAware (fallback)
        urls.append(f"https://raw.githubusercontent.com/Jxck-S/airline-logos/main/flightaware_logos/{icao}.png")
        # Tertiary: Google Flights CDN (high-quality)
        if iata:
            urls.append(f"https://www.gstatic.com/flights/airline_logos/70px/{iata}.png")
        # Quaternary: FlightAware direct (uses ICAO directly)
        urls.append(f"https://www.flightaware.com/images/airline_logos/90p/{icao}.png")
```

- [ ] **Step 2: Swap directory order in `bulk_import_from_github`**

Change:
```python
            # Build a per-ICAO lookup, preferring Radarbox over FlightAware.
            logo_choices: Dict[str, Path] = {}
            for source in (radarbox_dir, flightaware_dir):
```

- [ ] **Step 3: Swap source order in `download_logo_pack.py`**

```python
    sources = [
        f"https://raw.githubusercontent.com/{SOURCE_OWNER}/{SOURCE_REPO}/{SOURCE_BRANCH}/radarbox_logos/{icao}.png",
        f"https://raw.githubusercontent.com/{SOURCE_OWNER}/{SOURCE_REPO}/{SOURCE_BRANCH}/flightaware_logos/{icao}.png",
    ]
```

- [ ] **Step 4: Run logo tests**

Run: `pytest backend/tests/test_logo_manager.py -v`
Expected: existing tests still pass.

---

## Task 2: Replace corrupted placeholder logos with Radarbox versions

**Files:**
- Modify: `data/airline_logos/SIA.png`
- Modify: `data/airline_logos/QFA.png`
- Modify: `data/airline_logos/JST.png`

- [ ] **Step 1: Download corrected logos from the Radarbox source**

Run:
```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix
for code in SIA QFA JST; do
  curl -sL -o "data/airline_logos/${code}.png" \
    "https://raw.githubusercontent.com/Jxck-S/airline-logos/main/radarbox_logos/${code}.png"
done
```

- [ ] **Step 2: Resize/standardize logos to 96x96**

Run:
```bash
.venv/bin/python - <<'PY'
from PIL import Image
from pathlib import Path
for code in ("SIA", "QFA", "JST"):
    p = Path(f"data/airline_logos/{code}.png")
    img = Image.open(p).convert("RGBA").resize((96, 96), Image.LANCZOS)
    img.save(p, format="PNG", optimize=True)
PY
```

- [ ] **Step 3: Verify visually**

Inspect `data/airline_logos/SIA.png` (bird logo), `QFA.png` (kangaroo), `JST.png` (orange star).

---

## Task 3: Add RFDS callsign handling and local logo

**Files:**
- Create: `data/airline_logos/RFDS.png`
- Modify: `backend/app/services/logo_manager.py`

- [ ] **Step 1: Add the RFDS logo file**

Copy the prepared 96x96 RFDS logo to the logos directory:
```bash
cp /tmp/rfds_96.png /home/bchen/GitHub/adsledmatrix/adsbledmatrix/data/airline_logos/RFDS.png
```

- [ ] **Step 2: Add `FD` disambiguation in `_callsign_prefix_to_icao`**

Change the method signature and body:

```python
    def _callsign_prefix_to_icao(
        self, callsign: str, registration: Optional[str] = None
    ) -> Optional[str]:
        """Extract the airline code from a callsign and normalise it to ICAO.

        The prefix is the leading 2-3 alphabetic characters. If the prefix matches
        a known IATA code, the corresponding ICAO code is returned instead.

        The prefix FD is shared by Thai AirAsia (IATA FD -> ICAO AIQ) and the
        Royal Flying Doctor Service in Australia. We disambiguate by registration
        prefix: VH- is RFDS, HS- is Thai AirAsia. When no registration is known
        we default to RFDS because the display is deployed in Australia.
        """
        match = re.match(r"^([A-Z]{2,3})", callsign.upper().strip())
        if not match:
            return None
        prefix = match.group(1)
        if prefix == "FD":
            if registration:
                reg = registration.upper().strip()
                if reg.startswith("HS-"):
                    return "AIQ"
                if reg.startswith("VH-"):
                    return "RFDS"
            return "RFDS"
        # IATA codes are two letters; ICAO codes are three letters.
        return self._iata_to_icao.get(prefix, prefix)
```

- [ ] **Step 3: Update `logo_path_for_aircraft` to accept registration**

Change signature and pass registration through:

```python
    def logo_path_for_aircraft(
        self,
        operator_icao: Optional[str],
        callsign: Optional[str],
        registration: Optional[str] = None,
    ) -> Optional[Path]:
        """Return the local logo path for an aircraft, using the callsign prefix first.

        ...existing docstring...
        """
        resolved_icao: Optional[str] = None
        if callsign:
            prefix_icao = self._callsign_prefix_to_icao(callsign, registration)
            if prefix_icao:
                resolved_icao = (
                    _LOGO_DISPLAY_ALIASES.get(prefix_icao)
                    or _LOGO_ICAO_OVERRIDES.get(prefix_icao, prefix_icao)
                )
                path = settings.logos_dir / f"{resolved_icao}.png"
                if path.exists():
                    return path

        # Australian registration sanity check: VH- aircraft should not show a
        # foreign airline logo when the operator/callsign data is wrong.
        if registration and registration.upper().strip().startswith("VH-"):
            candidate = resolved_icao or operator_icao
            if candidate and candidate.upper() not in _AUSTRALIAN_OPERATOR_ICAOS:
                return self._unknown_path()

        if operator_icao:
            return self.logo_path_for_icao(operator_icao)

        return None
```

- [ ] **Step 4: Add the Australian-operator ICAO allow-list**

Add near the top of `logo_manager.py` after `_LOGO_ICAO_OVERRIDES`:

```python
# Australian operators. VH- registered aircraft whose resolved ICAO is not in
# this set are treated as private/unknown to avoid showing foreign airline logos
# from bad source data (e.g. VH-SZS incorrectly marked as SAS).
_AUSTRALIAN_OPERATOR_ICAOS: set[str] = {
    "QFA", "QLK", "VOZ", "JST", "TGW", "RXA", "UTY",
    "ANO", "ATM", "NJS", "SHA", "PEL", "MCK", "OZJ",
    "ELA", "HZA", "AAA", "ORC", "FJI", "ANZ", "RFDS",
}
```

---

## Task 4: Pass registration through to logo lookup

**Files:**
- Modify: `backend/app/services/display_engine.py:273-275`
- Modify: `backend/app/services/display_engine.py:533-535`
- Modify: `backend/app/services/aircraft_db.py:127-134`

- [ ] **Step 1: Update `_draw_image` in display_engine.py**

```python
        if not path and ctx.enriched:
            icao = ctx.enriched.get("operator_icao")
            callsign = ctx.aircraft.callsign if ctx.aircraft else None
            registration = ctx.enriched.get("registration")
            logo_path = logo_manager.logo_path_for_aircraft(icao, callsign, registration)
```

- [ ] **Step 2: Update `_evaluate_condition` for `has_logo`**

```python
        if condition == "has_logo":
            icao = (ctx.enriched or {}).get("operator_icao")
            callsign = ctx.aircraft.callsign if ctx.aircraft else None
            registration = (ctx.enriched or {}).get("registration")
            logo_path = logo_manager.logo_path_for_aircraft(icao, callsign, registration)
```

- [ ] **Step 3: Update `aircraft_db.get_logo_path`**

```python
    async def get_logo_path(
        self, icao_code: str, registration: Optional[str] = None
    ) -> Optional[str]:
        """Return local path to airline logo if cached."""
        if not icao_code:
            return None
        path = logo_manager.logo_path_for_icao(icao_code)
        if path and path.exists():
            return str(path)
        return None
```

(Note: `get_logo_path` currently only takes an ICAO; the display path already uses `logo_path_for_aircraft`. If callers need registration-aware lookup they can migrate later.)

---

## Task 5: Add/update tests

**Files:**
- Modify: `backend/tests/test_logo_manager.py`

- [ ] **Step 1: Add test for FD callsign with VH- registration -> RFDS**

```python
def test_fd_callsign_vh_registration_uses_rfds_logo(fake_logos_dir):
    """FD-prefixed callsigns on Australian-registered aircraft are RFDS."""
    _make_logo(fake_logos_dir, "RFDS")
    _make_logo(fake_logos_dir, "AIQ")

    path = logo_manager.logo_path_for_aircraft("AIQ", "FD511", "VH-SZS")

    assert path == fake_logos_dir / "RFDS.png"
```

- [ ] **Step 2: Add test for FD callsign with HS- registration -> Thai AirAsia**

```python
def test_fd_callsign_hs_registration_uses_thai_airasia_logo(fake_logos_dir):
    """FD-prefixed callsigns on Thai-registered aircraft remain Thai AirAsia."""
    _make_logo(fake_logos_dir, "RFDS")
    _make_logo(fake_logos_dir, "AIQ")

    path = logo_manager.logo_path_for_aircraft("AIQ", "FD511", "HS-ABC")

    assert path == fake_logos_dir / "AIQ.png"
```

- [ ] **Step 3: Add test for VH- aircraft with foreign operator -> unknown**

```python
def test_vh_registration_with_foreign_operator_uses_unknown(fake_logos_dir):
    """VH- registered aircraft with bad foreign operator data show UNKNOWN."""
    _make_logo(fake_logos_dir, "SAS")
    _make_logo(fake_logos_dir, "UNKNOWN")

    path = logo_manager.logo_path_for_aircraft("SAS", None, "VH-SZS")

    assert path == fake_logos_dir / "UNKNOWN.png"
```

- [ ] **Step 4: Add test for VH- aircraft with Australian operator -> logo**

```python
def test_vh_registration_with_australian_operator_uses_logo(fake_logos_dir):
    """VH- registered aircraft with a valid Australian operator show that logo."""
    _make_logo(fake_logos_dir, "QFA")

    path = logo_manager.logo_path_for_aircraft("QFA", None, "VH-OQI")

    assert path == fake_logos_dir / "QFA.png"
```

- [ ] **Step 5: Verify all tests pass**

Run: `pytest backend/tests/test_logo_manager.py -v`
Expected: all tests pass, including existing ones.

---

## Task 6: Verify on the Pi

**Files:**
- None (runtime verification)

- [ ] **Step 1: Deploy changes to the Pi**

Use the existing deployment path (`10.0.0.24`):
```bash
rsync -avz --exclude '.venv' --exclude '.git' \
  /home/bchen/GitHub/adsledmatrix/adsbledmatrix/ \
  pi@10.0.0.24:~/adsbledmatrix/
```

- [ ] **Step 2: Restart the backend on the Pi**

```bash
ssh pi@10.0.0.24 'cd ~/adsbledmatrix && sudo systemctl restart adsbledmatrix'
```

- [ ] **Step 3: Smoke-test logo endpoints**

From the Pi or local machine:
```bash
for code in SIA QFA JST RFDS; do
  curl -sI "http://10.0.0.24:8080/api/aircraft/logo/${code}" | head -1
done
```
Expected: `HTTP/1.1 200 OK` for each.

- [ ] **Step 4: Confirm with live aircraft**

Visit `http://10.0.0.24/adsb/adsb` and confirm:
- Singapore Airlines aircraft show the bird logo.
- Qantas/QantasLink aircraft show the kangaroo logo.
- Jetstar aircraft show the orange star logo.
- RFDS `FDxxx` callsigns show the RFDS logo.
- `VH-SZS` no longer shows the SAS logo.

---

## Self-review

- **Spec coverage:** Each reported symptom maps to one or more tasks above.
- **Placeholder scan:** No TBD/TODO; all code blocks and commands are concrete.
- **Type consistency:** `logo_path_for_aircraft` gains an optional `registration` parameter; existing callers with two positional args continue to work.
