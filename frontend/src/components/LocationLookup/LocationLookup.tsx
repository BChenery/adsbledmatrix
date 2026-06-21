import { useState } from 'react';
import { api } from '@/api/client';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Loader2, MapPin } from 'lucide-react';

interface GeocodeResult {
  display_name: string;
  latitude: number;
  longitude: number;
}

interface LocationLookupProps {
  latitude: number;
  longitude: number;
  disabled?: boolean;
  onChange: (lat: number, lon: number) => void;
}

export default function LocationLookup({
  latitude,
  longitude,
  disabled = false,
  onChange,
}: LocationLookupProps) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GeocodeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleLookup = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await api.get<GeocodeResult>(
        `/api/config/geocode?q=${encodeURIComponent(query.trim())}`
      );
      setResult(res);
      onChange(res.latitude, res.longitude);
    } catch (e: unknown) {
      const errStatus =
        e && typeof e === 'object' && 'status' in e
          ? (e as { status?: number }).status
          : undefined;
      let message: string;
      if (errStatus === 404) {
        message = 'No results found. Try a nearby town or city.';
      } else if (errStatus === 502 || errStatus === 503) {
        message =
          'Address lookup is temporarily unavailable. Please enter coordinates manually.';
      } else {
        message = 'Lookup failed. Please try again.';
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const hasLookupResult =
    result && result.latitude === latitude && result.longitude === longitude;

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <Label className="flex items-center gap-2">
          <MapPin size={14} />
          Address Lookup
        </Label>
        <div className="flex gap-2">
          <Input
            type="text"
            placeholder="Enter your address or town"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleLookup();
            }}
            disabled={disabled || loading}
            className="flex-1"
          />
          <Button
            onClick={handleLookup}
            disabled={disabled || loading || !query.trim()}
            type="button"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : 'Look up'}
          </Button>
        </div>
        {disabled && (
          <p className="text-xs text-white/40">
            Address lookup is available once the device is connected to the internet.
          </p>
        )}
      </div>

      {error && (
        <div className="text-xs text-red-400 bg-red-950/30 border border-red-900/40 rounded p-2">
          {error}
        </div>
      )}

      {hasLookupResult && (
        <div className="text-xs text-green-400 bg-green-950/30 border border-green-900/40 rounded p-2">
          Found: {result.display_name}
        </div>
      )}

      {!hasLookupResult && !error && result && (
        <div className="text-xs text-amber-400 bg-amber-950/30 border border-amber-900/40 rounded p-2">
          Lookup result differs from current coordinates. Press Look up again or adjust manually.
        </div>
      )}
    </div>
  );
}
