import platform
from pydantic import BaseModel
from fastapi import APIRouter
from app.api.config import get_user_config_sync
from app.config import settings
from app.services.updater import updater

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
    """Manual update is handled by the root systemd update service.

    This endpoint exists for backwards compatibility but does not apply
    updates from the app process (which lacks privileges after the LED
    matrix drops to the adsb user).
    """
    return {"status": "manual updates are applied by systemd; check status with GET /api/system/update"}


@router.post("/restart")
async def restart_system():
    import subprocess
    subprocess.Popen(["systemctl", "restart", "adsbledmatrix"])
    return {"message": "Restarting..."}


@router.post("/reboot")
async def reboot_system():
    import subprocess
    subprocess.Popen(["bash", "-c", "sleep 2 && sudo reboot"])
    return {"message": "Rebooting the Pi..."}


@router.post("/shutdown")
async def shutdown_system():
    import subprocess
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
