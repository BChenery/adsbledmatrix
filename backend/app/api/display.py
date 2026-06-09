import io
import logging
from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse
from app.services.display_engine import engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/display", tags=["display"])


@router.get("/status")
async def display_status():
    """Return LED matrix hardware status."""
    return {
        "hardware_mode": engine.is_hardware_mode(),
        "width": engine.width,
        "height": engine.height,
        "brightness": engine.get_brightness(),
        "mock": not engine.is_hardware_mode(),
    }


@router.get("/diagnostics")
async def display_diagnostics():
    """Return detailed LED matrix interface diagnostics."""
    return engine.get_diagnostics()


@router.post("/test")
async def display_test():
    """Run a red/green/blue test pattern on the LED matrix."""
    success = await engine.run_test_pattern()
    if not success:
        return {"success": False, "message": "Not in hardware mode — test pattern skipped"}
    return {"success": True, "message": "Test pattern running (red → green → blue)"}


@router.get("/preview")
async def display_preview():
    """Return the current LED matrix framebuffer as a PNG image."""
    img = engine.get_framebuffer()
    if img is None:
        return Response(status_code=404, content="No framebuffer available yet")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")
