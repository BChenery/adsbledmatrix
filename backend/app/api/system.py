import logging
import platform
import subprocess
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter
from app.api.config import get_user_config_sync
from app.config import settings
from app.services.updater import updater
from app.services.update_progress import read_update_progress, write_update_progress
from app.services.changelog import changelog_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])


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


class UpdateStatus(BaseModel):
    current_version: str
    latest_version: str
    update_available: bool
    release_notes: str = ""
    published_at: str = ""


class UpdateProgressResponse(BaseModel):
    status: str
    progress: int
    message: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class ChangelogSectionModel(BaseModel):
    title: str
    items: list[str]


class ChangelogEntryModel(BaseModel):
    version: str
    date: Optional[str] = None
    sections: list[ChangelogSectionModel]


class ChangelogResponse(BaseModel):
    current_version: str
    entries: list[ChangelogEntryModel]


@router.get("/health")
async def health_check():
    from app.config import settings
    return {"status": "ok", "version": settings.version}


@router.get("/status", response_model=SystemStatus)
async def get_status():
    from app.services.adsb_receiver import receiver

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


@router.get("/update", response_model=UpdateStatus)
async def check_update():
    result = await updater.check_for_update()
    return UpdateStatus(**result)


@router.get("/changelog", response_model=ChangelogResponse)
async def get_changelog():
    """Return structured release notes from the local CHANGELOG.md (offline-friendly)."""
    return ChangelogResponse(**changelog_payload())


def _update_service_is_running() -> bool:
    """True when the oneshot update unit is active or still starting."""
    result = subprocess.run(
        ["systemctl", "is-active", "adsbledmatrix-update.service"],
        capture_output=True,
        text=True,
        check=False,
    )
    state = (result.stdout or "").strip()
    return state in {"active", "activating"}


def _start_update_service() -> subprocess.CompletedProcess:
    """Start the update oneshot. Prefer passwordless sudo (service runs as adsb)."""
    return subprocess.run(
        ["sudo", "-n", "systemctl", "start", "--no-block", "adsbledmatrix-update.service"],
        capture_output=True,
        text=True,
        check=False,
    )


@router.post("/update")
async def trigger_update():
    """Trigger the systemd update service to check and install updates in the background."""
    try:
        if _update_service_is_running():
            return {
                "status": "already_running",
                "message": "An update is already running. Check the progress below.",
            }

        # Seed progress immediately so the UI never shows a stale 100% from a prior run.
        from datetime import datetime, timezone

        started_at = datetime.now(timezone.utc).isoformat()
        write_update_progress(
            status="checking",
            progress=0,
            message="Starting update...",
            started_at=started_at,
        )

        # Manual trigger bypasses auto_update=false and rollout skip gates in the script.
        force_flag = settings.data_dir / ".force_update"
        force_flag.parent.mkdir(parents=True, exist_ok=True)
        force_flag.write_text(started_at)

        start_result = _start_update_service()
        if start_result.returncode != 0:
            err = (start_result.stderr or start_result.stdout or "systemctl start failed").strip()
            logger.error("Failed to start adsbledmatrix-update.service: %s", err)
            write_update_progress(
                status="failed",
                progress=0,
                message="Could not start update service.",
                started_at=started_at,
                error=err,
            )
            try:
                force_flag.unlink(missing_ok=True)
            except TypeError:
                if force_flag.exists():
                    force_flag.unlink()
            return {
                "status": "error",
                "message": f"Could not start update: {err}",
                "started_at": started_at,
            }

        return {
            "status": "started",
            "message": "Update started. Progress will appear below.",
            "started_at": started_at,
        }
    except Exception as e:
        logger.error(f"Failed to trigger update service: {e}")
        return {
            "status": "error",
            "message": f"Could not start update: {e}",
        }


@router.get("/update-progress", response_model=UpdateProgressResponse)
async def get_update_progress():
    progress = read_update_progress()
    return UpdateProgressResponse(**progress.model_dump())


@router.post("/restart")
async def restart_system():
    subprocess.Popen(["systemctl", "restart", "adsbledmatrix"])
    return {"message": "Restarting..."}


@router.post("/reboot")
async def reboot_system():
    subprocess.Popen(["bash", "-c", "sleep 2 && sudo reboot"])
    return {"message": "Rebooting the Pi..."}


@router.post("/shutdown")
async def shutdown_system():
    subprocess.Popen(["bash", "-c", "sleep 2 && sudo shutdown now"])
    return {"message": "Shutting down the Pi..."}


class WiFiApplyRequest(BaseModel):
    ssid: str
    password: str


@router.post("/wifi/apply")
async def apply_wifi(req: WiFiApplyRequest):
    """Save WiFi credentials and trigger a switch to home-network mode + reboot."""
    import subprocess
    subprocess.Popen([
        "sudo", "/opt/adsbledmatrix/venv/bin/python3",
        "/opt/adsbledmatrix/scripts/wifi_manager.py",
        "connect-home", "--ssid", req.ssid, "--password", req.password,
    ])
    # Reboot after a short delay so the HTTP response can be sent.
    subprocess.Popen(["bash", "-c", "sleep 5 && sudo reboot"])
    return {"message": "WiFi configured. The device will reboot and connect to your network."}
