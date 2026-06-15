import asyncio
import logging
import math
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont
from app.config import settings
from app.services.geocalc import convert_distance, convert_altitude, convert_speed, format_heading
from app.services.route_service import route_service

logger = logging.getLogger(__name__)


@dataclass
class RenderContext:
    aircraft: Optional[Any] = None
    enriched: Optional[Dict[str, Any]] = None
    user_config: Optional[Any] = None
    is_idle: bool = False
    cycle_index: int = 0
    total_cycles: int = 1
    route: Optional[Any] = None
    all_routes: Optional[Dict[str, Any]] = None


class DisplayEngine:
    """Renders configured layouts to the LED matrix."""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._current_layout: Optional[Any] = None
        self._idle_layout: Optional[Any] = None
        self._framebuffer: Optional[Image.Image] = None
        self._font_cache: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}
        self._image_cache: Dict[str, Image.Image] = {}
        self.width = settings.led_matrix_cols * settings.led_matrix_chain
        self.height = settings.led_matrix_rows * settings.led_matrix_parallel
        self._matrix = None
        self._lock = threading.Lock()
        self._last_render = datetime.utcnow()
        self._cycle_index = 0
        self._cycle_time = datetime.utcnow()
        self._test_color: Optional[Tuple[int, int, int]] = None

        from hardware import create_matrix
        self._matrix = create_matrix(self.width, self.height)

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._render_loop())
        logger.info("Display engine started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Display engine stopped")

    def set_layout(self, layout: Optional[Any], idle_layout: Optional[Any] = None):
        self._current_layout = layout
        self._idle_layout = idle_layout

    async def _render_loop(self):
        while self._running:
            try:
                await self._render_frame()
                await asyncio.sleep(1 / 30)  # 30 FPS
            except Exception as e:
                logger.error(f"Render error: {e}")
                await asyncio.sleep(1)

    async def _render_frame(self):
        from app.services.adsb_receiver import receiver
        from app.services.aircraft_db import db
        from app.api.config import get_user_config_sync

        # Test pattern takes precedence over normal rendering
        if self._test_color is not None:
            img = Image.new("RGB", (self.width, self.height), self._test_color)
            self._output_to_matrix(img)
            return

        user_config = get_user_config_sync()

        # Determine what to display
        closest = receiver.get_closest(n=3)
        is_idle = len(closest) == 0

        if is_idle:
            layout = self._idle_layout or self._current_layout
            ctx = RenderContext(
                aircraft=None,
                enriched=None,
                user_config=user_config,
                is_idle=True,
            )
        else:
            layout = self._current_layout
            if not layout:
                return

            # Handle cycling
            cycle_interval = user_config.cycle_interval_sec if user_config else 5
            if (datetime.utcnow() - self._cycle_time).seconds >= cycle_interval:
                self._cycle_index = (self._cycle_index + 1) % max(1, len(closest))
                self._cycle_time = datetime.utcnow()

            mode = user_config.display_mode if user_config else "closest"
            if mode == "closest":
                idx = 0
            elif mode == "cycle3":
                idx = self._cycle_index % min(3, len(closest))
            else:
                idx = 0

            aircraft = closest[idx] if idx < len(closest) else closest[0]
            enriched = await db.enrich(aircraft.hex_code)
            route = await route_service.lookup(aircraft.callsign) if aircraft.callsign else None

            # Pre-fetch routes for all closest aircraft (used by aircraft_list)
            all_routes: Dict[str, Any] = {}
            for ac in closest:
                if ac.callsign:
                    r = await route_service.lookup(ac.callsign)
                    if r:
                        all_routes[ac.callsign] = r

            ctx = RenderContext(
                aircraft=aircraft,
                enriched=enriched,
                user_config=user_config,
                is_idle=False,
                cycle_index=idx,
                total_cycles=len(closest),
                route=route,
                all_routes=all_routes,
            )

        if layout:
            img = self._render_layout(layout, ctx)
            # Offload the matrix output to a thread so a slow/blocking panel
            # (or no panel connected) doesn't starve the asyncio event loop.
            await asyncio.to_thread(self._output_to_matrix, img)

    def _render_layout(self, layout: Any, ctx: RenderContext) -> Image.Image:
        img = Image.new("RGB", (layout.width, layout.height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        for element in sorted(layout.elements, key=lambda e: e.z_index):
            try:
                self._render_element(draw, img, element, ctx)
            except Exception as e:
                logger.debug(f"Element render error: {e}")

        # Scale to actual LED matrix size if different
        if (layout.width, layout.height) != (self.width, self.height):
            img = img.resize((self.width, self.height), Image.LANCZOS)

        return img

    def _render_element(self, draw: ImageDraw.Draw, img: Image.Image, element: Any, ctx: RenderContext):
        # Visibility check
        if element.show_if and not self._evaluate_condition(element.show_if, ctx):
            return

        x, y = element.x, element.y
        w = element.width or 100
        h = element.height or 20
        color = self._parse_color(element.color) or (255, 255, 255)
        bg_color = self._parse_color(element.bg_color)

        if bg_color:
            draw.rectangle([x, y, x + w, y + h], fill=bg_color)

        if element.element_type == "text":
            text = element.format_str or ""
            self._draw_text(draw, x, y, text, color, element.font_family, element.font_size)

        elif element.element_type == "data_field":
            text = self._resolve_data_field(element.data_field, element.format_str, ctx)
            self._draw_text(draw, x, y, text, color, element.font_family, element.font_size)

        elif element.element_type == "image":
            self._draw_image(img, x, y, w, h, element, ctx)

        elif element.element_type == "shape":
            self._draw_shape(draw, x, y, w, h, element, color)

        elif element.element_type == "heading_arrow":
            self._draw_heading_arrow(draw, x, y, w, h, ctx, color)

        elif element.element_type == "vertical_rate":
            self._draw_vertical_rate(draw, x, y, w, h, ctx, color)

        elif element.element_type == "distance_bar":
            self._draw_distance_bar(draw, x, y, w, h, ctx, color)

        elif element.element_type == "radar_blip":
            self._draw_radar_blip(draw, x, y, w, h, ctx, color)

        elif element.element_type == "aircraft_list":
            self._draw_aircraft_list(draw, x, y, w, h, element, ctx, color)

    def _draw_text(self, draw: ImageDraw.Draw, x: int, y: int, text: str, color: Tuple[int, int, int], font_family: Optional[str], font_size: Optional[int]):
        size = font_size or 12
        family = font_family or "default"
        key = (family, size)

        if key not in self._font_cache:
            try:
                # Try system fonts
                self._font_cache[key] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
            except Exception:
                self._font_cache[key] = ImageFont.load_default()

        font = self._font_cache[key]
        draw.text((x, y), str(text), fill=color, font=font)

    def _draw_image(self, img: Image.Image, x: int, y: int, w: int, h: int, element: Any, ctx: RenderContext):
        path = element.image_path
        if not path and ctx.enriched:
            icao = ctx.enriched.get("operator_icao")
            if icao:
                logo_path = settings.logos_dir / f"{icao}.png"
                if not logo_path.exists():
                    logo_path = settings.logos_dir / "UNKNOWN.png"
                path = str(logo_path)

        if not path:
            return

        try:
            if path not in self._image_cache:
                self._image_cache[path] = Image.open(path).convert("RGBA")
            logo = self._image_cache[path].copy()
            logo = logo.resize((w, h), Image.LANCZOS)
            img.paste(logo, (x, y), logo)
        except Exception:
            pass

    def _draw_shape(self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, element: Any, color: Tuple[int, int, int]):
        shape = element.extra.get("shape_type", "rectangle") if element.extra else "rectangle"
        if shape == "rectangle":
            draw.rectangle([x, y, x + w, y + h], outline=color)
        elif shape == "circle":
            draw.ellipse([x, y, x + w, y + h], outline=color)
        elif shape == "line":
            draw.line([x, y, x + w, y + h], fill=color, width=2)

    def _draw_heading_arrow(self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, ctx: RenderContext, color: Tuple[int, int, int]):
        heading = ctx.aircraft.heading if ctx.aircraft else None
        if heading is None:
            return

        cx, cy = x + w // 2, y + h // 2
        radius = min(w, h) // 2 - 2
        angle = math.radians(heading - 90)  # 0 is up

        # Arrow head
        tip = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
        left = (cx + (radius * 0.5) * math.cos(angle + 2.5), cy + (radius * 0.5) * math.sin(angle + 2.5))
        right = (cx + (radius * 0.5) * math.cos(angle - 2.5), cy + (radius * 0.5) * math.sin(angle - 2.5))

        draw.polygon([tip, left, right], fill=color)
        draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=color)

    def _draw_vertical_rate(self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, ctx: RenderContext, color: Tuple[int, int, int]):
        rate = ctx.aircraft.vertical_rate if ctx.aircraft else None
        if rate is None:
            text = "---"
        elif rate > 100:
            text = f"▲ {rate}"
        elif rate < -100:
            text = f"▼ {abs(rate)}"
        else:
            text = "→ level"
        self._draw_text(draw, x, y, text, color, None, h - 4)

    def _draw_distance_bar(self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, ctx: RenderContext, color: Tuple[int, int, int]):
        dist = ctx.aircraft.distance_km if ctx.aircraft else None
        if dist is None:
            return
        max_dist = 50.0  # km, scale max
        ratio = min(dist / max_dist, 1.0)
        bar_w = int(w * (1.0 - ratio))
        draw.rectangle([x, y, x + w, y + h], outline=(50, 50, 50))
        draw.rectangle([x, y, x + bar_w, y + h], fill=color)
        label = f"{dist:.1f} km"
        self._draw_text(draw, x, y + h + 2, label, color, None, 10)

    def _draw_radar_blip(self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, ctx: RenderContext, color: Tuple[int, int, int]):
        import random
        cx, cy = x + w // 2, y + h // 2
        radius = min(w, h) // 2
        # Draw concentric rings
        for r in range(radius, 0, -10):
            alpha = int(255 * (1 - r / radius))
            c = (color[0] * alpha // 255, color[1] * alpha // 255, color[2] * alpha // 255)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c)
        # Sweep line
        sweep_angle = (datetime.utcnow().second % 6) * 60
        angle = math.radians(sweep_angle)
        draw.line([cx, cy, cx + radius * math.cos(angle), cy + radius * math.sin(angle)], fill=color, width=2)

    def _draw_aircraft_list(self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, element: Any, ctx: RenderContext, color: Tuple[int, int, int]):
        from app.services.adsb_receiver import receiver

        extra = element.extra or {}
        max_rows = extra.get("max_rows", 5)
        columns = extra.get("columns", ["callsign", "origin", "destination"])
        row_height = extra.get("row_height", 24)
        show_header = extra.get("show_header", True)
        font_size = element.font_size or 12

        closest = receiver.get_closest(n=max_rows)
        if not closest:
            self._draw_text(draw, x, y, "No aircraft", color, None, font_size)
            return

        # Header
        row_y = y + 4
        if show_header:
            header_text = "  ".join(col.upper()[:8] for col in columns)
            self._draw_text(draw, x + 4, row_y, header_text, color, None, font_size)
            row_y += row_height
            # Separator line
            draw.line([x + 4, row_y - 4, x + w - 4, row_y - 4], fill=(50, 50, 50), width=1)

        # Rows
        for ac in closest[:max_rows]:
            values = {
                "hex_code": ac.hex_code,
                "callsign": ac.callsign or "---",
                "altitude": str(int(ac.altitude)) if ac.altitude is not None else "---",
                "ground_speed": str(int(ac.ground_speed)) if ac.ground_speed is not None else "---",
                "heading": format_heading(ac.heading),
                "distance": f"{ac.distance_km:.1f}" if ac.distance_km is not None else "---",
                "vertical_rate": str(ac.vertical_rate) if ac.vertical_rate is not None else "---",
                "squawk": ac.squawk or "---",
            }

            # Route data from pre-fetched all_routes
            route = (ctx.all_routes or {}).get(ac.callsign) if ac.callsign else None
            if route:
                values["route"] = f"{route.origin}-{route.destination}"
                values["origin"] = route.origin
                values["destination"] = route.destination
            else:
                values["route"] = "---"
                values["origin"] = "---"
                values["destination"] = "---"

            # Build row string
            row_parts = []
            for col in columns:
                val = values.get(col, "---")
                row_parts.append(str(val)[:10])
            row_text = "  ".join(row_parts)

            self._draw_text(draw, x + 4, row_y, row_text, color, None, font_size)
            row_y += row_height
            if row_y > y + h:
                break

    def _resolve_data_field(self, field: Optional[str], fmt: Optional[str], ctx: RenderContext) -> str:
        ac = ctx.aircraft
        enriched = ctx.enriched or {}
        config = ctx.user_config

        if not ac and not ctx.is_idle:
            return "---"

        values = {}
        if ac:
            unit_dist = config.distance_unit if config else "km"
            unit_alt = config.altitude_unit if config else "ft"
            unit_spd = config.speed_unit if config else "kts"

            values.update({
                "hex_code": ac.hex_code,
                "callsign": ac.callsign or "---",
                "altitude": f"{convert_altitude(ac.altitude, unit_alt):.0f}" if ac.altitude is not None else "---",
                "ground_speed": f"{convert_speed(ac.ground_speed, unit_spd):.0f}" if ac.ground_speed is not None else "---",
                "heading": format_heading(ac.heading),
                "distance": f"{convert_distance(ac.distance_km or 0, unit_dist):.1f}" if ac.distance_km is not None else "---",
                "vertical_rate": str(ac.vertical_rate) if ac.vertical_rate is not None else "---",
                "squawk": ac.squawk or "---",
                "messages": str(ac.messages),
                "last_seen": ac.last_seen.strftime("%H:%M:%S"),
            })

        values.update({
            "registration": enriched.get("registration") or "---",
            "manufacturer": enriched.get("manufacturer") or "---",
            "model": enriched.get("model") or "---",
            "type_code": enriched.get("type_code") or "---",
            "type_name": enriched.get("type_name") or "---",
            "operator": enriched.get("operator") or "---",
            "operator_icao": enriched.get("operator_icao") or "---",
            "cycle_index": str(ctx.cycle_index + 1),
            "total_cycles": str(ctx.total_cycles),
            "current_time": datetime.utcnow().strftime("%H:%M:%S"),
        })

        # Route data
        if ctx.route:
            values.update({
                "route": f"{ctx.route.origin}-{ctx.route.destination}",
                "origin": ctx.route.origin,
                "destination": ctx.route.destination,
            })
        else:
            values.update({"route": "---", "origin": "---", "destination": "---"})

        if fmt:
            try:
                return fmt.format(**values)
            except (KeyError, ValueError):
                return fmt
        return values.get(field, "---")

    def _evaluate_condition(self, condition: str, ctx: RenderContext) -> bool:
        if condition == "has_logo":
            icao = (ctx.enriched or {}).get("operator_icao")
            if icao:
                if (settings.logos_dir / f"{icao}.png").exists():
                    return True
            # Fallback logo is always available
            return (settings.logos_dir / "UNKNOWN.png").exists()
        if condition == "altitude>0":
            return (ctx.aircraft.altitude or 0) > 0 if ctx.aircraft else False
        if condition == "is_idle":
            return ctx.is_idle
        if condition == "not_idle":
            return not ctx.is_idle
        return True

    def _parse_color(self, color_str: Optional[str]) -> Optional[Tuple[int, int, int]]:
        if not color_str:
            return None
        color_str = color_str.lstrip("#")
        if len(color_str) == 6:
            return (
                int(color_str[0:2], 16),
                int(color_str[2:4], 16),
                int(color_str[4:6], 16),
            )
        return None

    def _output_to_matrix(self, img: Image.Image):
        with self._lock:
            self._framebuffer = img.copy()
            if self._matrix:
                self._matrix.SetImage(img)

    def is_hardware_mode(self) -> bool:
        return getattr(self._matrix, "is_hardware", False)

    def get_brightness(self) -> int:
        # Real matrix stores brightness on the object; mock ignores it
        if self.is_hardware_mode() and hasattr(self._matrix, "matrix") and self._matrix.matrix:
            return getattr(self._matrix.matrix, "brightness", settings.led_matrix_brightness)
        return settings.led_matrix_brightness

    def get_framebuffer(self) -> Optional[Image.Image]:
        with self._lock:
            return self._framebuffer.copy() if self._framebuffer else None

    async def run_test_pattern(self):
        """Flash red, green, blue on the LED matrix to verify hardware."""
        if not self.is_hardware_mode():
            logger.warning("Test pattern requested but not in hardware mode")
            return False
        logger.info("Running LED matrix test pattern")
        for color, name in [((255, 0, 0), "red"), ((0, 255, 0), "green"), ((0, 0, 255), "blue")]:
            self._test_color = color
            await asyncio.sleep(1)
        self._test_color = None
        logger.info("LED matrix test pattern complete")
        return True

    def get_diagnostics(self) -> Dict[str, Any]:
        """Return diagnostics about the LED matrix interface."""
        import os
        import getpass
        import grp

        spi_devices = [f for f in os.listdir("/dev") if f.startswith("spi")]
        gpio_access = os.access("/dev/gpiomem", os.R_OK | os.W_OK)
        if not gpio_access and os.path.exists("/dev/gpiochip0"):
            gpio_access = os.access("/dev/gpiochip0", os.R_OK | os.W_OK)

        user = getpass.getuser()
        groups = []
        try:
            for g in grp.getgrall():
                if user in g.gr_mem:
                    groups.append(g.gr_name)
        except Exception:
            pass

        return {
            "hardware_mode": self.is_hardware_mode(),
            "matrix_type": type(self._matrix).__name__,
            "width": self.width,
            "height": self.height,
            "brightness": self.get_brightness(),
            "hardware_mapping": settings.led_matrix_hardware_mapping,
            "rows": settings.led_matrix_rows,
            "cols": settings.led_matrix_cols,
            "chain": settings.led_matrix_chain,
            "parallel": settings.led_matrix_parallel,
            "spi_enabled": len(spi_devices) > 0,
            "spi_devices": spi_devices,
            "gpio_access": gpio_access,
            "user": user,
            "groups": groups,
        }


# Global singleton
engine = DisplayEngine()
