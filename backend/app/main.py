import logging
import os
import subprocess
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
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


class SPAStaticFiles(StaticFiles):
    """Serve index.html for any missing path so React Router works."""
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


# Static files (React frontend build) - must be LAST
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="static")
