import { useState, useRef, useEffect } from 'react';
import { useLayouts } from '@/hooks/useLayout';
import { useAircraft } from '@/hooks/useAircraft';
import { useDisplayDiagnostics } from '@/hooks/useDisplayDiagnostics';
import { Layout, LayoutElement } from '@/types/layout';
import { UserConfig } from '@/types/config';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { api } from '@/api/client';
import { MOCK_AIRCRAFT_FLEET } from '@/lib/mockAircraft';
import { toast } from 'sonner';
import { normalizeLayoutName } from '@/lib/layoutName';
import Canvas from './Canvas';
import ElementPalette, { QUICK_ADD_PRESETS, ADVANCED_ELEMENTS } from './ElementPalette';
import PropertyPanel from './PropertyPanel';
import Toolbar from './Toolbar';
import { Save, Plus, Layers, SlidersHorizontal, X } from 'lucide-react';

const DEFAULT_LAYOUT: Layout = {
  name: 'New Layout',
  width: 256,
  height: 128,
  is_default: false,
  elements: [],
};

const ALL_PRESETS = [...QUICK_ADD_PRESETS, ...ADVANCED_ELEMENTS];
const ELEMENT_TEMPLATES: Record<string, Partial<LayoutElement>> = Object.fromEntries(
  ALL_PRESETS.map((p) => [p.key, p.template])
);

export default function LayoutDesigner() {
  const { layouts, loading, create, update } = useLayouts();
  const aircraft = useAircraft();
  const diagnostics = useDisplayDiagnostics();
  const [activeLayout, setActiveLayout] = useState<Layout | null>(null);
  const [selectedElement, setSelectedElement] = useState<LayoutElement | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);
  const [newLayoutName, setNewLayoutName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [useMockData, setUseMockData] = useState(false);
  const [panelPreview, setPanelPreview] = useState(false);
  const [zoom, setZoom] = useState(3);
  const [config, setConfig] = useState<UserConfig | null>(null);
  const [mobilePanel, setMobilePanel] = useState<'palette' | 'props' | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.get<UserConfig>('/api/config').then(setConfig);
  }, []);

  const refreshConfig = async () => {
    const fresh = await api.get<UserConfig>('/api/config');
    setConfig(fresh);
  };

  const setAsActive = async () => {
    if (!activeLayout?.id) return;
    await api.put('/api/config', { active_layout_id: activeLayout.id });
    await refreshConfig();
  };

  const setAsIdle = async () => {
    if (!activeLayout?.id) return;
    await api.put('/api/config', { idle_layout_id: activeLayout.id });
    await refreshConfig();
  };

  const handleAddElement = (key: string) => {
    if (!activeLayout) return;
    const template = ELEMENT_TEMPLATES[key];
    if (!template) return;
    const newElement: LayoutElement = {
      ...template,
      z_index: activeLayout.elements.length,
    } as LayoutElement;
    setActiveLayout({
      ...activeLayout,
      elements: [...activeLayout.elements, newElement],
    });
    setSelectedElement(newElement);
  };

  const handleUpdateElement = (updated: LayoutElement) => {
    if (!activeLayout) return;
    setActiveLayout({
      ...activeLayout,
      elements: activeLayout.elements.map((e) =>
        e === selectedElement ? updated : e
      ),
    });
    setSelectedElement(updated);
  };

  const handleDeleteElement = () => {
    if (!activeLayout || !selectedElement) return;
    setActiveLayout({
      ...activeLayout,
      elements: activeLayout.elements.filter((e) => e !== selectedElement),
    });
    setSelectedElement(null);
  };

  const errorMessage = (err: unknown, fallback: string) =>
    err instanceof Error ? err.message : fallback;

  const handleSave = async () => {
    if (!activeLayout) return;
    try {
      if (activeLayout.id) {
        const updated = await update(activeLayout.id, {
          name: activeLayout.name,
          description: activeLayout.description,
          width: activeLayout.width,
          height: activeLayout.height,
          elements: activeLayout.elements,
        });
        setActiveLayout(updated);
        setSelectedElement(null);
        toast.success('Layout saved');
      } else {
        const created = await create(activeLayout);
        setActiveLayout(created);
        toast.success('Layout created');
      }
    } catch (err: unknown) {
      toast.error(`Save failed: ${errorMessage(err, 'Save failed')}`);
    }
  };

  const handleCreateNew = async () => {
    setIsCreating(true);
    try {
      const created = await create({
        ...DEFAULT_LAYOUT,
        name: normalizeLayoutName(newLayoutName, DEFAULT_LAYOUT.name),
      });
      setActiveLayout(created);
      setSelectedElement(null);
      setShowNewModal(false);
      setNewLayoutName('');
      toast.success('Layout created');
    } catch (err: unknown) {
      toast.error(`Create failed: ${errorMessage(err, 'Create failed')}`);
    } finally {
      setIsCreating(false);
    }
  };

  const handleRename = async (name: string) => {
    if (!activeLayout?.id || name === activeLayout.name) return;
    const normalized = normalizeLayoutName(name, activeLayout.name);
    try {
      const updated = await update(activeLayout.id, { name: normalized });
      // Keep unsaved local edits; only apply the renamed name from the server.
      setActiveLayout((prev) =>
        prev ? { ...prev, name: updated.name, updated_at: updated.updated_at } : updated,
      );
      toast.success('Layout renamed');
    } catch (err: unknown) {
      toast.error(`Rename failed: ${errorMessage(err, 'Rename failed')}`);
      throw err;
    }
  };

  const handleSelectLayout = async (layout: Layout | null) => {
    if (!layout || !layout.id) {
      setActiveLayout(layout);
      setSelectedElement(null);
      return;
    }
    const full = await api.get<Layout>(`/api/layouts/${layout.id}`);
    setActiveLayout(full);
    setSelectedElement(null);
  };

  if (loading) {
    return (
      <div className="flex h-[70dvh] items-center justify-center">
        <p className="font-mono text-xs uppercase tracking-[0.12em] text-led-faint">Loading layouts…</p>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100dvh-4.75rem)] flex-col md:h-[calc(100dvh-3.5rem)]">
      <Toolbar
        layouts={layouts}
        activeLayout={activeLayout}
        config={config}
        onSelectLayout={handleSelectLayout}
        onNew={() => setShowNewModal(true)}
        onSave={handleSave}
        useMockData={useMockData}
        onToggleMockData={() => setUseMockData((v) => !v)}
        zoom={zoom}
        onZoomChange={setZoom}
        onSetAsActive={setAsActive}
        onSetAsIdle={setAsIdle}
        panelPreview={panelPreview}
        onTogglePanelPreview={() => setPanelPreview((v) => !v)}
        layoutName={activeLayout?.name || ''}
        onRename={handleRename}
        canRename={!!activeLayout?.id}
      />

      <Dialog open={showNewModal} onOpenChange={setShowNewModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New layout</DialogTitle>
            <DialogDescription>
              Give your layout a name and create it for the {DEFAULT_LAYOUT.width}×{DEFAULT_LAYOUT.height} LED matrix.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="layout-name">Layout name</Label>
              <Input
                id="layout-name"
                placeholder="e.g. My Custom Layout"
                value={newLayoutName}
                onChange={(e) => setNewLayoutName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCreateNew();
                }}
                autoFocus
              />
            </div>
          </div>
          <DialogFooter className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowNewModal(false)} className="flex-1">
              Cancel
            </Button>
            <Button onClick={handleCreateNew} disabled={isCreating} className="flex-1 gap-2">
              <Plus size={16} />
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {activeLayout ? (
        <div className="relative flex min-h-0 flex-1 overflow-hidden">
          <ElementPalette
            onAddElement={(key) => {
              handleAddElement(key);
              setMobilePanel(null);
            }}
          />

          <div className="flex min-w-0 flex-1 flex-col">
            <div className="flex flex-1 items-center justify-center overflow-auto bg-[radial-gradient(circle_at_center,rgba(53,224,255,0.04),transparent_55%),#0a0a0a] p-4 sm:p-8">
              <div ref={canvasRef} className="rounded-lg border border-led-line/80 shadow-panel">
                <Canvas
                  layout={activeLayout}
                  selectedElement={selectedElement}
                  onSelectElement={(el) => {
                    setSelectedElement(el);
                    if (el) setMobilePanel('props');
                  }}
                  onUpdateElement={handleUpdateElement}
                  aircraft={useMockData ? MOCK_AIRCRAFT_FLEET : aircraft}
                  zoom={zoom}
                  flipVertical={panelPreview && (diagnostics?.flip_vertical ?? false)}
                />
              </div>
            </div>

            <div
              className="flex gap-2 border-t border-led-line bg-led-dark/95 px-3 py-2 lg:hidden"
              style={{ paddingBottom: 'calc(0.5rem + env(safe-area-inset-bottom, 0px))' }}
            >
              <Button
                variant={mobilePanel === 'palette' ? 'default' : 'secondary'}
                size="sm"
                className="flex-1 gap-2"
                onClick={() => setMobilePanel((v) => (v === 'palette' ? null : 'palette'))}
              >
                <Layers size={14} />
                Add
              </Button>
              <Button
                variant={mobilePanel === 'props' ? 'default' : 'secondary'}
                size="sm"
                className="flex-1 gap-2"
                onClick={() => setMobilePanel((v) => (v === 'props' ? null : 'props'))}
              >
                <SlidersHorizontal size={14} />
                Props
              </Button>
            </div>
          </div>

          <div className="hidden lg:flex">
            <PropertyPanel
              layout={activeLayout}
              onLayoutChange={setActiveLayout}
              onNameBlur={() => activeLayout?.id && handleRename(activeLayout.name)}
              element={selectedElement}
              onChange={handleUpdateElement}
              onDelete={handleDeleteElement}
            />
          </div>

          {mobilePanel && (
            <div className="absolute inset-0 z-30 flex flex-col justify-end bg-black/55 lg:hidden" onClick={() => setMobilePanel(null)}>
              <div
                className="flex max-h-[70dvh] flex-col overflow-hidden rounded-t-2xl border border-led-line bg-led-dark shadow-panel"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center justify-between border-b border-led-line px-4 py-3">
                  <span className="font-display text-sm font-medium tracking-tight">
                    {mobilePanel === 'palette' ? 'Add elements' : 'Properties'}
                  </span>
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setMobilePanel(null)}>
                    <X size={16} />
                  </Button>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto">
                  {mobilePanel === 'palette' ? (
                    <ElementPalette
                      compact
                      className="border-0"
                      onAddElement={(key) => {
                        handleAddElement(key);
                        setMobilePanel(null);
                      }}
                    />
                  ) : (
                    <PropertyPanel
                      layout={activeLayout}
                      onLayoutChange={setActiveLayout}
                      onNameBlur={() => activeLayout?.id && handleRename(activeLayout.name)}
                      element={selectedElement}
                      onChange={handleUpdateElement}
                      onDelete={() => {
                        handleDeleteElement();
                        setMobilePanel(null);
                      }}
                    />
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
          <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-led-line bg-led-dark text-led-faint">
            <Save size={28} />
          </div>
          <p className="eyebrow mb-2">Designer</p>
          <p className="font-display text-xl font-medium tracking-tight text-[#f5f5f5]">
            Select or create a layout
          </p>
          <p className="mt-2 max-w-sm text-sm text-led-dim">
            Build pixel-perfect LED screens for live aircraft and idle states.
          </p>
          <Button className="mt-6 gap-2" onClick={() => setShowNewModal(true)}>
            <Plus size={16} />
            New layout
          </Button>
        </div>
      )}
    </div>
  );
}
