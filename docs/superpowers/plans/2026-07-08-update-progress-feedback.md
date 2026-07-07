# Update Progress Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the confusing "manual updates are applied by systemd" message with plain English, make the **Trigger update** button actually start an update check, and show a real progress bar on the Settings page while the update runs.

**Architecture:** The app service runs as root, so `POST /api/system/update` can start the existing `adsbledmatrix-update.service` via `systemctl --no-block`. The shell scripts (`check_and_update.sh` and `install_latest.sh`) write progress to a JSON status file in the data directory. A new `GET /api/system/update-progress` endpoint reads that file and returns the current state. The Settings UI polls this endpoint and renders a progress bar plus human-readable status text.

**Tech Stack:** Python/FastAPI, Bash, React/TypeScript, Tailwind, systemd, JSON status file.

---

## File Structure

- `backend/app/services/update_progress.py` — new helper to read/write the JSON progress file.
- `backend/app/api/system.py` — update `POST /api/system/update` to start the service; add `GET /api/system/update-progress`.
- `scripts/check_and_update.sh` — write progress steps before/after version check, download, and hand-off to install script.
- `scripts/install_latest.sh` — write progress steps during backup, download, dependency install, service restart, health check.
- `frontend/src/types/update.ts` — new TypeScript type for update progress.
- `frontend/src/components/Settings/Settings.tsx` — replace the update button/message area with a progress-aware panel.
- `frontend/src/hooks/useUpdateProgress.ts` — new hook to poll update progress.
- `backend/tests/test_system.py` — add tests for the new endpoints.

---

## Task 1: Add Update Progress Helper Service

**Files:**
- Create: `backend/app/services/update_progress.py`
- Test: `backend/tests/test_update_progress.py`

- [ ] **Step 1: Write the helper**

```python
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from app.config import settings


class UpdateProgress(BaseModel):
    status: str  # "idle" | "checking" | "downloading" | "installing" | "completed" | "failed" | "up_to_date"
    progress: int  # 0-100
    message: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


PROGRESS_FILE: Path = settings.data_dir / ".update_progress.json"


def write_update_progress(
    status: str,
    progress: int,
    message: str,
    error: Optional[str] = None,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
) -> None:
    """Write the current update progress to disk."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = UpdateProgress(
        status=status,
        progress=max(0, min(100, progress)),
        message=message,
        error=error,
        started_at=started_at,
        completed_at=completed_at,
    ).model_dump()
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f)


def read_update_progress() -> UpdateProgress:
    """Read the current update progress from disk."""
    if not PROGRESS_FILE.exists():
        return UpdateProgress(
            status="idle",
            progress=0,
            message="No update has been run recently.",
        )
    try:
        with open(PROGRESS_FILE) as f:
            data = json.load(f)
        return UpdateProgress(**data)
    except Exception:
        return UpdateProgress(
            status="idle",
            progress=0,
            message="Update status unavailable.",
        )


def reset_update_progress() -> None:
    """Reset progress to idle."""
    write_update_progress(
        status="idle",
        progress=0,
        message="No update has been run recently.",
    )
```

- [ ] **Step 2: Write tests**

Create `backend/tests/test_update_progress.py`:

```python
import pytest
from app.services.update_progress import (
    write_update_progress,
    read_update_progress,
    reset_update_progress,
    PROGRESS_FILE,
)


def test_write_and_read_progress():
    write_update_progress("checking", 10, "Checking for updates...")
    progress = read_update_progress()
    assert progress.status == "checking"
    assert progress.progress == 10
    assert progress.message == "Checking for updates..."


def test_progress_clamps_to_0_100():
    write_update_progress("installing", 150, "too high")
    assert read_update_progress().progress == 100
    write_update_progress("installing", -10, "too low")
    assert read_update_progress().progress == 0


def test_reset_progress():
    write_update_progress("completed", 100, "Done")
    reset_update_progress()
    progress = read_update_progress()
    assert progress.status == "idle"
    assert progress.progress == 0
```

Run:

```bash
/home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend/.venv/bin/python -m pytest tests/test_update_progress.py -v
```

Expected: PASS.

---

## Task 2: Update Backend System Endpoints

**Files:**
- Modify: `backend/app/api/system.py`
- Test: `backend/tests/test_system.py`

- [ ] **Step 1: Add progress endpoint and response model**

In `backend/app/api/system.py`, add:

```python
from app.services.update_progress import read_update_progress, UpdateProgress as UpdateProgressModel


class UpdateProgressResponse(BaseModel):
    status: str
    progress: int
    message: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


@router.get("/update-progress", response_model=UpdateProgressResponse)
async def get_update_progress():
    return UpdateProgressResponse(**read_update_progress().model_dump())
```

- [ ] **Step 2: Make trigger update actually start the update**

Replace the existing `trigger_update` endpoint:

```python
import subprocess
import logging

logger = logging.getLogger(__name__)


@router.post("/update")
async def trigger_update():
    """Trigger the systemd update service to check and install updates in the background."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", "adsbledmatrix-update.service"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return {
                "status": "already_running",
                "message": "An update is already running. Check the progress below.",
            }

        subprocess.Popen(
            ["systemctl", "start", "--no-block", "adsbledmatrix-update.service"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {
            "status": "started",
            "message": "Update check started. Progress will appear below.",
        }
    except Exception as e:
        logger.error(f"Failed to trigger update service: {e}")
        return {
            "status": "error",
            "message": f"Could not start update: {e}",
        }
```

- [ ] **Step 3: Add tests**

In `backend/tests/test_system.py`, add:

```python
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_trigger_update_starts_service():
    with patch("app.api.system.subprocess.run") as mock_run, \
         patch("app.api.system.subprocess.Popen") as mock_popen:
        mock_run.return_value = MagicMock(returncode=1)  # not running
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/system/update")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    mock_popen.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_update_reports_already_running():
    with patch("app.api.system.subprocess.run") as mock_run, \
         patch("app.api.system.subprocess.Popen") as mock_popen:
        mock_run.return_value = MagicMock(returncode=0)  # already running
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/system/update")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "already_running"
    mock_popen.assert_not_called()
```

Run:

```bash
/home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend/.venv/bin/python -m pytest tests/test_system.py -v
```

Expected: PASS.

---

## Task 3: Add Progress Reporting to Shell Scripts

**Files:**
- Modify: `scripts/check_and_update.sh`
- Modify: `scripts/install_latest.sh`

- [ ] **Step 1: Add a shared progress helper in `check_and_update.sh`**

Near the top, after `LOG_FILE` definition, add:

```bash
PROGRESS_FILE="${INSTALL_DIR}/data/.update_progress.json"

write_progress() {
    local status="$1"
    local progress="$2"
    local message="$3"
    local error="${4:-}"
    local started_at="${5:-}"
    local completed_at="${6:-}"
    python3 - <<PY
import json, os
path = "${PROGRESS_FILE}"
os.makedirs(os.path.dirname(path), exist_ok=True)
data = {
    "status": "${status}",
    "progress": int(${progress}),
    "message": """${message}""",
    "error": ${error:+"""${error}"""} or None,
    "started_at": ${started_at:+"""${started_at}"""} or None,
    "completed_at": ${completed_at:+"""${completed_at}"""} or None,
}
with open(path, "w") as f:
    json.dump(data, f)
PY
}
```

- [ ] **Step 2: Update progress points in `check_and_update.sh`**

At the start of `main` execution (after lock acquired), add:

```bash
STARTED_AT=$(date -Iseconds)
write_progress "checking" 5 "Checking GitHub for latest release..." "" "$STARTED_AT"
```

After successful GitHub fetch:

```bash
write_progress "checking" 15 "Latest version: $LATEST_VERSION"
```

When already up to date:

```bash
write_progress "up_to_date" 100 "Already up to date." "" "$STARTED_AT" "$(date -Iseconds)"
exit 0
```

When skipped (rollout/auto_update):

```bash
write_progress "up_to_date" 100 "Update skipped: $reason" "" "$STARTED_AT" "$(date -Iseconds)"
exit 0
```

Before handing off to install script:

```bash
write_progress "downloading" 30 "Downloading update..." "" "$STARTED_AT"
```

On any fatal error:

```bash
write_progress "failed" 0 "Update check failed: $reason" "$reason" "$STARTED_AT" "$(date -Iseconds)"
```

- [ ] **Step 3: Add progress helper to `install_latest.sh`**

Same `PROGRESS_FILE` and `write_progress` function as above (duplicate is OK; these scripts are independent).

- [ ] **Step 4: Update progress points in `install_latest.sh`**

At start:

```bash
STARTED_AT=$(date -Iseconds)
write_progress "installing" 35 "Stopping services and preparing update..." "" "$STARTED_AT"
```

After `fetch_release`:

```bash
write_progress "installing" 45 "Release downloaded. Updating files..."
```

After `install_or_update_code`:

```bash
write_progress "installing" 55 "Updating Python dependencies..."
```

After `ensure_venv_and_requirements`:

```bash
write_progress "installing" 70 "Restarting services..."
```

After services start, before health check:

```bash
write_progress "installing" 85 "Waiting for app to come back online..."
```

On success:

```bash
write_progress "completed" 100 "Update completed successfully." "" "$STARTED_AT" "$(date -Iseconds)"
```

On failure/rollback:

```bash
write_progress "failed" 0 "Update failed: $reason" "$reason" "$STARTED_AT" "$(date -Iseconds)"
```

---

## Task 4: Add Frontend Types and Hook

**Files:**
- Create: `frontend/src/types/update.ts`
- Create: `frontend/src/hooks/useUpdateProgress.ts`

- [ ] **Step 1: Type**

```typescript
export interface UpdateProgress {
  status: 'idle' | 'checking' | 'downloading' | 'installing' | 'completed' | 'failed' | 'up_to_date' | 'already_running';
  progress: number;
  message: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
}
```

- [ ] **Step 2: Hook**

```typescript
import { useEffect, useState } from 'react';
import { api } from '@/api/client';
import { UpdateProgress } from '@/types/update';

const STATUS_POLL_INTERVAL = 2000;
const COMPLETED_STATUSES = ['completed', 'failed', 'up_to_date'];

export function useUpdateProgress(isActive: boolean) {
  const [progress, setProgress] = useState<UpdateProgress | null>(null);

  useEffect(() => {
    if (!isActive) {
      setProgress(null);
      return;
    }

    let cancelled = false;

    const fetchProgress = async () => {
      try {
        const data = await api.get<UpdateProgress>('/api/system/update-progress');
        if (!cancelled) setProgress(data);
      } catch {
        if (!cancelled) {
          setProgress({
            status: 'failed',
            progress: 0,
            message: 'Unable to read update progress.',
          });
        }
      }
    };

    fetchProgress();
    const id = setInterval(fetchProgress, STATUS_POLL_INTERVAL);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [isActive]);

  return progress;
}
```

---

## Task 5: Update Settings UI

**Files:**
- Modify: `frontend/src/components/Settings/Settings.tsx`

- [ ] **Step 1: Add hook and state**

Import:

```typescript
import { useUpdateProgress } from '@/hooks/useUpdateProgress';
```

Add state:

```typescript
const [updateActive, setUpdateActive] = useState(false);
const updateProgress = useUpdateProgress(updateActive);
```

- [ ] **Step 2: Update `handleApplyUpdate`**

```typescript
const handleApplyUpdate = async () => {
  setUpdateActive(true);
  try {
    const res = await api.post<{ status: string; message: string }>('/api/system/update');
    toast.success(res.message);
  } catch {
    toast.error('Failed to start update');
    setUpdateActive(false);
  }
};
```

- [ ] **Step 3: Clear active state when complete/failed**

Use an effect:

```typescript
useEffect(() => {
  if (
    updateProgress?.status === 'completed' ||
    updateProgress?.status === 'failed' ||
    updateProgress?.status === 'up_to_date'
  ) {
    const timer = setTimeout(() => setUpdateActive(false), 5000);
    return () => clearTimeout(timer);
  }
}, [updateProgress?.status]);
```

- [ ] **Step 4: Replace the update button/status area**

In the Updates card, replace the existing button/"Update available" section with:

```tsx
<div className="flex flex-col gap-3">
  <div className="flex items-center justify-between">
    <span className="text-white/60">
      {updateStatus?.update_available ? 'Update available' : 'Up to date'}
    </span>
    <div className="flex gap-2">
      <Button
        variant="secondary"
        size="sm"
        onClick={handleCheckUpdate}
        disabled={checkingUpdate || updateActive}
      >
        {checkingUpdate ? 'Checking...' : 'Check now'}
      </Button>
      {updateStatus?.update_available && (
        <Button
          size="sm"
          onClick={handleApplyUpdate}
          disabled={updateActive}
        >
          {updateActive ? 'Updating...' : 'Trigger update'}
        </Button>
      )}
    </div>
  </div>

  {updateActive && updateProgress && (
    <div className="space-y-2 rounded-lg border border-white/10 bg-white/5 p-3">
      <div className="flex items-center justify-between text-xs">
        <span className="text-white/70">{updateProgress.message}</span>
        <span className="text-white/50">{updateProgress.progress}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-led-accent transition-all duration-500"
          style={{ width: `${updateProgress.progress}%` }}
        />
      </div>
      {updateProgress.error && (
        <p className="text-xs text-red-400">{updateProgress.error}</p>
      )}
    </div>
  )}
</div>
```

Make sure `bg-led-accent` is a valid class in the project, or replace with `bg-primary`.

---

## Task 6: Run Full Validation

- [ ] **Step 1: Backend tests**

```bash
/home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend/.venv/bin/python -m pytest backend/tests -v
```

Expected: all PASS.

- [ ] **Step 2: Frontend type check and tests**

```bash
cd /home/bchen/GitHub/adsledmatrix/adsbledmatrix/frontend
npx tsc --noEmit
npm test
```

Expected: type check clean, tests PASS.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: real update progress feedback in Settings

- POST /api/system/update now starts the systemd update service
- New GET /api/system/update-progress endpoint reads progress file
- Shell scripts write progress to data/.update_progress.json
- Settings UI shows human-readable status and progress bar"
```

---

## Spec Coverage Check

| User requirement | Task implementing it |
|------------------|----------------------|
| Replace confusing trigger-update message | Task 2, Task 5 |
| Trigger update does something useful | Task 2 |
| Real progress feedback / progress bar | Task 1, Task 3, Task 4, Task 5 |

## Placeholder Scan

- No TBD/TODO placeholders.
- All code blocks contain concrete content.
- File paths are exact.
