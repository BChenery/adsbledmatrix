import { Layout } from '@/types/layout';
import { UserConfig } from '@/types/config';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Save, Plus, ChevronDown, Radio, FlaskConical, ZoomIn, ZoomOut, Monitor, Moon } from 'lucide-react';

interface ToolbarProps {
  layouts: Layout[];
  activeLayout: Layout | null;
  config: UserConfig | null;
  onSelectLayout: (layout: Layout | null) => void;
  onNew: () => void;
  onSave: () => void;
  useMockData: boolean;
  onToggleMockData: () => void;
  zoom: number;
  onZoomChange: (zoom: number) => void;
  onSetAsActive: () => void;
  onSetAsIdle: () => void;
}

const ZOOM_OPTIONS = [1, 2, 3, 4, 5, 6];

export default function Toolbar({
  layouts,
  activeLayout,
  config,
  onSelectLayout,
  onNew,
  onSave,
  useMockData,
  onToggleMockData,
  zoom,
  onZoomChange,
  onSetAsActive,
  onSetAsIdle,
}: ToolbarProps) {
  return (
    <div className="h-14 bg-led-panel border-b border-white/10 flex items-center px-4 gap-4">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="secondary" className="min-w-[160px] justify-between gap-2">
            <span className="truncate">{activeLayout?.name || 'Select Layout'}</span>
            <ChevronDown size={14} />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56">
          {layouts.map((l) => (
            <DropdownMenuItem key={l.id} onClick={() => onSelectLayout(l)}>
              <div>
                <div className="font-medium">{l.name}</div>
                <div className="text-xs text-white/40">{l.width}×{l.height}</div>
              </div>
            </DropdownMenuItem>
          ))}
          {layouts.length === 0 && (
            <div className="px-2 py-3 text-sm text-white/30">No layouts yet</div>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      <Button variant="secondary" size="icon" onClick={onNew}>
        <Plus size={16} />
      </Button>

      {activeLayout?.id && (
        <div className="flex items-center gap-2">
          {activeLayout.id === config?.active_layout_id && (
            <Badge variant="default" className="bg-green-500/20 text-green-400 hover:bg-green-500/30 gap-1">
              <Monitor size={12} />
              Active
            </Badge>
          )}
          {activeLayout.id === config?.idle_layout_id && (
            <Badge variant="default" className="bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 gap-1">
              <Moon size={12} />
              Idle
            </Badge>
          )}
        </div>
      )}

      {activeLayout?.id && (
        <div className="flex items-center gap-1">
          <Button
            variant={activeLayout.id === config?.active_layout_id ? 'default' : 'secondary'}
            size="sm"
            onClick={onSetAsActive}
            className="gap-2"
          >
            <Monitor size={14} />
            {activeLayout.id === config?.active_layout_id ? 'Active Layout' : 'Set Active'}
          </Button>
          <Button
            variant={activeLayout.id === config?.idle_layout_id ? 'default' : 'secondary'}
            size="sm"
            onClick={onSetAsIdle}
            className="gap-2"
          >
            <Moon size={14} />
            {activeLayout.id === config?.idle_layout_id ? 'Idle Layout' : 'Set Idle'}
          </Button>
        </div>
      )}

      <div className="flex-1" />

      <div className="flex items-center gap-1 bg-black/30 rounded-md px-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => onZoomChange(Math.max(1, zoom - 1))}
          disabled={zoom <= 1}
        >
          <ZoomOut size={16} />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="min-w-[64px] text-xs">
              {zoom}×
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="center">
            {ZOOM_OPTIONS.map((z) => (
              <DropdownMenuItem key={z} onClick={() => onZoomChange(z)}>
                {z}×
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => onZoomChange(Math.min(6, zoom + 1))}
          disabled={zoom >= 6}
        >
          <ZoomIn size={16} />
        </Button>
      </div>

      <Button
        variant={useMockData ? 'default' : 'secondary'}
        size="sm"
        onClick={onToggleMockData}
        className={`gap-2 ${useMockData ? 'bg-amber-500 hover:bg-amber-600 text-black' : 'text-green-400'}`}
      >
        {useMockData ? <FlaskConical size={16} /> : <Radio size={16} />}
        {useMockData ? 'Mock' : 'Live'}
      </Button>

      {activeLayout && (
        <Button onClick={onSave} className="gap-2">
          <Save size={16} />
          Save
        </Button>
      )}
    </div>
  );
}
