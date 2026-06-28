import { useEffect, useState } from 'react';
import { api } from '@/api/client';

export interface DisplayDiagnostics {
  hardware_mode: boolean;
  matrix_type: string;
  width: number;
  height: number;
  brightness: number;
  hardware_mapping: string;
  rows: number;
  cols: number;
  chain: number;
  parallel: number;
  flip_vertical: boolean;
  spi_enabled: boolean;
  spi_devices: string[];
  gpio_access: boolean;
  user: string;
  groups: string[];
}

export function useDisplayDiagnostics() {
  const [diagnostics, setDiagnostics] = useState<DisplayDiagnostics | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchDiagnostics = async () => {
      try {
        const data = await api.get<DisplayDiagnostics>('/api/display/diagnostics');
        if (!cancelled) setDiagnostics(data);
      } catch {
        // silently ignore
      }
    };

    fetchDiagnostics();
    const interval = setInterval(fetchDiagnostics, 10000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return diagnostics;
}
