import { LayoutElement } from '@/types/layout';
import { Button } from '@/components/ui/button';
import {
  Type,
  Database,
  Image as ImageIcon,
  Square,
  Circle,
  Minus,
  ArrowRight,
  ArrowLeft,
  ArrowUp,
  ArrowDown,
  Triangle,
  Diamond,
  ChevronRight,
  ChevronLeft,
  Navigation,
  ArrowUpDown,
  BarChart3,
  Radar,
  Plane,
  MapPin,
  MapPinOff,
  Route,
  Gauge,
  Thermometer,
  Compass,
  Ruler,
  List,
  Hash,
  Building2,
  Factory,
  Radio,
  Milestone,
  Cloud,
  CloudSun,
} from 'lucide-react';

export interface PalettePreset {
  key: string;
  label: string;
  icon: React.ReactNode;
  template: Partial<LayoutElement>;
}

export const QUICK_ADD_PRESETS: PalettePreset[] = [
  {
    key: 'logo',
    label: 'Airline Logo',
    icon: <ImageIcon size={18} />,
    template: { element_type: 'image', x: 10, y: 10, width: 48, height: 48, show_if: 'has_logo' },
  },
  {
    key: 'callsign',
    label: 'Callsign',
    icon: <Plane size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 150, height: 24, color: '#00d4ff', font_size: 16, data_field: 'callsign', format_str: '{callsign}' },
  },
  {
    key: 'origin',
    label: 'Origin',
    icon: <MapPin size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 60, height: 14, color: '#ffffff', font_size: 9, data_field: 'origin', format_str: '{origin}' },
  },
  {
    key: 'destination',
    label: 'Destination',
    icon: <MapPinOff size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 60, height: 14, color: '#ffffff', font_size: 9, data_field: 'destination', format_str: '{destination}' },
  },
  {
    key: 'route',
    label: 'Route',
    icon: <Route size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 120, height: 20, color: '#ffaa00', font_size: 12, data_field: 'route', format_str: '{route}' },
  },
  {
    key: 'type_code',
    label: 'Aircraft Type',
    icon: <Database size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 100, height: 14, color: '#aaaaaa', font_size: 9, data_field: 'type_code', format_str: '{type_code}' },
  },
  {
    key: 'type_name',
    label: 'Aircraft Name',
    icon: <Database size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 150, height: 14, color: '#aaaaaa', font_size: 9, data_field: 'type_name', format_str: '{type_name}' },
  },
  {
    key: 'altitude',
    label: 'Altitude',
    icon: <Thermometer size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 100, height: 12, color: '#aaaaaa', font_size: 8, data_field: 'altitude', format_str: 'ALT: {altitude} ft' },
  },
  {
    key: 'speed',
    label: 'Speed',
    icon: <Gauge size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 100, height: 12, color: '#aaaaaa', font_size: 8, data_field: 'ground_speed', format_str: 'SPD: {ground_speed} kts' },
  },
  {
    key: 'heading',
    label: 'Heading',
    icon: <Compass size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 60, height: 12, color: '#aaaaaa', font_size: 8, data_field: 'heading', format_str: 'HDG: {heading}' },
  },
  {
    key: 'distance',
    label: 'Distance',
    icon: <Ruler size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 100, height: 18, color: '#ffaa00', font_size: 12, data_field: 'distance', format_str: '{distance} km' },
  },
  {
    key: 'radar',
    label: 'Radar',
    icon: <Radar size={18} />,
    template: {
      element_type: 'radar',
      x: 10,
      y: 10,
      width: 80,
      height: 80,
      range_km: 20,
      ring_color: '#333333',
      dot_color: '#ff0000',
      user_dot_color: '#00ff00',
      show_rings: true,
      show_ticks: true,
    },
  },
  {
    key: 'heading_arrow',
    label: 'Heading Arrow',
    icon: <Navigation size={18} />,
    template: { element_type: 'heading_arrow', x: 10, y: 10, width: 40, height: 40, color: '#00ff88' },
  },
  {
    key: 'vertical_rate',
    label: 'V. Rate',
    icon: <ArrowUpDown size={18} />,
    template: { element_type: 'vertical_rate', x: 10, y: 10, width: 60, height: 12, color: '#ffffff' },
  },
  {
    key: 'distance_bar',
    label: 'Dist. Bar',
    icon: <BarChart3 size={18} />,
    template: { element_type: 'distance_bar', x: 10, y: 10, width: 246, height: 6, color: '#00d4ff' },
  },
  {
    key: 'registration',
    label: 'Registration',
    icon: <Hash size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 100, height: 12, color: '#888888', font_size: 7, data_field: 'registration', format_str: '{registration}' },
  },
  {
    key: 'model',
    label: 'Model',
    icon: <Factory size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 125, height: 12, color: '#888888', font_size: 7, data_field: 'model', format_str: '{model}' },
  },
  {
    key: 'airline',
    label: 'Airline',
    icon: <Building2 size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 100, height: 12, color: '#ffffff', font_size: 8, data_field: 'airline', format_str: '{airline}' },
  },
  {
    key: 'operator',
    label: 'Operator',
    icon: <Building2 size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 100, height: 12, color: '#888888', font_size: 7, data_field: 'operator', format_str: '{operator}' },
  },
  {
    key: 'squawk',
    label: 'Squawk',
    icon: <Radio size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 60, height: 12, color: '#ff5555', font_size: 7, data_field: 'squawk', format_str: '{squawk}' },
  },
  {
    key: 'bearing',
    label: 'Bearing',
    icon: <Milestone size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 60, height: 12, color: '#aaaaaa', font_size: 7, data_field: 'bearing', format_str: 'BRG: {bearing}' },
  },
  {
    key: 'origin_iata',
    label: 'From (IATA)',
    icon: <MapPin size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 50, height: 16, color: '#00d4ff', font_size: 14, data_field: 'origin_iata', format_str: '{origin_iata}' },
  },
  {
    key: 'destination_iata',
    label: 'To (IATA)',
    icon: <MapPinOff size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 50, height: 16, color: '#ffb347', font_size: 14, data_field: 'destination_iata', format_str: '{destination_iata}' },
  },
  {
    key: 'origin_city',
    label: 'From City',
    icon: <MapPin size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 100, height: 16, color: '#00d4ff', font_size: 14, data_field: 'origin_city', format_str: '{origin_city}' },
  },
  {
    key: 'destination_city',
    label: 'To City',
    icon: <MapPinOff size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 100, height: 16, color: '#ffb347', font_size: 14, data_field: 'destination_city', format_str: '{destination_city}' },
  },
  {
    key: 'aircraft_list',
    label: 'Flight List',
    icon: <List size={18} />,
    template: { element_type: 'aircraft_list', x: 10, y: 10, width: 246, height: 100, color: '#ffffff', extra: { max_rows: 3, columns: ['callsign', 'origin', 'destination', 'distance'], row_height: 14, show_header: true } },
  },
  {
    key: 'weather_city',
    label: 'Weather City',
    icon: <Cloud size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 150, height: 24, color: '#00d4ff', font_size: 16, data_field: 'weather_city', format_str: '{weather_city}' },
  },
  {
    key: 'weather_temp',
    label: 'Weather Temp',
    icon: <Thermometer size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 80, height: 24, color: '#ffffff', font_size: 16, data_field: 'weather_temp', format_str: '{weather_temp}' },
  },
  {
    key: 'weather_condition',
    label: 'Weather',
    icon: <CloudSun size={18} />,
    template: { element_type: 'data_field', x: 10, y: 10, width: 120, height: 16, color: '#4ade80', font_size: 12, data_field: 'weather_condition', format_str: '{weather_condition}' },
  },
];

export const ADVANCED_ELEMENTS: PalettePreset[] = [
  { key: 'text', label: 'Text', icon: <Type size={18} />, template: { element_type: 'text', x: 10, y: 10, width: 100, height: 15, color: '#ffffff', font_size: 8, format_str: 'Hello LED' } },
  { key: 'data_field', label: 'Data Field', icon: <Database size={18} />, template: { element_type: 'data_field', x: 10, y: 10, width: 100, height: 15, color: '#00d4ff', font_size: 8, data_field: 'callsign', format_str: '{callsign}' } },
  { key: 'image', label: 'Image', icon: <ImageIcon size={18} />, template: { element_type: 'image', x: 10, y: 10, width: 32, height: 32 } },
  { key: 'radar_blip', label: 'Radar Blip', icon: <Radar size={18} />, template: { element_type: 'radar_blip', x: 10, y: 10, width: 40, height: 40, color: '#00d4ff' } },
];

/** Decorative geometry — all use element_type "shape" with extra.shape_type. */
export const SHAPE_PRESETS: PalettePreset[] = [
  {
    key: 'shape_rect',
    label: 'Rectangle',
    icon: <Square size={18} />,
    template: { element_type: 'shape', x: 10, y: 10, width: 60, height: 24, color: '#ffffff', extra: { shape_type: 'rectangle', stroke_width: 1 } },
  },
  {
    key: 'shape_box',
    label: 'Filled Box',
    icon: <Square size={18} />,
    template: { element_type: 'shape', x: 10, y: 10, width: 40, height: 16, color: '#334155', extra: { shape_type: 'filled_rectangle' } },
  },
  {
    key: 'shape_circle',
    label: 'Circle',
    icon: <Circle size={18} />,
    template: { element_type: 'shape', x: 10, y: 10, width: 24, height: 24, color: '#ffffff', extra: { shape_type: 'circle', stroke_width: 1 } },
  },
  {
    key: 'shape_filled_circle',
    label: 'Filled Circle',
    icon: <Circle size={18} />,
    template: { element_type: 'shape', x: 10, y: 10, width: 16, height: 16, color: '#00d4ff', extra: { shape_type: 'filled_circle' } },
  },
  {
    key: 'shape_hline',
    label: 'H. Line',
    icon: <Minus size={18} />,
    template: { element_type: 'shape', x: 10, y: 10, width: 80, height: 4, color: '#a0aec0', extra: { shape_type: 'hline', stroke_width: 2 } },
  },
  {
    key: 'shape_vline',
    label: 'V. Line',
    icon: <Minus size={18} className="rotate-90" />,
    template: { element_type: 'shape', x: 10, y: 10, width: 4, height: 48, color: '#a0aec0', extra: { shape_type: 'vline', stroke_width: 2 } },
  },
  {
    key: 'shape_line',
    label: 'Diagonal',
    icon: <Minus size={18} className="-rotate-45" />,
    template: { element_type: 'shape', x: 10, y: 10, width: 40, height: 40, color: '#ffffff', extra: { shape_type: 'line', stroke_width: 2 } },
  },
  {
    key: 'shape_arrow_right',
    label: 'Arrow →',
    icon: <ArrowRight size={18} />,
    template: { element_type: 'shape', x: 10, y: 10, width: 40, height: 20, color: '#00d4ff', extra: { shape_type: 'arrow_right' } },
  },
  {
    key: 'shape_arrow_left',
    label: 'Arrow ←',
    icon: <ArrowLeft size={18} />,
    template: { element_type: 'shape', x: 10, y: 10, width: 40, height: 20, color: '#00d4ff', extra: { shape_type: 'arrow_left' } },
  },
  {
    key: 'shape_arrow_up',
    label: 'Arrow ↑',
    icon: <ArrowUp size={18} />,
    template: { element_type: 'shape', x: 10, y: 10, width: 20, height: 40, color: '#4ade80', extra: { shape_type: 'arrow_up' } },
  },
  {
    key: 'shape_arrow_down',
    label: 'Arrow ↓',
    icon: <ArrowDown size={18} />,
    template: { element_type: 'shape', x: 10, y: 10, width: 20, height: 40, color: '#f87171', extra: { shape_type: 'arrow_down' } },
  },
  {
    key: 'shape_chevron_right',
    label: 'Chevron ›',
    icon: <ChevronRight size={18} />,
    template: { element_type: 'shape', x: 10, y: 10, width: 20, height: 28, color: '#ffb347', extra: { shape_type: 'chevron_right' } },
  },
  {
    key: 'shape_chevron_left',
    label: 'Chevron ‹',
    icon: <ChevronLeft size={18} />,
    template: { element_type: 'shape', x: 10, y: 10, width: 20, height: 28, color: '#ffb347', extra: { shape_type: 'chevron_left' } },
  },
  {
    key: 'shape_triangle',
    label: 'Triangle',
    icon: <Triangle size={18} />,
    template: { element_type: 'shape', x: 10, y: 10, width: 24, height: 24, color: '#ffffff', extra: { shape_type: 'triangle' } },
  },
  {
    key: 'shape_diamond',
    label: 'Diamond',
    icon: <Diamond size={18} />,
    template: { element_type: 'shape', x: 10, y: 10, width: 24, height: 24, color: '#00d4ff', extra: { shape_type: 'diamond' } },
  },
];

interface ElementPaletteProps {
  onAddElement: (key: string) => void;
  className?: string;
  compact?: boolean;
}

export default function ElementPalette({ onAddElement, className, compact = false }: ElementPaletteProps) {
  return (
    <div
      className={[
        'flex flex-col border-led-line bg-led-dark',
        compact ? 'h-full' : 'hidden w-52 shrink-0 border-r lg:flex',
        className || '',
      ].join(' ')}
    >
      <div className="border-b border-led-line p-3">
        <h3 className="font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-led-faint">Quick add</h3>
      </div>
      <div className="flex-1 space-y-1 overflow-y-auto p-2">
        {QUICK_ADD_PRESETS.map((el) => (
          <Button
            key={el.key}
            variant="ghost"
            onClick={() => onAddElement(el.key)}
            className="h-auto w-full justify-start gap-3 rounded-lg px-3 py-2 text-sm text-led-dim hover:text-[#f5f5f5]"
          >
            <span className="text-led-faint">{el.icon}</span>
            {el.label}
          </Button>
        ))}
      </div>

      <div className="border-y border-led-line p-3">
        <h3 className="font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-led-faint">Shapes</h3>
      </div>
      <div className="space-y-1 p-2">
        {SHAPE_PRESETS.map((el) => (
          <Button
            key={el.key}
            variant="ghost"
            onClick={() => onAddElement(el.key)}
            className="h-auto w-full justify-start gap-3 rounded-lg px-3 py-2 text-sm text-led-dim hover:text-[#f5f5f5]"
          >
            <span className="text-led-faint">{el.icon}</span>
            {el.label}
          </Button>
        ))}
      </div>

      <div className="border-y border-led-line p-3">
        <h3 className="font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-led-faint">Advanced</h3>
      </div>
      <div className="space-y-1 p-2">
        {ADVANCED_ELEMENTS.map((el) => (
          <Button
            key={el.key}
            variant="ghost"
            onClick={() => onAddElement(el.key)}
            className="h-auto w-full justify-start gap-3 rounded-lg px-3 py-2 text-sm text-led-dim hover:text-[#f5f5f5]"
          >
            <span className="text-led-faint">{el.icon}</span>
            {el.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
