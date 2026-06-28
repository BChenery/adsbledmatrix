import { useState, useRef } from 'react';
import { useLayouts } from '@/hooks/useLayout';
import { useAircraft } from '@/hooks/useAircraft';
import { Layout, LayoutElement } from '@/types/layout';
import { Button } from '@/components/ui/button';
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
  const [activeLayout, setActiveLayout] = useState<Layout | null>(null);
  const [selectedElement, setSelectedElement] = useState<LayoutElement | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);
  const [useMockData, setUseMockData] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);

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
    if (activeLayout.id) {
      await update(activeLayout.id, {
        name: activeLayout.name,
        width: activeLayout.width,
        height: activeLayout.height,
        elements: activeLayout.elements,
      });
    } else {
      const created = await create(activeLayout);
      setActiveLayout(created);
    }
  };

  const handleCreateNew = () => {
    setActiveLayout({ ...DEFAULT_LAYOUT });
    setSelectedElement(null);
    setShowNewModal(false);
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
        onSelectLayout={handleSelectLayout}
        onNew={() => setShowNewModal(true)}
        onSave={handleSave}
        useMockData={useMockData}
        onToggleMockData={() => setUseMockData((v) => !v)}
      />

      <Dialog open={showNewModal} onOpenChange={setShowNewModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Layout</DialogTitle>
            <DialogDescription>
              Create a new layout for the {DEFAULT_LAYOUT.width}×{DEFAULT_LAYOUT.height} LED matrix.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowNewModal(false)} className="flex-1">
              Cancel
            </Button>
            <Button onClick={handleCreateNew} className="flex-1 gap-2">
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
              />
            </div>
          </div>

          <PropertyPanel
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
