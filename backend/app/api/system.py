import logging
import platform
import subprocess
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter
from app.api.config import get_user_config_sync
from app.config import settings
from app.services.updater import updater
from app.services.update_progress import read_update_progress

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
