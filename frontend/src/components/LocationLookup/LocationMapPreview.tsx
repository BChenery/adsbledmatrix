import { useEffect, useMemo, useState } from 'react';
import { MapPin } from 'lucide-react';

interface LocationMapPreviewProps {
  latitude: number;
  longitude: number;
  className?: string;
}

const DEBOUNCE_MS = 400;
const HALF_SPAN_DEG = 0.04;

function isValidCoord(lat: number, lon: number): boolean {
  return (
    Number.isFinite(lat) &&
    Number.isFinite(lon) &&
    lat >= -90 &&
    lat <= 90 &&
    lon >= -180 &&
    lon <= 180 &&
    !(lat === 0 && lon === 0)
  );
}

function buildEmbedUrl(lat: number, lon: number): string {
  const minLon = Math.max(-180, lon - HALF_SPAN_DEG);
  const maxLon = Math.min(180, lon + HALF_SPAN_DEG);
  const minLat = Math.max(-90, lat - HALF_SPAN_DEG);
  const maxLat = Math.min(90, lat + HALF_SPAN_DEG);
  const bbox = `${minLon},${minLat},${maxLon},${maxLat}`;
  return `https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${encodeURIComponent(`${lat},${lon}`)}`;
}

export default function LocationMapPreview({
  latitude,
  longitude,
  className,
}: LocationMapPreviewProps) {
  const [debounced, setDebounced] = useState({ lat: latitude, lon: longitude });

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebounced({ lat: latitude, lon: longitude });
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [latitude, longitude]);

  const valid = isValidCoord(debounced.lat, debounced.lon);
  const src = useMemo(
    () => (valid ? buildEmbedUrl(debounced.lat, debounced.lon) : null),
    [valid, debounced.lat, debounced.lon],
  );

  return (
    <div className={className ?? 'space-y-2'}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-white/50 flex items-center gap-1.5">
          <MapPin size={12} className="text-white/40" />
          Map preview
        </p>
        {valid && (
          <p className="text-xs text-white/40 font-mono">
            {debounced.lat.toFixed(5)}, {debounced.lon.toFixed(5)}
          </p>
        )}
      </div>

      <div className="relative w-full overflow-hidden rounded-lg border border-white/10 bg-black/40 aspect-[16/10] min-h-[180px]">
        {src ? (
          <iframe
            title="Receiver location map"
            src={src}
            className="absolute inset-0 h-full w-full border-0"
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center">
            <MapPin size={22} className="text-white/30" />
            <p className="text-sm text-white/50">
              Enter a valid latitude and longitude to preview your location.
            </p>
            <p className="text-xs text-white/35">
              0,0 is treated as unset so the map stays blank until you pick a real place.
            </p>
          </div>
        )}
      </div>

      {valid && (
        <p className="text-xs text-white/40">
          Confirm the pin is near your receiver. Map tiles need internet access.
        </p>
      )}
    </div>
  );
}
