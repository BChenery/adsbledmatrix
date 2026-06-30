# OTA Auto-Update Design

## Problem

The project already has a release-based updater (`app/services/updater.py`) and a systemd timer, but releases are created manually by tagging. For shipping to thousands of customers, updates need to happen automatically when code lands on `main`, with safeguards so a bad push doesn't brick the fleet.

## Goals

- Every merge to `main` produces a versioned, installable release.
- Devices check for updates daily and apply them automatically (when enabled).
- Updates are atomic and can be rolled back if the device fails health checks.
- Rollouts can be staged by percentage of the fleet.
- No build tools (npm, git) are required on the device.

## Non-Goals

- Delta/binary patches.
- Encrypted/signed updates.
- Per-customer release channels or feature flags.
- Self-hosted update control plane.

## Decision Summary

| Choice | Decision |
|--------|----------|
| Update source | GitHub Releases, auto-generated on every push to `main`. |
| Artifact | Pre-built tarball containing backend, data, scripts, systemd units, and built frontend static files. |
| Update frequency | Daily, driven by existing `adsbledmatrix-update.timer`. |
| Rollout control | Percentage-based via `rollout.json` asset attached to each release. |
| Rollback | Automatic: backup current install before update; restore if `/api/health` fails after restart. |
| Device ID | Stable machine identifier (fallback chain: `/etc/machine-id` → primary MAC → generated UUID stored in config). |

## Design Details

### 1. Release Generation

A GitHub Actions workflow (`.github/workflows/release.yml`) is modified to trigger on pushes to `main`.

Steps:

1. **Checkout** the repo.
2. **Run frontend tests**: `npm ci && npm run test`.
3. **Build frontend**: `npm run build` (outputs to `backend/app/static`).
4. **Bump version**: read `VERSION`, increment patch component, commit the change back to `main`.
5. **Create archive**:
   ```
   adsbledmatrix/
     backend/
     data/
     hardware/
     scripts/
     systemd/
     docs/
     README.md
     VERSION
   ```
6. **Compute SHA256** checksum for the archive.
7. **Create GitHub Release** with:
   - Tag: `v{VERSION}`
   - Asset: `adsbledmatrix-v{VERSION}.tar.gz`
   - Asset: `adsbledmatrix-v{VERSION}.tar.gz.sha256`
   - Asset: `rollout.json` containing `{"percentage": 100}`

### 2. Device Update Flow

The existing `adsbledmatrix-update.service` runs the Python update check daily.

Sequence:

1. `UpdateService.check_for_update()` calls the GitHub Releases API for the latest release.
2. Compare `latest_version` to the running `settings.version`.
3. If newer, fetch the `rollout.json` asset.
4. Compute device rollout bucket:
   - `device_id = /etc/machine-id` (or fallback).
   - `bucket = int(sha256(device_id + release_tag).hexdigest(), 16) % 100`.
   - If `bucket < rollout_percentage`, proceed; otherwise skip.
5. If `auto_update` is enabled (existing `UserConfig` flag), apply the update.
6. Download the archive and checksum.
7. Verify the archive against the checksum.
8. Back up `/opt/adsbledmatrix` to `/opt/adsbledmatrix-backup`.
9. Extract the archive over `/opt/adsbledmatrix`.
10. Run any pending DB migrations.
11. Restart `adsbledmatrix.service`.
12. Poll `/api/health` for up to 2 minutes.
13. If health fails, restore the backup and restart again.
14. Log the result.

### 3. Versioning

- `backend/app/config.py` reads `VERSION` from the project root.
- `settings.version` is exposed via `/api/system/status` and `/api/health`.
- The GitHub Actions workflow is the single source of truth for version bumps.

### 4. Rollout Control

- New releases default to `rollout.json: {"percentage": 100}`.
- To stage a release, edit the release asset and set `"percentage": 5`, `25`, etc.
- To pause, set `"percentage": 0`.
- To complete rollout, set `"percentage": 100`.
- Devices re-evaluate daily, so percentage changes take effect within 24 hours.

### 5. Settings UI

The existing Settings page is extended to show:

- Current version.
- Latest available version.
- Last update check time.
- Update status (up to date, available, downloading, applying, rolled back).
- Toggle for `auto_update`.
- Buttons: "Check now", "Apply update".

## Files to Modify

- `.github/workflows/release.yml` — trigger on `main`, bump version, build frontend, publish checksum + rollout.json.
- `backend/app/services/updater.py` — add percentage rollout, checksum verify, health-check rollback.
- `backend/app/config.py` — read version from `VERSION` file.
- `backend/app/api/system.py` — expose update status and trigger endpoints.
- `systemd/adsbledmatrix-update.service` — ensure it invokes the updated updater.
- `frontend/src/components/Settings/Settings.tsx` — show update status and controls.
- `VERSION` — add file if missing.

## API Surface

No breaking changes. Existing endpoints:

- `GET /api/system/update` — check status.
- `POST /api/system/update` — trigger apply.

These continue to work but gain rollout-aware behavior.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Bad release bricks fleet | Staged rollout + automatic rollback on health-check failure. |
| GitHub rate limits | Daily check frequency is low; public API limits are generous for this volume. |
| Release archive corrupt | SHA256 checksum verification before extraction. |
| Device has no machine-id | Fallback chain generates and persists a UUID in config. |
| DB migrations fail | Run migrations before restart; if they fail, do not proceed. |

## Success Criteria

- [ ] A push to `main` creates a new GitHub Release with a pre-built archive, checksum, and `rollout.json`.
- [ ] A device with `auto_update` enabled checks daily and applies the latest release when eligible.
- [ ] If the service fails health checks after an update, the device restores the previous version.
- [ ] Editing `rollout.json` percentage controls how much of the fleet receives the update.
- [ ] The Settings UI shows current version, available update, and update status.
