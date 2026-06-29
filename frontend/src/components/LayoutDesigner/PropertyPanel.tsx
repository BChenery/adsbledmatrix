import { Layout, LayoutElement } from '@/types/layout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Trash2 } from 'lucide-react';

interface PropertyPanelProps {
  layout: Layout;
  onLayoutChange: (layout: Layout) => void;
  onNameBlur?: () => void;
  element: LayoutElement | null;
  onChange: (el: LayoutElement) => void;
  onDelete: () => void;
}

export default function PropertyPanel({ layout, onLayoutChange, onNameBlur, element, onChange, onDelete }: PropertyPanelProps) {
  if (!element) {
    const updateLayout = (field: keyof Layout, value: unknown) => {
      onLayoutChange({ ...layout, [field]: value });
    };

    return (
      <div className="w-64 bg-led-panel border-l border-white/10 flex flex-col">
        <div className="p-3 border-b border-white/10">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50">Layout Properties</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <div className="space-y-1">
            <Label>Name</Label>
            <Input
              type="text"
              value={layout.name}
              onChange={(e) => updateLayout('name', e.target.value)}
              onBlur={onNameBlur}
              placeholder="Layout name"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label>Width</Label>
              <Input
                type="number"
                min={1}
                value={layout.width}
                onChange={(e) => updateLayout('width', parseInt(e.target.value) || 1)}
              />
            </div>
            <div className="space-y-1">
              <Label>Height</Label>
              <Input
                type="number"
                min={1}
                value={layout.height}
                onChange={(e) => updateLayout('height', parseInt(e.target.value) || 1)}
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label>Description</Label>
            <Input
              type="text"
              value={layout.description || ''}
              onChange={(e) => updateLayout('description', e.target.value)}
              placeholder="What this layout is for"
            />
          </div>
        </div>
      </div>
    );
  }

  const update = (field: keyof LayoutElement, value: unknown) => {
    onChange({ ...element, [field]: value });
  };

  return (
    <div className="w-64 bg-led-panel border-l border-white/10 flex flex-col">
      <div className="p-3 border-b border-white/10 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50">Properties</h3>
        <Button variant="ghost" size="icon" onClick={onDelete} className="text-led-red hover:text-red-400 hover:bg-led-red/10 h-8 w-8">
          <Trash2 size={16} />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="space-y-1">
          <Label>Type</Label>
          <div className="text-sm font-medium">{element.element_type}</div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label>X</Label>
            <Input
              type="number"
              value={element.x}
              onChange={(e) => update('x', parseInt(e.target.value) || 0)}
            />
          </div>
          <div className="space-y-1">
            <Label>Y</Label>
            <Input
              type="number"
              value={element.y}
              onChange={(e) => update('y', parseInt(e.target.value) || 0)}
            />
          </div>
          <div className="space-y-1">
            <Label>Width</Label>
            <Input
              type="number"
              value={element.width || ''}
              onChange={(e) => update('width', parseInt(e.target.value) || undefined)}
            />
          </div>
          <div className="space-y-1">
            <Label>Height</Label>
            <Input
              type="number"
              value={element.height || ''}
              onChange={(e) => update('height', parseInt(e.target.value) || undefined)}
            />
          </div>
        </div>

        <div className="space-y-1">
          <Label>Z-Index</Label>
          <Input
            type="number"
            value={element.z_index}
            onChange={(e) => update('z_index', parseInt(e.target.value) || 0)}
          />
        </div>

        <div className="space-y-1">
          <Label>Color</Label>
          <div className="flex gap-2">
            <input
              type="color"
              value={element.color || '#ffffff'}
              onChange={(e) => update('color', e.target.value)}
              className="w-10 h-9 rounded cursor-pointer border-0 p-0"
            />
            <Input
              type="text"
              value={element.color || ''}
              onChange={(e) => update('color', e.target.value)}
            />
          </div>
        </div>

        <div className="space-y-1">
          <Label>Background</Label>
          <div className="flex gap-2">
            <input
              type="color"
              value={element.bg_color || '#000000'}
              onChange={(e) => update('bg_color', e.target.value)}
              className="w-10 h-9 rounded cursor-pointer border-0 p-0"
            />
            <Input
              type="text"
              value={element.bg_color || ''}
              onChange={(e) => update('bg_color', e.target.value)}
              placeholder="None"
            />
          </div>
        </div>

        {(element.element_type === 'text' || element.element_type === 'data_field') && (
          <>
            <div className="space-y-1">
              <Label>Font Size</Label>
              <Input
                type="number"
                value={element.font_size || ''}
                onChange={(e) => update('font_size', parseInt(e.target.value) || undefined)}
              />
            </div>
            <div className="space-y-1">
              <Label>Font Family</Label>
              <Input
                type="text"
                value={element.font_family || ''}
                onChange={(e) => update('font_family', e.target.value)}
              />
            </div>
          </>
        )}

        {(element.element_type === 'text' || element.element_type === 'data_field') && (
          <div className="space-y-1">
            <Label>{element.element_type === 'data_field' ? 'Format String' : 'Text'}</Label>
            <Input
              type="text"
              value={element.format_str || ''}
              onChange={(e) => update('format_str', e.target.value)}
              placeholder="{callsign}"
            />
          </div>
        )}

        {element.element_type === 'data_field' && (
          <div className="space-y-1">
            <Label>Data Field</Label>
            <Select
              value={element.data_field || ''}
              onValueChange={(v) => {
                // Auto-update format_str to match the new data field
                const newFormat = `{${v}}`;
                const formatFields: Record<string, string> = {
                  altitude: 'ALT: {altitude} ft',
                  ground_speed: 'SPD: {ground_speed} kts',
                  heading: 'HDG: {heading}',
                  distance: '{distance} km',
                  vertical_rate: '{vertical_rate}',
                  bearing: 'BRG: {bearing}',
                };
                onChange({
                  ...element,
                  data_field: v,
                  format_str: formatFields[v] || newFormat,
                });
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select field..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="callsign">Callsign</SelectItem>
                <SelectItem value="registration">Registration</SelectItem>
                <SelectItem value="altitude">Altitude</SelectItem>
                <SelectItem value="ground_speed">Ground Speed</SelectItem>
                <SelectItem value="heading">Heading</SelectItem>
                <SelectItem value="distance">Distance</SelectItem>
                <SelectItem value="vertical_rate">Vertical Rate</SelectItem>
                <SelectItem value="model">Model</SelectItem>
                <SelectItem value="operator">Operator</SelectItem>
                <SelectItem value="operator_icao">Operator ICAO</SelectItem>
                <SelectItem value="type_code">Type Code</SelectItem>
                <SelectItem value="type_name">Type Name</SelectItem>
                <SelectItem value="manufacturer">Manufacturer</SelectItem>
                <SelectItem value="hex_code">Hex Code</SelectItem>
                <SelectItem value="squawk">Squawk</SelectItem>
                <SelectItem value="messages">Messages</SelectItem>
                <SelectItem value="route">Route</SelectItem>
                <SelectItem value="origin">Origin</SelectItem>
                <SelectItem value="destination">Destination</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}

        {element.element_type === 'image' && (
          <>
            <div className="space-y-1">
              <Label>Image Path</Label>
              <Input
                type="text"
                value={element.image_path || ''}
                onChange={(e) => update('image_path', e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label>Image URL</Label>
              <Input
                type="text"
                value={element.image_url || ''}
                onChange={(e) => update('image_url', e.target.value)}
              />
            </div>
          </>
        )}

        {element.element_type === 'aircraft_list' && (
          <>
            <div className="space-y-1">
              <Label>Max Rows</Label>
              <Input
                type="number"
                value={((element.extra as Record<string, any>)?.max_rows as number) || 5}
                onChange={(e) => update('extra', { ...(element.extra || {}), max_rows: parseInt(e.target.value) || 5 })}
              />
            </div>
            <div className="space-y-1">
              <Label>Columns (comma-separated)</Label>
              <Input
                type="text"
                value={(((element.extra as Record<string, any>)?.columns as string[]) || ['callsign', 'origin', 'destination']).join(',')}
                onChange={(e) => update('extra', { ...(element.extra || {}), columns: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
                placeholder="callsign,origin,destination"
              />
            </div>
            <div className="space-y-1">
              <Label>Row Height</Label>
              <Input
                type="number"
                value={((element.extra as Record<string, any>)?.row_height as number) || 24}
                onChange={(e) => update('extra', { ...(element.extra || {}), row_height: parseInt(e.target.value) || 24 })}
              />
            </div>
            <div className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                id="show_header"
                checked={((element.extra as Record<string, any>)?.show_header as boolean) ?? true}
                onChange={(e) => update('extra', { ...(element.extra || {}), show_header: e.target.checked })}
                className="w-4 h-4 rounded border-gray-600"
              />
              <Label htmlFor="show_header" className="cursor-pointer">Show Header</Label>
            </div>
          </>
        )}

        {element.element_type === 'radar' && (
          <>
            <div className="space-y-1">
              <Label>Range (km)</Label>
              <Input
                type="number"
                min={1}
                value={element.range_km || 20}
                onChange={(e) => update('range_km', parseInt(e.target.value) || 20)}
              />
            </div>
            <div className="space-y-1">
              <Label>Ring Color</Label>
              <div className="flex gap-2">
                <input
                  type="color"
                  value={element.ring_color || '#333333'}
                  onChange={(e) => update('ring_color', e.target.value)}
                  className="w-10 h-9 rounded cursor-pointer border-0 p-0"
                />
                <Input
                  type="text"
                  value={element.ring_color || ''}
                  onChange={(e) => update('ring_color', e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-1">
              <Label>Aircraft Dot Color</Label>
              <div className="flex gap-2">
                <input
                  type="color"
                  value={element.dot_color || '#ff0000'}
                  onChange={(e) => update('dot_color', e.target.value)}
                  className="w-10 h-9 rounded cursor-pointer border-0 p-0"
                />
                <Input
                  type="text"
                  value={element.dot_color || ''}
                  onChange={(e) => update('dot_color', e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-1">
              <Label>User Dot Color</Label>
              <div className="flex gap-2">
                <input
                  type="color"
                  value={element.user_dot_color || '#00ff00'}
                  onChange={(e) => update('user_dot_color', e.target.value)}
                  className="w-10 h-9 rounded cursor-pointer border-0 p-0"
                />
                <Input
                  type="text"
                  value={element.user_dot_color || ''}
                  onChange={(e) => update('user_dot_color', e.target.value)}
                />
              </div>
            </div>
            <div className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                id="show_rings"
                checked={element.show_rings ?? true}
                onChange={(e) => update('show_rings', e.target.checked)}
                className="w-4 h-4 rounded border-gray-600"
              />
              <Label htmlFor="show_rings" className="cursor-pointer">Show Range Rings</Label>
            </div>
            <div className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                id="show_ticks"
                checked={element.show_ticks ?? true}
                onChange={(e) => update('show_ticks', e.target.checked)}
                className="w-4 h-4 rounded border-gray-600"
              />
              <Label htmlFor="show_ticks" className="cursor-pointer">Show N/E/S/W Ticks</Label>
            </div>
          </>
        )}

        <div className="space-y-1">
          <Label>Show If</Label>
          <Input
            type="text"
            value={element.show_if || ''}
            onChange={(e) => update('show_if', e.target.value)}
            placeholder="e.g. has_logo"
          />
        </div>
      </div>
    </div>
  );
}
