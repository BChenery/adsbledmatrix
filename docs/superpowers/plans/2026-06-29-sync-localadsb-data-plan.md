# Sync `localadsb` data into `adsbledmatrix` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GitHub Actions workflow that copies `BChenery/localadsb` data assets into `adsbledmatrix`, regenerates `data/aircraft_db.sqlite3`, commits the result, and extend the Pi’s `sync_data.py` to pull those files.

**Architecture:** A scheduled + repository-dispatch workflow in `adsbledmatrix` clones `localadsb`, copies the tracked data files, runs `scripts/import_localadsb.py`, validates row counts, and commits/pushes. A companion workflow in `localadsb` triggers the dispatch on data-file pushes. The Pi’s existing `scripts/sync_data.py` is extended to download the new binary assets and re-run the import as a fallback.

**Tech Stack:** GitHub Actions, Python 3.11, `sqlite3`, `httpx`, `git-auto-commit-action`.

---

## File map

| File | Responsibility |
|---|---|
| `.github/workflows/sync-localadsb.yml` | `adsbledmatrix` workflow that performs the sync |
| `.github/workflows/trigger-adsbledmatrix-sync.yml` | `localadsb` workflow that sends `repository_dispatch` events |
| `scripts/sync_data.py` | Pi-side sync script; extended to download localadsb assets and re-import |

---

## Task 1: Add `adsbledmatrix` sync workflow

**Files:**
- Create: `.github/workflows/sync-localadsb.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
name: Sync localadsb data

on:
  repository_dispatch:
    types: [localadsb-updated]
  schedule:
    - cron: '0 * * * *'
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Check out adsbledmatrix
        uses: actions/checkout@v4
        with:
          ref: main

      - name: Check out localadsb
        uses: actions/checkout@v4
        with:
          repository: BChenery/localadsb
          path: _localadsb

      - name: Copy data assets
        run: |
          mkdir -p data/localadsb
          cp _localadsb/flights.db data/localadsb/flights.db
          cp _localadsb/aircraft_type_names.json data/localadsb/aircraft_type_names.json
          # Optional route enrichment files
          for f in _localadsb/qantas_routes.json _localadsb/acars_routes.json; do
            if [ -f "$f" ]; then cp "$f" data/localadsb/; fi
          done

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install backend dependencies
        working-directory: ./backend
        run: pip install -r requirements.txt

      - name: Regenerate aircraft_db.sqlite3
        run: python scripts/import_localadsb.py

      - name: Validate generated database
        run: |
          python - <<'PY'
          import sqlite3, sys
          conn = sqlite3.connect('data/aircraft_db.sqlite3')
          cur = conn.cursor()
          aircraft = cur.execute('SELECT COUNT(*) FROM aircraft').fetchone()[0]
          routes = cur.execute('SELECT COUNT(*) FROM routes').fetchone()[0]
          conn.close()
          print(f'aircraft: {aircraft}, routes: {routes}')
          if aircraft == 0 or routes == 0:
              sys.exit('Generated database is empty')
          PY

      - name: Commit and push changes
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: 'chore: sync localadsb data'
          file_pattern: 'data/localadsb/* data/aircraft_db.sqlite3'
```

- [ ] **Step 2: Inspect the workflow syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/sync-localadsb.yml'))"`

Expected: exits 0 with no output.

- [ ] **Step 3: Commit the workflow**

```bash
git add .github/workflows/sync-localadsb.yml
git commit -m "ci: add localadsb data sync workflow"
```

---

## Task 2: Add `localadsb` dispatch trigger workflow

**Files:**
- Create: `BChenery/localadsb/.github/workflows/trigger-adsbledmatrix-sync.yml`

This task is in the `localadsb` repository. If you cannot write to it from this workspace, document the required file and apply it separately.

- [ ] **Step 1: Create the trigger workflow**

```yaml
name: Trigger adsbledmatrix sync

on:
  push:
    branches:
      - main
    paths:
      - 'flights.db'
      - 'aircraft_type_names.json'
      - 'qantas_routes.json'
      - 'acars_routes.json'

jobs:
  dispatch:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger sync in adsbledmatrix
        run: |
          curl -L -X POST \
            -H "Accept: application/vnd.github+json" \
            -H "Authorization: Bearer ${{ secrets.ADSBLEDMATRIX_DISPATCH_TOKEN }}" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            https://api.github.com/repos/BChenery/adsbledmatrix/dispatches \
            -d '{"event_type":"localadsb-updated"}'
```

- [ ] **Step 2: Configure the PAT secret**

In the `localadsb` repo settings, add a repository secret named `ADSBLEDMATRIX_DISPATCH_TOKEN`.
The token must have `repo` scope (classic PAT) or `actions:write` on `BChenery/adsbledmatrix`.

- [ ] **Step 3: Commit the trigger workflow**

```bash
git add .github/workflows/trigger-adsbledmatrix-sync.yml
git commit -m "ci: trigger adsbledmatrix sync on data changes"
```

---

## Task 3: Extend Pi `sync_data.py` to pull localadsb assets

**Files:**
- Modify: `scripts/sync_data.py`

- [ ] **Step 1: Add localadsb files to the download list**

Change the `DATA_FILES` list near line 29:

```python
DATA_FILES = [
    "data/aircraft_db.csv",
    "data/airlines.csv",
    "data/routes.csv",
    "data/localadsb/flights.db",
    "data/localadsb/aircraft_type_names.json",
    "data/aircraft_db.sqlite3",
]
```

- [ ] **Step 2: Re-import localadsb data when flights.db changes**

After the data-file download loop in `main()`, insert:

```python
        localadsb_script = Path(__file__).resolve().parent / "import_localadsb.py"
        flights_db_local = settings.data_dir / "localadsb" / "flights.db"
        if localadsb_script.exists() and flights_db_local.exists():
            print()
            print("[5/4] Importing localadsb databases...")
            import subprocess
            result = subprocess.run(
                [sys.executable, str(localadsb_script)],
                capture_output=True,
                text=True,
            )
            print(result.stdout)
            if result.returncode != 0:
                print(f"  ⚠ localadsb import warning: {result.stderr.strip() or 'unknown'}")
```

Replace the existing `[5/4] Importing localadsb databases...` block (lines 167-180) with the above so it always runs when `flights.db` is present, not only when the script file exists.

- [ ] **Step 3: Run sync_data.py locally in dry mode**

Run: `cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend && ../.venv/bin/python ../scripts/sync_data.py --skip-logos`

Expected: downloads current data files, imports aircraft and routes, and reports counts.

- [ ] **Step 4: Commit the change**

```bash
git add scripts/sync_data.py
git commit -m "feat: sync localadsb binary assets and re-import on the Pi"
```

---

## Task 4: Validate the end-to-end flow

- [ ] **Step 1: Push the adsbledmatrix workflow**

```bash
git push origin main
```

- [ ] **Step 2: Run the workflow manually**

In the GitHub UI, navigate to **Actions → Sync localadsb data → Run workflow**.

Expected: workflow completes, commits updated `data/localadsb/*` and `data/aircraft_db.sqlite3` if changed.

- [ ] **Step 3: Verify the generated database locally**

Run:
```bash
python - <<'PY'
import sqlite3
conn = sqlite3.connect('data/aircraft_db.sqlite3')
print(conn.execute('SELECT COUNT(*) FROM aircraft').fetchone()[0])
print(conn.execute('SELECT COUNT(*) FROM routes').fetchone()[0])
conn.close()
PY
```

Expected: non-zero counts.

- [ ] **Step 4: Deploy to the Pi and run sync_data.py**

SSH to the Pi and run:
```bash
cd /opt/adsbledmatrix
python scripts/sync_data.py --skip-logos
```

Expected: output shows `data/localadsb/flights.db` and `data/aircraft_db.sqlite3` updated, plus aircraft/route import counts.

---

## Spec coverage self-review

| Spec requirement | Plan task |
|---|---|
| Copy `flights.db` and `aircraft_type_names.json` from `localadsb` | Task 1 Step 1 |
| Regenerate `aircraft_db.sqlite3` | Task 1 Step 1 |
| Scheduled + `repository_dispatch` triggers | Task 1 Step 1, Task 2 |
| Commit/push only when changed | Task 1 Step 1 (`git-auto-commit-action`) |
| Pi pulls data via `sync_data.py` | Task 3 |
| Validate non-empty database | Task 1 Step 1 |
| Error handling / empty file guard | Task 1 Step 1 validation step |

No placeholders or TBDs remain.
