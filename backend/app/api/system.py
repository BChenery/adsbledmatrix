import platform
from pydantic import BaseModel
from fastapi import APIRouter
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
    return SystemStatus(
        app_name=settings.app_name,
        version=settings.version,
        platform=platform.system(),
        python_version=platform.python_version(),
        debug=settings.debug,
        led_matrix_enabled=settings.led_matrix_brightness > 0,
        readsb_host=settings.readsb_host,
        readsb_port=settings.readsb_port,
    )


@router.get("/update", response_model=UpdateStatus)
async def check_update():
    result = await updater.check_for_update()
    return UpdateStatus(**result)


@router.post("/update")
async def apply_update():
    result = await updater.check_for_update()
    if not result.get("update_available"):
        return {"message": "No update available"}

    success = await updater.apply_update(result["download_url"])
    if success:
        return {"message": "Update applied. Please restart the device."}
    return {"message": "Update failed. Check logs for details."}


@router.post("/restart")
async def restart_system():
    import subprocess
    subprocess.Popen(["systemctl", "restart", "adsbledmatrix"])
    return {"message": "Restarting..."}


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
