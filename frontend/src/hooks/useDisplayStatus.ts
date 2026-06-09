import { useEffect, useState } from 'react';
import { api } from '@/api/client';

export interface DisplayStatus {
  hardware_mode: boolean;
  width: number;
  height: number;
  brightness: number;
  mock: boolean;
}

export function useDisplayStatus() {
  const [status, setStatus] = useState<DisplayStatus | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchStatus = async () => {
      try {
        const data = await api.get<DisplayStatus>('/api/display/status');
        if (!cancelled) setStatus(data);
      } catch {
        // silently ignore — status is best-effort
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return status;
}
