import { useState, useEffect, useRef } from 'react';
import { api } from '@/api/client';
import { UserConfig } from '@/types/config';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { Plane, MapPin, Layout, Wifi, Check, Search, Loader2 } from 'lucide-react';

interface Props {
  onComplete: (config: UserConfig) => void;
}

interface NominatimResult {
  display_name: string;
  lat: string;
  lon: string;
}

export default function OnboardingWizard({ onComplete: _onComplete }: Props) {
  const [step, setStep] = useState(0);
  const [lat, setLat] = useState('');
  const [lon, setLon] = useState('');
  const [wifiSsid, setWifiSsid] = useState('');
  const [wifiPassword, setWifiPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [rebooting, setRebooting] = useState(false);
  const [rebootError, setRebootError] = useState('');

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<NominatimResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (resultsRef.current && !resultsRef.current.contains(e.target as Node)) {
        setShowResults(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    if (searchQuery.trim().length < 3) {
      setSearchResults([]);
      setShowResults(false);
      return;
    }
    setSearchLoading(true);
    searchTimeout.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(searchQuery)}&format=json&limit=5`,
          { headers: { 'Accept-Language': 'en' } }
        );
        const data = await res.json();
        setSearchResults(data);
        setShowResults(true);
      } catch {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 500);
  }, [searchQuery]);

  const handleSelectLocation = (result: NominatimResult) => {
    setLat(result.lat);
    setLon(result.lon);
    setSearchQuery(result.display_name.split(',')[0]);
    setShowResults(false);
    setSearchResults([]);
  };

  const handleLocationSubmit = async () => {
    const latitude = parseFloat(lat);
    const longitude = parseFloat(lon);
    if (isNaN(latitude) || isNaN(longitude)) return;
    setStep(2);
  };

  const handleFinish = async () => {
    setLoading(true);
    setRebootError('');
    try {
      // Save user configuration
      await api.put<UserConfig>('/api/config', {
        latitude: parseFloat(lat),
        longitude: parseFloat(lon),
        wifi_ssid: wifiSsid || undefined,
        wifi_password: wifiPassword || undefined,
        onboarding_complete: true,
      });

      // Trigger WiFi switch and reboot
      setRebooting(true);
      await api.post('/api/system/wifi/apply', {
        ssid: wifiSsid,
        password: wifiPassword,
      });
    } catch (e) {
      console.error(e);
      setRebootError('Failed to apply WiFi settings. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const steps = [
    { icon: Plane, label: 'Welcome' },
    { icon: MapPin, label: 'Location' },
    { icon: Layout, label: 'Layout' },
    { icon: Wifi, label: 'WiFi' },
  ];

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-md">
        {/* Progress */}
        <div className="flex items-center justify-center gap-4 mb-8">
          {steps.map((s, i) => (
            <div key={i} className={cn('flex items-center gap-2', i === step ? 'text-led-accent' : i < step ? 'text-led-green' : 'text-white/20')}>
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
                  Search for your location or enter coordinates manually so the display can calculate distances to aircraft.
                </p>

                {/* OSM Search */}
                <div className="relative" ref={resultsRef}>
                  <div className="relative">
                    <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
                    <Input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search city, airport, address..."
                      className="pl-9"
                    />
                  </div>
                  {searchLoading && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      <Loader2 size={16} className="animate-spin text-led-accent" />
                    </div>
                  )}
                  {showResults && searchResults.length > 0 && (
                    <div className="absolute z-20 w-full mt-1 bg-led-panel border border-white/10 rounded-lg shadow-xl max-h-60 overflow-y-auto">
                      {searchResults.map((result, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleSelectLocation(result)}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-white/5 transition-colors border-b border-white/5 last:border-0"
                        >
                          <div className="truncate text-white/80">{result.display_name}</div>
                          <div className="text-xs text-white/30">{parseFloat(result.lat).toFixed(4)}, {parseFloat(result.lon).toFixed(4)}</div>
                        </button>
                      ))}
                    </div>
                  )}
                  {showResults && searchResults.length === 0 && !searchLoading && (
                    <div className="absolute z-20 w-full mt-1 bg-led-panel border border-white/10 rounded-lg shadow-xl p-3 text-sm text-white/40">
                      No results found
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  <div className="space-y-2">
                    <Label>Latitude</Label>
                    <Input
                      type="number"
                      step="any"
                      value={lat}
                      onChange={(e) => setLat(e.target.value)}
                      placeholder="e.g. 51.5074"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Longitude</Label>
                    <Input
                      type="number"
                      step="any"
                      value={lon}
                      onChange={(e) => setLon(e.target.value)}
                      placeholder="e.g. -0.1278"
                    />
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => setStep(0)} className="flex-1">Back</Button>
                  <Button onClick={handleLocationSubmit} className="flex-1">Continue</Button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-4">
                <h2 className="text-xl font-semibold flex items-center gap-2">
                  <Layout size={20} className="text-led-accent" />
                  Choose a Layout
                </h2>
                <p className="text-sm text-white/50">
                  Pick a starting layout for your LED matrix. You can customize it later.
                </p>
                <div className="space-y-2">
                  <LayoutOption
                    title="Aviation Enthusiast"
                    desc="Full detail: callsign, altitude, speed, heading, distance"
                    onClick={() => setStep(3)}
                  />
                  <LayoutOption
                    title="Minimal"
                    desc="Just the essentials: callsign and distance"
                    onClick={() => setStep(3)}
                  />
                  <LayoutOption
                    title="List View"
                    desc="Show top 3 closest aircraft in a compact list"
                    onClick={() => setStep(3)}
                  />
                </div>
                <Button variant="secondary" onClick={() => setStep(1)} className="w-full">Back</Button>
              </div>
            )}

            {step === 3 && !rebooting && (
              <div className="space-y-4">
                <h2 className="text-xl font-semibold flex items-center gap-2">
                  <Wifi size={20} className="text-led-accent" />
                  Connect to WiFi
                </h2>
                <p className="text-sm text-white/50">
                  Enter your home WiFi credentials so the device can connect to your network.
                </p>
                <div className="space-y-3">
                  <div className="space-y-2">
                    <Label>Network Name (SSID)</Label>
                    <Input
                      type="text"
                      value={wifiSsid}
                      onChange={(e) => setWifiSsid(e.target.value)}
                      placeholder="MyHomeWiFi"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Password</Label>
                    <Input
                      type="password"
                      value={wifiPassword}
                      onChange={(e) => setWifiPassword(e.target.value)}
                      placeholder="••••••••"
                    />
                  </div>
                </div>
                {rebootError && (
                  <p className="text-sm text-red-400">{rebootError}</p>
                )}
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => setStep(2)} className="flex-1">Back</Button>
                  <Button onClick={handleFinish} disabled={loading || !wifiSsid} className="flex-1">
                    {loading ? 'Saving...' : 'Finish Setup'}
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
                  Once it&apos;s back online, visit <strong>http://adsb-display.local</strong> (or check your router for its IP).
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

function LayoutOption({ title, desc, onClick }: { title: string; desc: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="w-full text-left p-3 rounded-lg bg-led-dark border border-white/10 hover:border-led-accent/50 transition-colors">
      <div className="font-medium text-sm">{title}</div>
      <div className="text-xs text-white/40">{desc}</div>
    </button>
  );
}
