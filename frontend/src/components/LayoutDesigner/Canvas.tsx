import { useRef, useEffect, useState, useCallback } from 'react';
import { Layout, LayoutElement } from '@/types/layout';
import { Aircraft } from '@/types/aircraft';
import { getAircraftDisplayValue } from '@/lib/layoutDisplay';

function rotatePoint(px: number, py: number, cx: number, cy: number, angleDeg: number): [number, number] {
  const angle = (angleDeg * Math.PI) / 180;
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return [
    cx + (px - cx) * cos - (py - cy) * sin,
    cy + (px - cx) * sin + (py - cy) * cos,
  ];
}

interface CanvasProps {
  layout: Layout;
  selectedElement: LayoutElement | null;
  onSelectElement: (el: LayoutElement | null) => void;
  onUpdateElement: (el: LayoutElement) => void;
  aircraft?: Aircraft[];
  zoom?: number;
  flipVertical?: boolean;
}


export default function Canvas({ layout, selectedElement, onSelectElement, onUpdateElement, aircraft = [], zoom = 1, flipVertical = false }: CanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const logoCacheRef = useRef<Record<string, HTMLImageElement>>({});
  const [dragging, setDragging] = useState<{ el: LayoutElement; offsetX: number; offsetY: number } | null>(null);
  const [resizing, setResizing] = useState<{ el: LayoutElement; corner: string } | null>(null);

  const getDisplayValue = useCallback((el: LayoutElement): string => {
    return getAircraftDisplayValue(aircraft[0], el);
  }, [aircraft]);

  const drawRef = useRef<() => void>(() => {});

  const loadLogo = useCallback((icao: string) => {
    const code = icao.toUpperCase();
    const cached = logoCacheRef.current[code];
    if (cached) return;
    const img = new Image();
    img.src = `/api/aircraft/logo/${code}`;
    img.onload = () => {
      logoCacheRef.current[code] = img;
      drawRef.current();
    };
    logoCacheRef.current[code] = img;
  }, []);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = layout.width;
    canvas.height = layout.height;

    // Background
    ctx.fillStyle = '#0a0a0a';
    ctx.fillRect(0, 0, layout.width, layout.height);

    // Grid
    ctx.strokeStyle = '#1a1a2e';
    ctx.lineWidth = 1;
    for (let x = 0; x <= layout.width; x += 16) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, layout.height);
      ctx.stroke();
    }
    for (let y = 0; y <= layout.height; y += 16) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(layout.width, y);
      ctx.stroke();
    }

    // Elements
    (layout.elements || []).forEach((el) => {
      const isSelected = el === selectedElement;
      const x = el.x;
      const y = el.y;
      const w = el.width || 50;
      const h = el.height || 20;

      // Background
      if (el.bg_color) {
        ctx.fillStyle = el.bg_color;
        ctx.fillRect(x, y, w, h);
      }

      // Content preview
      ctx.fillStyle = el.color || '#ffffff';
      ctx.font = `${el.font_size || 12}px monospace`;
      ctx.textBaseline = 'top';

      let text = '';
      if (el.element_type === 'text') text = el.format_str || 'Text';
      else if (el.element_type === 'data_field') text = getDisplayValue(el) || el.format_str || `{${el.data_field}}`;
      else if (el.element_type === 'vertical_rate') text = getDisplayValue(el) || '▲ 1200';
      else if (el.element_type === 'distance_bar') text = getDisplayValue(el) || '|||||';
      else if (el.element_type === 'radar_blip') text = '◎';
      else if (el.element_type === 'image') {
        const icao = aircraft[0]?.operator_icao;
        let drewLogo = false;
        if (icao) {
          const code = icao.toUpperCase();
          const logo = logoCacheRef.current[code];
          if (logo?.complete && logo.naturalWidth > 0) {
            ctx.drawImage(logo, x, y, w, h);
            drewLogo = true;
          } else {
            loadLogo(icao);
          }
        }
        if (!drewLogo) {
          text = icao ? `[${icao}]` : '[IMG]';
        }
      }
      else if (el.element_type === 'shape') text = '';
      else if (el.element_type === 'aircraft_list') {
        // Handled separately below
      }

      if (text) {
        // Match the LED engine: hard-clip to the element box. Long text is
        // left-aligned and cropped (not horizontally squeezed via maxWidth).
        const fontSize = el.font_size || 12;
        const metrics = ctx.measureText(text);
        const textWidth = metrics.width;
        const textX =
          textWidth > w ? x : x + Math.max(0, (w - textWidth) / 2);
        const textHeight =
          (metrics.actualBoundingBoxAscent || 0) +
            (metrics.actualBoundingBoxDescent || 0) || fontSize;
        const textY = y + Math.max(0, (fontSize - textHeight) / 2);

        ctx.save();
        ctx.beginPath();
        ctx.rect(x, y, w, h);
        ctx.clip();
        ctx.fillText(text, textX, textY);
        ctx.restore();
      }

      // Shape preview
      if (el.element_type === 'shape') {
        ctx.strokeStyle = el.color || '#ffffff';
        ctx.strokeRect(x, y, w, h);
      }

      // Heading arrow: match LED engine — filled triangle rotated by aircraft
      // heading, sized to the element box (min(width, height)).
      if (el.element_type === 'heading_arrow') {
        const ac = aircraft[0];
        // Preview default north when no live heading is available
        const heading =
          ac?.heading !== undefined && ac?.heading !== null
            ? Number(ac.heading)
            : 0;
        const cx = x + w / 2;
        const cy = y + h / 2;
        const radius = Math.max(2, Math.min(w, h) / 2 - 2);
        // 0° is up (north), same convention as display_engine._draw_heading_arrow
        const angle = ((heading - 90) * Math.PI) / 180;
        const tipX = cx + radius * Math.cos(angle);
        const tipY = cy + radius * Math.sin(angle);
        const leftX = cx + radius * 0.5 * Math.cos(angle + 2.5);
        const leftY = cy + radius * 0.5 * Math.sin(angle + 2.5);
        const rightX = cx + radius * 0.5 * Math.cos(angle - 2.5);
        const rightY = cy + radius * 0.5 * Math.sin(angle - 2.5);
        const dotR = Math.max(1, Math.min(2, radius * 0.15));

        ctx.fillStyle = el.color || '#00ff88';
        ctx.beginPath();
        ctx.moveTo(tipX, tipY);
        ctx.lineTo(leftX, leftY);
        ctx.lineTo(rightX, rightY);
        ctx.closePath();
        ctx.fill();
        ctx.beginPath();
        ctx.arc(cx, cy, dotR, 0, Math.PI * 2);
        ctx.fill();
      }

      // Radar preview
      if (el.element_type === 'radar') {
        const ac = aircraft[0];
        const cx = x + w / 2;
        const cy = y + h / 2;
        const radius = Math.min(w, h) / 2 - 2;
        const ringColor = el.ring_color || '#333333';
        const dotColor = el.dot_color || '#ff0000';
        const userColor = el.user_dot_color || '#00ff00';
        const showRings = el.show_rings ?? true;
        const showTicks = el.show_ticks ?? true;
        const rangeKm = el.range_km || 20;

        ctx.strokeStyle = ringColor;
        ctx.lineWidth = 1;

        // Outer circle
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.stroke();

        // Range rings
        if (showRings) {
          [0.25, 0.5, 0.75].forEach((step) => {
            const r = radius * step;
            if (r > 0) {
              ctx.beginPath();
              ctx.arc(cx, cy, r, 0, Math.PI * 2);
              ctx.stroke();
            }
          });
        }

        // N/E/S/W tick marks
        if (showTicks) {
          const tickLen = Math.max(3, Math.floor(radius / 10));
          [0, 90, 180, 270].forEach((bearingDeg) => {
            const angle = (bearingDeg - 90) * (Math.PI / 180);
            const innerR = radius - tickLen;
            const outerR = radius;
            ctx.beginPath();
            ctx.moveTo(cx + innerR * Math.cos(angle), cy + innerR * Math.sin(angle));
            ctx.lineTo(cx + outerR * Math.cos(angle), cy + outerR * Math.sin(angle));
            ctx.stroke();
          });
        }

        // Centre user dot
        ctx.fillStyle = userColor;
        ctx.beginPath();
        ctx.arc(cx, cy, 2, 0, Math.PI * 2);
        ctx.fill();

        // Aircraft marker
        if (ac && ac.distance_km !== undefined && ac.bearing !== undefined) {
          const ratio = Math.min(ac.distance_km / rangeKm, 1.0);
          const angle = (ac.bearing - 90) * (Math.PI / 180);
          const dotX = cx + radius * ratio * Math.cos(angle);
          const dotY = cy + radius * ratio * Math.sin(angle);

          ctx.fillStyle = dotColor;

          if (el.use_plane_symbol && ac.heading !== undefined && ac.heading !== null) {
            const heading = Number(ac.heading);
            const plane: [number, number][] = [
              [0, -4],
              [-3, 2],
              [-1, 1],
              [0, 3],
              [1, 1],
              [3, 2],
            ];
            ctx.beginPath();
            const [startX, startY] = rotatePoint(dotX + plane[0][0], dotY + plane[0][1], dotX, dotY, heading);
            ctx.moveTo(startX, startY);
            for (let i = 1; i < plane.length; i++) {
              const [rx, ry] = rotatePoint(dotX + plane[i][0], dotY + plane[i][1], dotX, dotY, heading);
              ctx.lineTo(rx, ry);
            }
            ctx.closePath();
            ctx.fill();
          } else {
            ctx.beginPath();
            ctx.arc(dotX, dotY, 3, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }

      // Aircraft list preview
      if (el.element_type === 'aircraft_list') {
        const extra = (el.extra || {}) as Record<string, any>;
        const maxRows = (extra.max_rows as number) || 5;
        const columns: string[] = (extra.columns as string[]) || ['callsign', 'origin', 'destination'];
        const rowHeight = (extra.row_height as number) || 24;
        const showHeader = (extra.show_header as boolean) ?? true;
        const listAircraft = aircraft.slice(0, maxRows);

        ctx.save();
        ctx.beginPath();
        ctx.rect(x, y, w, h);
        ctx.clip();

        ctx.fillStyle = el.color || '#ffffff';
        ctx.font = `${Math.max(10, (el.font_size || 12))}px monospace`;
        ctx.textBaseline = 'top';

        let rowY = y + 4;

        if (showHeader) {
          ctx.fillStyle = el.color || '#ffaa00';
          const headerText = columns.map((c) => c.toUpperCase()).join('  ');
          ctx.fillText(headerText, x + 4, rowY);
          rowY += rowHeight;
          ctx.strokeStyle = '#333333';
          ctx.beginPath();
          ctx.moveTo(x + 4, rowY - 4);
          ctx.lineTo(x + w - 4, rowY - 4);
          ctx.stroke();
        }

        ctx.fillStyle = el.color || '#ffffff';
        for (let i = 0; i < maxRows; i++) {
          const ac = listAircraft[i];
          if (ac) {
            const rowText = columns.map((col) => {
              const val = ac[col as keyof Aircraft];
              return val !== undefined && val !== null ? String(val) : '---';
            }).join('  ');
            ctx.fillText(rowText, x + 4, rowY);
          } else {
            ctx.fillStyle = '#333333';
            ctx.fillText('─'.repeat(Math.floor((w - 8) / 8)), x + 4, rowY);
            ctx.fillStyle = el.color || '#ffffff';
          }
          rowY += rowHeight;
          if (rowY > y + h) break;
        }

        ctx.restore();
      }

      // Faint bounding box on every element so overlaps are visible in the
      // designer before they cause colour-bleed or ghosting on the matrix.
      if (!isSelected) {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.18)';
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]);
        ctx.strokeRect(x, y, w, h);
        ctx.setLineDash([]);
      }

      // Selection outline
      if (isSelected) {
        ctx.strokeStyle = '#00d4ff';
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.strokeRect(x - 2, y - 2, w + 4, h + 4);
        ctx.setLineDash([]);

        // Resize handles
        ctx.fillStyle = '#00d4ff';
        const handles = [
          { x: x - 4, y: y - 4 },
          { x: x + w - 4, y: y - 4 },
          { x: x - 4, y: y + h - 4 },
          { x: x + w - 4, y: y + h - 4 },
        ];
        handles.forEach((h) => ctx.fillRect(h.x, h.y, 8, 8));
      }
    });

    // If the hardware is configured to swap panel rows, mirror that here so the
    // designer preview matches the physical LED output.
    if (flipVertical) {
      const half = canvas.height / 2;
      const offscreen = document.createElement('canvas');
      offscreen.width = canvas.width;
      offscreen.height = canvas.height;
      const offCtx = offscreen.getContext('2d');
      if (offCtx) {
        offCtx.drawImage(canvas, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(offscreen, 0, half, canvas.width, half, 0, 0, canvas.width, half);
        ctx.drawImage(offscreen, 0, 0, canvas.width, half, 0, half, canvas.width, half);
      }
    }
  }, [layout, selectedElement, getDisplayValue, flipVertical]);

  // Keep a ref to the latest draw function for async logo loading callbacks.
  drawRef.current = draw;

  useEffect(() => {
    draw();
  }, [draw]);

  const getMousePos = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return { x: (e.clientX - rect.left) / zoom, y: (e.clientY - rect.top) / zoom };
  };

  const getHandleAt = (mx: number, my: number, el: LayoutElement): string | null => {
    const x = el.x;
    const y = el.y;
    const w = el.width || 50;
    const h = el.height || 20;
    const handles = [
      { name: 'nw', x: x - 4, y: y - 4 },
      { name: 'ne', x: x + w - 4, y: y - 4 },
      { name: 'sw', x: x - 4, y: y + h - 4 },
      { name: 'se', x: x + w - 4, y: y + h - 4 },
    ];
    for (const h of handles) {
      if (mx >= h.x && mx <= h.x + 8 && my >= h.y && my <= h.y + 8) {
        return h.name;
      }
    }
    return null;
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    const { x: mx, y: my } = getMousePos(e);

    // Check handles first (resize)
    if (selectedElement) {
      const handle = getHandleAt(mx, my, selectedElement);
      if (handle) {
        setResizing({ el: selectedElement, corner: handle });
        return;
      }
    }

    // Check elements (reverse order for z-index)
    for (let i = layout.elements.length - 1; i >= 0; i--) {
      const el = layout.elements[i];
      const w = el.width || 50;
      const h = el.height || 20;
      if (mx >= el.x && mx <= el.x + w && my >= el.y && my <= el.y + h) {
        onSelectElement(el);
        setDragging({ el, offsetX: mx - el.x, offsetY: my - el.y });
        return;
      }
    }

    onSelectElement(null);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const { x: mx, y: my } = getMousePos(e);

    if (dragging) {
      const newX = Math.round(Math.max(0, Math.min(mx - dragging.offsetX, layout.width - (dragging.el.width || 50))));
      const newY = Math.round(Math.max(0, Math.min(my - dragging.offsetY, layout.height - (dragging.el.height || 20))));
      onUpdateElement({ ...dragging.el, x: newX, y: newY });
    } else if (resizing) {
      const { el, corner } = resizing;
      let newX = el.x;
      let newY = el.y;
      let newW = el.width || 50;
      let newH = el.height || 20;

      if (corner.includes('e')) newW = Math.max(10, mx - el.x);
      if (corner.includes('s')) newH = Math.max(10, my - el.y);
      if (corner.includes('w')) {
        const right = el.x + newW;
        newX = Math.min(mx, right - 10);
        newW = right - newX;
      }
      if (corner.includes('n')) {
        const bottom = el.y + newH;
        newY = Math.min(my, bottom - 10);
        newH = bottom - newY;
      }

      onUpdateElement({
        ...el,
        x: Math.round(newX),
        y: Math.round(newY),
        width: Math.round(newW),
        height: Math.round(newH),
      });
    }
  };

  const handleMouseUp = () => {
    setDragging(null);
    setResizing(null);
  };

  return (
    <div
      className="relative shadow-2xl"
      style={{
        width: layout.width * zoom,
        height: layout.height * zoom,
      }}
    >
      <canvas
        ref={canvasRef}
        className="cursor-crosshair block"
        style={{
          width: layout.width * zoom,
          height: layout.height * zoom,
          imageRendering: 'pixelated',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      />
    </div>
  );
}
