import React, { useEffect, useRef, useState } from 'react';
import { api } from '@/api/client';
import { UserConfig } from '@/types/config';
import { Layout } from '@/types/layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Save, RotateCcw, Moon, Sun, Monitor, Cpu, Activity, LayoutTemplate, Plane, ListOrdered, Crosshair, Radio, Power, PowerOff } from 'lucide-react';
import { toast } from 'sonner';
import { useDisplayStatus } from '@/hooks/useDisplayStatus';
import { useDisplayPreview } from '@/hooks/useDisplayPreview';
import { useDisplayDiagnostics } from '@/hooks/useDisplayDiagnostics';
import { useLayouts } from '@/hooks/useLayout';
import { useAircraft } from '@/hooks/useAircraft';
import LocationLookup from '@/components/LocationLookup/LocationLookup';

export default function Settings() {
  const [config, setConfig] = useState<UserConfig | null>(null);
  const [powerAction, setPowerAction] = useState<'reboot' | 'shutdown' | null>(null);
  const [brightnessSaved, setBrightnessSaved] = useState(false);
  const brightnessTimer = useRef<number | null>(null);

  useEffect(() => {
    api.get<UserConfig>('/api/config').then(setConfig);
  }, []);

  const update = (field: keyof UserConfig, value: unknown) => {
    if (!config) return;
    setConfig({ ...config, [field]: value });
  };

  const handleBrightnessChange = (value: number) => {
    if (!config) return;
    update('led_matrix_brightness', value);
    setBrightnessSaved(false);

    if (brightnessTimer.current) {
      window.clearTimeout(brightnessTimer.current);
    }
    brightnessTimer.current = window.setTimeout(async () => {
      try {
        await api.put('/api/config', { led_matrix_brightness: value });
        setBrightnessSaved(true);
      } catch {
        toast.error('Failed to update brightness');
      }
    }, 300);
  };

  const handlePowerAction = async () => {
    if (!powerAction) return;
    try {
      if (powerAction === 'reboot') {
        await api.post('/api/system/reboot');
        toast.success('The Pi is rebooting. This page will become unreachable.');
      } else {
        await api.post('/api/system/shutdown');
        toast.success('The Pi is shutting down. Power off once the LEDs go dark.');
      }
    } catch {
      toast.error(`Failed to ${powerAction === 'reboot' ? 'reboot' : 'shut down'} the Pi`);
    } finally {
      setPowerAction(null);
    }
  };

  const handleSave = async () => {
    if (!config) return;
    await api.put('/api/config', config);
    toast.success('Settings saved');
  };

  const handleResetOnboarding = async () => {
    await api.put('/api/config', { onboarding_complete: false });
    window.location.reload();
  };

  const displayStatus = useDisplayStatus();
  const preview = useDisplayPreview();
  const diagnostics = useDisplayDiagnostics();
  const { layouts } = useLayouts();
  const aircraft = useAircraft();

  const activeLayout = layouts.find((l) => l.id === config?.active_layout_id);
  const idleLayout = layouts.find((l) => l.id === config?.idle_layout_id);

  if (!config) return <div className="p-6 text-white/50">Loading...</div>;

  return (
    <div className="p-4 space-y-4">
      <h1 className="text-lg font-semibold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-white/70 flex items-center gap-2">
            <Cpu size={14} />
            LED Matrix Status
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm">Connection</span>
            {displayStatus ? (
              <span
                className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full ${
                  displayStatus.hardware_mode
                    ? 'bg-green-500/20 text-green-400'
                    : 'bg-amber-500/20 text-amber-400'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${displayStatus.hardware_mode ? 'bg-green-400' : 'bg-amber-400'}`} />
                {displayStatus.hardware_mode ? 'Connected' : 'Mock Mode'}
              </span>
            ) : (
              <span className="text-xs text-white/40">Checking...</span>
            )}
          </div>
          {displayStatus && (
            <div className="grid grid-cols-3 gap-3 text-xs text-white/50">
              <div>
                <span className="block text-white/30">Width</span>
                {displayStatus.width}px
              </div>
              <div>
                <span className="block text-white/30">Height</span>
                {displayStatus.height}px
              </div>
              <div>
                <span className="block text-white/30">Brightness</span>
                {displayStatus.brightness}%
              </div>
            </div>
          )}
          {diagnostics && (
            <div className="space-y-2 pt-2 border-t border-white/10">
              <div className="grid grid-cols-2 gap-2 text-xs text-white/50">
                <div>
                  <span className="block text-white/30">Mapping</span>
                  {diagnostics.hardware_mapping}
                </div>
                <div>
                  <span className="block text-white/30">Panels</span>
                  {diagnostics.rows}×{diagnostics.cols} × {diagnostics.chain} chain
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="block text-white/30">SPI</span>
                  <span className={diagnostics.spi_enabled ? 'text-green-400' : 'text-red-400'}>
                    {diagnostics.spi_enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="block text-white/30">GPIO</span>
                  <span className={diagnostics.gpio_access ? 'text-green-400' : 'text-red-400'}>
                    {diagnostics.gpio_access ? 'Accessible' : 'No Access'}
                  </span>
                </div>
              </div>
              <div className="text-xs text-white/30">
                Running as <span className="text-white/50">{diagnostics.user}</span>
                {diagnostics.groups.length > 0 && (
                  <span> · groups: {diagnostics.groups.join(', ')}</span>
                )}
              </div>
              <Button
                variant="secondary"
                size="sm"
                className="w-full gap-2 text-xs"
                onClick={async () => {
                  try {
                    const res = await api.post<{ success: boolean; message: string }>('/api/display/test');
                    if (res.success) {
                      toast.success(res.message);
                    } else {
                      toast.error(res.message);
                    }
                  } catch {
                    toast.error('Failed to run test pattern');
                  }
                }}
                disabled={!diagnostics.hardware_mode}
              >
                <Activity size={14} />
                Test Matrix (Red → Green → Blue)
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-white/70 flex items-center gap-2">
            <Sun size={14} />
            LED Matrix Brightness
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-white/60">Brightness</span>
            <span className="font-medium tabular-nums">{config.led_matrix_brightness}%</span>
          </div>
          <div className="flex items-center gap-3">
            <Moon size={14} className="text-white/30" />
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={config.led_matrix_brightness}
              onChange={(e) => handleBrightnessChange(parseInt(e.target.value, 10))}
              className="slider flex-1"
              style={{ '--brightness': `${config.led_matrix_brightness}%` } as React.CSSProperties}
              aria-label="LED matrix brightness"
            />
            <Sun size={20} className="text-white/70" />
          </div>
          <div className="flex items-center justify-between text-xs">
            <p className="text-white/40">
              Drag to adjust the live LED matrix brightness. Changes are applied immediately.
            </p>
            {brightnessSaved && (
              <span className="text-led-accent transition-opacity duration-500">Saved</span>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-white/70 flex items-center gap-2">
            <Monitor size={14} />
            Live Matrix Preview
          </CardTitle>
        </CardHeader>
        <CardContent>
          {preview.url ? (
            <div className="rounded border border-white/10 overflow-hidden bg-black">
              <img
                src={preview.url}
                alt="Live LED matrix preview"
                className="w-full h-auto object-contain"
                style={{ imageRendering: 'pixelated' }}
              />
            </div>
          ) : (
            <div className="rounded border border-white/10 bg-black flex items-center justify-center h-32">
              <span className="text-xs text-white/30">
                {preview.error ? 'No framebuffer available yet' : 'Loading preview...'}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-white/70">Location</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <LocationLookup
            latitude={config.latitude}
            longitude={config.longitude}
            onChange={(lat, lon) => {
              update('latitude', lat);
              update('longitude', lon);
            }}
          />

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Latitude</Label>
              <Input
                type="number"
                step="any"
                value={config.latitude}
                onChange={(e) => update('latitude', parseFloat(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label>Longitude</Label>
              <Input
                type="number"
                step="any"
                value={config.longitude}
                onChange={(e) => update('longitude', parseFloat(e.target.value))}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-white/70">Units</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <SelectField
              label="Distance"
              value={config.distance_unit}
              options={['km', 'nm', 'mi']}
              onChange={(v) => update('distance_unit', v)}
            />
            <SelectField
              label="Altitude"
              value={config.altitude_unit}
              options={['ft', 'm']}
              onChange={(v) => update('altitude_unit', v)}
            />
            <SelectField
              label="Speed"
              value={config.speed_unit}
              options={['kts', 'kmh', 'mph']}
              onChange={(v) => update('speed_unit', v)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-white/70 flex items-center gap-2">
            <Monitor size={14} />
            Display Behaviour
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <Label className="flex items-center gap-2">
                <Plane size={14} className="text-white/50" />
                When aircraft are detected
              </Label>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 gap-1">
                <Radio size={10} />
                {aircraft.length} in range
              </Badge>
            </div>
            <Select
              value={config.display_mode}
              onValueChange={(v) => update('display_mode', v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="closest">Closest aircraft only</SelectItem>
                <SelectItem value="cycle3">Cycle up to 3 nearest aircraft</SelectItem>
                <SelectItem value="list">Show list of nearby aircraft</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-white/40">
              {config.display_mode === 'closest' && (aircraft.length <= 1 ? 'Only one aircraft in range, so the display stays on it.' : 'Keeps the display focused on the single closest aircraft.')}
              {config.display_mode === 'cycle3' && (aircraft.length <= 1 ? 'Cycle mode is on, but only one aircraft is in range. It will switch when more are detected.' : `Rotates through the ${Math.min(3, aircraft.length)} nearest aircraft every ${config.cycle_interval_sec} seconds.`)}
              {config.display_mode === 'list' && 'Uses a layout that can show multiple aircraft at once. Pick a list-capable layout below.'}
            </p>
          </div>

          {config.display_mode === 'cycle3' && (
            <div className="space-y-2">
              <Label>Switch aircraft every</Label>
              <div className="flex items-center gap-3">
                <Input
                  type="number"
                  min={1}
                  max={60}
                  value={config.cycle_interval_sec}
                  onChange={(e) => update('cycle_interval_sec', parseInt(e.target.value))}
                  className="w-24"
                />
                <span className="text-sm text-white/60">seconds</span>
              </div>
            </div>
          )}

          <Separator />

          <div className="space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <Label className="flex items-center gap-2">
                  <LayoutTemplate size={14} className="text-white/50" />
                  Aircraft layout
                </Label>
                <p className="text-xs text-white/40 mt-0.5">
                  Shown when at least one aircraft is in range.
                </p>
              </div>
              {activeLayout && (
                <Badge variant="default" className="shrink-0">Active</Badge>
              )}
            </div>
            <LayoutPicker
              layouts={layouts}
              selectedId={config.active_layout_id}
              onSelect={(id) => update('active_layout_id', id)}
              highlightMode="active"
            />
          </div>

          <Separator />

          <div className="space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <Label className="flex items-center gap-2">
                  <Crosshair size={14} className="text-white/50" />
                  Idle / scanning layout
                </Label>
                <p className="text-xs text-white/40 mt-0.5">
                  Shown when no aircraft are detected.
                </p>
              </div>
              {idleLayout && (
                <Badge variant="secondary" className="shrink-0">Idle</Badge>
              )}
            </div>
            <LayoutPicker
              layouts={layouts}
              selectedId={config.idle_layout_id}
              onSelect={(id) => update('idle_layout_id', id)}
              highlightMode="idle"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-white/70">Night Mode</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {config.night_mode ? <Moon size={16} /> : <Sun size={16} />}
              <span className="text-sm">Enable Night Mode</span>
            </div>
            <Switch
              checked={config.night_mode}
              onCheckedChange={(v) => update('night_mode', v)}
            />
          </div>
          {config.night_mode && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Start Time</Label>
                <Input
                  type="time"
                  value={config.night_mode_start || '22:00'}
                  onChange={(e) => update('night_mode_start', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>End Time</Label>
                <Input
                  type="time"
                  value={config.night_mode_end || '06:00'}
                  onChange={(e) => update('night_mode_end', e.target.value)}
                />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-white/70">Updates</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <span className="text-sm">Auto-update</span>
            <Switch
              checked={config.auto_update}
              onCheckedChange={(v) => update('auto_update', v)}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-3 pt-4">
        <Button onClick={handleSave} className="flex-1 gap-2">
          <Save size={16} />
          Save Settings
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-white/70 flex items-center gap-2">
            <Power size={14} />
            System Power
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-white/40">
            Reboot or shut down the Raspberry Pi. These actions disconnect the device from the network.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <Button
              variant="secondary"
              className="w-full gap-2"
              onClick={() => setPowerAction('reboot')}
            >
              <RotateCcw size={16} />
              Reboot Pi
            </Button>
            <Button
              variant="destructive"
              className="w-full gap-2"
              onClick={() => setPowerAction('shutdown')}
            >
              <PowerOff size={16} />
              Shut Down Pi
            </Button>
          </div>
        </CardContent>
      </Card>

      <Separator />

      <Button variant="destructive" onClick={handleResetOnboarding} className="w-full gap-2">
        <RotateCcw size={16} />
        Reset Onboarding
      </Button>

      <Dialog open={!!powerAction} onOpenChange={() => setPowerAction(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {powerAction === 'reboot' ? 'Reboot the Pi?' : 'Shut down the Pi?'}
            </DialogTitle>
            <DialogDescription>
              {powerAction === 'reboot'
                ? 'The Raspberry Pi will restart. You will lose connection to this page until it comes back online.'
                : 'The Raspberry Pi will power off. You will need to cycle power to turn it back on.'}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPowerAction(null)}>
              Cancel
            </Button>
            <Button
              variant={powerAction === 'shutdown' ? 'destructive' : 'default'}
              onClick={handlePowerAction}
            >
              {powerAction === 'reboot' ? 'Reboot Pi' : 'Shut Down Pi'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o} value={o}>{o}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function LayoutPicker({
  layouts,
  selectedId,
  onSelect,
  highlightMode,
}: {
  layouts: Layout[];
  selectedId?: number;
  onSelect: (id?: number) => void;
  highlightMode: 'active' | 'idle';
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {layouts.length === 0 && (
        <div className="text-sm text-white/40 col-span-full">No layouts available.</div>
      )}
      {layouts.map((layout) => {
        const isSelected = layout.id === selectedId;
        const elements = layout.elements || [];
        const hasList = elements.some((e) => e.element_type === 'aircraft_list');
        return (
          <div
            key={layout.id}
            className={`relative rounded-lg border p-3 transition-colors ${
              isSelected
                ? highlightMode === 'active'
                  ? 'border-primary bg-primary/10'
                  : 'border-white/40 bg-white/10'
                : 'border-white/10 bg-white/5 hover:border-white/20'
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-sm font-medium">{layout.name}</div>
                <div className="text-xs text-white/40 mt-0.5">
                  {layout.width}×{layout.height}px
                </div>
              </div>
              <div className="flex flex-wrap justify-end gap-1">
                {layout.is_default && <Badge variant="secondary" className="text-[10px] px-1 py-0">Default</Badge>}
                {hasList && (
                  <Badge variant="outline" className="text-[10px] px-1 py-0 flex items-center gap-1">
                    <ListOrdered size={10} />
                    List
                  </Badge>
                )}
              </div>
            </div>
            {layout.description && (
              <p className="text-xs text-white/50 mt-2 line-clamp-2">{layout.description}</p>
            )}
            <div className="flex items-center gap-2 mt-3">
              <Button
                variant={isSelected ? 'default' : 'secondary'}
                size="sm"
                className="flex-1 text-xs"
                onClick={() => onSelect(layout.id)}
              >
                {isSelected ? 'Selected' : `Use for ${highlightMode === 'active' ? 'aircraft' : 'idle'}`}
              </Button>
              {isSelected && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs text-white/50 hover:text-white"
                  onClick={() => onSelect(undefined)}
                >
                  Clear
                </Button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
