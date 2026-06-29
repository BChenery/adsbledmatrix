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
import { Save, Plus } from 'lucide-react';

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

  const handleSave = async () => {
    if (!activeLayout) return;
    try {
      if (activeLayout.id) {
        await update(activeLayout.id, {
          name: activeLayout.name,
          width: activeLayout.width,
          height: activeLayout.height,
          elements: activeLayout.elements,
        });
        toast.success('Layout saved');
      } else {
        const created = await create(activeLayout);
        setActiveLayout(created);
        toast.success('Layout created');
      }
    } catch (err: any) {
      const message = err?.response?.detail
        ? JSON.stringify(err.response.detail)
        : err instanceof Error
        ? err.message
        : 'Save failed';
      toast.error(`Save failed: ${message}`);
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
    } catch (err: any) {
      const message = err?.response?.detail
        ? JSON.stringify(err.response.detail)
        : err instanceof Error
        ? err.message
        : 'Create failed';
      toast.error(`Create failed: ${message}`);
    } finally {
      setIsCreating(false);
    }
  };

  const handleRename = async (name: string) => {
    if (!activeLayout?.id || name === activeLayout.name) return;
    const normalized = normalizeLayoutName(name, activeLayout.name);
    try {
      const updated = await update(activeLayout.id, { name: normalized });
      setActiveLayout(updated);
      toast.success('Layout renamed');
    } catch (err: any) {
      const message = err?.response?.detail
        ? JSON.stringify(err.response.detail)
        : err instanceof Error
        ? err.message
        : 'Rename failed';
      toast.error(`Rename failed: ${message}`);
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
    return <div className="p-6 text-white/50">Loading layouts...</div>;
  }

  return (
    <div className="h-screen flex flex-col">
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
            <DialogTitle>New Layout</DialogTitle>
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
        <div className="flex-1 flex overflow-hidden">
          <ElementPalette onAddElement={handleAddElement} />

          <div className="flex-1 overflow-auto bg-led-black flex items-center justify-center p-8">
            <div ref={canvasRef}>
              <Canvas
                layout={activeLayout}
                selectedElement={selectedElement}
                onSelectElement={setSelectedElement}
                onUpdateElement={handleUpdateElement}
                aircraft={useMockData ? MOCK_AIRCRAFT_FLEET : aircraft}
                zoom={zoom}
                flipVertical={panelPreview && (diagnostics?.flip_vertical ?? false)}
              />
            </div>
          </div>

          <PropertyPanel
            layout={activeLayout}
            onLayoutChange={setActiveLayout}
            onNameBlur={() => activeLayout?.id && handleRename(activeLayout.name)}
            element={selectedElement}
            onChange={handleUpdateElement}
            onDelete={handleDeleteElement}
          />
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center text-white/30">
          <Save size={48} className="mb-4 opacity-20" />
          <p className="text-lg">Select or create a layout to begin designing</p>
        </div>
      )}
    </div>
  );
}
