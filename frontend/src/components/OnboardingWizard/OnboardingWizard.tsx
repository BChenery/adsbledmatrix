import { useEffect, useState } from 'react';
import { api } from '@/api/client';
import LocationLookup from '@/components/LocationLookup/LocationLookup';
import LocationMapPreview from '@/components/LocationLookup/LocationMapPreview';
import WifiCredentialsForm, {
  WIFI_PASSWORD_MIN,
  wifiPasswordError,
} from '@/components/WifiCredentialsForm/WifiCredentialsForm';
import { applyPayload } from '@/lib/applyPayload';
import { UserConfig } from '@/types/config';
import { Layout } from '@/types/layout';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { Plane, MapPin, Layout as LayoutIcon, Wifi, Check, Loader2 } from 'lucide-react';

interface LayoutSummary {
  id: number;
  name: string;
  description?: string | null;
  is_default: boolean;
}

interface Props {
  config: UserConfig | null;
}

function validateLocation(lat: string, lon: string): string {
  const latitude = parseFloat(lat);
  const longitude = parseFloat(lon);
  if (!lat.trim() || !lon.trim()) return 'Enter both latitude and longitude.';
  if (isNaN(latitude) || isNaN(longitude)) return 'Coordinates must be numbers, e.g. 51.5074.';
  if (latitude < -90 || latitude > 90) return 'Latitude must be between -90 and 90.';
  if (longitude < -180 || longitude > 180) return 'Longitude must be between -180 and 180.';
  return '';
}

export default function OnboardingWizard({ config }: Props) {
  const [step, setStep] = useState(0);
  const [lat, setLat] = useState('');
  const [lon, setLon] = useState('');
  const [layouts, setLayouts] = useState<LayoutSummary[] | null>(null);
  const [activeLayoutId, setActiveLayoutId] = useState<number | null>(null);
  const [wifiSsid, setWifiSsid] = useState('');
  const [wifiPassword, setWifiPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [rebooting, setRebooting] = useState(false);
  const [finishError, setFinishError] = useState('');
  const [online, setOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Fetch the real seeded layouts when the layout step is first shown
  useEffect(() => {
    if (step !== 2 || layouts !== null) return;
    api
      .get<LayoutSummary[]>('/api/layouts')
      .then((list) => setLayouts(list.filter((l) => l.id !== config?.idle_layout_id)))
      .catch(() => setLayouts([]));
  }, [step, layouts, config?.idle_layout_id]);

  const locationError = validateLocation(lat, lon);
  const passwordError = wifiPasswordError(wifiPassword);
  const canFinish = !loading && !!wifiSsid.trim() && wifiPassword.length >= WIFI_PASSWORD_MIN;

  const previewLayout = async (layoutId: number) => {
    try {
      const full = await api.get<Layout>(`/api/layouts/${layoutId}`);
      await api.post('/api/display/apply-layout', applyPayload(full));
    } catch {
      // Best effort — the live matrix preview is a bonus, not a blocker.
    }
  };

  const handleLayoutSelect = (layoutId: number) => {
    setActiveLayoutId(layoutId);
    void previewLayout(layoutId);
  };

  const handleFinish = async () => {
    if (!canFinish) return;
    setLoading(true);
    setFinishError('');
    try {
      await api.put('/api/config', {
        latitude: parseFloat(lat),
        longitude: parseFloat(lon),
        wifi_ssid: wifiSsid.trim(),
        wifi_password: wifiPassword,
        ...(activeLayoutId != null ? { active_layout_id: activeLayoutId } : {}),
        onboarding_complete: true,
      });
    } catch {
      setFinishError('Could not save your settings. Check the details above and try again.');
      setLoading(false);
      return;
    }

    // Config is saved — switch networks and reboot. The wizard intentionally
    // stays mounted (no onComplete callback) so this status stays visible
    // until the device goes down.
    setRebooting(true);
    try {
      await api.post('/api/system/wifi/apply', {
        ssid: wifiSsid.trim(),
        password: wifiPassword,
      });
    } catch {
      setRebooting(false);
      setFinishError('Settings saved, but the network switch could not start. Try Finish Setup again.');
    } finally {
      setLoading(false);
    }
  };

  const steps = [
    { icon: Plane, label: 'Welcome' },
    { icon: MapPin, label: 'Location' },
    { icon: LayoutIcon, label: 'Layout' },
    { icon: Wifi, label: 'WiFi' },
  ];

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-md">
        {/* Progress */}
        <div className="flex items-center justify-center gap-4 mb-8" role="list" aria-label="Setup progress">
          {steps.map((s, i) => (
            <div
              key={i}
              role="listitem"
              aria-label={`Step ${i + 1}: ${s.label}`}
              aria-current={i === step ? 'step' : undefined}
              className={cn('flex items-center gap-2', i === step ? 'text-led-accent' : i < step ? 'text-led-green' : 'text-white/20')}
            >
              <div className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center border-2',
                i === step ? 'border-led-accent bg-led-accent/10' : i < step ? 'border-led-green bg-led-green/10' : 'border-white/20'
              )}>
                {i < step ? <Check size={14} /> : <s.icon size={16} />}
              </div>
              {i < steps.length - 1 && <div className={cn('w-8 h-px', i < step ? 'bg-led-green' : 'bg-white/10')} />}
            </div>
          ))}
        </div>

        <Card>
          <CardContent className="p-6">
            {step === 0 && (
              <div className="text-center space-y-4">
                <div className="w-16 h-16 rounded-full bg-led-accent/10 flex items-center justify-center mx-auto">
                  <Plane size={32} className="text-led-accent" />
                </div>
                <h1 className="text-2xl font-bold">ADS-B LED Display</h1>
                <p className="text-white/50 text-sm">
                  Welcome! Let's get your device set up to track nearby aircraft on your LED matrix.
                  It takes about a minute — have your home WiFi password handy.
                </p>
                <Button onClick={() => setStep(1)} className="w-full">
                  Get Started
                </Button>
              </div>
            )}

            {step === 1 && (
              <div className="space-y-4">
                <h2 className="text-xl font-semibold flex items-center gap-2">
                  <MapPin size={20} className="text-led-accent" />
                  Set Your Location
                </h2>
                <p className="text-sm text-white/50">
                  Used to calculate distance and direction to aircraft. The nearest town is plenty —
                  you can refine it later in Settings.
                </p>
                <LocationLookup
                  latitude={lat ? parseFloat(lat) : 0}
                  longitude={lon ? parseFloat(lon) : 0}
                  disabled={!online}
                  onChange={(latitude, longitude) => {
                    setLat(latitude.toString());
                    setLon(longitude.toString());
                  }}
                />

                <div className="space-y-3">
                  <div className="space-y-2">
                    <Label htmlFor="onboarding-lat">Latitude</Label>
                    <Input
                      id="onboarding-lat"
                      type="text"
                      inputMode="decimal"
                      value={lat}
                      onChange={(e) => setLat(e.target.value)}
                      placeholder="e.g. 51.5074"
                      autoComplete="off"
                      spellCheck={false}
                      aria-invalid={!!locationError && !!(lat.trim() || lon.trim())}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="onboarding-lon">Longitude</Label>
                    <Input
                      id="onboarding-lon"
                      type="text"
                      inputMode="decimal"
                      value={lon}
                      onChange={(e) => setLon(e.target.value)}
                      placeholder="e.g. -0.1278"
                      autoComplete="off"
                      spellCheck={false}
                      aria-invalid={!!locationError && !!(lat.trim() || lon.trim())}
                    />
                  </div>
                </div>
                {locationError && (
                  <p className={cn('text-xs', lat.trim() || lon.trim() ? 'text-red-400' : 'text-white/40')}>
                    {locationError}
                  </p>
                )}
                {online ? (
                  <LocationMapPreview
                    latitude={lat ? parseFloat(lat) : 0}
                    longitude={lon ? parseFloat(lon) : 0}
                  />
                ) : (
                  <p className="text-xs text-white/40">
                    Map preview needs internet — it will work once the device is online.
                  </p>
                )}
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => setStep(0)} className="flex-1">Back</Button>
                  <Button onClick={() => setStep(2)} disabled={!!locationError} className="flex-1">Continue</Button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-4">
                <h2 className="text-xl font-semibold flex items-center gap-2">
                  <LayoutIcon size={20} className="text-led-accent" />
                  Choose a Layout
                </h2>
                <p className="text-sm text-white/50">
                  Pick what the matrix shows when aircraft are nearby — watch it preview live on your
                  matrix. You can change or design layouts later.
                </p>
                {layouts === null ? (
                  <div className="flex items-center gap-2 text-sm text-white/40">
                    <Loader2 size={14} className="animate-spin" />
                    Loading layouts…
                  </div>
                ) : layouts.length === 0 ? (
                  <p className="text-sm text-white/40">No layouts found — you can design one later.</p>
                ) : (
                  <div className="space-y-2">
                    {layouts.map((l) => (
                      <LayoutOption
                        key={l.id}
                        title={l.name}
                        desc={l.description ?? ''}
                        selected={activeLayoutId === l.id}
                        onClick={() => handleLayoutSelect(l.id)}
                      />
                    ))}
                  </div>
                )}
                {layouts != null && layouts.length > 0 && activeLayoutId == null && (
                  <p className="text-xs text-white/40">Select a layout to continue.</p>
                )}
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => setStep(1)} className="flex-1">Back</Button>
                  <Button
                    onClick={() => setStep(3)}
                    disabled={layouts != null && layouts.length > 0 && activeLayoutId == null}
                    className="flex-1"
                  >
                    Continue
                  </Button>
                </div>
              </div>
            )}

            {step === 3 && !rebooting && (
              <div className="space-y-4">
                <h2 className="text-xl font-semibold flex items-center gap-2">
                  <Wifi size={20} className="text-led-accent" />
                  Connect to WiFi
                </h2>
                <p className="text-sm text-white/50">
                  Pick your home network so the display can reach the internet. The device will
                  restart to join it.
                </p>
                <WifiCredentialsForm
                  ssid={wifiSsid}
                  password={wifiPassword}
                  onSsidChange={setWifiSsid}
                  onPasswordChange={setWifiPassword}
                />
                {finishError && (
                  <p className="text-sm text-red-400">{finishError}</p>
                )}
                {!canFinish && !finishError && (
                  <p className="text-xs text-white/40">
                    {!wifiSsid.trim()
                      ? 'Choose or type your network to continue.'
                      : passwordError || 'Enter the network password to continue.'}
                  </p>
                )}
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => setStep(2)} className="flex-1">Back</Button>
                  <Button onClick={handleFinish} disabled={!canFinish} className="flex-1" aria-busy={loading}>
                    {loading ? 'Saving…' : 'Finish Setup'}
                  </Button>
                </div>
              </div>
            )}

            {rebooting && (
              <div className="text-center space-y-4">
                <div className="w-16 h-16 rounded-full bg-led-green/10 flex items-center justify-center mx-auto">
                  <Check size={32} className="text-led-green" />
                </div>
                <h2 className="text-2xl font-bold">All Set!</h2>
                <p className="text-white/50 text-sm">
                  Your device is restarting and will join <strong>{wifiSsid}</strong>.
                </p>
                <p className="text-white/50 text-sm">
                  Reconnect your phone to your home network, then visit{' '}
                  <strong>http://adsb-display.local</strong> (or check your router for its IP).
                </p>
                <p className="text-white/40 text-xs">
                  If it doesn't appear within a couple of minutes, the device will reopen the
                  ADSB-Display hotspot — reconnect to it and double-check the password.
                </p>
                <div className="flex justify-center">
                  <Loader2 size={24} className="animate-spin text-led-accent" />
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function LayoutOption({ title, desc, selected, onClick }: { title: string; desc: string; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        'w-full text-left p-3 rounded-lg bg-led-dark border transition-colors flex items-center gap-3',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-led-accent/60',
        selected ? 'border-led-accent bg-led-accent/10' : 'border-white/10 hover:border-led-accent/50',
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="font-medium text-sm">{title}</div>
        {desc && <div className="text-xs text-white/40 break-words">{desc}</div>}
      </div>
      {selected && <Check size={16} className="text-led-accent shrink-0" />}
    </button>
  );
}
