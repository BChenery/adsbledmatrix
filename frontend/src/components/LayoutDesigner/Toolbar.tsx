import { useState, useEffect } from 'react';
import { Layout } from '@/types/layout';
import { UserConfig } from '@/types/config';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Save, Plus, ChevronDown, Radio, FlaskConical, ZoomIn, ZoomOut, Monitor, Moon, Eye, Trash2 } from 'lucide-react';

interface ToolbarProps {
  layouts: Layout[];
  activeLayout: Layout | null;
  config: UserConfig | null;
  onSelectLayout: (layout: Layout | null) => void;
  onNew: () => void;
  onSave: () => void;
  onDelete?: () => void;
  canDelete?: boolean;
  useMockData: boolean;
  onToggleMockData: () => void;
  zoom: number;
  onZoomChange: (zoom: number) => void;
  onSetAsActive: () => void;
  onSetAsIdle: () => void;
  panelPreview: boolean;
  onTogglePanelPreview: () => void;
  layoutName: string;
  onRename: (name: string) => Promise<void>;
  canRename: boolean;
}

const ZOOM_OPTIONS = [1, 2, 3, 4, 5, 6];

export default function Toolbar({
  layouts,
  activeLayout,
  config,
  onSelectLayout,
  onNew,
  onSave,
  onDelete,
  canDelete = false,
  useMockData,
  onToggleMockData,
  zoom,
  onZoomChange,
  onSetAsActive,
  onSetAsIdle,
  panelPreview,
  onTogglePanelPreview,
  layoutName,
  onRename,
  canRename,
}: ToolbarProps) {
  const [draftName, setDraftName] = useState(layoutName);

  useEffect(() => {
    setDraftName(layoutName);
  }, [layoutName]);

  return (
    <div className="flex flex-col gap-2 border-b border-led-line bg-led-dark/95 px-3 py-2.5 backdrop-blur-xl sm:px-4">
      <div className="flex items-center gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-1">
          <Input
            type="text"
            value={draftName}
            onChange={(e) => setDraftName(e.target.value)}
            onBlur={async () => {
              if (!canRename || draftName === layoutName) return;
              try {
                await onRename(draftName);
              } catch {
                setDraftName(layoutName);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.currentTarget.blur();
              }
            }}
            disabled={!canRename}
            placeholder="Layout name"
            title={canRename ? 'Edit name, then press Enter or click away to rename' : undefined}
            aria-label="Layout name"
            className="h-9 min-w-0 flex-1 bg-led-black text-sm sm:max-w-[220px]"
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="secondary" size="icon" className="h-9 w-9 shrink-0">
                <ChevronDown size={14} />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              {layouts.map((l) => (
                <DropdownMenuItem key={l.id} onClick={() => onSelectLayout(l)}>
                  <div>
                    <div className="font-medium">{l.name}</div>
                    <div className="font-mono text-xs text-led-faint">{l.width}×{l.height}</div>
                  </div>
                </DropdownMenuItem>
              ))}
              {layouts.length === 0 && (
                <div className="px-2 py-3 text-sm text-led-faint">No layouts yet</div>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <Button variant="secondary" size="icon" onClick={onNew} className="h-9 w-9 shrink-0">
          <Plus size={16} />
        </Button>

        {activeLayout && (
          <Button onClick={onSave} size="sm" className="gap-2 shrink-0">
            <Save size={14} />
            <span className="hidden xs:inline sm:inline">Save</span>
          </Button>
        )}

        {activeLayout?.id && onDelete && (
          <Button
            variant="secondary"
            size="icon"
            onClick={onDelete}
            disabled={!canDelete}
            className="h-9 w-9 shrink-0 text-red-400 hover:bg-red-500/15 hover:text-red-300 disabled:opacity-40"
            title={
              canDelete
                ? 'Delete this layout'
                : 'At least one layout must remain'
            }
            aria-label={canDelete ? 'Delete layout' : 'Cannot delete last layout'}
          >
            <Trash2 size={16} />
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {activeLayout?.id && (
          <>
            {activeLayout.id === config?.active_layout_id && (
              <Badge variant="default" className="gap-1">
                <Monitor size={11} />
                Active
              </Badge>
            )}
            {activeLayout.id === config?.idle_layout_id && (
              <Badge variant="secondary" className="gap-1 text-led-accent">
                <Moon size={11} />
                Idle
              </Badge>
            )}
          </>
        )}

        <Button
          variant={activeLayout?.id === config?.active_layout_id ? 'default' : 'secondary'}
          size="sm"
          onClick={onSetAsActive}
          disabled={!activeLayout?.id}
          className="gap-1.5"
        >
          <Monitor size={13} />
          <span className="hidden sm:inline">
            {activeLayout?.id === config?.active_layout_id ? 'Active' : 'Set active'}
          </span>
          <span className="sm:hidden">Active</span>
        </Button>
        <Button
          variant={activeLayout?.id === config?.idle_layout_id ? 'default' : 'secondary'}
          size="sm"
          onClick={onSetAsIdle}
          disabled={!activeLayout?.id}
          className="gap-1.5"
        >
          <Moon size={13} />
          <span className="hidden sm:inline">
            {activeLayout?.id === config?.idle_layout_id ? 'Idle' : 'Set idle'}
          </span>
          <span className="sm:hidden">Idle</span>
        </Button>

        <div className="ml-auto flex items-center gap-1 rounded-full border border-led-line bg-led-black/50 px-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => onZoomChange(Math.max(1, zoom - 1))}
            disabled={zoom <= 1}
          >
            <ZoomOut size={15} />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="min-w-[48px] font-mono text-xs">
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
            <ZoomIn size={15} />
          </Button>
        </div>

        <Button
          variant={panelPreview ? 'default' : 'secondary'}
          size="sm"
          onClick={onTogglePanelPreview}
          className="gap-1.5"
          title="Show canvas as the physical panels see it"
        >
          <Eye size={14} />
          <span className="hidden md:inline">{panelPreview ? 'Panel' : 'Logical'}</span>
        </Button>

        <Button
          variant={useMockData ? 'default' : 'secondary'}
          size="sm"
          onClick={onToggleMockData}
          className={`gap-1.5 ${useMockData ? 'bg-led-amber text-led-black hover:bg-led-amber/90' : ''}`}
        >
          {useMockData ? <FlaskConical size={14} /> : <Radio size={14} />}
          <span className="hidden sm:inline">{useMockData ? 'Mock' : 'Live'}</span>
        </Button>
      </div>
    </div>
  );
}
