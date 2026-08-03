# Sync `localadsb` data into `adsbledmatrix`

## Goal
Keep `adsbledmatrix` up to date with the databases maintained in `BChenery/localadsb`, treating `localadsb` as the source of truth for aircraft registry, route cache, and aircraft type names.

## Scope
- Automatically copy selected data assets from `localadsb` into `adsbledmatrix`.
- Regenerate `adsbledmatrix`’s consumed SQLite database from those assets.
- Commit and push the result to `adsbledmatrix/main`.
- Let the Pi pull the new data via its existing `scripts/sync_data.py` mechanism (Option A).

Out of scope:
- Syncing `adsbledmatrix/data/airlines.csv` — `localadsb` does not currently generate this file.
- Changing how the Pi receives code updates (releases / auto-update tarball).

## Source-of-truth mapping

| `localadsb` asset | Copied to | Consumed by | Purpose |
|---|---|---|---|
| `aircraft_routes.db` (preferred) | `data/localadsb/aircraft_routes.db` | `scripts/import_localadsb.py` | Slim aircraft + routes export (no live history) |
| `flights.db` (legacy fallback) | `data/localadsb/flights.db` | `scripts/import_localadsb.py` | Full operational DB if aircraft_routes.db not yet published |
| `aircraft_type_names.json` | `data/localadsb/aircraft_type_names.json` | `scripts/import_localadsb.py` | Maps type codes to model names |
| `qantas_routes.json`, `acars_routes.json` | `data/localadsb/` (optional) | Future route enrichment | Additional route sources if needed |

## Generated artifact

`scripts/import_localadsb.py` produces:

- `data/aircraft_db.sqlite3` — SQLite database with `aircraft` and `routes` tables used by the backend.

This file is also committed by the workflow so the Pi can use it directly without re-running the import.

## Workflow architecture

Add `.github/workflows/sync-localadsb.yml` to `adsbledmatrix`.

### Triggers
1. **Scheduled:** `cron: '0 * * * *'` (hourly) — picks up any `localadsb` change even if the dispatch trigger is missed.
2. **`repository_dispatch`:** fired by `localadsb` on every push that changes a data asset — near-real-time sync.

### Steps
1. Check out `adsbledmatrix`.
2. Check out `BChenery/localadsb` into a temporary directory.
3. Copy the tracked assets into `data/localadsb/`.
4. Set up Python and install backend dependencies.
5. Run `python scripts/import_localadsb.py` to regenerate `data/aircraft_db.sqlite3`.
6. Run a lightweight validation:
   - `aircraft_routes.db` (or legacy `flights.db`) is non-empty.
   - `aircraft_db.sqlite3` has non-zero rows in `aircraft` and `routes`.
7. Commit and push changes only if the data files or generated SQLite changed.

### Commit behavior
- Use a dedicated bot email / name.
- Commit message: `chore: sync localadsb data - <timestamp>`.
- Skip the commit (but mark the workflow as successful) if nothing changed.

## Pi consumption (Option A)

The Pi already runs `scripts/sync_data.py` via the updater service. Extend it:

1. Add these paths to `sync_data.py`’s `DATA_FILES` list:
   - `data/localadsb/aircraft_routes.db` (preferred slim DB)
   - `data/localadsb/flights.db` (legacy fallback during transition)
   - `data/localadsb/aircraft_type_names.json`
2. After downloading, if the source DB changed, run `scripts/import_localadsb.py` to regenerate the local `data/aircraft_db.sqlite3`.
3. The Pi’s existing data-sync cadence then keeps it up to date automatically.

## Error handling

- Workflow failures are reported via GitHub Actions notifications.
- Empty or zero-byte source files abort the workflow before committing.
- Failed import step aborts the workflow before committing.
- The generated SQLite database is validated for row counts before commit.

## Security / tokens

- `repository_dispatch` from `localadsb` requires a GitHub Personal Access Token (PAT) or GitHub App with `actions:write` on `adsbledmatrix`.
- The `adsbledmatrix` workflow only needs default `GITHUB_TOKEN` to commit/push.

## Testing / verification

- A manual workflow run should copy the latest `localadsb` files and commit them.
- After the commit, `scripts/import_localadsb.py` run locally should produce the same `aircraft_db.sqlite3`.
- On the Pi, `scripts/sync_data.py` should download the new files and report updated counts.
