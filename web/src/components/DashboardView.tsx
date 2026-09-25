import React from 'react';
import { AlertTriangle, ShieldCheck, ArrowRight, MapPin, Star, Check, Calendar, Plus } from 'lucide-react';
import { Watcher, DetectedEvent, SourceHealth, PresetWatcher } from '../types.js';
import { Button, IconButton, DateTile, EmptyState, formatWhen, formatTime, intervalLabel, intervalShort, shortDate } from './ui.js';

interface DashboardViewProps {
  watchers: Watcher[];
  events: DetectedEvent[];
  sources: SourceHealth[];
  schedulerStatus: any;
  eventTotal: number;
  onSelectTab: (tab: string) => void;
  onOpenNewWatcher: () => void;
  onCheckAll: () => void;
  isCheckingAll: boolean;
  onToggleEventFavorite: (id: string) => void;
  onMarkEventRead: (id: string) => void;
  presets: PresetWatcher[];
  onUsePreset: (preset: PresetWatcher) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  watchers,
  events,
  sources,
  schedulerStatus,
  eventTotal,
  onSelectTab,
  onOpenNewWatcher,
  onCheckAll,
  isCheckingAll,
  onToggleEventFavorite,
  onMarkEventRead,
  presets,
  onUsePreset,
}) => {
  const failing = sources.filter((s) => !s.is_healthy);
  const healthy = sources.length - failing.length;
  const unread = events.filter((e) => e.notification_status === 'unread');
  const earlier = events.filter((e) => e.notification_status !== 'unread').slice(0, 5);
  const healthColor = failing.length ? 'bg-err-soft text-err' : 'bg-ok-soft text-ok';
  const pct = Math.round((healthy / Math.max(sources.length, 1)) * 100);
  const watcherHealth = (id: string) => sources.find((s) => s.watcher_id === id);

  return (
    <>
      {failing.length > 0 && (
        <div role="alert" className="flex flex-wrap items-center gap-4 px-6 py-5 rounded-2xl bg-err-soft border border-err-edge">
          <AlertTriangle className="w-[22px] h-[22px] text-err" strokeWidth={1.8} />
          <div className="flex-[1_1_320px] flex flex-col gap-1">
            <strong className="text-base font-semibold text-ink">
              {failing.length === 1 ? `1 source can't be reached: ${failing[0].watcher_name}` : `${failing.length} sources can't be reached`}
            </strong>
            <span className="text-sm leading-normal text-ink2">
              The monitor couldn't fetch updates. Other sources are still being checked normally.
            </span>
          </div>
          <Button variant="secondary" onClick={() => onSelectTab('sources')}>Inspect sources</Button>
        </div>
      )}

      <section aria-label="Status" className="ew-card p-6 flex flex-wrap gap-x-10 gap-y-6 items-center">
        <div className="flex-[1_1_300px] flex items-center gap-4 min-w-0">
          <span className={`w-12 h-12 rounded-[14px] flex items-center justify-center shrink-0 ${healthColor}`}>
            <ShieldCheck className="w-6 h-6" strokeWidth={1.8} />
          </span>
          <div className="flex flex-col gap-1 min-w-0">
            <div className="font-serif font-semibold text-[22px] leading-tight text-ink">
              {failing.length ? `${healthy} of ${sources.length} sources reachable` : 'All sources reachable'}
            </div>
            <div className="text-sm text-ink3">
              {pct}% operational · Last check {schedulerStatus?.lastCheckTime ? formatWhen(schedulerStatus.lastCheckTime) : 'pending'}
            </div>
          </div>
        </div>
        <div className="flex gap-10 flex-wrap">
          <div className="flex flex-col gap-1.5">
            <span className="ew-caps">Watchers</span>
            <span className="ew-stat">
              {watchers.filter((w) => w.enabled).length}
              <span className="font-sans font-medium text-sm tracking-normal text-ink3"> of {watchers.length} active</span>
            </span>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="ew-caps">Events</span>
            <span className="ew-stat">
              {eventTotal}
              {unread.length > 0 && <span className="font-sans font-medium text-sm tracking-normal text-accent"> · {unread.length} new</span>}
            </span>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="ew-caps">Next check</span>
            <span className="ew-stat">{formatTime(schedulerStatus?.nextCheckTime)}</span>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap gap-8 items-start">
        <div className="flex-[2_1_520px] min-w-0 flex flex-col gap-8">
          <section className="flex flex-col gap-4">
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="m-0 font-serif font-semibold text-2xl text-ink flex items-baseline gap-3">
                New events
                {unread.length > 0 && <span className="font-display font-semibold text-base text-accent">{unread.length}</span>}
              </h2>
              <Button variant="ghost" iconRight={<ArrowRight className="w-4 h-4" />} onClick={() => onSelectTab('events')}>All events</Button>
            </div>

            {unread.length > 0 ? (
              unread.map((e) => (
                <article key={e.id} className="ew-card !border-accent-edge p-5 flex gap-5 items-start">
                  <DateTile date={e.event_date} />
                  <div className="flex-1 min-w-0 flex flex-col gap-2">
                    <div className="flex flex-wrap gap-x-2 gap-y-1 text-[13px] text-ink3">
                      <span className="font-semibold text-ink2">{e.category}</span>
                      <span aria-hidden="true">·</span>
                      <span>{e.source_name}</span>
                    </div>
                    <a href={e.source_url} target="_blank" rel="noopener noreferrer" className="font-serif font-semibold text-xl leading-snug text-ink no-underline hover:text-accent [text-wrap:pretty]">
                      {e.title}
                    </a>
                    {e.venue && (
                      <div className="flex items-center gap-1.5 text-sm font-medium text-ink2">
                        <MapPin className="w-4 h-4 text-ink3" strokeWidth={1.8} />
                        {e.venue}
                      </div>
                    )}
                    {e.short_description && <p className="m-0 text-sm leading-relaxed text-ink3 line-clamp-2">{e.short_description}</p>}
                    <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                      <span className="text-[13px] text-ink3">
                        {e.matched_keywords.length > 0 ? (
                          <>Matched <span className="font-mono text-ink2">{e.matched_keywords.join(', ')}</span></>
                        ) : (
                          <>Every event from this source</>
                        )}
                      </span>
                      <div className="flex items-center gap-1">
                        <IconButton
                          label={e.is_favorite ? 'Remove star' : 'Star this event'}
                          aria-pressed={e.is_favorite}
                          onClick={() => onToggleEventFavorite(e.id)}
                          className={e.is_favorite ? '!text-accent' : '!text-ink3'}
                        >
                          <Star className="w-[18px] h-[18px]" strokeWidth={1.8} fill={e.is_favorite ? 'currentColor' : 'none'} />
                        </IconButton>
                        <Button variant="secondary" icon={<Check className="w-[18px] h-[18px]" />} onClick={() => onMarkEventRead(e.id)}>
                          Mark as read
                        </Button>
                      </div>
                    </div>
                  </div>
                </article>
              ))
            ) : (
              <EmptyState icon={<Calendar className="w-7 h-7" strokeWidth={1.8} />} title="You're all caught up">
                <p className="m-0 max-w-[420px] text-sm leading-relaxed text-ink3">
                  Watchers keep checking automatically. New announcements will appear here and you'll get a desktop notification.
                </p>
                <div className="flex gap-2 mt-2 flex-wrap justify-center">
                  <Button variant="secondary" onClick={onCheckAll} disabled={isCheckingAll}>{isCheckingAll ? 'Checking…' : 'Check all now'}</Button>
                  <Button variant="primary" onClick={onOpenNewWatcher}>Create watcher</Button>
                </div>
              </EmptyState>
            )}
          </section>

          {earlier.length > 0 && (
            <section className="flex flex-col gap-3">
              <h2 className="m-0 ew-caps">Earlier</h2>
              <div className="ew-card p-2 flex flex-col gap-0.5">
                {earlier.map((e) => (
                  <div key={e.id} className="grid grid-cols-[104px_minmax(0,1fr)_auto] gap-4 items-center py-2 pr-2 pl-3 rounded-[10px] hover:bg-hover">
                    <span className="font-mono font-medium text-[13px] text-ink2">{shortDate(e.event_date)}</span>
                    <div className="min-w-0 flex flex-col gap-0.5">
                      <a href={e.source_url} target="_blank" rel="noopener noreferrer" className="font-medium text-[15px] text-ink no-underline truncate hover:text-accent">
                        {e.title}
                      </a>
                      <span className="text-[13px] text-ink3 truncate">{[e.venue, e.category].filter(Boolean).join(' · ')}</span>
                    </div>
                    <IconButton
                      label={e.is_favorite ? 'Remove star' : 'Star this event'}
                      aria-pressed={e.is_favorite}
                      onClick={() => onToggleEventFavorite(e.id)}
                      className={e.is_favorite ? '!text-accent' : '!text-ink3'}
                    >
                      <Star className="w-[18px] h-[18px]" strokeWidth={1.8} fill={e.is_favorite ? 'currentColor' : 'none'} />
                    </IconButton>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        <aside className="flex-[1_1_300px] min-w-0 flex flex-col gap-6">
          <section className="ew-card p-5 flex flex-col gap-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="m-0 font-serif font-semibold text-lg text-ink">Watching</h2>
              <Button variant="ghost" onClick={() => onSelectTab('watchers')}>Manage</Button>
            </div>
            <div className="flex flex-col">
              {watchers.map((w) => {
                const h = watcherHealth(w.id);
                const dot = !w.enabled ? 'bg-ink3' : h && !h.is_healthy ? 'bg-err' : 'bg-ok';
                return (
                  <div key={w.id} className="flex items-center gap-2.5 py-2.5 border-t border-line">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${dot}`} />
                    <span className="flex-1 min-w-0 text-sm font-medium text-ink truncate" title={w.name}>{w.name}</span>
                    <span className="font-mono font-medium text-[13px] text-ink3">{intervalShort(w.check_interval_minutes)}</span>
                  </div>
                );
              })}
            </div>
          </section>

          {presets.length > 0 && (
            <section className="ew-card p-5 flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <h2 className="m-0 font-serif font-semibold text-lg text-ink">Add a ready-made watcher</h2>
                <p className="m-0 text-[13px] leading-normal text-ink3">One click, then review before saving.</p>
              </div>
              <div className="flex flex-col">
                {presets.map((p) => (
                  <div key={p.id} className="flex items-center gap-3 py-3 border-t border-line">
                    <div className="flex-1 min-w-0 flex flex-col gap-[3px]">
                      <span className="text-sm font-medium text-ink" title={p.description}>{p.name}</span>
                      <span className="text-[13px] text-ink3">{p.category} · every {intervalLabel(p.check_interval_minutes)}</span>
                    </div>
                    <Button variant="ghost" icon={<Plus className="w-4 h-4" />} onClick={() => onUsePreset(p)} aria-label={`Use preset: ${p.name}`}>
                      Use
                    </Button>
                  </div>
                ))}
              </div>
            </section>
          )}

          <div className="flex gap-3 px-1 pt-1">
            <ShieldCheck className="w-[18px] h-[18px] text-ok shrink-0 mt-0.5" strokeWidth={1.8} />
            <div className="flex flex-col gap-1.5">
              <p className="m-0 text-[13px] leading-relaxed text-ink3">
                <strong className="font-semibold text-ink2">Your data stays on this computer.</strong> Stored in a local SQLite file — no accounts,
                telemetry or external AI services.
              </p>
              <a
                href="#handover"
                onClick={(ev) => { ev.preventDefault(); onSelectTab('handover'); }}
                className="text-[13px] font-semibold text-accent no-underline"
              >
                View handover &amp; verification →
              </a>
            </div>
          </div>
        </aside>
      </div>
    </>
  );
};
