import { useEffect, useState } from 'react';
import { api } from '@/api/client';

export interface ReceiverStatus {
  receiver_source: 'local' | 'network';
  readsb_host: string;
  readsb_port: number;
  receiver_connected: boolean;
}

export function useReceiverStatus() {
  const [status, setStatus] = useState<ReceiverStatus | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchStatus = async () => {
      try {
        const data = await api.get<ReceiverStatus>('/api/system/status');
        if (!cancelled) setStatus(data);
      } catch {
        // ignore
      }
    };

    fetchStatus();
    const id = setInterval(fetchStatus, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return status;
}
