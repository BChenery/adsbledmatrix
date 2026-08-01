import { useState, useEffect, useRef } from 'react';
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
import {
  Save,
  Plus,
  ChevronDown,
  Radio,
  FlaskConical,
  ZoomIn,
  ZoomOut,
  Monitor,
  Moon,
  Eye,
  Trash2,
  Play,
  CopyPlus,
  Pencil,
} from 'lucide-react';

interface ToolbarProps {
  layouts: Layout[];
  activeLayout: Layout | null;
  config: UserConfig | null;
  onSelectLayout: (layout: Layout | null) => void;
  onNew: () => void;
  onDuplicate?: () => void;
  canDuplicate?: boolean;
  isDuplicating?: boolean;
  onApply: () => void;
  onSave: () => void;
  isDirty?: boolean;
  isApplied?: boolean;
  isApplying?: boolean;
  isSaving?: boolean;
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
  /** Increment to focus + select the name field (e.g. after duplicate). */
  nameFocusToken?: number;
}

const ZOOM_OPTIONS = [1, 2, 3, 4, 5, 6];

export default function Toolbar({
  layouts,
  activeLayout,
  config,
  onSelectLayout,
  onNew,
  onDuplicate,
  canDuplicate = false,
  isDuplicating = false,
  onApply,
  onSave,
  isDirty = false,
  isApplied = false,
  isApplying = false,
  isSaving = false,
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
  nameFocusToken = 0,
}: ToolbarProps) {
  const [draftName, setDraftName] = useState(layoutName);
  const [nameFocused, setNameFocused] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDraftName(layoutName);
  }, [layoutName]);

  useEffect(() => {
    if (nameFocusToken <= 0) return;
    const input = nameInputRef.current;
    if (!input || input.disabled) return;
    // Wait a tick so the new layout name has rendered.
    const id = window.requestAnimationFrame(() => {
      input.focus();
      input.select();
    });
    return () => window.cancelAnimationFrame(id);
  }, [nameFocusToken]);

  const commitRename = async () => {
    if (!canRename || draftName === layoutName) return;
    try {
      await onRename(draftName);
    } catch {
      setDraftName(layoutName);
    }
  };

  return (
    <div className="flex flex-col gap-2 border-b border-led-line bg-led-dark/95 px-3 py-2.5 backdrop-blur-xl sm:px-4">
      <div className="flex items-center gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-1">
          {/* Document-title style name: looks plain until hover/focus, then clearly editable */}
          <div
            className={`group relative min-w-0 flex-1 sm:max-w-[240px] ${
              canRename ? '' : 'opacity-70'
            }`}
          >
            <Input
              ref={nameInputRef}
              type="text"
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              onFocus={(e) => {
                setNameFocused(true);
                e.currentTarget.select();
              }}
              onBlur={async () => {
                setNameFocused(false);
                await commitRename();
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.currentTarget.blur();
                }
                if (e.key === 'Escape') {
                  setDraftName(layoutName);
                  e.currentTarget.blur();
                }
              }}
              disabled={!canRename}
              placeholder={canRename ? 'Layout name' : 'Select a layout'}
              title={
                canRename
                  ? 'Click to rename — Enter to save, Esc to cancel'
                  : undefined
              }
              aria-label="Layout name — click to rename"
              className={`h-9 min-w-0 bg-led-black pr-8 text-sm font-medium transition-colors ${
                nameFocused
                  ? 'border-led-accent/50'
                  : 'border-transparent hover:border-led-line'
              }`}
            />
            {canRename && (
              <Pencil
                size={13}
                className={`pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-led-faint transition-opacity ${
                  nameFocused ? 'opacity-70' : 'opacity-0 group-hover:opacity-50'
                }`}
                aria-hidden
              />
            )}
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="secondary"
                size="icon"
                className="h-9 w-9 shrink-0"
                title="Switch layout"
                aria-label="Switch layout"
              >
                <ChevronDown size={14} />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              {layouts.map((l) => (
                <DropdownMenuItem
                  key={l.id}
                  onClick={() => onSelectLayout(l)}
                  className={l.id === activeLayout?.id ? 'bg-white/10' : undefined}
                >
                  <div className="min-w-0">
                    <div className="truncate font-medium">
                      {l.name}
                      {l.id === activeLayout?.id ? (
                        <span className="ml-1.5 font-mono text-[10px] uppercase tracking-wide text-led-accent">
                          open
                        </span>
                      ) : null}
                    </div>
                    <div className="font-mono text-xs text-led-faint">
                      {l.width}×{l.height}
                    </div>
                  </div>
                </DropdownMenuItem>
              ))}
              {layouts.length === 0 && (
                <div className="px-2 py-3 text-sm text-led-faint">No layouts yet</div>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <Button
          variant="secondary"
          size="icon"
          onClick={onNew}
          className="h-9 w-9 shrink-0"
          title="New blank layout"
          aria-label="New blank layout"
        >
          <Plus size={16} />
        </Button>

        {onDuplicate && (
          <Button
            variant="secondary"
            size="icon"
            onClick={onDuplicate}
            disabled={!canDuplicate || isDuplicating}
            className="h-9 w-9 shrink-0"
            title="Duplicate this layout — copy everything, then rename"
            aria-label="Duplicate layout"
          >
            <CopyPlus size={16} />
          </Button>
        )}

        {activeLayout && (
          <>
            <Button
              variant="secondary"
              onClick={onApply}
              disabled={isApplying}
              size="sm"
              className="gap-2 shrink-0"
              title="Show this draft on the LED matrix without saving"
            >
              <Play size={14} />
              <span className="hidden xs:inline sm:inline">Apply</span>
            </Button>
            <Button
              onClick={onSave}
              disabled={isSaving}
              size="sm"
              className="gap-2 shrink-0"
              title="Save layout permanently"
            >
              <Save size={14} />
              <span className="hidden xs:inline sm:inline">Save</span>
            </Button>
          </>
        )}

        {isDirty && (
          <Badge variant="secondary" className="hidden shrink-0 gap-1 text-led-amber sm:inline-flex">
            Unsaved
          </Badge>
        )}
        {isApplied && (
          <Badge variant="secondary" className="hidden shrink-0 gap-1 text-led-accent sm:inline-flex">
            Applied
          </Badge>
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
