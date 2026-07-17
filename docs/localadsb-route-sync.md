# Localadsb Route Sync

## Overview

Flight route and aircraft data originates in the separate `localadsb`
repository. That repo is private and contains a `flights.db` SQLite database.
The ADS-B LED Matrix project mirrors that data into this repo and the deployed
Pis keep themselves up to date automatically.

## Architecture

```
┌──────────────────┐     push      ┌─────────────────────────────────────┐
│  localadsb repo  │ ─────────────▶ │  adsbledmatrix repo (GitHub Action) │
│  flights.db      │               │  - copies flights.db                │
│  (private)       │               │  - regenerates aircraft_db.sqlite3  │
└──────────────────┘               │  - commits data/localadsb/*         │
                                   └─────────────────────────────────────┘
                                                      │
                                                      │  hourly
                                                      ▼
                                   ┌─────────────────────────────────────┐
                                   │  Raspberry Pi                       │
                                   │  - sync_data.py downloads data      │
                                   │  - import_localadsb.py imports      │
                                   │  - service restarts to clear cache  │
                                   └─────────────────────────────────────┘
```

## GitHub Actions flow

1. **localadsb** — `.github/workflows/trigger-adsbledmatrix-sync.yml`
   - Triggered on push to `main` when `flights.db` or `aircraft_type_names.json` changes.
   - Sends a `localadsb-updated` repository dispatch event to the adsbledmatrix repo.

2. **adsbledmatrix** — `.github/workflows/sync-localadsb.yml`
   - Triggered by the dispatch event, hourly (`cron: '0 * * * *'`), or manually.
   - Checks out the private localadsb repo using `secrets.LOCALADSB_PAT`.
   - Copies `flights.db` and `aircraft_type_names.json` into `data/localadsb/`.
   - Runs `scripts/import_localadsb.py` to regenerate `data/aircraft_db.sqlite3`
     (validation only in CI; that file is not committed).
   - Commits and pushes `data/localadsb/*` to `main`.

## On-device sync

The Pi runs `systemd/adsbledmatrix-sync.timer` (`OnCalendar=hourly`, up to
5 minutes random delay), which triggers `scripts/sync_data.py`:

- Downloads `data/localadsb/flights.db` (and other data files) from the
  adsbledmatrix repo if they have changed.
- If `flights.db` changed (or is newer than the local DB), runs
  `scripts/import_localadsb.py` to rebuild `data/aircraft_db.sqlite3` on the Pi.
- Restarts the `adsbledmatrix` service to clear the in-memory route cache so
  new routes appear immediately.

## Default schedule

- GitHub Action: hourly (`0 * * * *`)
- Pi sync: hourly (`OnCalendar=hourly`, `RandomizedDelaySec=300`)

To change the Pi schedule, edit `systemd/adsbledmatrix-sync.timer`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart adsbledmatrix-sync.timer
```

## Why a restart is needed

`app.services.route_service.RouteService` caches every callsign lookup in
memory. Once a callsign has been looked up and found to have no route, that
negative result is cached. After new routes are imported, the service must be
restarted to clear the cache and pick up the new data.

## Manual sync on the Pi

```bash
cd /opt/adsbledmatrix
/opt/adsbledmatrix/venv/bin/python scripts/sync_data.py --force
```

## Notes for future agents

- Do not remove `data/localadsb/flights.db` from `scripts/sync_data.py`'s
  `DATA_FILES`. It is the mechanism that gets the updated database onto the Pi.
- `localadsb` is a private repo; the adsbledmatrix GitHub Action uses
  `secrets.LOCALADSB_PAT` to access it.
- If routes are missing on the matrix, check:
  1. Was `flights.db` pushed to localadsb?
  2. Did the adsbledmatrix `sync-localadsb.yml` workflow run and commit?
  3. Did the Pi run `adsbledmatrix-sync.timer`?
  4. Did the service restart after the sync? (`systemctl status adsbledmatrix`)
