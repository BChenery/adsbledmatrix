# Universal Installer & Auto-Updater Design

## Problem

The current production update path has two critical failure modes discovered during the v0.1.6 rollout:

1. **Data loss on update.** The installer (`scripts/install_latest.sh`) excludes `data/*.db` and `data/*.sqlite` but the application database is `data/aircraft_db.sqlite3`. `rsync --delete` therefore wipes customer settings, layouts, and location on every update.
2. **Permission crash after update.** The release tarball is owned by the GitHub Actions UID (1001). After `rsync`, `data/` is owned by UID 1001. The service starts as `root`, but `rpi-rgb-led-matrix` drops privileges to the `adsb` user during LED matrix initialization. SQLite then cannot create `aircraft_db.sqlite3`, so the app crashes on startup.
3. **Auto-updater cannot run inside the app.** Once privileges are dropped to `adsb`, the in-app updater cannot write to `/opt/adsbledmatrix`, extract archives, or run `systemctl restart`. The design in `2026-06-30-ota-auto-update-design.md` assumed the updater could run from the app process; this document revises that.

## Goals

- A single `curl ... | sudo bash` one-liner works for both fresh Pi installs and updates.
- Customer data (SQLite DBs, `.env`, `venv`) is never lost or overwritten during an update.
- After install or update, the service starts cleanly with correct ownership.
- Dependency changes in `backend/requirements.txt` are applied on update without rebuilding the whole venv.
- Automatic updates run from a root-privileged systemd timer, not the dropped-privilege app process.
- Failed updates roll back automatically using a pre-update backup.

## Non-Goals

- Delta/binary patches.
- Encrypted/signed updates beyond SHA256 checksum verification.
- Fresh builds of the LED matrix C++ library on every update (build once, preserve).
- Per-customer release channels.

## Decision Summary

| Choice | Decision |
|--------|----------|
| One-liner entry point | `scripts/install_latest.sh` downloaded from GitHub `main` branch. |
| Install mode detection | Fresh install if `/opt/adsbledmatrix/venv` is missing; otherwise update. |
| Data preservation | Exclude `venv/`, `.env`, and **all** SQLite files (`*.db`, `*.sqlite`, `*.sqlite3`) anywhere under `data/`. |
| Ownership | `adsb:adsb` for `venv/` and `data/`; `root:root` for code/services. |
| Dependency updates | Run `pip install -r backend/requirements.txt` on every update. |
| Auto-update trigger | `systemd/adsbledmatrix-update.timer` + `adsbledmatrix-update.service` running as `root`. |
| Update application | `scripts/check_and_update.sh` fetches release info and invokes `install_latest.sh`. |
| App updater role | Status/notification only; no file writes or service restarts. |
| Rollback | Timestamped backup before update; restore if `/api/health` fails within 2 minutes. |
| Backup retention | Keep the 2 most recent backups. |

## Design Details

### 1. `scripts/install_latest.sh` — universal installer/updater

Entry command remains:

```bash
curl -L https://raw.githubusercontent.com/BChenery/adsbledmatrix/main/scripts/install_latest.sh | sudo bash
```

The script is idempotent and branch-aware: it always downloads the latest **release** tarball but uses the install logic from the `main` branch script.

#### Fresh install path

Triggered when `/opt/adsbledmatrix/venv` does not exist.

1. Create `adsb` system user if missing (`useradd -r -s /usr/sbin/nologin adsb`).
2. Install OS packages: `python3`, `python3-venv`, `python3-dev`, `python3-pip`, `libssl-dev`, `libffi-dev`, `build-essential`.
3. Create `/opt/adsbledmatrix` from the release tarball.
4. Create venv and install `backend/requirements.txt`.
5. Build and install `rpi-rgb-led-matrix` Python bindings from source if `rgbmatrix` is not importable.
6. Install systemd service files and enable:
   - `adsbledmatrix.service`
   - `adsbledmatrix-update.timer`
   - `adsbledmatrix-update.service`
   - `readsb.service` (if present in release)
7. Set ownership.
8. Start services.
9. Health check via `/api/health`.

#### Update path

Triggered when `/opt/adsbledmatrix/venv` exists.

1. Stop `adsbledmatrix.service`.
2. Create timestamped backup: `/opt/adsbledmatrix-backup-YYYYMMDDhhmmss`.
3. Extract release tarball to `/tmp/adsbledmatrix`.
4. `rsync -a --delete` with excludes:
   - `venv/`
   - `.env`
   - `data/*.db`
   - `data/*.sqlite`
   - `data/*.sqlite3`
   - `data/**/*.db`
   - `data/**/*.sqlite`
   - `data/**/*.sqlite3`
5. Run `pip install -r backend/requirements.txt` in the venv.
6. Set ownership (`adsb:adsb` on `venv/` and `data/`).
7. Install/refresh systemd unit files.
8. Start `adsbledmatrix.service`.
9. Poll `/api/health` for up to 2 minutes.
10. On failure, stop service, restore backup, start service, and exit with an error.
11. On success, prune old backups (keep last 2).

#### Ownership rules

- `venv/` and `data/` → `adsb:adsb`
- Code, scripts, docs, systemd units → `root:root`
- Service runs as `root` so `rpi-rgb-led-matrix` can init GPIO, then drops to `adsb`; `data/` and `venv/` remain writable.

### 2. Auto-updater architecture

The in-app `UpdateService.apply_update()` is removed or made a no-op. The app only checks for updates and reports status.

#### `systemd/adsbledmatrix-update.timer`

```ini
[Unit]
Description=Daily ADS-B LED Matrix update check

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

#### `systemd/adsbledmatrix-update.service`

```ini
[Unit]
Description=ADS-B LED Matrix update check

[Service]
Type=oneshot
User=root
Group=root
ExecStart=/opt/adsbledmatrix/scripts/check_and_update.sh
```

#### `scripts/check_and_update.sh`

1. Fetch latest release tag from GitHub API.
2. Read current version from `/opt/adsbledmatrix/VERSION`.
3. If same or older, exit.
4. (Optional) Respect `rollout.json` percentage — skip if device not in bucket.
5. If `auto_update` is enabled in the app config (read from SQLite or `.env`), invoke `install_latest.sh`.
6. Log result to `/var/log/adsbledmatrix-update.log`.

#### App updater role

`backend/app/services/updater.py` retains:

- `check_for_update()` — status/info only.
- `update_database()` / `sync_data()` — data sync operations that don't touch system files.

It no longer:

- Downloads release archives.
- Extracts over `/opt/adsbledmatrix`.
- Runs `systemctl` commands.

### 3. Data preservation

Explicit SQLite patterns to exclude from `rsync`:

```text
*.db
*.sqlite
*.sqlite3
```

Applied to `data/` recursively. The `venv/` and `.env` exclusions remain.

### 4. Rollback

Before every update, the script copies the entire install directory with `cp -a`. If the health check fails after the update:

1. Stop `adsbledmatrix.service`.
2. `rsync` or `cp -a` the backup over `/opt/adsbledmatrix`.
3. Start `adsbledmatrix.service`.
4. Health check again.
5. If still failing, leave the service stopped and log a critical error.

After a successful update, only the two most recent backups are kept.

### 5. Logging

Install/update output is echoed to stdout and appended to `/var/log/adsbledmatrix-update.log`. The log is rotated by systemd because the update runs as a one-shot service; additional logrotate config is a future enhancement.

## Files to Modify / Create

- `scripts/install_latest.sh` — rewrite as universal installer/updater.
- `scripts/check_and_update.sh` — new daily update checker.
- `systemd/adsbledmatrix-update.service` — change to run as `root`, invoke shell script.
- `systemd/adsbledmatrix-update.timer` — new or update existing timer.
- `backend/app/services/updater.py` — remove `apply_update`, keep status/check.
- `backend/app/api/system.py` — remove or deprecate `POST /api/system/update` apply endpoint; keep status endpoint.
- `.github/workflows/release.yml` — ensure release tarball is built correctly (already mostly done).

## API Surface

- `GET /api/system/update` — remains: returns current version, latest version, update available, last check time.
- `POST /api/system/update` — changed: optionally triggers the systemd update timer (`systemctl start adsbledmatrix-update.timer` or D-Bus). If privilege limitations make this unreliable, it becomes a no-op and the UI tells the user updates are applied automatically.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Data loss on update | Exclude all SQLite extensions recursively; explicit preservation list. |
| Permission crash | Set `adsb:adsb` ownership on `data/` and `venv/` after every install/update. |
| Auto-updater can't write/restart | Run updater as root via systemd timer, not in-app. |
| Dependency changes break update | Re-run `pip install -r backend/requirements.txt` on every update. |
| Bad release bricks device | Timestamped backup + automatic rollback on health-check failure. |
| Fresh install missing LED matrix bindings | Build from source if not present; document required OS packages. |
| Backup disk usage | Keep only last 2 backups. |

## Success Criteria

- [ ] A customer can run the one-liner on a fresh Pi and end up with a working display.
- [ ] A customer can run the one-liner on an existing install without losing settings, layouts, or location.
- [ ] After the install/update, `sudo systemctl status adsbledmatrix.service` shows it running and stable.
- [ ] Updating to a release with new Python dependencies works without manual venv rebuild.
- [ ] The daily timer can apply updates while the app process runs as `adsb`.
- [ ] A failed update is automatically rolled back from backup.
