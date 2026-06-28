import { useAircraft } from '@/hooks/useAircraft';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Plane, Navigation, Gauge, ArrowUp, ArrowDown, Clock, Radio } from 'lucide-react';

export default function LiveAircraft() {
  const aircraft = useAircraft();

  if (aircraft.length === 0) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-6 text-center">
        <div className="relative mb-8">
          <div className="w-32 h-32 rounded-full border-2 border-led-accent/20 flex items-center justify-center">
            <div className="w-24 h-24 rounded-full border border-led-accent/40 animate-ping absolute" />
            <Plane size={40} className="text-led-accent relative z-10" />
          </div>
        </div>
        <h2 className="text-xl font-semibold mb-2">Scanning for Aircraft</h2>
        <p className="text-white/50 text-sm max-w-xs">
          No messages received yet. When the receiver detects aircraft they will appear here.
        </p>
      </div>
    );
  }

  const ac = aircraft[0];
  const positionedCount = aircraft.filter((a) => a.distance_km != null).length;
  const noPositionCount = aircraft.length - positionedCount;

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Recent Aircraft</h1>
        <div className="flex gap-2">
          <Badge variant="secondary">{aircraft.length} seen</Badge>
          {positionedCount > 0 && <Badge variant="secondary">{positionedCount} with position</Badge>}
          {noPositionCount > 0 && <Badge variant="outline">{noPositionCount} no position</Badge>}
        </div>
      </div>

      {noPositionCount > 0 && positionedCount === 0 && (
        <div className="flex items-start gap-2 text-xs text-amber-300/90 bg-amber-900/20 border border-amber-700/30 rounded-lg p-3">
          <Radio size={14} className="mt-0.5 shrink-0" />
          <p>
            Aircraft messages are being received, but position frames are not decoded yet. This is normal with weak signals or aircraft beyond line-of-sight.
          </p>
        </div>
      )}

      <Card>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold font-mono tracking-tight">
                {ac.callsign || '---'}
              </div>
              <div className="text-sm text-white/50">
                {ac.registration || '---'} · {ac.type_code || 'Unknown type'} · {ac.operator || 'Unknown operator'}
              </div>
            </div>
            <div className="text-right">
              <div className={`text-2xl font-bold ${ac.distance_km != null ? 'text-led-accent' : 'text-white/40'}`}>
                {ac.distance_display || 'No position'}
              </div>
              <div className="text-xs text-white/40">distance</div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <StatCard
              icon={<Gauge size={16} />}
              label="Altitude"
              value={ac.altitude != null ? `${ac.altitude.toLocaleString()} ft` : '---'}
            />
            <StatCard
              icon={<Navigation size={16} />}
              label="Speed"
              value={ac.ground_speed != null ? `${ac.ground_speed} kts` : '---'}
            />
            <StatCard
              icon={<Clock size={16} />}
              label="Heading"
              value={ac.heading != null ? `${Math.round(ac.heading)}°` : '---'}
            />
          </div>

          {ac.vertical_rate !== undefined && ac.vertical_rate !== 0 && (
            <div className={`flex items-center gap-2 text-sm ${ac.vertical_rate > 0 ? 'text-led-green' : 'text-led-red'}`}>
              {ac.vertical_rate > 0 ? <ArrowUp size={16} /> : <ArrowDown size={16} />}
              <span>{Math.abs(ac.vertical_rate)} ft/min</span>
            </div>
          )}

          <div className="text-xs text-white/30 font-mono">
            HEX: {ac.hex_code} · {ac.messages ?? 0} msgs
            {ac.last_seen ? ` · ${new Date(ac.last_seen).toLocaleTimeString()}` : ''}
          </div>
        </CardContent>
      </Card>

      {aircraft.length > 1 && (
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-white/60">Also Seen Recently</h2>
          {aircraft.slice(1).map((a) => (
            <Card key={a.hex_code}>
              <CardContent className="p-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Plane size={16} className="text-white/40" />
                  <div>
                    <div className="font-mono text-sm">{a.callsign || a.hex_code}</div>
                    <div className="text-xs text-white/40">{a.type_code || 'Unknown type'}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium">{a.distance_display || 'No position'}</div>
                  <div className="text-xs text-white/40">{a.altitude != null ? `${a.altitude.toLocaleString()} ft` : '---'}</div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="bg-led-dark rounded-lg p-3 text-center">
      <div className="text-white/40 mb-1 flex justify-center">{icon}</div>
      <div className="text-lg font-semibold font-mono">{value}</div>
      <div className="text-[10px] text-white/30 uppercase tracking-wider">{label}</div>
    </div>
  );
}
