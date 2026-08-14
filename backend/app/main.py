import logging
import os
import subprocess
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from app.config import settings
from app.lifespan import lifespan
from app.api import config, layouts, aircraft, websocket, system, display

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes (must be before static files)
app.include_router(config.router)
app.include_router(layouts.router)
app.include_router(aircraft.router)
app.include_router(websocket.router)
app.include_router(system.router)
app.include_router(display.router)


@app.get("/api/health")
async def api_health():
    """Compatibility health endpoint used by install/update scripts."""
    return {"status": "ok", "version": settings.version}


@app.get("/health")
async def root_health():
    """Short health alias for external probes."""
    return {"status": "ok", "version": settings.version}


def _is_ap_mode():
    """Detect whether the device is currently acting as a WiFi access point."""
    try:
        result = subprocess.run(
            ["nmcli", "-g", "NAME", "connection", "show", "--active"],
            capture_output=True, text=True
        )
        if "adsb-hotspot" in result.stdout:
            return True
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "hostapd"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass
    return False


# Captive portal detection endpoints — only active in AP mode so they don't
# interfere when the Pi is connected to the customer's home WiFi.
if _is_ap_mode():
    @app.get("/hotspot-detect.html")
    async def apple_captive():
        return RedirectResponse(url="http://192.168.4.1/", status_code=302)

    @app.get("/library/test/success.html")
    async def apple_captive_old():
        return RedirectResponse(url="http://192.168.4.1/", status_code=302)

    @app.get("/generate_204")
    async def android_captive():
        return RedirectResponse(url="http://192.168.4.1/", status_code=302)

    @app.get("/connecttest.txt")
    async def ms_captive():
        return RedirectResponse(url="http://192.168.4.1/", status_code=302)

    @app.get("/ncsi.txt")
    async def ms_captive_old():
        return RedirectResponse(url="http://192.168.4.1/", status_code=302)


# Static files (React frontend build). Do not mount StaticFiles at "/":
# Starlette Mount("/") also matches websocket scopes and can steal /ws/aircraft.
static_dir = os.path.join(os.path.dirname(__file__), "static")
_static_root = os.path.abspath(static_dir)
_assets_dir = os.path.join(_static_root, "assets")
if os.path.isdir(_assets_dir):
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """Serve built files, then index.html so React Router works."""
    if full_path:
        candidate = os.path.abspath(os.path.join(_static_root, full_path))
        if candidate.startswith(_static_root + os.sep) and os.path.isfile(candidate):
            return FileResponse(candidate)
    return FileResponse(os.path.join(_static_root, "index.html"))
