import { Layout } from '@/types/layout';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Save, Plus, ChevronDown, Radio, FlaskConical } from 'lucide-react';

interface ToolbarProps {
  layouts: Layout[];
  activeLayout: Layout | null;
  onSelectLayout: (layout: Layout | null) => void;
  onNew: () => void;
  onSave: () => void;
  useMockData: boolean;
  onToggleMockData: () => void;
}

export default function Toolbar({ layouts, activeLayout, onSelectLayout, onNew, onSave, useMockData, onToggleMockData }: ToolbarProps) {
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

      <div className="flex-1" />

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
