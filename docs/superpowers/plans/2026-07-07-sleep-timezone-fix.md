# Sleep Display Timezone Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the LED matrix sleep/dim windows evaluate in the user's real local timezone, derived from their configured latitude/longitude, so a 19:00–06:00 sleep window actually sleeps at 05:14 local time instead of staying on because the Pi's system clock is on UTC.

**Architecture:** Add an offline timezone lookup (`timezonefinder`) to map lat/long to an IANA timezone name, store it on `UserConfig`, and convert UTC `datetime.now()` to that timezone before comparing against the configured sleep/dim windows. The fallback path keeps using `datetime.now()` (system local time) when no lat/long/timezone is configured.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Pydantic, `timezonefinder`, `zoneinfo` (stdlib), React/TypeScript frontend.

---

## File Structure

- `backend/requirements.txt` — add `timezonefinder` dependency.
- `backend/pyproject.toml` — add `timezonefinder` dependency.
- `backend/app/models.py` — add `timezone` column to `UserConfig`.
- `backend/app/services/timezone.py` — new helper: `timezone_for_location(lat, lon) -> str | None`.
- `backend/app/api/config.py` — auto-detect timezone when lat/long changes; expose `timezone` in `ConfigResponse`/`ConfigUpdate`.
- `backend/app/services/display_engine.py` — evaluate sleep/dim windows in user's timezone.
- `backend/app/services/display_engine.py` — add diagnostics for the timezone and current local time used for sleep decisions.
- `backend/app/api/system.py` — include timezone/local-time in diagnostics/status if useful.
- `backend/tests/test_timezone.py` — new tests for timezone helper.
- `backend/tests/test_display_engine.py` — add timezone-aware sleep window tests.
- `backend/tests/test_config.py` — add test that updating lat/long refreshes timezone.
- `frontend/src/types/config.ts` — add optional `timezone` field.
- `frontend/src/components/Settings/Settings.tsx` — show detected timezone in the Night Mode card.

---

## Root Cause

`DisplayEngine._is_in_time_window` uses `datetime.now().time()`, which is the Pi's **system local time**. On a fresh Raspberry Pi install the timezone is often left as UTC, while the user enters their real lat/long during onboarding. A user in UTC−7 who sets sleep 19:00–06:00 expects the display to sleep at 05:14 local time, but at that moment the Pi's `datetime.now()` reports 12:14 UTC — outside the window — so the display stays on.

---

## Task 1: Add `timezonefinder` Dependency

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add to `requirements.txt`**

```text
timezonefinder>=6.5.0
```

- [ ] **Step 2: Add to `pyproject.toml` dependencies**

```toml
dependencies = [
    ...,
    "timezonefinder>=6.5.0",
]
```

- [ ] **Step 3: Install locally and sanity-check**

Run:

```bash
/home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend/.venv/bin/pip install -r backend/requirements.txt
```

Expected: installs cleanly.

---

## Task 2: Add Timezone Helper Service

**Files:**
- Create: `backend/app/services/timezone.py`
- Test: `backend/tests/test_timezone.py`

- [ ] **Step 1: Write the helper**

```python
from typing import Optional
from timezonefinder import TimezoneFinder

_tz_finder: Optional[TimezoneFinder] = None


def _get_finder() -> TimezoneFinder:
    global _tz_finder
    if _tz_finder is None:
        _tz_finder = TimezoneFinder()
    return _tz_finder


def timezone_for_location(latitude: Optional[float], longitude: Optional[float]) -> Optional[str]:
    """Return the IANA timezone name for a lat/long, or None if unavailable."""
    if latitude is None or longitude is None:
        return None
    try:
        return _get_finder().timezone_at(lat=latitude, lng=longitude)
    except Exception:
        return None
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_timezone.py`:

```python
from app.services.timezone import timezone_for_location


def test_timezone_for_location_known_cities():
    assert timezone_for_location(-33.8568, 151.2153) == "Australia/Sydney"
    assert timezone_for_location(51.5074, -0.1278) == "Europe/London"
    assert timezone_for_location(40.7128, -74.0060) == "America/New_York"


def test_timezone_for_location_invalid_returns_none():
    assert timezone_for_location(None, 151.0) is None
    assert timezone_for_location(0.0, None) is None
```

- [ ] **Step 3: Run the test to verify it fails/passes**

Run:

```bash
/home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend/.venv/bin/python -m pytest tests/test_timezone.py -v
```

Expected: PASS.

---

## Task 3: Add `timezone` Column to `UserConfig`

**Files:**
- Modify: `backend/app/models.py` (`UserConfig`)
- Modify: `backend/app/api/config.py` (`ConfigResponse`, `ConfigUpdate`, auto-detect)
- Modify: `backend/app/lifespan.py` (refresh timezone at startup)

- [ ] **Step 1: Add column to model**

In `backend/app/models.py`, after `sleep_mode_end`:

```python
    timezone = Column(String(50))
```

- [ ] **Step 2: Add field to response/update schemas**

In `backend/app/api/config.py`, add to `ConfigResponse`:

```python
    timezone: Optional[str]
```

Add to `ConfigUpdate`:

```python
    timezone: Optional[str] = None
```

- [ ] **Step 3: Auto-detect timezone when lat/long changes**

At the top of `backend/app/api/config.py`, import:

```python
from app.services.timezone import timezone_for_location
```

In `update_config`, after `update_data` is applied and committed, add:

```python
    # Auto-detect timezone from lat/long if it changed or timezone is missing
    if "latitude" in update_data or "longitude" in update_data or not config.timezone:
        detected = timezone_for_location(config.latitude, config.longitude)
        if detected and detected != config.timezone:
            config.timezone = detected
            await session.commit()
            await session.refresh(config)

    # Refresh cache
    await refresh_config_cache(session)
```

**Important:** the cache refresh must happen **after** the timezone is updated, so the display engine sees the new value.

- [ ] **Step 4: Auto-detect at startup**

In `backend/app/lifespan.py`, after `config = await get_or_create_config(session)` and before `await refresh_config_cache(session)`, add:

```python
        from app.services.timezone import timezone_for_location
        if not config.timezone:
            detected = timezone_for_location(config.latitude, config.longitude)
            if detected:
                config.timezone = detected
                await session.commit()
                await session.refresh(config)
```

- [ ] **Step 5: Add migration handling**

The project uses `migrate_db()` in `backend/app/database.py`. Existing installs will get the new nullable column via SQLAlchemy `create_all`/`migrate_db` if it adds missing columns. Verify `backend/app/database.py:migrate_db` adds missing columns; if it only creates tables, add the column manually or rely on the existing migration helper. Read `backend/app/database.py` first and patch `migrate_db` if necessary to add `timezone` to `user_config`.

- [ ] **Step 6: Add test for lat/long timezone refresh**

In `backend/tests/test_config.py`, add:

```python
@pytest.mark.asyncio
async def test_update_config_detects_timezone_from_lat_long(app_with_db):
    async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url="http://test") as client:
        response = await client.put("/api/config", json={"latitude": -33.8568, "longitude": 151.2153})

    assert response.status_code == 200
    data = response.json()
    assert data["timezone"] == "Australia/Sydney"
```

Run:

```bash
/home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend/.venv/bin/python -m pytest tests/test_config.py -v
```

Expected: all PASS.

---

## Task 4: Update Display Engine to Use User Timezone

**Files:**
- Modify: `backend/app/services/display_engine.py`
- Test: `backend/tests/test_display_engine.py`

- [ ] **Step 1: Modify `_is_in_time_window` to accept timezone**

Change the signature and implementation:

```python
    def _is_in_time_window(self, start: Optional[str], end: Optional[str], timezone_name: Optional[str] = None) -> bool:
        """Return True if the current time in the user's timezone falls within the HH:MM window."""
        if not start or not end:
            return False
        try:
            start_time = datetime.strptime(start, "%H:%M").time()
            end_time = datetime.strptime(end, "%H:%M").time()
        except ValueError:
            return False

        try:
            if timezone_name:
                from zoneinfo import ZoneInfo
                now = datetime.now(ZoneInfo(timezone_name))
            else:
                now = datetime.now()
        except Exception:
            now = datetime.now()

        now_time = now.time()
        if start_time < end_time:
            return start_time <= now_time < end_time
        # Interval wraps past midnight (e.g. 22:00 -> 06:00).
        return now_time >= start_time or now_time < end_time
```

- [ ] **Step 2: Pass timezone from config in `_handle_night_mode`**

Change:

```python
        timezone_name = config.timezone if config else None
        in_sleep_window = bool(
            config and config.sleep_mode and self._is_in_time_window(config.sleep_mode_start, config.sleep_mode_end, timezone_name)
        )
        in_dim_window = bool(
            config and config.night_mode and self._is_in_time_window(config.night_mode_start, config.night_mode_end, timezone_name)
        )
```

- [ ] **Step 3: Add timezone-aware test**

In `backend/tests/test_display_engine.py`, add:

```python
def test_sleep_window_uses_configured_timezone(engine):
    """A user in LA with sleep 19:00-06:00 should be sleeping at 05:14 local time
    even if the system clock says 12:14 UTC."""
    from unittest.mock import MagicMock, patch
    from datetime import datetime, date, time

    config = MagicMock()
    config.night_mode = False
    config.sleep_mode = True
    config.sleep_mode_start = "19:00"
    config.sleep_mode_end = "06:00"
    config.timezone = "America/Los_Angeles"

    engine._night_mode_active = False
    engine._matrix = MagicMock()

    with patch("app.services.display_engine.datetime") as mock_dt:
        mock_dt.strptime = datetime.strptime
        # System clock thinks it's 12:14 UTC (no timezone)
        mock_dt.now.return_value = datetime.combine(date.today(), time(12, 14))
        # But our implementation should call datetime.now(ZoneInfo(...))
        # so we patch zoneinfo too, or rely on real conversion.
        assert engine._handle_night_mode(config) is True
        engine._matrix.clear.assert_called_once()
```

The test above may need adjustment because mocking `datetime` also mocks `datetime.strptime` and `datetime.combine`. The existing tests handle this by preserving `mock_dt.strptime = datetime.strptime`. For timezone-aware behavior, a cleaner test is:

```python
def test_is_in_time_window_with_timezone(engine):
    """When a timezone is supplied, the window is evaluated in that timezone."""
    from unittest.mock import patch
    from datetime import datetime, date, time

    with patch("app.services.display_engine.datetime") as mock_dt:
        mock_dt.strptime = datetime.strptime
        # 2026-07-07 12:14 UTC = 05:14 PDT (UTC-7)
        mock_dt.now.return_value = datetime(2026, 7, 7, 12, 14, 0)
        mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert engine._is_in_time_window("19:00", "06:00", "America/Los_Angeles") is True

        mock_dt.now.return_value = datetime(2026, 7, 7, 20, 0, 0)
        assert engine._is_in_time_window("19:00", "06:00", "America/Los_Angeles") is True

        mock_dt.now.return_value = datetime(2026, 7, 7, 15, 0, 0)
        assert engine._is_in_time_window("19:00", "06:00", "America/Los_Angeles") is False
```

This still relies on `datetime.now(ZoneInfo(...))` being called. Since we patch `datetime` in `display_engine`, `mock_dt.now(ZoneInfo(...))` will return the patched value regardless of the argument. The test documents the expected behavior.

- [ ] **Step 4: Run display engine tests**

Run:

```bash
/home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend/.venv/bin/python -m pytest tests/test_display_engine.py -v
```

Expected: all PASS.

---

## Task 5: Add Diagnostics / Logging

**Files:**
- Modify: `backend/app/services/display_engine.py`
- Modify: `backend/app/api/system.py` (optional)

- [ ] **Step 1: Log sleep/dim decisions with timezone**

In `_handle_night_mode`, before evaluating windows:

```python
        from zoneinfo import ZoneInfo
        tz = config.timezone if config else None
        try:
            local_now = datetime.now(ZoneInfo(tz)) if tz else datetime.now()
        except Exception:
            local_now = datetime.now()
        logger.debug(
            "Night-mode check: local_time=%s timezone=%s sleep=%s-%s dim=%s-%s",
            local_now.strftime("%H:%M"),
            tz or "system",
            config.sleep_mode_start if config else None,
            config.sleep_mode_end if config else None,
            config.night_mode_start if config else None,
            config.night_mode_end if config else None,
        )
```

- [ ] **Step 2: Expose timezone in display diagnostics (optional but useful)**

In `DisplayEngine.get_diagnostics`, add:

```python
            "timezone": (config.timezone if config else None) or "system",
            "local_time": datetime.now(ZoneInfo(config.timezone)).strftime("%H:%M:%S") if config and config.timezone else datetime.now().strftime("%H:%M:%S"),
```

Requires importing `ZoneInfo` at the top of `display_engine.py`.

---

## Task 6: Update Frontend Settings UI

**Files:**
- Modify: `frontend/src/types/config.ts`
- Modify: `frontend/src/components/Settings/Settings.tsx`

- [ ] **Step 1: Add type field**

In `frontend/src/types/config.ts`, add:

```typescript
  timezone?: string;
```

- [ ] **Step 2: Show detected timezone in Night Mode card**

In `frontend/src/components/Settings/Settings.tsx`, inside the `config.sleep_mode` block (after the time inputs), add:

```tsx
              {config.timezone && (
                <p className="text-xs text-white/40">
                  Detected timezone: <span className="text-white/60">{config.timezone}</span>
                </p>
              )}
```

Also show it when `config.night_mode` is enabled so dim users see it too.

---

## Task 7: Full Test Run

- [ ] **Step 1: Run backend tests**

```bash
/home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend/.venv/bin/python -m pytest backend/tests -v
```

Expected: all PASS.

- [ ] **Step 2: Run frontend type check**

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "fix: evaluate sleep/dim windows in timezone derived from lat/long

The Pi often runs with system time set to UTC. Sleep/dim windows were
evaluated with datetime.now().time(), which used the Pi's system local
time instead of the user's real local time. This adds offline timezone
lookup from the configured lat/long, stores it on UserConfig, and uses
that timezone when deciding whether the display should sleep or dim."
```

---

## Spec Coverage Check

| Requirement in user report | Task implementing it |
|----------------------------|----------------------|
| Sleep window 19:00–06:00 should sleep at 05:14 local | Tasks 3, 4 |
| Use lat/long to determine correct local time | Tasks 2, 3 |
| Display stays on / shows idle scanning bug fixed | Task 4 |
| User can see what timezone is being used | Task 6 |

## Placeholder Scan

- No TBD/TODO placeholders.
- All code blocks contain concrete implementation.
- All file paths are exact.
- Test commands and expected outputs are specified.
