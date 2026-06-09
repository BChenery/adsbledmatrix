import { useEffect, useState } from 'react';

export function useDisplayPreview() {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const fetchPreview = async () => {
      try {
        const res = await fetch('/api/display/preview');
        if (!res.ok) {
          if (!cancelled) {
            setError(true);
            setUrl(null);
          }
          return;
        }
        const blob = await res.blob();
        const objectUrl = URL.createObjectURL(blob);
        if (!cancelled) {
          setUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev);
            return objectUrl;
          });
          setError(false);
        } else {
          URL.revokeObjectURL(objectUrl);
        }
      } catch {
        if (!cancelled) setError(true);
      }
    };

    fetchPreview();
    const interval = setInterval(fetchPreview, 2000);
    return () => {
      cancelled = true;
      clearInterval(interval);
      setUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
    };
  }, []);

  return { url, error };
}
