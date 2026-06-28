import { useEffect, useState } from 'react';
import { api } from '@/api/client';
import { UserConfig } from '@/types/config';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Save, RotateCcw, Moon, Sun, Monitor, Cpu, Activity } from 'lucide-react';
import { toast } from 'sonner';
import { useDisplayStatus } from '@/hooks/useDisplayStatus';
import { useDisplayPreview } from '@/hooks/useDisplayPreview';
import { useDisplayDiagnostics } from '@/hooks/useDisplayDiagnostics';
import LocationLookup from '@/components/LocationLookup/LocationLookup';

export default function Settings() {
  const [config, setConfig] = useState<UserConfig | null>(null);

  useEffect(() => {
    api.get<UserConfig>('/api/config').then(setConfig);
  }, []);

  const update = (field: keyof UserConfig, value: unknown) => {
    if (!config) return;
    setConfig({ ...config, [field]: value });
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
          <CardTitle className="text-sm text-white/70">Display</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <SelectField
            label="Display Mode"
            value={config.display_mode}
            options={['closest', 'cycle3', 'list']}
            onChange={(v) => update('display_mode', v)}
          />
          <div className="space-y-2">
            <Label>Cycle Interval (seconds)</Label>
            <Input
              type="number"
              min={1}
              max={60}
              value={config.cycle_interval_sec}
              onChange={(e) => update('cycle_interval_sec', parseInt(e.target.value))}
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

      <Separator />

      <Button variant="destructive" onClick={handleResetOnboarding} className="w-full gap-2">
        <RotateCcw size={16} />
        Reset Onboarding
      </Button>
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
