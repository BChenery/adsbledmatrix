# Localadsb Route Sync

## Overview

Flight route and aircraft data originates in the separate `localadsb`
repository. That repo is private and maintains:

- `flights.db` — operational DB (live capture history + reference tables)
- `aircraft_routes.db` — **slim published export** (aircraft + routes only)

The ADS-B LED Matrix project mirrors `aircraft_routes.db` into this repo so Pis do
not have to download ~50 MB of flight-track history they never use.

## Architecture

```
┌──────────────────┐     push      ┌─────────────────────────────────────┐
│  localadsb repo  │ ─────────────▶ │  adsbledmatrix repo (GitHub Action) │
│  aircraft_routes.db    │               │  - copies aircraft_routes.db              │
│  (slim publish)  │               │  - regenerates aircraft_db.sqlite3  │
│  flights.db      │               │  - commits data/localadsb/*         │
│  (ops only)      │               └─────────────────────────────────────┘
└──────────────────┘                                      │
                                                          │  hourly
                                                          ▼
                                       ┌─────────────────────────────────────┐
                                       │  Raspberry Pi                       │
                                       │  - sync_data.py downloads data      │
                                       │  - import_localadsb.py imports      │
                                       │  - service restarts to clear cache  │
                                       └─────────────────────────────────────┘
```

## What is in aircraft_routes.db?

| Table | Purpose |
|-------|---------|
| `aircraft_registry` | hex → registration / type / operator |
| `aero_fleet` | curated fleet types + airline ICAO |
| `australian_registry` | CASA register for VH- type resolution |
| `route_cache` | callsign → origin / destination |
| `city_iata_mapping` | optional city helpers |

Aircraft and routes live in **one** database (not two). Both datasets are
small, updated together, and consumed by the same importer.

## Publishing from localadsb

After changing registry or routes in `flights.db`:

```bash
python3 export_aircraft_routes_db.py
git add aircraft_routes.db aircraft_type_names.json
git commit -m "chore: refresh aircraft_routes.db"
git push
```

## GitHub Actions flow

1. **localadsb** — `.github/workflows/trigger-adsbledmatrix-sync.yml`
   - Triggered on push to `main` when `aircraft_routes.db`, `aircraft_type_names.json`,
     or (legacy) `flights.db` changes.
   - Sends a `localadsb-updated` repository dispatch event to the adsbledmatrix repo.

2. **adsbledmatrix** — `.github/workflows/sync-localadsb.yml`
   - Triggered by the dispatch event, hourly (`cron: '0 * * * *'`), or manually.
   - Checks out the private localadsb repo using `secrets.LOCALADSB_PAT`.
   - Copies `aircraft_routes.db` (preferred) or falls back to `flights.db`, plus
     `aircraft_type_names.json`, into `data/localadsb/`.
   - Runs `scripts/import_localadsb.py` to regenerate `data/aircraft_db.sqlite3`
     (validation only in CI; that file is not committed).
   - Commits and pushes `data/localadsb/*` to `main`.

## On-device sync

The Pi runs `systemd/adsbledmatrix-sync.timer` (`OnCalendar=hourly`, up to
5 minutes random delay), which triggers `scripts/sync_data.py`:

- Downloads `data/localadsb/aircraft_routes.db` (and other data files) from the
  adsbledmatrix repo if they have changed. Legacy `flights.db` is still
  listed for transition devices.
- If the source DB changed (or is newer than the local DB), runs
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

- Prefer `data/localadsb/aircraft_routes.db` over `flights.db`. Do not reintroduce
  the full operational DB as the primary sync asset.
- `localadsb` is a private repo; the adsbledmatrix GitHub Action uses
  `secrets.LOCALADSB_PAT` to access it.
- If routes are missing on the matrix, check:
  1. Was `aircraft_routes.db` regenerated and pushed to localadsb?
  2. Did the adsbledmatrix `sync-localadsb.yml` workflow run and commit?
  3. Did the Pi run `adsbledmatrix-sync.timer`?
  4. Did the service restart after the sync? (`systemctl status adsbledmatrix`)
