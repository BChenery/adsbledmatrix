# Network ADS-B Receiver Support

## Goal

Allow `adsbledmatrix` to consume live ADS-B data from a remote `readsb` instance on the local network (e.g., a Mac Mini with RTL-SDR receivers) instead of requiring a local RTL-SDR stick. The existing local-stick path remains the default and is completely unchanged for the out-of-the-box experience.

## Background

The project already decodes SBS/BaseStation format from `readsb` on TCP port 30003. The user's Mac Mini runs `readsb` with `--net-sbs-port 30003`, so the Pi can consume the same format over the network. The implementation therefore reuses the existing parser and only changes the TCP endpoint and local service state.

## Scope

- Add an opt-in "Network receiver" mode controlled from the Settings page.
- Persist the choice in the existing SQLite `UserConfig` table.
- Start/stop the local `readsb.service` automatically based on the selected mode.
- Prevent `readsb.service` from starting on boot when network mode is enabled.
- Validate network host/port before saving.
- Provide a "Test connection" button to verify reachability before saving.
- Expose receiver connection status via the existing `/api/system/status` endpoint.
- Add unit tests and manual verification steps.

## Non-Goals

- Support multiple concurrent receiver sources (local + network).
- Add authentication or encryption to the SBS stream (standard local-network `readsb` behavior).
- Support protocols other than SBS/BaseStation on port 30003.
- Auto-discovery of network receivers.

## Detailed Design

### 1. Data Model

Add three columns to `UserConfig`:

| Column | Type | Default | Notes |
|---|---|---|---|
| `receiver_source` | `TEXT` | `'local'` | `'local'` or `'network'` |
| `network_readsb_host` | `TEXT` | `NULL` | e.g. `10.0.0.158` |
| `network_readsb_port` | `INTEGER` | `30003` | 1–65535 |

Existing installations default to `'local'`, preserving current behavior.

The `ConfigResponse` and `ConfigUpdate` Pydantic schemas in `backend/app/api/config.py` are extended with the same fields. Validation in `ConfigUpdate` rejects:
- `receiver_source == 'network'` with an empty `network_readsb_host`.
- `network_readsb_port` outside the range 1–65535.

### 2. Backend: Receiver Configuration

`ADSBReceiver` in `backend/app/services/adsb_receiver.py` gains a `set_endpoint(host, port)` method that:

1. Cancels the current read loop.
2. Updates the effective host/port.
3. Restarts the read loop, which uses the existing 5-second reconnect logic.

A helper function `resolve_receiver_config(config: UserConfig) -> (host, port)` returns:
- `(config.network_readsb_host, config.network_readsb_port)` when `receiver_source == 'network'` and host is set.
- `('127.0.0.1', 30003)` otherwise.

`ADSBReceiver` stores the effective endpoint as instance variables (`_readsb_host`, `_readsb_port`) and uses them in `_read_loop()` instead of the global `settings`. This allows the receiver to switch endpoints at runtime without restarting the app. On first start, these instance variables are initialised from `settings.readsb_host` and `settings.readsb_port`, so existing `ADSB_READSB_HOST`/`ADSB_READSB_PORT` env-var overrides continue to work as deployment defaults. `ADSBReceiver` also tracks a boolean `_connected` flag that is `True` while the TCP stream is actively receiving data. This flag is exposed through the receiver instance.

### 3. Backend: Service Manager

A new module `backend/app/services/readsb_service_manager.py` wraps `systemctl`:

- `start_readsb()` — runs `systemctl start readsb.service`.
- `stop_readsb()` — runs `systemctl stop readsb.service`.
- `is_readsb_available()` — checks whether `systemctl` is present and `readsb.service` exists.

If `readsb.service` is not available (e.g., development laptop, Docker), the manager logs an info message and skips service management. It never raises an exception that would crash the app.

A higher-level `apply_receiver_source(config)` function lives in `backend/app/services/readsb_service_manager.py`:

1. Resolves the effective endpoint.
2. Calls `receiver.set_endpoint(host, port)`.
3. If `receiver_source == 'network'`:
   - Create flag file `settings.data_dir / '.network_receiver_enabled'`.
   - Call `stop_readsb()`.
4. If `receiver_source == 'local'`:
   - Remove flag file if it exists.
   - Call `start_readsb()`.

This function is called:
- During startup in `lifespan.py`, after `UserConfig` is loaded.
- In `backend/app/api/config.py` after a successful `PUT /api/config` that changes any receiver-related field.

### 4. systemd Integration

The installer creates a systemd drop-in for `readsb.service`:

```ini
# /etc/systemd/system/readsb.service.d/10-network-mode.conf
[Unit]
ConditionPathExists=!/opt/adsbledmatrix/data/.network_receiver_enabled
```

Because the flag file is created or removed immediately when Settings are saved, the next boot will start or skip `readsb.service` correctly. There is no race condition at boot time.

The existing `adsbledmatrix.service` keeps its `Wants=readsb.service` dependency. When the flag file exists, systemd skips `readsb.service`, and the main app starts normally. When the flag file does not exist, `readsb.service` starts as before.

> **Note:** The drop-in hard-codes the production data path (`/opt/adsbledmatrix/data`) because systemd units cannot read application env vars. This matches the production installer default for `ADSB_DATA_DIR`. Development environments do not install this drop-in, so the app-managed flag file location there is irrelevant to systemd.

### 5. Frontend: Settings UI

A new "Receiver" card is added near the top of `frontend/src/components/Settings/Settings.tsx`:

- **Source selector** (radio group or select):
  - "Local RTL-SDR" (default)
  - "Network receiver"
- **Network fields**, visible only in network mode:
  - Host input
  - Port input (default 30003)
- **Live status line** showing:
  - Current source
  - Effective host:port
  - Connection state: "Connected", "Reconnecting...", or "No data"
- **"Test connection" button**, visible only in network mode.
- Save is disabled until validation passes.

The `UserConfig` type in `frontend/src/types/config.ts` is updated with the three new fields.

### 6. Test Connection

A new backend endpoint verifies that the configured network receiver is reachable:

```
POST /api/config/test-receiver
{
  "host": "10.0.0.158",
  "port": 30003
}
```

Response:

```json
{
  "reachable": true,
  "message": "Connected and receiving SBS data."
}
```

or

```json
{
  "reachable": false,
  "message": "Cannot connect to 10.0.0.158:30003."
}
```

Implementation:

1. Open an async TCP connection to the provided host/port with a short timeout (e.g., 5 seconds).
2. If the connection fails, return `reachable: false`.
3. If the connection succeeds, wait up to 5 seconds for any line of data.
   - If a line starting with `MSG,` is received, return `reachable: true` with message "Receiving SBS data."
   - If no data arrives (e.g., no aircraft in range), return `reachable: true` with message "Connected — no data yet."
4. Close the connection and return the result.

This endpoint does not save anything; it only validates reachability before the user commits the change.

### 7. Migration

`backend/app/database.py`'s `migrate_db()` adds the new columns if they are missing:

```sql
ALTER TABLE user_config ADD COLUMN receiver_source TEXT NOT NULL DEFAULT 'local';
ALTER TABLE user_config ADD COLUMN network_readsb_host TEXT;
ALTER TABLE user_config ADD COLUMN network_readsb_port INTEGER NOT NULL DEFAULT 30003;
```

Existing installs therefore remain in local mode and continue working unchanged.

### 8. Error Handling

| Scenario | Behaviour |
|---|---|
| Network receiver offline | `ADSBReceiver` reconnects every 5 seconds; UI shows "Reconnecting...". |
| `systemctl` unavailable | Service manager logs an info message and skips; receiver still connects. |
| Invalid host/port | API returns 422; UI disables Save and shows inline errors. |
| Test connection fails | UI shows the failure reason; user can correct host/port before saving. |
| Flag file missing after manual DB edit | App recreates the flag file on the next Settings save, so the next boot is correct. |

## API Changes

- `GET /api/config` — returns `receiver_source`, `network_readsb_host`, `network_readsb_port`.
- `PUT /api/config` — accepts the same fields; applies service state and receiver endpoint after saving.
- `POST /api/config/test-receiver` — tests reachability of a network receiver without saving.
- `GET /api/system/status` — returns `receiver_source`, `readsb_host`, `readsb_port`, `receiver_connected`.

## Testing

### Unit Tests

- `test_config.py`: validation rejects empty host and invalid port in network mode.
- `test_readsb_service_manager.py`: mock `subprocess` to verify `start_readsb`, `stop_readsb`, and dev-mode skip.
- `test_adsb_receiver.py`: verify `set_endpoint()` reconnects to the new host/port.
- `test_system.py`: verify `/api/system/status` includes receiver connection state.

### Manual Tests

1. Fresh install / default boot:
   - Verify `readsb.service` starts automatically.
   - Verify Pi displays aircraft from local RTL-SDR.
2. Switch to network mode:
   - Enter Mac Mini IP and port.
   - Click "Test connection" — expect success.
   - Save.
   - Verify `readsb.service` stops.
   - Verify Pi displays aircraft from Mac Mini.
   - Verify flag file exists.
   - Reboot Pi and confirm `readsb.service` does not start.
3. Switch back to local mode:
   - Change Settings to "Local RTL-SDR".
   - Save.
   - Verify `readsb.service` starts.
   - Verify flag file is removed.
   - Reboot Pi and confirm `readsb.service` starts normally.
4. Negative test:
   - Enter an unreachable IP in network mode.
   - Click "Test connection" — expect failure.
   - Verify Save is disabled.

## Security Considerations

- The SBS/BaseStation protocol has no authentication. This design assumes the remote `readsb` is on a trusted local network, which matches the user's deployment and standard hobbyist ADS-B setups.
- The `adsbledmatrix` app already runs as root for GPIO access, so it can manage `readsb.service`. Service management commands are hard-coded and do not accept user input.
- The test-connection endpoint only opens a TCP socket to the user-supplied host/port and reads one line; it does not forward traffic or execute commands.

## Files to Modify

- `backend/app/models.py`
- `backend/app/database.py`
- `backend/app/api/config.py`
- `backend/app/api/system.py`
- `backend/app/services/adsb_receiver.py`
- `backend/app/services/readsb_service_manager.py` (new)
- `backend/app/lifespan.py`
- `frontend/src/types/config.ts`
- `frontend/src/components/Settings/Settings.tsx`
- `backend/tests/test_config.py`
- `backend/tests/test_readsb_service_manager.py` (new)
- `backend/tests/test_adsb_receiver.py`
- `backend/tests/test_system.py`
- `scripts/install.sh` (install systemd drop-in)
- `systemd/readsb.service.d/10-network-mode.conf` (new)

## Open Questions

None. All known edge cases are addressed in the design.
