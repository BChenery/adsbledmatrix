import { useRef, useEffect, useState, useCallback } from 'react';
import { Layout, LayoutElement } from '@/types/layout';
import { Aircraft } from '@/types/aircraft';

interface CanvasProps {
  layout: Layout;
  selectedElement: LayoutElement | null;
  onSelectElement: (el: LayoutElement | null) => void;
  onUpdateElement: (el: LayoutElement) => void;
  aircraft?: Aircraft[];
  zoom?: number;
}


export default function Canvas({ layout, selectedElement, onSelectElement, onUpdateElement, aircraft = [], zoom = 1 }: CanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [dragging, setDragging] = useState<{ el: LayoutElement; offsetX: number; offsetY: number } | null>(null);
  const [resizing, setResizing] = useState<{ el: LayoutElement; corner: string } | null>(null);

  const getAircraftDisplayValue = useCallback((ac: Aircraft | undefined, el: LayoutElement): string => {
    if (!ac) return '';

    if (el.element_type === 'data_field') {
      let template = el.format_str || `{${el.data_field}}`;
      return template.replace(/\{(\w+)\}/g, (_, key) => {
        if (key === 'distance' && ac.distance_km !== undefined) {
          return ac.distance_display || `${ac.distance_km.toFixed(1)} km`;
        }
        const val = ac[key as keyof Aircraft];
        return val !== undefined && val !== null ? String(val) : '';
      });
    }

    if (el.element_type === 'vertical_rate') {
      const vr = ac.vertical_rate;
      if (vr === undefined) return '▲ 1200';
      return `${vr > 0 ? '▲' : '▼'} ${Math.abs(vr)}`;
    }

    if (el.element_type === 'distance_bar') {
      const dist = ac.distance_km;
      if (dist === undefined) return '|||||';
      const bars = Math.min(10, Math.max(1, Math.round(dist)));
      return '█'.repeat(bars);
    }

    if (el.element_type === 'heading_arrow') {
      const heading = ac.heading;
      if (heading === undefined) return '→';
      const arrows = ['→', '↘', '↓', '↙', '←', '↖', '↑', '↗'];
      const idx = Math.round(heading / 45) % 8;
      return arrows[idx];
    }

    return '';
  }, []);

  const getDisplayValue = useCallback((el: LayoutElement): string => {
    return getAircraftDisplayValue(aircraft[0], el);
  }, [aircraft, getAircraftDisplayValue]);

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
      else if (el.element_type === 'heading_arrow') text = getDisplayValue(el) || '→';
      else if (el.element_type === 'vertical_rate') text = getDisplayValue(el) || '▲ 1200';
      else if (el.element_type === 'distance_bar') text = getDisplayValue(el) || '|||||';
      else if (el.element_type === 'radar_blip') text = '◎';
      else if (el.element_type === 'image') {
        text = aircraft[0]?.operator_icao ? `[${aircraft[0].operator_icao}]` : '[IMG]';
      }
      else if (el.element_type === 'shape') text = '';
      else if (el.element_type === 'aircraft_list') {
        // Handled separately below
      }

      if (text) {
        const metrics = ctx.measureText(text);
        const textX = x + Math.max(0, (w - metrics.width) / 2);
        ctx.fillText(text, textX, y + 4, w - 8);
      }

      // Shape preview
      if (el.element_type === 'shape') {
        ctx.strokeStyle = el.color || '#ffffff';
        ctx.strokeRect(x, y, w, h);
      }

      if (el.element_type === 'heading_arrow') {
        ctx.strokeStyle = el.color || '#ffffff';
        ctx.beginPath();
        ctx.moveTo(x + w / 2, y + 4);
        ctx.lineTo(x + w / 2, y + h - 4);
        ctx.moveTo(x + w / 2, y + 4);
        ctx.lineTo(x + w / 2 - 6, y + 12);
        ctx.moveTo(x + w / 2, y + 4);
        ctx.lineTo(x + w / 2 + 6, y + 12);
        ctx.stroke();
      }

      // Aircraft list preview
      if (el.element_type === 'aircraft_list') {
        const extra = (el.extra || {}) as Record<string, any>;
        const maxRows = (extra.max_rows as number) || 5;
        const columns: string[] = (extra.columns as string[]) || ['callsign', 'origin', 'destination'];
        const rowHeight = (extra.row_height as number) || 24;
        const showHeader = (extra.show_header as boolean) ?? true;
        const listAircraft = aircraft.slice(0, maxRows);

        ctx.fillStyle = el.color || '#ffffff';
        ctx.font = `${Math.max(10, (el.font_size || 12))}px monospace`;
        ctx.textBaseline = 'top';

        let rowY = y + 4;

        if (showHeader) {
          ctx.fillStyle = el.color || '#ffaa00';
          const headerText = columns.map((c) => c.toUpperCase()).join('  ');
          ctx.fillText(headerText, x + 4, rowY, w - 8);
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
            ctx.fillText(rowText, x + 4, rowY, w - 8);
          } else {
            ctx.fillStyle = '#333333';
            ctx.fillText('─'.repeat(Math.floor((w - 8) / 8)), x + 4, rowY, w - 8);
            ctx.fillStyle = el.color || '#ffffff';
          }
          rowY += rowHeight;
          if (rowY > y + h) break;
        }
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
  }, [layout, selectedElement, getDisplayValue]);

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
      const newX = Math.max(0, Math.min(mx - dragging.offsetX, layout.width - (dragging.el.width || 50)));
      const newY = Math.max(0, Math.min(my - dragging.offsetY, layout.height - (dragging.el.height || 20)));
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

      onUpdateElement({ ...el, x: newX, y: newY, width: newW, height: newH });
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
