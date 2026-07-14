import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '@/api/client';
import type { ChangelogEntry, ChangelogResponse, ChangelogSection } from '@/types/changelog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import {
  ChevronDown,
  Loader2,
  Sparkles,
  Settings as SettingsIcon,
  AlertCircle,
} from 'lucide-react';

function sectionTone(title: string): {
  badge: 'default' | 'secondary' | 'destructive' | 'outline';
  accent: string;
} {
  const key = title.toLowerCase();
  if (key.includes('added') || key.includes('new')) {
    return { badge: 'default', accent: 'border-l-led-accent/70' };
  }
  if (key.includes('fix') || key.includes('security')) {
    return { badge: 'outline', accent: 'border-l-led-amber/70' };
  }
  if (key.includes('remov') || key.includes('deprecated')) {
    return { badge: 'destructive', accent: 'border-l-led-red/60' };
  }
  if (key.includes('changed') || key.includes('improv')) {
    return { badge: 'secondary', accent: 'border-l-white/25' };
  }
  return { badge: 'secondary', accent: 'border-l-led-line' };
}

function formatDate(date?: string | null): string | null {
  if (!date) return null;
  const parsed = new Date(date + 'T12:00:00');
  if (Number.isNaN(parsed.getTime())) return date;
  return parsed.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/** Strip light markdown (bold / links) so bullets read cleanly without a MD lib. */
function stripMarkdownLight(text: string): string {
  let out = text;
  out = out.replace(/\*\*([^*]+)\*\*/g, '$1');
  // Avoid raw /.../ patterns that confuse TSX parsers for link syntax.
  const linkRe = new RegExp('\\[([^\\]]+)\\]\\([^)]+\\)', 'g');
  out = out.replace(linkRe, '$1');
  return out;
}

function EntryCard({
  entry,
  isCurrent,
  defaultOpen,
}: {
  entry: ChangelogEntry;
  isCurrent: boolean;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const dateLabel = formatDate(entry.date);
  const changeCount = entry.sections.reduce((n, s) => n + s.items.length, 0);

  return (
    <Card
      className={cn(
        'overflow-hidden transition-colors',
        isCurrent && 'border-led-accent/30 shadow-glow',
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-3 p-4 text-left sm:p-5"
        aria-expanded={open}
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-lg font-medium tracking-tight text-[#f5f5f5] sm:text-xl">
              v{entry.version}
            </span>
            {isCurrent && (
              <Badge variant="default" className="gap-1">
                <Sparkles size={11} />
                Installed
              </Badge>
            )}
            {dateLabel && (
              <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-led-faint">
                {dateLabel}
              </span>
            )}
          </div>
          <p className="mt-1.5 text-xs text-led-dim sm:text-[13px]">
            {changeCount === 0
              ? 'No detailed notes for this release'
              : `${changeCount} change${changeCount === 1 ? '' : 's'}`}
          </p>
        </div>
        <ChevronDown
          size={18}
          className={cn(
            'mt-1 shrink-0 text-led-faint transition-transform duration-200',
            open && 'rotate-180 text-led-accent',
          )}
        />
      </button>

      {open && (
        <CardContent className="space-y-4 border-t border-led-line/80 px-4 pb-5 pt-4 sm:px-5">
          {entry.sections.length === 0 ? (
            <p className="text-sm text-led-faint">No notes listed for this version.</p>
          ) : (
            entry.sections.map((section) => (
              <SectionBlock key={entry.version + '-' + section.title} section={section} />
            ))
          )}
        </CardContent>
      )}
    </Card>
  );
}

function SectionBlock({ section }: { section: ChangelogSection }) {
  const tone = sectionTone(section.title);
  return (
    <div
      className={cn(
        'rounded-lg border border-led-line/60 bg-led-panel/40 border-l-2 pl-3 pr-3 py-3',
        tone.accent,
      )}
    >
      <div className="mb-2.5 flex items-center gap-2">
        <Badge variant={tone.badge}>{section.title}</Badge>
      </div>
      <ul className="space-y-2">
        {section.items.map((item, idx) => (
          <li
            key={section.title + '-' + idx}
            className="flex gap-2.5 text-sm leading-relaxed text-led-dim"
          >
            <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-led-faint" aria-hidden />
            <span className="text-[#e8e8e8]">{stripMarkdownLight(item)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function WhatsNew() {
  const [data, setData] = useState<ChangelogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get<ChangelogResponse>('/api/system/changelog')
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setData(null);
          setError('Could not load release notes from this device.');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const entries = data?.entries ?? [];
  const currentVersion = data?.current_version;

  const openDefaults = useMemo(() => {
    const open = new Set<string>();
    for (const entry of entries.slice(0, 2)) {
      open.add(entry.version);
    }
    if (currentVersion) open.add(currentVersion);
    return open;
  }, [entries, currentVersion]);

  return (
    <main className="page-shell space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow mb-2 flex items-center gap-2">
            <Sparkles size={12} className="text-led-accent" />
            Release notes
          </p>
          <h1 className="font-display text-2xl font-medium tracking-tight sm:text-[28px]">
            What&apos;s new
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-led-dim">
            Changes included on this device - works offline, no website required.
          </p>
        </div>
        {currentVersion && (
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="font-mono">
              running v{currentVersion}
            </Badge>
            <Button asChild variant="secondary" size="sm" className="gap-1.5">
              <Link to="/settings">
                <SettingsIcon size={14} />
                Updates in Settings
              </Link>
            </Button>
          </div>
        )}
      </header>

      {loading && (
        <div className="flex min-h-[40dvh] flex-col items-center justify-center gap-3 text-led-faint">
          <Loader2 size={22} className="animate-spin text-led-accent" />
          <p className="font-mono text-xs uppercase tracking-[0.12em]">Loading changelog</p>
        </div>
      )}

      {!loading && error && (
        <div className="flex items-start gap-3 rounded-xl border border-led-red/25 bg-led-red/[0.06] p-4 text-sm text-led-red">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">{error}</p>
            <p className="mt-1 text-led-dim">
              The changelog file may be missing from this install. Update the software from Settings
              when online to pick it up.
            </p>
          </div>
        </div>
      )}

      {!loading && !error && entries.length === 0 && (
        <Card>
          <CardContent className="space-y-2 p-6 text-center">
            <p className="font-display text-lg text-[#f5f5f5]">No release notes yet</p>
            <p className="text-sm text-led-dim">
              When new versions ship, notes will appear here automatically.
            </p>
          </CardContent>
        </Card>
      )}

      {!loading && !error && entries.length > 0 && (
        <div className="relative space-y-3">
          <div
            className="absolute bottom-4 left-[11px] top-4 w-px bg-gradient-to-b from-led-accent/40 via-led-line to-transparent sm:left-[13px]"
            aria-hidden
          />
          {entries.map((entry, index) => {
            const isCurrent =
              !!currentVersion &&
              entry.version.replace(/^v/i, '') === currentVersion.replace(/^v/i, '');
            return (
              <div key={entry.version} className="relative flex gap-3 sm:gap-4">
                <div className="relative z-10 mt-5 flex w-6 shrink-0 justify-center sm:w-7">
                  <span
                    className={cn(
                      'h-2.5 w-2.5 rounded-full border-2 border-led-black',
                      isCurrent || index === 0
                        ? 'bg-led-accent shadow-[0_0_10px_rgba(53,224,255,0.45)]'
                        : 'bg-led-faint',
                    )}
                  />
                </div>
                <div className="min-w-0 flex-1">
                  <EntryCard
                    entry={entry}
                    isCurrent={isCurrent}
                    defaultOpen={openDefaults.has(entry.version) || index < 2}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}
