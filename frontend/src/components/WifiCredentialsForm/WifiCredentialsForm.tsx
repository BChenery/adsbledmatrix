import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/api/client';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { Eye, EyeOff, Loader2, Lock, RefreshCw, Wifi } from 'lucide-react';

export const WIFI_PASSWORD_MIN = 8;

export interface WifiNetwork {
  ssid: string;
  signal: number;
  secured: boolean;
}

interface WifiScanResponse {
  networks: WifiNetwork[];
  error?: string | null;
}

export function wifiPasswordError(password: string): string {
  if (password.length > 0 && password.length < WIFI_PASSWORD_MIN) {
    return `WPA passwords are at least ${WIFI_PASSWORD_MIN} characters.`;
  }
  return '';
}

function signalTier(signal: number): string {
  if (signal >= 66) return 'text-led-green';
  if (signal >= 33) return 'text-led-accent';
  return 'text-white/30';
}

interface Props {
  ssid: string;
  password: string;
  onSsidChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  autoScan?: boolean;
}

export default function WifiCredentialsForm({
  ssid,
  password,
  onSsidChange,
  onPasswordChange,
  autoScan = true,
}: Props) {
  const [networks, setNetworks] = useState<WifiNetwork[] | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanFailed, setScanFailed] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const passwordRef = useRef<HTMLInputElement>(null);

  const scan = useCallback(async () => {
    setScanning(true);
    try {
      const res = await api.get<WifiScanResponse>('/api/system/wifi/networks');
      const found = res.networks ?? [];
      setNetworks(found);
      setScanFailed(found.length === 0);
    } catch {
      setNetworks([]);
      setScanFailed(true);
    } finally {
      setScanning(false);
    }
  }, []);

  useEffect(() => {
    if (autoScan) void scan();
  }, [autoScan, scan]);

  const passwordError = wifiPasswordError(password);

  return (
    <div className="space-y-3">
      {/* Nearby networks */}
      {networks === null ? (
        <div className="flex items-center gap-2 text-sm text-white/40">
          <Loader2 size={14} className="animate-spin" />
          Scanning for networks…
        </div>
      ) : networks.length > 0 ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-white/40">Nearby networks</span>
            <button
              type="button"
              onClick={() => void scan()}
              disabled={scanning}
              aria-label="Rescan networks"
              className="text-white/40 hover:text-led-accent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-led-accent/60 rounded"
            >
              <RefreshCw size={14} className={cn(scanning && 'animate-spin')} />
            </button>
          </div>
          <div className="max-h-44 overflow-y-auto space-y-1 pr-1">
            {networks.map((net) => (
              <button
                key={net.ssid}
                type="button"
                aria-pressed={ssid === net.ssid}
                onClick={() => {
                  onSsidChange(net.ssid);
                  passwordRef.current?.focus();
                }}
                className={cn(
                  'w-full flex items-center gap-2 p-2.5 rounded-lg bg-led-dark border transition-colors text-left',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-led-accent/60',
                  ssid === net.ssid
                    ? 'border-led-accent bg-led-accent/10'
                    : 'border-white/10 hover:border-led-accent/50',
                )}
              >
                <Wifi size={14} className={signalTier(net.signal)} aria-hidden />
                <span className="flex-1 min-w-0 truncate text-sm">{net.ssid}</span>
                {net.secured && <Lock size={12} className="text-white/30" aria-label="Secured" />}
                <span className="text-xs text-white/30 tabular-nums">{net.signal}%</span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <p className="text-xs text-white/40">
          {scanFailed
            ? 'Network scan unavailable here — type your network name below.'
            : 'No networks found — type the name below.'}
        </p>
      )}

      {/* Credentials */}
      <div className="space-y-2">
        <Label htmlFor="wifi-ssid">Network Name (SSID)</Label>
        <Input
          id="wifi-ssid"
          name="wifi-ssid"
          type="text"
          value={ssid}
          onChange={(e) => onSsidChange(e.target.value)}
          placeholder="e.g. MyHomeWiFi"
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="wifi-password">Password</Label>
        <div className="relative">
          <Input
            id="wifi-password"
            name="wifi-password"
            ref={passwordRef}
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(e) => onPasswordChange(e.target.value)}
            placeholder="WiFi password…"
            autoComplete="off"
            autoCapitalize="off"
            spellCheck={false}
            className="pr-10"
            aria-invalid={!!passwordError}
            aria-describedby={passwordError ? 'wifi-password-error' : undefined}
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-led-accent/60 rounded"
          >
            {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
        {passwordError && (
          <p id="wifi-password-error" className="text-xs text-red-400">
            {passwordError}
          </p>
        )}
      </div>
    </div>
  );
}
