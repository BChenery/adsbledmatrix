import { Routes, Route, Navigate, NavLink } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { api } from '@/api/client';
import { UserConfig } from '@/types/config';
import OnboardingWizard from '@/components/OnboardingWizard/OnboardingWizard';
import LayoutDesigner from '@/components/LayoutDesigner/LayoutDesigner';
import Settings from '@/components/Settings/Settings';
import LiveAircraft from '@/components/LiveAircraft/LiveAircraft';
import { Layout, Settings as SettingsIcon, Radio } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useDisplayStatus } from '@/hooks/useDisplayStatus';

const links = [
  { href: '/', icon: Radio, label: 'Live' },
  { href: '/designer', icon: Layout, label: 'Designer' },
  { href: '/settings', icon: SettingsIcon, label: 'Settings' },
] as const;

function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={cn('flex items-center gap-2.5 min-w-0', compact && 'gap-2')}>
      <div
        className={cn(
          'shrink-0 rounded-[6px] bg-gradient-to-br from-led-accent to-[#1a8fa3] shadow-[0_0_16px_rgba(53,224,255,0.25)]',
          compact ? 'h-7 w-7' : 'h-8 w-8',
        )}
        aria-hidden
      />
      <div className="min-w-0">
        <div className="font-display text-[15px] font-medium tracking-tight text-[#f5f5f5] leading-none">
          ADS-B <span className="text-led-accent">LED</span>
        </div>
        {!compact && (
          <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.12em] text-led-faint">
            Matrix control
          </div>
        )}
      </div>
    </div>
  );
}

function DesktopNav() {
  const displayStatus = useDisplayStatus();

  return (
    <header className="sticky top-0 z-40 hidden border-b border-led-line/80 bg-led-black/85 backdrop-blur-xl md:block">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-6">
        <BrandMark compact />
        <nav className="flex items-center gap-1">
          {links.map((link) => (
            <NavLink
              key={link.href}
              to={link.href}
              end={link.href === '/'}
              className={({ isActive }) =>
                cn(
                  'relative flex items-center gap-2 rounded-full px-3.5 py-2 text-[13.5px] font-medium transition-colors',
                  isActive
                    ? 'bg-white/[0.05] text-[#f5f5f5]'
                    : 'text-led-dim hover:bg-white/[0.03] hover:text-[#f5f5f5]',
                )
              }
            >
              {({ isActive }) => (
                <>
                  <link.icon size={15} className={isActive ? 'text-led-accent' : undefined} />
                  {link.label}
                  {link.href === '/settings' && displayStatus && (
                    <span
                      className={cn(
                        'h-1.5 w-1.5 rounded-full',
                        displayStatus.hardware_mode ? 'bg-led-green' : 'bg-led-amber',
                      )}
                      title={displayStatus.hardware_mode ? 'LED Matrix Connected' : 'LED Matrix Mock Mode'}
                    />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2 font-mono text-[11px] text-led-faint">
          <span className="status-dot" />
          <span>live</span>
        </div>
      </div>
    </header>
  );
}

function MobileNav() {
  const displayStatus = useDisplayStatus();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-led-line/80 bg-led-black/90 backdrop-blur-xl md:hidden"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
    >
      <div className="flex items-stretch justify-around px-2 pt-2 pb-2">
        {links.map((link) => (
          <NavLink
            key={link.href}
            to={link.href}
            end={link.href === '/'}
            className={({ isActive }) =>
              cn(
                'relative flex min-w-[4.5rem] flex-col items-center gap-1 rounded-xl px-3 py-2 transition-colors',
                isActive ? 'text-led-accent' : 'text-led-faint hover:text-led-dim',
              )
            }
          >
            {({ isActive }) => (
              <>
                <link.icon size={20} strokeWidth={isActive ? 2.25 : 1.75} />
                <span className="font-mono text-[10px] uppercase tracking-[0.08em]">{link.label}</span>
                {link.href === '/settings' && displayStatus && (
                  <span
                    className={cn(
                      'absolute right-2 top-1.5 h-1.5 w-1.5 rounded-full',
                      displayStatus.hardware_mode ? 'bg-led-green' : 'bg-led-amber',
                    )}
                    title={displayStatus.hardware_mode ? 'LED Matrix Connected' : 'LED Matrix Mock Mode'}
                  />
                )}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-led-black">
      <DesktopNav />
      <div className="safe-bottom md:pb-0">{children}</div>
      <MobileNav />
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
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-led-black">
        <div className="h-10 w-10 rounded-[8px] bg-gradient-to-br from-led-accent to-[#1a8fa3] shadow-[0_0_24px_rgba(53,224,255,0.3)] animate-pulse" />
        <div className="font-mono text-xs uppercase tracking-[0.14em] text-led-faint">
          Booting display control
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
