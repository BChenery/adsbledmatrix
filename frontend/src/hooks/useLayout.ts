import { useEffect, useState } from 'react';
import { api } from '@/api/client';
import { Layout } from '@/types/layout';

export function useLayouts() {
  const [layouts, setLayouts] = useState<Layout[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    const data = await api.get<Layout[]>('/api/layouts');
    setLayouts(data);
    setLoading(false);
  };

  useEffect(() => { refresh(); }, []);

  const create = async (layout: Omit<Layout, 'id'>) => {
    const created = await api.post<Layout>('/api/layouts', layout);
    setLayouts((prev) => [...prev, created]);
    return created;
  };

  const update = async (id: number, data: Partial<Layout>) => {
    const updated = await api.put<Layout>(`/api/layouts/${id}`, data);
    setLayouts((prev) => prev.map((l) => (l.id === id ? updated : l)));
    return updated;
  };

  const remove = async (id: number) => {
    await api.delete(`/api/layouts/${id}`);
    setLayouts((prev) => prev.filter((l) => l.id !== id));
  };

  return { layouts, loading, refresh, create, update, remove };
}
