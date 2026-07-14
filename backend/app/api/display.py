import io
import logging
from types import SimpleNamespace
from typing import Any, List, Optional

from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.display_engine import engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/display", tags=["display"])


class ApplyElement(BaseModel):
    element_type: str
    x: int
    y: int
    width: Optional[int] = None
    height: Optional[int] = None
    z_index: int = 0
    font_family: Optional[str] = None
    font_size: Optional[int] = None
    color: Optional[str] = None
    bg_color: Optional[str] = None
    format_str: Optional[str] = None
    data_field: Optional[str] = None
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    show_if: Optional[str] = None
    extra: Optional[dict] = None
    range_km: Optional[int] = 20
    ring_color: Optional[str] = "#333333"
    dot_color: Optional[str] = "#ff0000"
    user_dot_color: Optional[str] = "#00ff00"
    show_rings: Optional[bool] = True
    show_ticks: Optional[bool] = True
    use_plane_symbol: Optional[bool] = False


class ApplyLayoutRequest(BaseModel):
    """Designer draft pushed to the matrix without persisting to the DB."""

    name: Optional[str] = None
    width: int = Field(default=256, ge=1)
    height: int = Field(default=128, ge=1)
    elements: List[ApplyElement] = Field(default_factory=list)


def layout_from_apply_request(body: ApplyLayoutRequest) -> Any:
    """Build a duck-typed layout object the display engine can render."""
    elements = [SimpleNamespace(**elem.model_dump()) for elem in body.elements]
    return SimpleNamespace(
        name=body.name or "preview",
        width=body.width,
        height=body.height,
        elements=elements,
    )


@router.get("/status")
async def display_status():
    """Return LED matrix hardware status."""
    return {
        "hardware_mode": engine.is_hardware_mode(),
        "width": engine.width,
        "height": engine.height,
        "brightness": engine.get_brightness(),
        "mock": not engine.is_hardware_mode(),
        "preview_active": engine.get_preview_layout() is not None,
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


@router.post("/apply-layout")
async def apply_layout(body: ApplyLayoutRequest):
    """Push a designer draft onto the LED matrix without writing the DB."""
    layout = layout_from_apply_request(body)
    engine.set_preview_layout(layout)
    logger.info(
        "Preview layout applied (%s×%s, %d elements)",
        layout.width,
        layout.height,
        len(layout.elements),
    )
    return {
        "success": True,
        "message": "Layout applied to display (not saved)",
        "preview_active": True,
        "element_count": len(layout.elements),
    }


@router.post("/clear-apply")
async def clear_apply():
    """Clear the designer preview override so saved layouts drive the matrix again."""
    engine.set_preview_layout(None)
    logger.info("Preview layout cleared")
    return {"success": True, "message": "Preview cleared", "preview_active": False}


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
