import { LayoutElement } from '@/types/layout';
import { Button } from '@/components/ui/button';
import {
  Type,
  Database,
  Image as ImageIcon,
  Square,
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
    key: 'aircraft_list',
    label: 'Flight List',
    icon: <List size={18} />,
    template: { element_type: 'aircraft_list', x: 10, y: 10, width: 246, height: 100, color: '#ffffff', extra: { max_rows: 3, columns: ['callsign', 'origin', 'destination', 'distance'], row_height: 14, show_header: true } },
  },
];

export const ADVANCED_ELEMENTS: PalettePreset[] = [
  { key: 'text', label: 'Text', icon: <Type size={18} />, template: { element_type: 'text', x: 10, y: 10, width: 100, height: 15, color: '#ffffff', font_size: 8, format_str: 'Hello LED' } },
  { key: 'data_field', label: 'Data Field', icon: <Database size={18} />, template: { element_type: 'data_field', x: 10, y: 10, width: 100, height: 15, color: '#00d4ff', font_size: 8, data_field: 'callsign', format_str: '{callsign}' } },
  { key: 'image', label: 'Image', icon: <ImageIcon size={18} />, template: { element_type: 'image', x: 10, y: 10, width: 32, height: 32 } },
  { key: 'shape', label: 'Shape', icon: <Square size={18} />, template: { element_type: 'shape', x: 10, y: 10, width: 50, height: 2, color: '#ffffff', extra: { shape_type: 'rectangle' } } },
  { key: 'radar_blip', label: 'Radar', icon: <Radar size={18} />, template: { element_type: 'radar_blip', x: 10, y: 10, width: 40, height: 40, color: '#00d4ff' } },
];

interface ElementPaletteProps {
  onAddElement: (key: string) => void;
}

export default function ElementPalette({ onAddElement }: ElementPaletteProps) {
  return (
    <div className="w-48 bg-led-panel border-r border-white/10 flex flex-col">
      <div className="p-3 border-b border-white/10">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50">Quick Add</h3>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {QUICK_ADD_PRESETS.map((el) => (
          <Button
            key={el.key}
            variant="ghost"
            onClick={() => onAddElement(el.key)}
            className="w-full justify-start gap-3 px-3 py-2 h-auto text-sm text-white/70 hover:text-white"
          >
            <span className="text-white/40">{el.icon}</span>
            {el.label}
          </Button>
        ))}
      </div>

      <div className="p-3 border-t border-b border-white/10">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50">Advanced</h3>
      </div>
      <div className="p-2 space-y-1">
        {ADVANCED_ELEMENTS.map((el) => (
          <Button
            key={el.key}
            variant="ghost"
            onClick={() => onAddElement(el.key)}
            className="w-full justify-start gap-3 px-3 py-2 h-auto text-sm text-white/70 hover:text-white"
          >
            <span className="text-white/40">{el.icon}</span>
            {el.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
