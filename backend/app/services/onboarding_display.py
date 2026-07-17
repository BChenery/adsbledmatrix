"""Setup instructions shown on the LED matrix while onboarding is incomplete.

Reuses the designer preview slot: ``engine.set_preview_layout`` takes priority
over idle and aircraft layouts, so no display-engine changes are needed. The
screen tells the user the hotspot name, password, and setup URL — the one
piece of information they otherwise only get from the README.
"""

import logging
import os
from types import SimpleNamespace
from typing import Any, Optional

logger = logging.getLogger(__name__)

AP_SSID_PREFIX = os.environ.get("ADSB_AP_SSID_PREFIX", "ADSB-Display")
AP_PASSWORD = os.environ.get("ADSB_AP_PASSWORD", "adsbsetup")
AP_IP = "192.168.4.1"

SETUP_LAYOUT_NAME = "onboarding-setup"
MATRIX_W = 256
MATRIX_H = 128

# Matches the design system palette in scripts/generate_default_layouts.py
ACCENT = "#ffb347"
PRIMARY = "#00d4ff"
SECONDARY = "#a0aec0"


def get_ap_ssid() -> str:
    """Mirror scripts/wifi_manager.py: hotspot SSID = prefix + last 4 MAC hex."""
    iface = "wlan0"
    try:
        for name in sorted(os.listdir("/sys/class/net")):
            if name.startswith("wl"):
                iface = name
                break
    except OSError:
        pass
    try:
        with open(f"/sys/class/net/{iface}/address", encoding="utf-8") as f:
            suffix = f.read().strip().replace(":", "")[-4:].upper()
    except OSError:
        suffix = "0000"
    return f"{AP_SSID_PREFIX}-{suffix}"


def _text(x: int, y: int, content: str, *, font_size: int = 16, color: str = SECONDARY):
    # Same attribute set the engine gets from layout_from_apply_request.
    return SimpleNamespace(
        element_type="text",
        x=x,
        y=y,
        width=MATRIX_W - 2 * x,
        height=font_size + 4,
        z_index=0,
        font_family=None,
        font_size=font_size,
        color=color,
        bg_color=None,
        format_str=content,
        data_field=None,
        image_path=None,
        image_url=None,
        show_if=None,
        extra=None,
        range_km=20,
        ring_color="#333333",
        dot_color="#ff0000",
        user_dot_color="#00ff00",
        show_rings=True,
        show_ticks=True,
        use_plane_symbol=False,
    )


def build_setup_layout(ssid: Optional[str] = None) -> Any:
    """Duck-typed layout the display engine can render during onboarding."""
    ssid = ssid or get_ap_ssid()
    elements = [
        _text(4, 10, "SETUP REQUIRED", font_size=24, color=ACCENT),
        _text(4, 46, f"WiFi: {ssid}", font_size=16, color=PRIMARY),
        _text(4, 68, f"Pass: {AP_PASSWORD}", font_size=16, color=PRIMARY),
        _text(4, 96, f"Open: http://{AP_IP}", font_size=16, color=SECONDARY),
    ]
    return SimpleNamespace(
        name=SETUP_LAYOUT_NAME,
        width=MATRIX_W,
        height=MATRIX_H,
        elements=elements,
    )


def show_setup_screen() -> None:
    """Force setup instructions onto the matrix (no-op if engine unavailable)."""
    try:
        from app.services.display_engine import engine

        engine.set_preview_layout(build_setup_layout())
        logger.info("Onboarding setup screen shown on matrix")
    except Exception as exc:
        logger.warning("Could not show onboarding setup screen: %s", exc)


def clear_setup_screen() -> None:
    """Release the preview slot, but only if we still own it.

    The onboarding wizard may have pushed a layout preview of its own; that
    one is left alone (the upcoming reboot clears it anyway).
    """
    try:
        from app.services.display_engine import engine

        preview = engine.get_preview_layout()
        if preview is not None and getattr(preview, "name", None) == SETUP_LAYOUT_NAME:
            engine.set_preview_layout(None)
            logger.info("Onboarding setup screen cleared")
    except Exception as exc:
        logger.warning("Could not clear onboarding setup screen: %s", exc)
