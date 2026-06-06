import { Routes, Route, Navigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { api } from '@/api/client';
import { UserConfig } from '@/types/config';
import OnboardingWizard from '@/components/OnboardingWizard/OnboardingWizard';
import LayoutDesigner from '@/components/LayoutDesigner/LayoutDesigner';
import Settings from '@/components/Settings/Settings';
import LiveAircraft from '@/components/LiveAircraft/LiveAircraft';
import { Plane, Layout, Settings as SettingsIcon, Radio } from 'lucide-react';
import { cn } from '@/lib/utils';

function Nav() {
  const links = [
    { href: '/', icon: Radio, label: 'Live' },
    { href: '/designer', icon: Layout, label: 'Designer' },
    { href: '/settings', icon: SettingsIcon, label: 'Settings' },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-led-panel border-t border-white/10 px-6 py-3 flex justify-around z-50">
      {links.map((link) => (
        <a
          key={link.href}
          href={link.href}
          className={cn(
            'flex flex-col items-center gap-1 transition-colors',
            location.pathname === link.href
              ? 'text-led-accent'
              : 'text-white/60 hover:text-white'
          )}
        >
          <link.icon size={20} />
          <span className="text-[10px]">{link.label}</span>
        </a>
      ))}
    </nav>
  );
}

function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen pb-20">
      {children}
      <Nav />
    </div>
  );
}

export default function App() {
  const [config, setConfig] = useState<UserConfig | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<UserConfig>('/api/config')
      .then((c) => { setConfig(c); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-led-accent">
          <Plane size={48} className="animate-bounce" />
        </div>
      </div>
    );
  }

  if (!config?.onboarding_complete) {
    return <OnboardingWizard onComplete={(c) => setConfig(c)} />;
  }

  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<LiveAircraft />} />
        <Route path="/designer" element={<LayoutDesigner />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </AppLayout>
  );
}
