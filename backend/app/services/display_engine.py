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
from app.services.logo_manager import logo_manager
from app.services.route_service import route_service
from hardware.led_config import calculate_matrix_dimensions

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
        try:
            self.width, self.height = calculate_matrix_dimensions(
                settings.led_matrix_rows,
                settings.led_matrix_cols,
                settings.led_matrix_chain,
                settings.led_matrix_parallel,
                settings.led_matrix_pixel_mapper,
            )
        except ValueError as exc:
            logger.warning(
                "Invalid LED matrix dimension config (%s). Falling back to raw chain size.",
                exc,
            )
            self.width = settings.led_matrix_cols * settings.led_matrix_chain
            self.height = settings.led_matrix_rows * settings.led_matrix_parallel
        self._matrix = None
        self._lock = threading.Lock()
        self._last_render = datetime.utcnow()
        self._cycle_index = 0
        self._cycle_time = datetime.utcnow()
        self._test_color: Optional[Tuple[int, int, int]] = None
        self._brightness = settings.led_matrix_brightness
        self._night_mode_active = False

        from hardware import create_matrix
        self._matrix = create_matrix(self.width, self.height)
        self.width = getattr(self._matrix, "width", self.width)
        self.height = getattr(self._matrix, "height", self.height)

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

        # Night mode handling: dim or sleep the display during configured hours.
        if self._handle_night_mode(user_config):
            return

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
        show_if = getattr(element, "show_if", None)
        if show_if and not self._evaluate_condition(show_if, ctx):
            return

        x, y = element.x, element.y
        w = getattr(element, "width", None) or 100
        h = getattr(element, "height", None) or 20
        color = self._parse_color(getattr(element, "color", None)) or (255, 255, 255)
        bg_color = self._parse_color(getattr(element, "bg_color", None))

        if bg_color:
            draw.rectangle([x, y, x + w, y + h], fill=bg_color)

        element_type = element.element_type
        font_family = getattr(element, "font_family", None)
        font_size = getattr(element, "font_size", None)

        if element_type == "text":
            text = getattr(element, "format_str", None) or ""
            self._draw_text(draw, x, y, w, text, color, font_family, font_size, height=h)

        elif element_type == "data_field":
            text = self._resolve_data_field(getattr(element, "data_field", None), getattr(element, "format_str", None), ctx)
            self._draw_text(draw, x, y, w, text, color, font_family, font_size, height=h)

        elif element_type == "image":
            self._draw_image(img, x, y, w, h, element, ctx)

        elif element_type == "shape":
            self._draw_shape(draw, x, y, w, h, element, color)

        elif element_type == "heading_arrow":
            self._draw_heading_arrow(draw, x, y, w, h, ctx, color)

        elif element_type == "vertical_rate":
            self._draw_vertical_rate(draw, x, y, w, h, ctx, color)

        elif element_type == "distance_bar":
            self._draw_distance_bar(draw, x, y, w, h, ctx, color)

        elif element_type == "radar":
            self._draw_radar(draw, img, element, ctx)

        elif element_type == "radar_blip":
            self._draw_radar_blip(draw, x, y, w, h, ctx, color)

        elif element_type == "aircraft_list":
            self._draw_aircraft_list(draw, x, y, w, h, element, ctx, color)

    def _draw_text(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        width: int,
        text: str,
        color: Tuple[int, int, int],
        font_family: Optional[str],
        font_size: Optional[int],
        align: str = "center",
        height: Optional[int] = None,
    ):
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
        text = str(text)
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        if align == "center":
            draw_x = x + max(0, (width - text_width) // 2)
        elif align == "right":
            draw_x = x + max(0, width - text_width)
        else:
            draw_x = x

        # Vertically centre the glyph bounding box inside the declared box so
        # cap-height sits near the top and descenders do not spill out.
        draw_y = y + max(0, (size - text_height) // 2)

        # Determine whether the text would spill below the declared element box.
        overflow_bottom = 0
        if height and height > 0:
            overflow_bottom = max(0, (draw_y - y) + bbox[3] - height)

        # Render text into a temporary grayscale buffer so we can threshold the
        # anti-aliased edges.  TrueType fonts can apply subpixel LCD rendering
        # when drawn to an RGB(A) surface, which tints the edges red or blue.
        # Drawing to a grayscale surface forces neutral greyscale anti-aliasing,
        # and thresholding converts edges to fully opaque or fully transparent
        # pixels.  The result is pasted as a solid-colour mask, eliminating
        # colour fringing on low-resolution LED matrices.
        render_w = max(text_width, width)
        render_h = height if height and height > 0 else text_height + 2
        tmp = Image.new("L", (render_w, render_h), 0)
        tmp_draw = ImageDraw.Draw(tmp)
        # Long text is left-aligned so the start of the value remains readable;
        # short text honours the horizontal alignment inside the temp buffer.
        offset_x = 0 if text_width > width else max(0, draw_x - x)
        tmp_draw.text((offset_x, draw_y - y), text, fill=255, font=font)

        # Threshold anti-aliased edges to solid pixels.
        mask = tmp.point(lambda p: 255 if p > 128 else 0)

        # Build a solid-colour image and paste it through the thresholded mask.
        solid = Image.new("RGB", (render_w, render_h), color)
        output = Image.new("RGB", (width, render_h), (0, 0, 0))
        output.paste(solid, (0, 0), mask)
        draw._image.paste(output, (x, y), mask.crop((0, 0, width, render_h)))

    def _draw_image(self, img: Image.Image, x: int, y: int, w: int, h: int, element: Any, ctx: RenderContext):
        path = element.image_path
        if not path and ctx.enriched:
            icao = ctx.enriched.get("operator_icao")
            callsign = ctx.aircraft.callsign if ctx.aircraft else None
            registration = ctx.enriched.get("registration")
            logo_path = logo_manager.logo_path_for_aircraft(icao, callsign, registration)
            if logo_path and logo_path.exists():
                path = str(logo_path)
            else:
                # No ICAO known for this aircraft — fall back to the unknown logo
                # rather than drawing nothing.
                unknown_path = settings.logos_dir / "UNKNOWN.png"
                if unknown_path.exists():
                    path = str(unknown_path)

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
        self._draw_text(draw, x, y, w, text, color, None, h - 4, height=h)

    def _draw_distance_bar(self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, ctx: RenderContext, color: Tuple[int, int, int]):
        dist = ctx.aircraft.distance_km if ctx.aircraft else None
        if dist is None:
            return
        max_dist = 50.0  # km, scale max
        ratio = min(dist / max_dist, 1.0)
        bar_w = int(w * (1.0 - ratio))
        draw.rectangle([x, y, x + w, y + h], outline=(50, 50, 50))
        draw.rectangle([x, y, x + bar_w, y + h], fill=color)
        # The distance value is rendered by a separate data_field element in the
        # redesigned layouts; do not draw a label here to avoid clipping the margin.

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
            self._draw_text(draw, x, y, w, "No aircraft", color, None, font_size, align="left", height=h)
            return

        # Header
        row_y = y + 4
        if show_header:
            header_text = "  ".join(col.upper()[:8] for col in columns)
            self._draw_text(draw, x + 4, row_y, w - 8, header_text, color, None, font_size, align="left", height=row_height)
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

            self._draw_text(draw, x + 4, row_y, w - 8, row_text, color, None, font_size, align="left", height=row_height)
            row_y += row_height
            if row_y > y + h:
                break

    def _rotate_point(self, px: float, py: float, cx: float, cy: float, angle_deg: float) -> Tuple[float, float]:
        angle = math.radians(angle_deg)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        rx = cx + (px - cx) * cos_a - (py - cy) * sin_a
        ry = cy + (px - cx) * sin_a + (py - cy) * cos_a
        return rx, ry

    def _draw_radar(self, draw: ImageDraw.Draw, img: Image.Image, element: Any, ctx: RenderContext):
        x, y = element.x, element.y
        w = element.width or 100
        h = element.height or 100
        ring_color = self._parse_color(element.ring_color) or (50, 50, 50)
        dot_color = self._parse_color(element.dot_color) or (255, 0, 0)
        user_color = self._parse_color(element.user_dot_color) or (0, 255, 0)
        bg_color = self._parse_color(element.bg_color)

        if bg_color:
            draw.rectangle([x, y, x + w, y + h], fill=bg_color)

        # Keep the radar circular inside the bounding box
        cx = x + w // 2
        cy = y + h // 2
        radius = min(w, h) // 2 - 2
        range_km = getattr(element, "range_km", 20) or 20

        # Outer circle
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=ring_color)

        # Range rings
        if getattr(element, 'show_rings', True):
            for step in (0.25, 0.5, 0.75):
                r = int(radius * step)
                if r > 0:
                    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ring_color)

        # N/E/S/W tick marks
        if getattr(element, 'show_ticks', True):
            tick_len = max(3, radius // 10)
            for bearing_deg in (0, 90, 180, 270):
                angle = math.radians(bearing_deg - 90)
                inner_r = radius - tick_len
                outer_r = radius
                x1 = cx + inner_r * math.cos(angle)
                y1 = cy + inner_r * math.sin(angle)
                x2 = cx + outer_r * math.cos(angle)
                y2 = cy + outer_r * math.sin(angle)
                draw.line([(x1, y1), (x2, y2)], fill=ring_color, width=1)

        # Centre user dot
        draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=user_color)

        # Aircraft marker
        ac = ctx.aircraft
        if ac and ac.distance_km is not None and ac.bearing is not None:
            ratio = min(ac.distance_km / range_km, 1.0)
            angle = math.radians(ac.bearing - 90)
            dot_x = cx + radius * ratio * math.cos(angle)
            dot_y = cy + radius * ratio * math.sin(angle)

            use_plane = getattr(element, "use_plane_symbol", False)
            heading = getattr(ac, 'heading', None)

            if use_plane and heading is not None:
                # Simple plane silhouette pointing up (0° heading = North)
                plane = [
                    (0, -4),
                    (-3, 2),
                    (-1, 1),
                    (0, 3),
                    (1, 1),
                    (3, 2),
                ]
                rotated = [self._rotate_point(dot_x + px, dot_y + py, dot_x, dot_y, heading) for px, py in plane]
                draw.polygon(rotated, fill=dot_color)
            else:
                draw.ellipse([dot_x - 3, dot_y - 3, dot_x + 3, dot_y + 3], fill=dot_color)

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
            callsign = ctx.aircraft.callsign if ctx.aircraft else None
            registration = (ctx.enriched or {}).get("registration")
            logo_path = logo_manager.logo_path_for_aircraft(icao, callsign, registration)
            if logo_path and logo_path.exists():
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

    def _is_in_time_window(self, start: Optional[str], end: Optional[str]) -> bool:
        """Return True if the current local time falls within the HH:MM window."""
        if not start or not end:
            return False
        try:
            now = datetime.now().time()
            start_time = datetime.strptime(start, "%H:%M").time()
            end_time = datetime.strptime(end, "%H:%M").time()
        except ValueError:
            return False
        if start_time < end_time:
            return start_time <= now < end_time
        # Interval wraps past midnight (e.g. 22:00 -> 06:00).
        return now >= start_time or now < end_time

    def _apply_matrix_brightness(self, brightness: int):
        """Apply a brightness value directly to the matrix hardware."""
        if self._matrix and hasattr(self._matrix, "set_brightness"):
            self._matrix.set_brightness(max(0, min(100, brightness)))

    def _handle_night_mode(self, config: Optional[Any]) -> bool:
        """Apply sleep or dim windows. Returns True when rendering should be skipped."""
        in_sleep_window = bool(
            config and config.sleep_mode and self._is_in_time_window(config.sleep_mode_start, config.sleep_mode_end)
        )
        in_dim_window = bool(
            config and config.night_mode and self._is_in_time_window(config.night_mode_start, config.night_mode_end)
        )

        if in_sleep_window:
            # Sleep: blank the matrix and skip rendering entirely.
            if not self._night_mode_active:
                logger.info("Sleep window active — turning display off")
                self._night_mode_active = True
            if self._matrix:
                self._matrix.clear()
            self._framebuffer = None
            return True

        if in_dim_window:
            # Dim: drop to 20% of the configured brightness (min 5%).
            night_brightness = max(5, int(self._brightness * 0.2))
            if not self._night_mode_active:
                logger.info(f"Night mode dim active — brightness {self._brightness} -> {night_brightness}")
                self._night_mode_active = True
                self._apply_matrix_brightness(night_brightness)
        else:
            if self._night_mode_active:
                logger.info(f"Night mode ended — restoring brightness {self._brightness}")
                self._night_mode_active = False
                self._apply_matrix_brightness(self._brightness)
        return False

    def _output_to_matrix(self, img: Image.Image):
        with self._lock:
            self._framebuffer = img.copy()
            if self._matrix:
                self._matrix.SetImage(img)

    def is_hardware_mode(self) -> bool:
        return getattr(self._matrix, "is_hardware", False)

    def set_brightness(self, brightness: int):
        """Set the user's target brightness.  During night mode the matrix stays
        dimmed until the period ends, but the target is updated so the correct
        level is restored afterwards."""
        brightness = max(0, min(100, brightness))
        self._brightness = brightness
        if not self._night_mode_active:
            self._apply_matrix_brightness(brightness)

    def get_brightness(self) -> int:
        return self._brightness

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
            "pixel_mapper": settings.led_matrix_pixel_mapper,
            "row_address_type": settings.led_matrix_row_address_type,
            "multiplexing": settings.led_matrix_multiplexing,
            "panel_type": settings.led_matrix_panel_type,
            "pwm_bits": settings.led_matrix_pwm_bits,
            "gpio_slowdown": settings.led_matrix_gpio_slowdown,
            "flip_vertical": settings.led_matrix_flip_vertical,
            "rgb_sequence": settings.led_matrix_rgb_sequence,
            "spi_enabled": len(spi_devices) > 0,
            "spi_devices": spi_devices,
            "gpio_access": gpio_access,
            "user": user,
            "groups": groups,
        }


# Global singleton
engine = DisplayEngine()
