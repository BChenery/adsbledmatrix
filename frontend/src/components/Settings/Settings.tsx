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
import { Save, RotateCcw, Moon, Sun } from 'lucide-react';
import { toast } from 'sonner';

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

  if (!config) return <div className="p-6 text-white/50">Loading...</div>;

  return (
    <div className="p-4 space-y-4">
      <h1 className="text-lg font-semibold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-white/70">Location</CardTitle>
        </CardHeader>
        <CardContent>
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
