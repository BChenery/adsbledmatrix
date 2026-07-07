import json
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
