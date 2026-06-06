import io
import logging
from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse
from app.services.display_engine import engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/display", tags=["display"])


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
