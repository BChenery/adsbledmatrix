import { useAircraft } from '@/hooks/useAircraft';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Plane, Navigation, Gauge, ArrowUp, ArrowDown, Clock, Radio } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function LiveAircraft() {
  const aircraft = useAircraft();

  if (aircraft.length === 0) {
    return (
      <main className="page-shell flex min-h-[70dvh] flex-col items-center justify-center text-center">
        <div className="relative mb-8">
          <div className="flex h-28 w-28 items-center justify-center rounded-full border border-led-accent/20 bg-led-dark/60 shadow-glow">
            <div className="absolute h-24 w-24 animate-ping rounded-full border border-led-accent/25" />
            <Plane size={36} className="relative z-10 text-led-accent" />
          </div>
        </div>
        <p className="eyebrow mb-3">Receiver</p>
        <h2 className="font-display text-2xl font-medium tracking-tight text-[#f5f5f5]">
          Scanning for aircraft
        </h2>
        <p className="mt-3 max-w-sm text-sm leading-relaxed text-led-dim">
          No messages yet. When the receiver picks up traffic, it will stream here in real time.
        </p>
      </main>
    );
  }

  const ac = aircraft[0];
  const positionedCount = aircraft.filter((a) => a.distance_km != null).length;
  const noPositionCount = aircraft.length - positionedCount;

  return (
    <main className="page-shell space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow mb-2 flex items-center gap-2">
            <span className="status-dot" />
            Live traffic
          </p>
          <h1 className="font-display text-2xl font-medium tracking-tight sm:text-[28px]">
            Recent aircraft
          </h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{aircraft.length} seen</Badge>
          {positionedCount > 0 && <Badge variant="default">{positionedCount} positioned</Badge>}
          {noPositionCount > 0 && <Badge variant="outline">{noPositionCount} no pos</Badge>}
        </div>
      </header>

      {noPositionCount > 0 && positionedCount === 0 && (
        <div className="flex items-start gap-3 rounded-xl border border-led-amber/25 bg-led-amber/[0.06] p-3.5 text-sm text-led-amber">
          <Radio size={16} className="mt-0.5 shrink-0" />
          <p className="leading-relaxed">
            Messages are arriving, but position frames are not decoded yet. Common with weak signals or aircraft beyond line-of-sight.
          </p>
        </div>
      )}

      <Card className="overflow-hidden">
        <div className="h-px w-full bg-gradient-to-r from-transparent via-led-accent/50 to-transparent" />
        <CardContent className="space-y-5 p-4 sm:p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="font-mono text-[28px] font-medium leading-none tracking-tight text-[#f5f5f5] sm:text-3xl">
                {ac.callsign || '---'}
              </div>
              <div className="mt-2 truncate text-sm text-led-dim">
                {ac.registration || '---'}
                <span className="text-led-faint"> · </span>
                {ac.type_code || 'Unknown type'}
                <span className="text-led-faint"> · </span>
                {ac.operator || 'Unknown operator'}
              </div>
            </div>
            <div className="sm:text-right">
              <div
                className={cn(
                  'font-display text-[28px] font-medium leading-none tracking-tight sm:text-3xl',
                  ac.distance_km != null ? 'text-led-accent' : 'text-led-faint',
                )}
              >
                {ac.distance_display || 'No position'}
              </div>
              <div className="mt-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-led-faint">
                distance
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 sm:gap-3">
            <StatCard
              icon={<Gauge size={14} />}
              label="Altitude"
              value={ac.altitude != null ? `${ac.altitude.toLocaleString()} ft` : '---'}
            />
            <StatCard
              icon={<Navigation size={14} />}
              label="Speed"
              value={ac.ground_speed != null ? `${ac.ground_speed} kts` : '---'}
            />
            <StatCard
              icon={<Clock size={14} />}
              label="Heading"
              value={ac.heading != null ? `${Math.round(ac.heading)}°` : '---'}
            />
          </div>

          {ac.vertical_rate !== undefined && ac.vertical_rate !== 0 && (
            <div
              className={cn(
                'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm',
                ac.vertical_rate > 0
                  ? 'border-led-green/25 bg-led-green/10 text-led-green'
                  : 'border-led-red/25 bg-led-red/10 text-led-red',
              )}
            >
              {ac.vertical_rate > 0 ? <ArrowUp size={14} /> : <ArrowDown size={14} />}
              <span className="font-mono">{Math.abs(ac.vertical_rate)} ft/min</span>
            </div>
          )}

          <div className="border-t border-led-line pt-3 font-mono text-[11px] text-led-faint">
            HEX {ac.hex_code}
            <span className="mx-2 text-led-line">|</span>
            {ac.messages ?? 0} msgs
            {ac.last_seen ? (
              <>
                <span className="mx-2 text-led-line">|</span>
                {new Date(ac.last_seen).toLocaleTimeString()}
              </>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {aircraft.length > 1 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="eyebrow">Also seen</h2>
            <span className="font-mono text-[11px] text-led-faint">{aircraft.length - 1} more</span>
          </div>
          <div className="divide-y divide-led-line overflow-hidden rounded-xl border border-led-line bg-led-dark">
            {aircraft.slice(1).map((a) => (
              <div
                key={a.hex_code}
                className="flex items-center justify-between gap-3 px-3.5 py-3 transition-colors hover:bg-white/[0.02] sm:px-4"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-led-line bg-led-panel text-led-faint">
                    <Plane size={14} />
                  </div>
                  <div className="min-w-0">
                    <div className="truncate font-mono text-sm text-[#f5f5f5]">
                      {a.callsign || a.hex_code}
                    </div>
                    <div className="truncate text-xs text-led-faint">
                      {a.type_code || 'Unknown type'}
                    </div>
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="text-sm font-medium text-[#f5f5f5]">
                    {a.distance_display || 'No pos'}
                  </div>
                  <div className="font-mono text-[11px] text-led-faint">
                    {a.altitude != null ? `${a.altitude.toLocaleString()} ft` : '---'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-xl border border-led-line bg-led-black/60 p-3 text-center sm:p-3.5">
      <div className="mb-2 flex justify-center text-led-faint">{icon}</div>
      <div className="font-mono text-sm font-medium tracking-tight text-[#f5f5f5] sm:text-base">
        {value}
      </div>
      <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.1em] text-led-faint">
        {label}
      </div>
    </div>
  );
}
