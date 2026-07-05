# Network ADS-B Receiver Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in Settings-controlled "network receiver" mode so the Pi can consume ADS-B from a remote `readsb` instance on the local network while keeping the local RTL-SDR stick path as the unchanged default.

**Architecture:** Persist receiver source and network endpoint in `UserConfig`. Add a small service manager that starts/stops the local `readsb.service` and toggles a persistent flag file used by a systemd condition. Extend `ADSBReceiver` to re-point its TCP connection at runtime. Add a Settings UI card with validation and a "Test connection" endpoint.

**Tech Stack:** FastAPI, SQLAlchemy + aiosqlite, Pydantic, pytest, React + TypeScript + Tailwind, systemd, bash.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/models.py` | Adds `receiver_source`, `network_readsb_host`, `network_readsb_port` columns to `UserConfig`. |
| `backend/app/database.py` | SQLite migration for the new columns. |
| `backend/app/services/readsb_service_manager.py` | New module: wraps `systemctl start/stop/status` and manages the network-mode flag file. |
| `backend/app/services/adsb_receiver.py` | Adds `set_endpoint()`, runtime endpoint instance variables, and a `_connected` flag. |
| `backend/app/api/config.py` | Extends schemas, adds validation, calls service manager on save, adds `POST /api/config/test-receiver`. |
| `backend/app/api/system.py` | Extends `/api/system/status` with receiver source/endpoint/connected state. |
| `backend/app/lifespan.py` | Applies receiver source configuration on startup. |
| `frontend/src/types/config.ts` | Adds the three new fields to `UserConfig`. |
| `frontend/src/components/Settings/Settings.tsx` | Adds a "Receiver" settings card with source selector, network inputs, status, and test connection. |
| `systemd/readsb.service.d/10-network-mode.conf` | New systemd drop-in that skips `readsb.service` when the network flag file exists. |
| `scripts/install.sh` | Installs the systemd drop-in during fresh install. |
| `backend/tests/test_readsb_service_manager.py` | Unit tests for the service manager. |
| `backend/tests/test_config.py` | Validation tests for network receiver config. |
| `backend/tests/test_adsb_receiver.py` | Tests for `set_endpoint()` and `_connected`. |
| `backend/tests/test_system.py` | Tests for extended system status. |

---

## Task 1: Data Model and Migration

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/database.py`
- Test: `backend/tests/test_config.py`

### Step 1.1: Add columns to `UserConfig`

Modify `backend/app/models.py`:

```python
class UserConfig(Base):
    __tablename__ = "user_config"

    id = Column(Integer, primary_key=True)
    latitude = Column(Float, nullable=False, default=0.0)
    longitude = Column(Float, nullable=False, default=0.0)
    distance_unit = Column(String(10), nullable=False, default="km")
    altitude_unit = Column(String(10), nullable=False, default="ft")
    speed_unit = Column(String(10), nullable=False, default="kts")
    cycle_interval_sec = Column(Integer, nullable=False, default=5)
    display_mode = Column(String(20), nullable=False, default="closest")
    active_layout_id = Column(Integer, ForeignKey("layouts.id"), nullable=True)
    idle_layout_id = Column(Integer, ForeignKey("layouts.id"), nullable=True)
    onboarding_complete = Column(Boolean, nullable=False, default=False)
    wifi_ssid = Column(String(100))
    wifi_password = Column(String(100))
    auto_update = Column(Boolean, nullable=False, default=True)
    night_mode = Column(Boolean, nullable=False, default=False)
    night_mode_start = Column(String(5))
    night_mode_end = Column(String(5))
    led_matrix_brightness = Column(Integer, nullable=False, default=70)

    # Receiver source
    receiver_source = Column(String(10), nullable=False, default="local")
    network_readsb_host = Column(String(255))
    network_readsb_port = Column(Integer, nullable=False, default=30003)
```

### Step 1.2: Add migration in `migrate_db()`

Modify `backend/app/database.py` inside `_add_missing_columns`:

```python
def _add_missing_columns(sync_conn):
    from sqlalchemy import text

    result = sync_conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='user_config'")
    )
    if not result.fetchone():
        return
    result = sync_conn.execute(text("PRAGMA table_info(user_config)"))
    columns = {row[1] for row in result}

    if "led_matrix_brightness" not in columns:
        sync_conn.execute(
            text("ALTER TABLE user_config ADD COLUMN led_matrix_brightness INTEGER NOT NULL DEFAULT 70")
        )

    # Network receiver settings
    if "receiver_source" not in columns:
        sync_conn.execute(
            text("ALTER TABLE user_config ADD COLUMN receiver_source TEXT NOT NULL DEFAULT 'local'")
        )
    if "network_readsb_host" not in columns:
        sync_conn.execute(
            text("ALTER TABLE user_config ADD COLUMN network_readsb_host TEXT")
        )
    if "network_readsb_port" not in columns:
        sync_conn.execute(
            text("ALTER TABLE user_config ADD COLUMN network_readsb_port INTEGER NOT NULL DEFAULT 30003")
        )

    # Radar element settings added after initial schema
    ...
```

### Step 1.3: Write migration test

Append to `backend/tests/test_config.py`:

```python
import pytest
from sqlalchemy import text
from app.database import engine


@pytest.mark.asyncio
async def test_user_config_has_receiver_columns():
    async with engine.begin() as conn:
        def _check(sync_conn):
            result = sync_conn.execute(text("PRAGMA table_info(user_config)"))
            columns = {row[1] for row in result}
            assert "receiver_source" in columns
            assert "network_readsb_host" in columns
            assert "network_readsb_port" in columns

        await conn.run_sync(_check)
```

### Step 1.4: Run migration test

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend
python3 -m pytest tests/test_config.py::test_user_config_has_receiver_columns -v
```

Expected: PASS.

### Step 1.5: Commit

```bash
git add backend/app/models.py backend/app/database.py backend/tests/test_config.py
git commit -m "feat(network-receiver): add UserConfig columns and migration"
```

---

## Task 2: Readsb Service Manager

**Files:**
- Create: `backend/app/services/readsb_service_manager.py`
- Test: `backend/tests/test_readsb_service_manager.py`

### Step 2.1: Create the service manager

Create `backend/app/services/readsb_service_manager.py`:

```python
import logging
import subprocess
from pathlib import Path
from typing import Optional

from app.config import settings
from app.services.adsb_receiver import receiver

logger = logging.getLogger(__name__)

NETWORK_FLAG_FILE = Path(settings.data_dir) / ".network_receiver_enabled"


def _run_systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def is_readsb_available() -> bool:
    """Return True if systemctl and readsb.service are present."""
    result = _run_systemctl("status", "readsb.service")
    # status returns 0 if active, 3 if inactive but unit exists, 4 if unit missing
    return result.returncode in (0, 3)


def start_readsb() -> None:
    if not is_readsb_available():
        logger.info("readsb.service not available; skipping start")
        return
    logger.info("Starting readsb.service")
    result = _run_systemctl("start", "readsb.service")
    if result.returncode != 0:
        logger.warning(f"Failed to start readsb.service: {result.stderr.strip()}")


def stop_readsb() -> None:
    if not is_readsb_available():
        logger.info("readsb.service not available; skipping stop")
        return
    logger.info("Stopping readsb.service")
    result = _run_systemctl("stop", "readsb.service")
    if result.returncode != 0:
        logger.warning(f"Failed to stop readsb.service: {result.stderr.strip()}")


def _resolve_receiver_config(config) -> tuple[str, int]:
    if config.receiver_source == "network" and config.network_readsb_host:
        return config.network_readsb_host, config.network_readsb_port
    return "127.0.0.1", 30003


def set_network_flag(enabled: bool) -> None:
    if enabled:
        NETWORK_FLAG_FILE.touch(exist_ok=True)
    else:
        NETWORK_FLAG_FILE.unlink(missing_ok=True)


def apply_receiver_source(config) -> None:
    """Apply receiver source configuration: endpoint + local service state + flag file."""
    host, port = _resolve_receiver_config(config)
    receiver.set_endpoint(host, port)

    if config.receiver_source == "network":
        set_network_flag(True)
        stop_readsb()
    else:
        set_network_flag(False)
        start_readsb()
```

### Step 2.2: Write service manager tests

Create `backend/tests/test_readsb_service_manager.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from app.services import readsb_service_manager as manager


@pytest.fixture
def mock_receiver(monkeypatch):
    recv = MagicMock()
    monkeypatch.setattr(manager, "receiver", recv)
    return recv


@pytest.fixture
def clear_flag_file(monkeypatch, tmp_path):
    flag = tmp_path / ".network_receiver_enabled"
    monkeypatch.setattr(manager, "NETWORK_FLAG_FILE", flag)
    yield flag


def fake_config(source="local", host=None, port=30003):
    c = MagicMock()
    c.receiver_source = source
    c.network_readsb_host = host
    c.network_readsb_port = port
    return c


def test_resolve_local_config():
    c = fake_config("local")
    assert manager._resolve_receiver_config(c) == ("127.0.0.1", 30003)


def test_resolve_network_config():
    c = fake_config("network", "10.0.0.158", 30003)
    assert manager._resolve_receiver_config(c) == ("10.0.0.158", 30003)


def test_resolve_network_config_without_host_falls_back():
    c = fake_config("network", None, 30003)
    assert manager._resolve_receiver_config(c) == ("127.0.0.1", 30003)


def test_set_network_flag_creates_and_removes_file(clear_flag_file):
    assert not clear_flag_file.exists()
    manager.set_network_flag(True)
    assert clear_flag_file.exists()
    manager.set_network_flag(False)
    assert not clear_flag_file.exists()


def test_apply_local_config_starts_service_and_clears_flag(mock_receiver, clear_flag_file):
    c = fake_config("local")
    with patch.object(manager, "start_readsb") as mock_start, \
         patch.object(manager, "stop_readsb") as mock_stop:
        manager.apply_receiver_source(c)

    mock_receiver.set_endpoint.assert_called_once_with("127.0.0.1", 30003)
    mock_start.assert_called_once()
    mock_stop.assert_not_called()
    assert not clear_flag_file.exists()


def test_apply_network_config_stops_service_and_sets_flag(mock_receiver, clear_flag_file):
    c = fake_config("network", "10.0.0.158", 30003)
    with patch.object(manager, "start_readsb") as mock_start, \
         patch.object(manager, "stop_readsb") as mock_stop:
        manager.apply_receiver_source(c)

    mock_receiver.set_endpoint.assert_called_once_with("10.0.0.158", 30003)
    mock_stop.assert_called_once()
    mock_start.assert_not_called()
    assert clear_flag_file.exists()
```

### Step 2.3: Run service manager tests

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend
python3 -m pytest tests/test_readsb_service_manager.py -v
```

Expected: all PASS.

### Step 2.4: Commit

```bash
git add backend/app/services/readsb_service_manager.py backend/tests/test_readsb_service_manager.py
git commit -m "feat(network-receiver): add readsb service manager"
```

---

## Task 3: ADSBReceiver Endpoint Switching

**Files:**
- Modify: `backend/app/services/adsb_receiver.py`
- Test: `backend/tests/test_adsb_receiver.py`

### Step 3.1: Modify `ADSBReceiver`

In `backend/app/services/adsb_receiver.py`, update `__init__` and `_read_loop`, and add `set_endpoint`:

```python
class ADSBReceiver:
    """Reads SBS/BaseStation format from readsb TCP port 30003."""

    def __init__(self):
        self.aircraft: Dict[str, LiveAircraft] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable] = []
        self._user_lat: Optional[float] = None
        self._user_lon: Optional[float] = None
        self._mock_defs: List[dict] = []

        # Effective endpoint; initialised from settings but can change at runtime
        self._readsb_host = settings.readsb_host
        self._readsb_port = settings.readsb_port
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def endpoint(self) -> tuple[str, int]:
        return self._readsb_host, self._readsb_port

    def set_endpoint(self, host: str, port: int) -> None:
        if self._readsb_host == host and self._readsb_port == port:
            return
        logger.info(f"Switching ADS-B receiver endpoint to {host}:{port}")
        self._readsb_host = host
        self._readsb_port = port
        if self._running:
            self._task.cancel()
```

Update `_read_loop` to use the instance endpoint and set `_connected`:

```python
    async def _read_loop(self):
        while self._running:
            try:
                reader, writer = await asyncio.open_connection(
                    self._readsb_host, self._readsb_port
                )
                self._connected = True
                logger.info(
                    f"Connected to readsb at {self._readsb_host}:{self._readsb_port}"
                )
                buffer = ""
                while self._running:
                    try:
                        data = await asyncio.wait_for(
                            reader.read(4096), timeout=10.0
                        )
                        if not data:
                            break
                        buffer += data.decode("utf-8", errors="ignore")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            self._parse_line(line.strip())
                    except asyncio.TimeoutError:
                        continue
            except asyncio.CancelledError:
                self._connected = False
                raise
            except Exception as e:
                self._connected = False
                logger.warning(f"readsb connection error: {e}, retrying in 5s...")
                await asyncio.sleep(5)
            finally:
                self._connected = False
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
```

### Step 3.2: Write ADSBReceiver tests

Create `backend/tests/test_adsb_receiver.py`:

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.adsb_receiver import ADSBReceiver


@pytest.fixture
def receiver():
    r = ADSBReceiver()
    r._running = True
    return r


def test_initial_endpoint_from_settings(receiver):
    assert receiver.endpoint == ("127.0.0.1", 30003)


def test_set_endpoint_updates_values(receiver):
    receiver.set_endpoint("10.0.0.158", 30003)
    assert receiver.endpoint == ("10.0.0.158", 30003)


def test_set_endpoint_does_nothing_when_unchanged(receiver):
    with patch.object(receiver._task, "cancel") as mock_cancel:
        receiver.set_endpoint("127.0.0.1", 30003)
        mock_cancel.assert_not_called()


@pytest.mark.asyncio
async def test_set_endpoint_cancels_running_loop(receiver):
    receiver._task = MagicMock()
    receiver.set_endpoint("10.0.0.158", 30003)
    receiver._task.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_read_loop_sets_connected_true(receiver):
    receiver._running = True
    mock_reader = AsyncMock()
    mock_reader.read.side_effect = [b"MSG,1,1,1,406A86,1,2024/01/15,12:34:56.789,2024/01/15,12:34:56.789,BAW123,,,,,,,,,,\n", b""]
    mock_writer = MagicMock()

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        task = asyncio.create_task(receiver._read_loop())
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert receiver.connected is False  # after finally block
```

### Step 3.3: Run ADSBReceiver tests

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend
python3 -m pytest tests/test_adsb_receiver.py -v
```

Expected: PASS (with the caveat that `connected` assertion may need adjustment based on exact timing).

### Step 3.4: Commit

```bash
git add backend/app/services/adsb_receiver.py backend/tests/test_adsb_receiver.py
git commit -m "feat(network-receiver): add runtime endpoint switching to ADSBReceiver"
```

---

## Task 4: Config API — Schemas, Validation, Test Endpoint, Apply on Save

**Files:**
- Modify: `backend/app/api/config.py`
- Test: `backend/tests/test_config.py`

### Step 4.1: Extend schemas

Modify `backend/app/api/config.py`:

```python
from pydantic import Field, field_validator


class ConfigResponse(BaseModel):
    latitude: float
    longitude: float
    distance_unit: str
    altitude_unit: str
    speed_unit: str
    cycle_interval_sec: int
    display_mode: str
    active_layout_id: Optional[int]
    idle_layout_id: Optional[int]
    onboarding_complete: bool
    wifi_ssid: Optional[str]
    auto_update: bool
    night_mode: bool
    night_mode_start: Optional[str]
    night_mode_end: Optional[str]
    led_matrix_brightness: int
    receiver_source: str
    network_readsb_host: Optional[str]
    network_readsb_port: int

    model_config = ConfigDict(from_attributes=True)


class ConfigUpdate(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_unit: Optional[str] = None
    altitude_unit: Optional[str] = None
    speed_unit: Optional[str] = None
    cycle_interval_sec: Optional[int] = None
    display_mode: Optional[str] = None
    active_layout_id: Optional[int] = None
    idle_layout_id: Optional[int] = None
    onboarding_complete: Optional[bool] = None
    wifi_ssid: Optional[str] = None
    wifi_password: Optional[str] = None
    auto_update: Optional[bool] = None
    night_mode: Optional[bool] = None
    night_mode_start: Optional[str] = None
    night_mode_end: Optional[str] = None
    led_matrix_brightness: Optional[int] = None
    receiver_source: Optional[str] = None
    network_readsb_host: Optional[str] = None
    network_readsb_port: Optional[int] = None

    @field_validator("receiver_source")
    @classmethod
    def validate_receiver_source(cls, v):
        if v is not None and v not in ("local", "network"):
            raise ValueError("receiver_source must be 'local' or 'network'")
        return v

    @field_validator("network_readsb_port")
    @classmethod
    def validate_port(cls, v):
        if v is not None and not (1 <= v <= 65535):
            raise ValueError("network_readsb_port must be between 1 and 65535")
        return v

    @model_validator(mode="after")
    def validate_network_config(self):
        if self.receiver_source == "network":
            if not self.network_readsb_host or not self.network_readsb_host.strip():
                raise ValueError("network_readsb_host is required when receiver_source is 'network'")
        return self
```

Note: `model_validator` requires importing it from pydantic:

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
```

### Step 4.2: Apply receiver source on save

In `update_config()`, after refreshing the cache and before returning:

```python
    # Apply receiver source changes
    receiver_fields = {"receiver_source", "network_readsb_host", "network_readsb_port"}
    if receiver_fields & set(update_data.keys()):
        from app.services.readsb_service_manager import apply_receiver_source
        from app.services.adsb_receiver import receiver
        apply_receiver_source(config)
        # Refresh cached receiver endpoint in system status
        await refresh_config_cache(session)
```

Also keep the existing location/layout/brightness notification blocks.

### Step 4.3: Add test-receiver endpoint

Add to `backend/app/api/config.py`:

```python
import asyncio


class TestReceiverRequest(BaseModel):
    host: str
    port: int


class TestReceiverResponse(BaseModel):
    reachable: bool
    message: str


@router.post("/test-receiver", response_model=TestReceiverResponse)
async def test_receiver(req: TestReceiverRequest):
    """Open a TCP connection to the proposed network receiver and verify SBS data if available."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(req.host, req.port),
            timeout=5.0,
        )
    except (OSError, asyncio.TimeoutError) as e:
        return TestReceiverResponse(
            reachable=False,
            message=f"Cannot connect to {req.host}:{req.port}: {e}",
        )

    try:
        line = await asyncio.wait_for(reader.readline(), timeout=5.0)
        if line.startswith(b"MSG,"):
            return TestReceiverResponse(
                reachable=True,
                message="Connected and receiving SBS data.",
            )
        if line:
            return TestReceiverResponse(
                reachable=True,
                message="Connected — unexpected data format.",
            )
        return TestReceiverResponse(
            reachable=True,
            message="Connected — no data yet.",
        )
    except asyncio.TimeoutError:
        return TestReceiverResponse(
            reachable=True,
            message="Connected — no data yet.",
        )
    finally:
        writer.close()
        await writer.wait_closed()
```

### Step 4.4: Add validation tests

Append to `backend/tests/test_config.py`:

```python
from app.api.config import ConfigUpdate


def test_network_config_requires_host():
    with pytest.raises(ValueError, match="network_readsb_host is required"):
        ConfigUpdate(receiver_source="network", network_readsb_host="")


def test_network_config_accepts_valid_host():
    update = ConfigUpdate(
        receiver_source="network",
        network_readsb_host="10.0.0.158",
        network_readsb_port=30003,
    )
    assert update.receiver_source == "network"
    assert update.network_readsb_host == "10.0.0.158"


def test_invalid_receiver_source_rejected():
    with pytest.raises(ValueError, match="receiver_source must be"):
        ConfigUpdate(receiver_source="satellite")


def test_invalid_port_rejected():
    with pytest.raises(ValueError, match="network_readsb_port"):
        ConfigUpdate(receiver_source="network", network_readsb_host="10.0.0.158", network_readsb_port=70000)
```

### Step 4.5: Run config tests

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend
python3 -m pytest tests/test_config.py -v
```

Expected: all PASS.

### Step 4.6: Commit

```bash
git add backend/app/api/config.py backend/tests/test_config.py
git commit -m "feat(network-receiver): extend config API with validation and test endpoint"
```

---

## Task 5: System Status Endpoint

**Files:**
- Modify: `backend/app/api/system.py`
- Test: `backend/tests/test_system.py`

### Step 5.1: Extend `SystemStatus`

Modify `backend/app/api/system.py`:

```python
from typing import Optional


class SystemStatus(BaseModel):
    app_name: str
    version: str
    platform: str
    python_version: str
    debug: bool
    led_matrix_enabled: bool
    readsb_host: str
    readsb_port: int
    receiver_source: str
    receiver_connected: bool


@router.get("/status", response_model=SystemStatus)
async def get_status():
    from app.services.adsb_receiver import receiver
    from app.api.config import get_user_config_sync

    config = get_user_config_sync()
    host, port = receiver.endpoint
    return SystemStatus(
        app_name=settings.app_name,
        version=settings.version,
        platform=platform.system(),
        python_version=platform.python_version(),
        debug=settings.debug,
        led_matrix_enabled=settings.led_matrix_brightness > 0,
        readsb_host=host,
        readsb_port=port,
        receiver_source=config.receiver_source if config else "local",
        receiver_connected=receiver.connected,
    )
```

### Step 5.2: Write system status test

Append to `backend/tests/test_system.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_status_includes_receiver_info():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/system/status")

    assert response.status_code == 200
    data = response.json()
    assert "receiver_source" in data
    assert "receiver_connected" in data
    assert "readsb_host" in data
    assert "readsb_port" in data
    assert data["receiver_source"] == "local"
```

### Step 5.3: Run system tests

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend
python3 -m pytest tests/test_system.py -v
```

Expected: PASS.

### Step 5.4: Commit

```bash
git add backend/app/api/system.py backend/tests/test_system.py
git commit -m "feat(network-receiver): expose receiver source and connection in system status"
```

---

## Task 6: Lifespan Startup

**Files:**
- Modify: `backend/app/lifespan.py`

### Step 6.1: Apply receiver source on startup

In `backend/app/lifespan.py`, after loading `UserConfig` and setting user location, add:

```python
        # Apply receiver source configuration (local vs network)
        from app.services.readsb_service_manager import apply_receiver_source
        apply_receiver_source(config)
```

Place this immediately before `await receiver.start()`.

### Step 6.2: Verify startup path manually

Run the backend locally (or in a test) and confirm no exception is raised. Since this touches hardware/systemd, a full unit test is not required here; the service manager tests cover the logic.

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend
python3 -m pytest tests/ -k "not test_display" -q
```

Expected: suite passes.

### Step 6.3: Commit

```bash
git add backend/app/lifespan.py
git commit -m "feat(network-receiver): apply receiver source on app startup"
```

---

## Task 7: Frontend Types and Settings UI

**Files:**
- Modify: `frontend/src/types/config.ts`
- Modify: `frontend/src/components/Settings/Settings.tsx`

### Step 7.1: Extend `UserConfig` type

Modify `frontend/src/types/config.ts`:

```typescript
export interface UserConfig {
  latitude: number;
  longitude: number;
  distance_unit: string;
  altitude_unit: string;
  speed_unit: string;
  cycle_interval_sec: number;
  display_mode: string;
  active_layout_id?: number;
  idle_layout_id?: number;
  onboarding_complete: boolean;
  wifi_ssid?: string;
  auto_update: boolean;
  night_mode: boolean;
  night_mode_start?: string;
  night_mode_end?: string;
  led_matrix_brightness: number;
  receiver_source: string;
  network_readsb_host?: string;
  network_readsb_port: number;
}
```

### Step 7.2: Add Receiver card to Settings

Modify `frontend/src/components/Settings/Settings.tsx`. Add the following helper near `SelectField`:

```typescript
function isValidHost(host: string | undefined): boolean {
  return !!host && host.trim().length > 0;
}

function isValidPort(port: number): boolean {
  return Number.isInteger(port) && port >= 1 && port <= 65535;
}
```

Add a new card after the LED Matrix Status card (around line 240):

```tsx
      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-white/70 flex items-center gap-2">
            <Radio size={14} />
            Receiver
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>ADS-B source</Label>
            <Select
              value={config.receiver_source}
              onValueChange={(v) => update('receiver_source', v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="local">Local RTL-SDR</SelectItem>
                <SelectItem value="network">Network receiver</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-white/40">
              {config.receiver_source === 'local'
                ? 'Use the RTL-SDR stick plugged into this Pi.'
                : 'Use a readsb instance on your local network.'}
            </p>
          </div>

          {config.receiver_source === 'network' && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label>Host</Label>
                  <Input
                    type="text"
                    placeholder="10.0.0.158"
                    value={config.network_readsb_host || ''}
                    onChange={(e) => update('network_readsb_host', e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Port</Label>
                  <Input
                    type="number"
                    min={1}
                    max={65535}
                    value={config.network_readsb_port}
                    onChange={(e) => update('network_readsb_port', parseInt(e.target.value, 10) || 0)}
                  />
                </div>
              </div>

              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  className="gap-2"
                  disabled={!isValidHost(config.network_readsb_host) || !isValidPort(config.network_readsb_port)}
                  onClick={async () => {
                    try {
                      const res = await api.post<{ reachable: boolean; message: string }>('/api/config/test-receiver', {
                        host: config.network_readsb_host,
                        port: config.network_readsb_port,
                      });
                      if (res.reachable) {
                        toast.success(res.message);
                      } else {
                        toast.error(res.message);
                      }
                    } catch {
                      toast.error('Test connection failed');
                    }
                  }}
                >
                  <Activity size={14} />
                  Test connection
                </Button>
              </div>
            </>
          )}

          <div className="text-xs text-white/40">
            Current endpoint: {receiverStatus?.readsb_host || '127.0.0.1'}:{receiverStatus?.readsb_port || 30003}
            {' · '}
            {receiverStatus?.receiver_connected ? 'Connected' : 'Reconnecting...'}
          </div>
        </CardContent>
      </Card>
```

Use the new `useReceiverStatus` hook (created in the next step) to poll `/api/system/status` for live receiver state.

### Step 7.3: Create/use receiver status hook

If creating a new hook, add `frontend/src/hooks/useReceiverStatus.ts`:

```typescript
import { useEffect, useState } from 'react';
import { api } from '@/api/client';

interface ReceiverStatus {
  receiver_source: string;
  readsb_host: string;
  readsb_port: number;
  receiver_connected: boolean;
}

export function useReceiverStatus() {
  const [status, setStatus] = useState<ReceiverStatus | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await api.get<ReceiverStatus>('/api/system/status');
        setStatus(res);
      } catch {
        // ignore
      }
    };
    fetchStatus();
    const id = setInterval(fetchStatus, 5000);
    return () => clearInterval(id);
  }, []);

  return status;
}
```

Then in `Settings.tsx`:

```typescript
import { useReceiverStatus } from '@/hooks/useReceiverStatus';
// ...
const receiverStatus = useReceiverStatus();
```

And replace the status line with:

```tsx
          <div className="text-xs text-white/40">
            Current endpoint: {receiverStatus?.readsb_host || '127.0.0.1'}:{receiverStatus?.readsb_port || 30003}
            {' · '}
            {receiverStatus?.receiver_connected ? 'Connected' : 'Reconnecting...'}
          </div>
```

### Step 7.4: Validate before save

In `handleSave`, add a guard for network mode:

```typescript
  const handleSave = async () => {
    if (!config) return;
    if (config.receiver_source === 'network') {
      if (!isValidHost(config.network_readsb_host) || !isValidPort(config.network_readsb_port)) {
        toast.error('Please enter a valid network receiver host and port');
        return;
      }
    }
    await api.put('/api/config', config);
    toast.success('Settings saved');
  };
```

### Step 7.5: Build and lint frontend

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/frontend
npm run build
```

Expected: build succeeds with no new TypeScript errors.

### Step 7.6: Commit

```bash
git add frontend/src/types/config.ts frontend/src/components/Settings/Settings.tsx
git add frontend/src/hooks/useReceiverStatus.ts  # if created
git commit -m "feat(network-receiver): add receiver settings UI and status hook"
```

---

## Task 8: systemd Drop-In and Installer

**Files:**
- Create: `systemd/readsb.service.d/10-network-mode.conf`
- Modify: `scripts/install.sh`

### Step 8.1: Create drop-in file

Create `systemd/readsb.service.d/10-network-mode.conf`:

```ini
[Unit]
ConditionPathExists=!/opt/adsbledmatrix/data/.network_receiver_enabled
```

### Step 8.2: Install drop-in in `install.sh`

Find the section in `scripts/install.sh` that installs systemd services. Add after the `readsb.service` is copied/installed:

```bash
# Install readsb drop-in to disable it when network receiver mode is active
mkdir -p /etc/systemd/system/readsb.service.d
cp "${INSTALL_DIR}/systemd/readsb.service.d/10-network-mode.conf" /etc/systemd/system/readsb.service.d/
chmod 644 /etc/systemd/system/readsb.service.d/10-network-mode.conf
systemctl daemon-reload
```

### Step 8.3: Verify installer syntax

```bash
bash -n /home/bchen/GitHub/adsledmatrix/adsbledmatrix/scripts/install.sh
```

Expected: no output (syntax OK).

### Step 8.4: Commit

```bash
git add systemd/readsb.service.d/10-network-mode.conf scripts/install.sh
git commit -m "feat(network-receiver): install systemd drop-in to skip readsb in network mode"
```

---

## Task 9: Full Test Suite and Manual Verification

**Files:** all

### Step 9.1: Run backend tests

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend
python3 -m pytest tests/ -q
```

Expected: all PASS.

### Step 9.2: Run frontend build

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/frontend
npm run build
```

Expected: build succeeds.

### Step 9.3: Manual verification on Pi

1. Fresh install or update a Pi with the changes.
2. Boot with a local RTL-SDR stick. Verify `readsb.service` is active and aircraft display.
3. Open Settings → Receiver → switch to "Network receiver".
4. Enter the Mac Mini IP (`10.0.0.158`) and port `30003`.
5. Click "Test connection" — expect success message.
6. Save.
7. Verify:
   - `sudo systemctl status readsb.service` shows inactive.
   - `ls /opt/adsbledmatrix/data/.network_receiver_enabled` exists.
   - LED matrix displays aircraft from the Mac Mini.
   - `/api/system/status` shows `receiver_source: network` and `receiver_connected: true`.
8. Reboot the Pi. Verify `readsb.service` does not start.
9. Switch back to "Local RTL-SDR" in Settings and save.
10. Verify:
    - `readsb.service` is active.
    - Flag file is gone.
    - LED matrix displays aircraft from local stick.

### Step 9.4: Final commit

```bash
git commit --allow-empty -m "feat(network-receiver): verified end-to-end on Pi"
```

---

## Self-Review

**Spec coverage:**
- Data model → Task 1
- Backend receiver configuration → Task 3
- Service manager → Task 2
- systemd integration → Task 8
- Frontend Settings UI → Task 7
- Test connection endpoint → Task 4
- Migration → Task 1
- Error handling → covered in each task (dev fallback, validation, retry, status)
- Testing → Task 9

**Placeholder scan:**
- No TBD/TODO.
- No vague "add error handling" steps; concrete validation and fallback code shown.
- No "write tests for the above"; actual test code included.

**Type consistency:**
- `receiver_source` is `str` / `String(10)` / `TEXT` everywhere.
- `network_readsb_host` is `Optional[str]` / `String(255)` / `TEXT` everywhere.
- `network_readsb_port` is `int` / `Integer` everywhere.
- `apply_receiver_source` is called from `lifespan.py` and `config.py`.
- `set_endpoint` signature is `(host: str, port: int)` consistently.

No gaps found.
