import { useEffect, useState } from 'react';
import { api } from '@/api/client';

interface ReceiverStatus {
  receiver_source: string;
  readsb_host: string;
  readsb_port: number;
  receiver_connected: boolean;
}

export function useReceiverStatus() {
  const [status, setStatus] = useState<ReceiverStatus | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await api.get<ReceiverStatus>('/api/system/status');
        setStatus(res);
      } catch {
        // ignore
      }
    };
    fetchStatus();
    const id = setInterval(fetchStatus, 5000);
    return () => clearInterval(id);
  }, []);

  return status;
}
