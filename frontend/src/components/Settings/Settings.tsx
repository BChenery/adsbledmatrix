import React, { useEffect, useRef, useState } from 'react';
import { api } from '@/api/client';
import { UserConfig } from '@/types/config';
import { Layout } from '@/types/layout';
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
import { Save, RotateCcw, Moon, Sun, Monitor, Cpu, Activity, LayoutTemplate, Plane, ListOrdered, Crosshair, Radio, Power, PowerOff, Loader2, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { useDisplayStatus } from '@/hooks/useDisplayStatus';
import { useDisplayPreview } from '@/hooks/useDisplayPreview';
import { useDisplayDiagnostics } from '@/hooks/useDisplayDiagnostics';
import { useLayouts } from '@/hooks/useLayout';
import { useAircraft } from '@/hooks/useAircraft';
import { useReceiverStatus } from '@/hooks/useReceiverStatus';
import { useUpdateProgress } from '@/hooks/useUpdateProgress';
import { UPDATE_STAGES, type UpdateProgressStatus } from '@/types/update';
import LocationLookup from '@/components/LocationLookup/LocationLookup';
import LocationMapPreview from '@/components/LocationLookup/LocationMapPreview';
import SettingsSection from './SettingsSection';
import FormGrid from './FormGrid';

export default function Settings() {
  const [config, setConfig] = useState<UserConfig | null>(null);
  const [powerAction, setPowerAction] = useState<'reboot' | 'shutdown' | null>(null);
  const [brightnessSaved, setBrightnessSaved] = useState(false);
  const brightnessTimer = useRef<number | null>(null);
  type UpdateStatus = {
    current_version: string;
    latest_version: string;
    update_available: boolean;
    release_notes?: string;
    published_at?: string;
    error?: string;
  };
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus | null>(null);
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [updateActive, setUpdateActive] = useState(false);
  const [updateSessionStartedAt, setUpdateSessionStartedAt] = useState<string | null>(null);
  const { progress: updateProgress, unreachable: updateUnreachable } = useUpdateProgress(
    updateActive,
    updateSessionStartedAt,
  );

  useEffect(() => {
    api.get<UserConfig>('/api/config').then((raw) => {
      setConfig({
        ...raw,
        cycle_count: raw.cycle_count ?? 3,
        proximity_focus_enabled: raw.proximity_focus_enabled ?? false,
        proximity_focus_km: raw.proximity_focus_km ?? 3,
        layout_rotation_enabled: raw.layout_rotation_enabled ?? false,
        layout_playlist_ids: raw.layout_playlist_ids ?? [],
        layout_rotation_interval_sec: raw.layout_rotation_interval_sec ?? 30,
      });
    });
    api.get<UpdateStatus>('/api/system/update').then(setUpdateStatus).catch(() => {});
  }, []);

  useEffect(() => {
    if (
      updateProgress?.status === 'completed' ||
      updateProgress?.status === 'failed' ||
      updateProgress?.status === 'up_to_date'
    ) {
      // Only auto-dismiss after a run that belongs to this session.
      if (
        updateSessionStartedAt &&
        updateProgress.started_at &&
        updateProgress.started_at < updateSessionStartedAt
      ) {
        return;
      }
      const delay = updateProgress.status === 'failed' ? 12000 : 8000;
      const timer = setTimeout(() => {
        setUpdateActive(false);
        setUpdateSessionStartedAt(null);
        if (updateProgress.status === 'completed' || updateProgress.status === 'up_to_date') {
          api.get<UpdateStatus>('/api/system/update').then(setUpdateStatus).catch(() => {});
        }
      }, delay);
      return () => clearTimeout(timer);
    }
  }, [updateProgress?.status, updateProgress?.started_at, updateSessionStartedAt]);

  const update = (field: keyof UserConfig, value: unknown) => {
    if (!config) return;
    // Enabling night/sleep without ever touching the time inputs left start/end null
    // while the UI showed defaults — so the engine never entered those windows.
    if (field === 'night_mode' && value === true) {
      setConfig({
        ...config,
        night_mode: true,
        night_mode_start: config.night_mode_start || '22:00',
        night_mode_end: config.night_mode_end || '06:00',
      });
      return;
    }
    if (field === 'sleep_mode' && value === true) {
      setConfig({
        ...config,
        sleep_mode: true,
        sleep_mode_start: config.sleep_mode_start || '23:00',
        sleep_mode_end: config.sleep_mode_end || '06:00',
      });
      return;
    }
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

  const handleCheckUpdate = async () => {
    setCheckingUpdate(true);
    try {
      const status = await api.get<UpdateStatus>('/api/system/update');
      setUpdateStatus(status);
    } catch {
      toast.error('Failed to check for updates');
    } finally {
      setCheckingUpdate(false);
    }
  };

  const handleApplyUpdate = async () => {
    const startedAt = new Date().toISOString();
    setUpdateSessionStartedAt(startedAt);
    setUpdateActive(true);
    try {
      const res = await api.post<{ status: string; message: string; started_at?: string }>(
        '/api/system/update',
      );
      if (res.status === 'error') {
        toast.error(res.message || 'Failed to trigger update');
        setUpdateActive(false);
        setUpdateSessionStartedAt(null);
        return;
      }
      if (res.status === 'already_running') {
        // Attach to the in-flight run; do not filter by this click time.
        setUpdateSessionStartedAt(null);
      } else if (res.started_at) {
        setUpdateSessionStartedAt(res.started_at);
      }
      toast.success(res.message || 'Update started');
    } catch {
      toast.error('Failed to trigger update');
      setUpdateActive(false);
      setUpdateSessionStartedAt(null);
    }
  };

  const updateStageIndex = (status: UpdateProgressStatus | undefined): number => {
    if (!status) return 0;
    if (status === 'failed') return -1;
    if (status === 'up_to_date' || status === 'completed') return UPDATE_STAGES.length - 1;
    if (status === 'already_running') return 1;
    const idx = UPDATE_STAGES.findIndex((s) => s.key === status);
    return idx >= 0 ? idx : 0;
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
    if (config.receiver_source === 'network') {
      if (!isValidHost(config.network_readsb_host) || !isValidPort(config.network_readsb_port)) {
        toast.error('Please enter a valid network receiver host and port');
        return;
      }
    }
    const payload: UserConfig = {
      ...config,
      display_mode: config.display_mode === 'cycle3' ? 'cycle' : config.display_mode,
      cycle_count: clampInt(config.cycle_count ?? 3, 1, 10),
      proximity_focus_km: Math.min(50, Math.max(0.1, config.proximity_focus_km ?? 3)),
      layout_rotation_interval_sec: clampInt(config.layout_rotation_interval_sec ?? 30, 5, 600),
      layout_playlist_ids: config.layout_playlist_ids ?? [],
      // Persist the same defaults the time inputs display when modes are enabled.
      night_mode_start: config.night_mode
        ? (config.night_mode_start || '22:00')
        : config.night_mode_start,
      night_mode_end: config.night_mode
        ? (config.night_mode_end || '06:00')
        : config.night_mode_end,
      sleep_mode_start: config.sleep_mode
        ? (config.sleep_mode_start || '23:00')
        : config.sleep_mode_start,
      sleep_mode_end: config.sleep_mode
        ? (config.sleep_mode_end || '06:00')
        : config.sleep_mode_end,
    };
    if (payload.layout_rotation_enabled && payload.layout_playlist_ids.length > 0) {
      payload.active_layout_id = payload.layout_playlist_ids[0];
    }
    try {
      const saved = await api.put<UserConfig>('/api/config', payload);
      setConfig({
        ...payload,
        ...saved,
        night_mode_start: saved.night_mode_start ?? payload.night_mode_start,
        night_mode_end: saved.night_mode_end ?? payload.night_mode_end,
        sleep_mode_start: saved.sleep_mode_start ?? payload.sleep_mode_start,
        sleep_mode_end: saved.sleep_mode_end ?? payload.sleep_mode_end,
      });
      toast.success('Settings saved');
    } catch {
      toast.error('Failed to save settings');
    }
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
  const receiverStatus = useReceiverStatus();

  const activeLayout = layouts.find((l) => l.id === config?.active_layout_id);
  const idleLayout = layouts.find((l) => l.id === config?.idle_layout_id);
  const focusLayout = layouts.find((l) => l.id === config?.proximity_focus_layout_id);
  const isCycleMode = config?.display_mode === 'cycle' || config?.display_mode === 'cycle3';
  const cycleCount = clampInt(config?.cycle_count ?? 3, 1, 10);
  const distanceUnit = config?.distance_unit || 'km';
  const proximityDisplay = config
    ? roundDistance(kmToDisplay(config.proximity_focus_km ?? 3, distanceUnit))
    : 3;

  if (!config) return <div className="p-6 text-white/50">Loading...</div>;

  return (
    <main className="max-w-3xl mx-auto px-4 py-6 pb-24 space-y-4 md:space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Settings</h1>
        {brightnessSaved && (
          <span className="text-xs text-led-accent">Brightness saved</span>
        )}
      </header>

      <SettingsSection title="LED Matrix Status" icon={Cpu}>
        <div className="space-y-3">
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

          <div className="space-y-2 pt-2 border-t border-white/10">
            <div className="text-sm text-white/70 flex items-center gap-2">
              <Monitor size={14} />
              Live Matrix Preview
            </div>
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
          </div>
        </div>
      </SettingsSection>

      <SettingsSection title="Receiver" icon={Radio} description="Choose and configure the ADS-B data source.">
        <div className="space-y-2">
          <Label>ADS-B source</Label>
          <Select
            value={config.receiver_source}
            onValueChange={(v) => update('receiver_source', v)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="local">Local RTL-SDR</SelectItem>
              <SelectItem value="network">Network receiver</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-white/40">
            {config.receiver_source === 'local'
              ? 'Use the RTL-SDR receiver connected directly to this device.'
              : 'Connect to a remote readsb receiver over the network.'}
          </p>
        </div>

        {config.receiver_source === 'network' && (
          <div className="space-y-3">
            <FormGrid>
              <div className="space-y-2">
                <Label>Host</Label>
                <Input
                  type="text"
                  placeholder="10.0.0.158"
                  value={config.network_readsb_host || ''}
                  onChange={(e) => update('network_readsb_host', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Port</Label>
                <Input
                  type="number"
                  min={1}
                  max={65535}
                  value={config.network_readsb_port}
                  onChange={(e) => update('network_readsb_port', parseInt(e.target.value, 10) || 0)}
                />
              </div>
            </FormGrid>
            <Button
              variant="secondary"
              size="sm"
              className="w-full gap-2 text-xs"
              onClick={async () => {
                try {
                  const res = await api.post<{ reachable: boolean; message: string }>('/api/config/test-receiver', {
                    host: config.network_readsb_host,
                    port: config.network_readsb_port,
                  });
                  if (res.reachable) {
                    toast.success(res.message);
                  } else {
                    toast.error(res.message);
                  }
                } catch {
                  toast.error('Failed to test receiver connection');
                }
              }}
              disabled={!isValidHost(config.network_readsb_host) || !isValidPort(config.network_readsb_port)}
            >
              <Activity size={14} />
              Test connection
            </Button>
          </div>
        )}

        <div className="flex items-center justify-between text-xs border-t border-white/10 pt-3">
          <span className="text-white/40">
            {receiverStatus
              ? `${receiverStatus.readsb_host}:${receiverStatus.readsb_port}`
              : 'Checking status...'}
          </span>
          {receiverStatus && (
            <span
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full ${
                receiverStatus.receiver_connected
                  ? 'bg-green-500/20 text-green-400'
                  : 'bg-red-500/20 text-red-400'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${receiverStatus.receiver_connected ? 'bg-green-400' : 'bg-red-400'}`} />
              {receiverStatus.receiver_connected ? 'Connected' : 'Disconnected'}
            </span>
          )}
        </div>
      </SettingsSection>

      <SettingsSection title="Display" icon={LayoutTemplate} description="Choose what appears on the matrix when aircraft are detected or when idle.">
        <div className="space-y-4">
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
        </div>

        <Separator />

        <div className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <Label className="flex items-center gap-2">
              <Plane size={14} className="text-white/50" />
              When aircraft are detected
            </Label>
            <Badge variant="outline" className="text-xs px-1.5 py-0 gap-1">
              <Radio size={10} />
              {aircraft.length} in range
            </Badge>
          </div>
          <Select
            value={isCycleMode ? 'cycle' : config.display_mode}
            onValueChange={(v) => update('display_mode', v)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="closest">Closest aircraft only</SelectItem>
              <SelectItem value="cycle">Cycle nearest aircraft</SelectItem>
              <SelectItem value="list">Show list of nearby aircraft</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-white/40">
            {config.display_mode === 'closest' && (aircraft.length <= 1 ? 'Only one aircraft in range, so the display stays on it.' : 'Keeps the display focused on the single closest aircraft.')}
            {isCycleMode && (aircraft.length <= 1 ? 'Cycle mode is on, but only one aircraft is in range. It will switch when more are detected.' : `Rotates through the ${Math.min(cycleCount, aircraft.length)} nearest aircraft every ${config.cycle_interval_sec} seconds.`)}
            {config.display_mode === 'list' && 'Uses a layout that can show multiple aircraft at once. Pick a list-capable layout below.'}
          </p>
        </div>

        {isCycleMode && (
          <FormGrid>
            <div className="space-y-2">
              <Label>Number of aircraft to cycle</Label>
              <Input
                type="number"
                min={1}
                max={10}
                value={cycleCount}
                onChange={(e) => update('cycle_count', clampInt(parseInt(e.target.value || '3', 10), 1, 10))}
                className="w-24"
              />
            </div>
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
          </FormGrid>
        )}

        <Separator />

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <Label className="flex items-center gap-2">
                <Crosshair size={14} className="text-white/50" />
                Highlight aircraft when they get close
              </Label>
              <p className="text-xs text-white/40 mt-0.5">
                When an aircraft is within this distance, the display locks onto it so you can identify what you hear.
              </p>
            </div>
            <Switch
              checked={!!config.proximity_focus_enabled}
              onCheckedChange={(v) => update('proximity_focus_enabled', v)}
            />
          </div>
          {config.proximity_focus_enabled && (
            <div className="space-y-3">
              <div className="space-y-2">
                <Label>Focus distance</Label>
                <div className="flex items-center gap-3">
                  <Input
                    type="number"
                    min={0.1}
                    max={distanceUnit === 'mi' ? 31 : 50}
                    step={0.1}
                    value={proximityDisplay}
                    onChange={(e) => {
                      const raw = parseFloat(e.target.value);
                      if (Number.isNaN(raw)) return;
                      update('proximity_focus_km', displayToKm(raw, distanceUnit));
                    }}
                    className="w-28"
                  />
                  <span className="text-sm text-white/60">{distanceUnit}</span>
                </div>
              </div>
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <Label className="flex items-center gap-2">
                      <LayoutTemplate size={14} className="text-white/50" />
                      Focus layout (optional)
                    </Label>
                    <p className="text-xs text-white/40 mt-0.5">
                      Used only while an aircraft is within the focus distance. Leave unset to keep the current layout.
                    </p>
                  </div>
                  {focusLayout && (
                    <Badge variant="outline" className="shrink-0">Focus</Badge>
                  )}
                </div>
                <LayoutPicker
                  layouts={layouts}
                  selectedId={config.proximity_focus_layout_id ?? undefined}
                  onSelect={(id) => update('proximity_focus_layout_id', id ?? null)}
                  highlightMode="active"
                  selectLabel="Use for focus"
                />
              </div>
            </div>
          )}
        </div>

        <Separator />

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <Label className="flex items-center gap-2">
                <LayoutTemplate size={14} className="text-white/50" />
                Rotate layouts for variety
              </Label>
              <p className="text-xs text-white/40 mt-0.5">
                Cycle through multiple aircraft layouts so the display has more variety.
              </p>
            </div>
            <Switch
              checked={!!config.layout_rotation_enabled}
              onCheckedChange={(v) => {
                setConfig({
                  ...config,
                  layout_rotation_enabled: v,
                  layout_playlist_ids:
                    v && (!config.layout_playlist_ids || config.layout_playlist_ids.length === 0) && config.active_layout_id
                      ? [config.active_layout_id]
                      : (config.layout_playlist_ids ?? []),
                });
              }}
            />
          </div>

          {config.layout_rotation_enabled ? (
            <>
              <div className="space-y-2">
                <Label>Switch layout every</Label>
                <div className="flex items-center gap-3">
                  <Input
                    type="number"
                    min={5}
                    max={600}
                    value={config.layout_rotation_interval_sec ?? 30}
                    onChange={(e) => update('layout_rotation_interval_sec', clampInt(parseInt(e.target.value || '30', 10), 5, 600))}
                    className="w-24"
                  />
                  <span className="text-sm text-white/60">seconds</span>
                </div>
              </div>
              <div className="space-y-2">
                <Label>Layout playlist</Label>
                <p className="text-xs text-white/40">
                  Click layouts to add or remove them. Order is the order you selected them.
                </p>
                <LayoutPlaylistPicker
                  layouts={layouts}
                  selectedIds={config.layout_playlist_ids ?? []}
                  onChange={(ids) => {
                    setConfig({
                      ...config,
                      layout_playlist_ids: ids,
                      active_layout_id: ids.length > 0 ? ids[0] : config.active_layout_id,
                    });
                  }}
                />
              </div>
            </>
          ) : (
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
          )}
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
      </SettingsSection>

      <SettingsSection title="Location & Units" icon={Monitor} description="Set your receiver location and preferred units.">
        <LocationLookup
          latitude={config.latitude}
          longitude={config.longitude}
          onChange={(lat, lon) => {
            update('latitude', lat);
            update('longitude', lon);
          }}
        />

        <FormGrid>
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
        </FormGrid>

        <LocationMapPreview latitude={config.latitude} longitude={config.longitude} />

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
      </SettingsSection>

      <SettingsSection title="Night Mode" icon={Moon} description="Dim or turn off the display during scheduled hours.">
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
          <div className="space-y-3">
            <p className="text-xs text-white/50">
              During these hours the display dims to 20% brightness.
            </p>
            <FormGrid>
              <div className="space-y-2">
                <Label>Dim Start Time</Label>
                <Input
                  type="time"
                  value={config.night_mode_start || '22:00'}
                  onChange={(e) => update('night_mode_start', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Dim End Time</Label>
                <Input
                  type="time"
                  value={config.night_mode_end || '06:00'}
                  onChange={(e) => update('night_mode_end', e.target.value)}
                />
              </div>
            </FormGrid>
            {config.timezone && (
              <p className="text-xs text-white/40">
                Detected timezone: <span className="text-white/60">{config.timezone}</span>
              </p>
            )}
          </div>
        )}

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {config.sleep_mode ? <Moon size={16} /> : <Sun size={16} />}
            <span className="text-sm">Sleep Display</span>
          </div>
          <Switch
            checked={config.sleep_mode}
            onCheckedChange={(v) => update('sleep_mode', v)}
          />
        </div>

        {config.sleep_mode && (
          <div className="space-y-3">
            <p className="text-xs text-white/50">
              During these hours the display turns off completely. Sleep overrides dim if windows overlap.
            </p>
            <FormGrid>
              <div className="space-y-2">
                <Label>Sleep Start Time</Label>
                <Input
                  type="time"
                  value={config.sleep_mode_start || '23:00'}
                  onChange={(e) => update('sleep_mode_start', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Sleep End Time</Label>
                <Input
                  type="time"
                  value={config.sleep_mode_end || '06:00'}
                  onChange={(e) => update('sleep_mode_end', e.target.value)}
                />
              </div>
            </FormGrid>
            {config.timezone && (
              <p className="text-xs text-white/40">
                Detected timezone: <span className="text-white/60">{config.timezone}</span>
              </p>
            )}
          </div>
        )}
      </SettingsSection>

      <SettingsSection title="System" icon={Power} description="Update, reboot, or reset the device.">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm">Auto-update</span>
            <Switch
              checked={config.auto_update}
              onCheckedChange={(v) => update('auto_update', v)}
            />
          </div>

          {updateStatus ? (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-white/60">Current</span>
                <span className="font-medium">{updateStatus.current_version}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/60">Latest</span>
                <span className="font-medium">{updateStatus.latest_version}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-white/60">Status</span>
                {updateStatus.update_available ? (
                  <span className="text-amber-400">Update available</span>
                ) : (
                  <span className="text-green-400">Up to date</span>
                )}
              </div>
              {updateStatus.error && (
                <div className="text-xs text-red-400">{updateStatus.error}</div>
              )}
              <div className="flex flex-col gap-3 pt-1">
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleCheckUpdate}
                    disabled={checkingUpdate || updateActive}
                  >
                    {checkingUpdate ? 'Checking...' : 'Check now'}
                  </Button>
                  {updateStatus.update_available && (
                    <Button
                      size="sm"
                      onClick={handleApplyUpdate}
                      disabled={updateActive}
                    >
                      {updateActive ? 'Updating...' : 'Trigger update'}
                    </Button>
                  )}
                </div>

                {updateActive && (
                  <div
                    className={`space-y-3 rounded-lg border p-3 ${
                      updateProgress?.status === 'failed'
                        ? 'border-red-500/30 bg-red-950/20'
                        : updateProgress?.status === 'completed'
                          ? 'border-green-500/30 bg-green-950/20'
                          : updateProgress?.status === 'up_to_date'
                            ? 'border-sky-500/30 bg-sky-950/20'
                            : 'border-white/10 bg-white/5'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex min-w-0 items-start gap-2">
                        {updateProgress?.status === 'completed' ? (
                          <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-green-400" />
                        ) : updateProgress?.status === 'failed' ? (
                          <XCircle size={16} className="mt-0.5 shrink-0 text-red-400" />
                        ) : updateProgress?.status === 'up_to_date' ? (
                          <AlertCircle size={16} className="mt-0.5 shrink-0 text-sky-400" />
                        ) : (
                          <Loader2 size={16} className="mt-0.5 shrink-0 animate-spin text-primary" />
                        )}
                        <div className="min-w-0 space-y-0.5">
                          <p className="text-sm font-medium text-white/90">
                            {updateProgress?.status === 'completed'
                              ? 'Update complete'
                              : updateProgress?.status === 'failed'
                                ? 'Update failed'
                                : updateProgress?.status === 'up_to_date'
                                  ? 'No update applied'
                                  : updateProgress?.status === 'installing'
                                    ? 'Installing update'
                                    : updateProgress?.status === 'downloading'
                                      ? 'Downloading update'
                                      : 'Checking for updates'}
                          </p>
                          <p className="text-xs text-white/60">
                            {updateProgress?.message ?? 'Starting update...'}
                          </p>
                        </div>
                      </div>
                      <span className="shrink-0 tabular-nums text-xs font-medium text-white/50">
                        {updateProgress?.progress ?? 0}%
                      </span>
                    </div>

                    <div className="h-2.5 w-full overflow-hidden rounded-full bg-white/10">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ease-out ${
                          updateProgress?.status === 'failed'
                            ? 'bg-red-500'
                            : updateProgress?.status === 'completed'
                              ? 'bg-green-500'
                              : updateProgress?.status === 'up_to_date'
                                ? 'bg-sky-500'
                                : 'bg-primary'
                        }`}
                        style={{
                          width: `${Math.max(2, updateProgress?.progress ?? 0)}%`,
                        }}
                      />
                    </div>

                    <div className="flex items-center justify-between gap-1">
                      {UPDATE_STAGES.map((stage, i) => {
                        const current = updateStageIndex(updateProgress?.status);
                        const isFailed = updateProgress?.status === 'failed';
                        const done = !isFailed && current >= i;
                        const active = !isFailed && current === i;
                        return (
                          <div key={stage.key} className="flex flex-1 flex-col items-center gap-1">
                            <div
                              className={`h-1.5 w-full rounded-full ${
                                done
                                  ? active
                                    ? 'bg-primary'
                                    : 'bg-primary/60'
                                  : 'bg-white/10'
                              }`}
                            />
                            <span
                              className={`text-[10px] ${
                                active
                                  ? 'font-medium text-white/80'
                                  : done
                                    ? 'text-white/50'
                                    : 'text-white/30'
                              }`}
                            >
                              {stage.label}
                            </span>
                          </div>
                        );
                      })}
                    </div>

                    {updateUnreachable &&
                      updateProgress?.status !== 'completed' &&
                      updateProgress?.status !== 'failed' && (
                        <p className="text-xs text-amber-400/90">
                          The LED matrix may go dark while services restart. This page will reconnect automatically.
                        </p>
                      )}

                    {updateProgress?.error && (
                      <p className="text-xs text-red-400">{updateProgress.error}</p>
                    )}

                    {(updateProgress?.status === 'completed' ||
                      updateProgress?.status === 'failed' ||
                      updateProgress?.status === 'up_to_date') && (
                      <button
                        type="button"
                        className="text-xs text-white/50 underline-offset-2 hover:text-white/80 hover:underline"
                        onClick={() => {
                          setUpdateActive(false);
                          setUpdateSessionStartedAt(null);
                        }}
                      >
                        Dismiss
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-sm text-white/50">Loading update status...</div>
          )}
        </div>

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

        <Button variant="destructive" onClick={handleResetOnboarding} className="w-full gap-2">
          <RotateCcw size={16} />
          Reset Onboarding
        </Button>
      </SettingsSection>

      <div className="flex flex-col sm:flex-row gap-3 pt-4">
        <Button
          onClick={handleSave}
          className="w-full sm:flex-1 gap-2"
          disabled={
            config.receiver_source === 'network' &&
            (!isValidHost(config.network_readsb_host) || !isValidPort(config.network_readsb_port))
          }
        >
          <Save size={16} />
          Save Settings
        </Button>
      </div>

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
    </main>
  );
}

function isValidHost(host: string | undefined): boolean {
  return !!host && host.trim().length > 0;
}

function isValidPort(port: number): boolean {
  return Number.isInteger(port) && port >= 1 && port <= 65535;
}

const KM_PER_MI = 1.60934;

function kmToDisplay(km: number, unit: string): number {
  return unit === 'mi' ? km / KM_PER_MI : km;
}

function displayToKm(value: number, unit: string): number {
  return unit === 'mi' ? value * KM_PER_MI : value;
}

function roundDistance(value: number): number {
  return Math.round(value * 10) / 10;
}

function clampInt(value: number, min: number, max: number): number {
  if (Number.isNaN(value)) return min;
  return Math.min(max, Math.max(min, value));
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
  selectLabel,
}: {
  layouts: Layout[];
  selectedId?: number;
  onSelect: (id?: number) => void;
  highlightMode: 'active' | 'idle';
  selectLabel?: string;
}) {
  const useLabel = selectLabel || `Use for ${highlightMode === 'active' ? 'aircraft' : 'idle'}`;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
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
                {layout.is_default && <Badge variant="secondary" className="text-xs px-1 py-0">Default</Badge>}
                {hasList && (
                  <Badge variant="outline" className="text-xs px-1 py-0 flex items-center gap-1">
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
                {isSelected ? 'Selected' : useLabel}
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

function LayoutPlaylistPicker({
  layouts,
  selectedIds,
  onChange,
}: {
  layouts: Layout[];
  selectedIds: number[];
  onChange: (ids: number[]) => void;
}) {
  const toggle = (id: number) => {
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((x) => x !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {layouts.length === 0 && (
        <div className="text-sm text-white/40 col-span-full">No layouts available.</div>
      )}
      {layouts.map((layout) => {
        if (layout.id == null) return null;
        const layoutId = layout.id;
        const order = selectedIds.indexOf(layoutId);
        const isSelected = order >= 0;
        return (
          <button
            key={layoutId}
            type="button"
            onClick={() => toggle(layoutId)}
            className={`text-left rounded-lg border p-3 transition-colors ${
              isSelected
                ? 'border-primary bg-primary/10'
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
              {isSelected && (
                <Badge variant="default" className="shrink-0 text-xs px-1.5 py-0">
                  #{order + 1}
                </Badge>
              )}
            </div>
            {layout.description && (
              <p className="text-xs text-white/50 mt-2 line-clamp-2">{layout.description}</p>
            )}
          </button>
        );
      })}
    </div>
  );
}
