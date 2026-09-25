import React from 'react';
import { ShieldCheck, RefreshCw, FlaskConical } from 'lucide-react';
import { SourceHealth, SourceType } from '../types.js';
import { IconButton, formatWhen } from './ui.js';

interface SourcesViewProps {
  sources: SourceHealth[];
  onTestUrl: (url: string, type: SourceType, keywords: string[], exclusions: string[]) => void;
  onCheckWatcher: (watcherId: string) => void;
  checkingWatcherId: string | null;
}

export const SourcesView: React.FC<SourcesViewProps> = ({ sources, onTestUrl, onCheckWatcher, checkingWatcherId }) => {
  const failing = sources.filter((s) => !s.is_healthy);
  const healthy = sources.length - failing.length;

  return (
    <>
      <section className="ew-card p-6 flex flex-wrap gap-x-10 gap-y-6 items-center">
        <div className="flex-[1_1_320px] flex items-center gap-4">
          <span className={`w-12 h-12 rounded-[14px] flex items-center justify-center shrink-0 ${failing.length ? 'bg-err-soft text-err' : 'bg-ok-soft text-ok'}`}>
            <ShieldCheck className="w-6 h-6" strokeWidth={1.8} />
          </span>
          <div className="flex flex-col gap-1">
            <div className="font-serif font-semibold text-[22px] leading-tight text-ink">
              {failing.length ? `${healthy} of ${sources.length} sources reachable` : 'All sources reachable'}
            </div>
            <div className="text-sm text-ink3">Response codes, speed and reliability of every website you watch.</div>
          </div>
        </div>
        <div className="flex gap-10">
          <div className="flex flex-col gap-1.5">
            <span className="ew-caps">Reachable</span>
            <span className="ew-stat !text-ok">
              {healthy}
              <span className="font-medium text-base text-ink3"> / {sources.length}</span>
            </span>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="ew-caps">Failing</span>
            <span className={`ew-stat ${failing.length ? '!text-err' : '!text-ink3'}`}>{failing.length}</span>
          </div>
        </div>
      </section>

      <section className="ew-card overflow-hidden">
        {sources.map((s, i) => {
          const bad = !s.is_healthy;
          const checking = checkingWatcherId === s.watcher_id;
          const httpOk = s.last_http_code !== null && s.last_http_code < 400;
          return (
            <div key={s.watcher_id} className={`flex flex-wrap gap-x-8 gap-y-4 items-center py-[18px] px-6 ${i ? 'border-t border-line' : ''} ${bad ? 'bg-err-soft' : ''}`}>
              <div className="flex-[1_1_300px] min-w-0 flex flex-col gap-1">
                <div className="flex items-center gap-2.5">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${bad ? 'bg-err' : s.last_checked_at ? 'bg-ok' : 'bg-ink3'}`} />
                  <span className="font-semibold text-[15px] text-ink">{s.watcher_name}</span>
                </div>
                <a href={s.url} target="_blank" rel="noopener noreferrer" className="pl-[18px] font-mono text-[13px] text-ink3 no-underline truncate hover:text-accent">
                  {s.url}
                </a>
                {s.last_error && (
                  <div className={`pl-[18px] text-[13px] font-medium ${bad ? 'text-err' : 'text-ink2'}`}>
                    {s.last_error}
                    {s.consecutive_failures > 1 ? ` — ${s.consecutive_failures} checks in a row` : ''}
                  </div>
                )}
              </div>
              <dl className="m-0 grid grid-cols-[repeat(5,auto)] gap-x-7 gap-y-1">
                {['Type', 'HTTP', 'Speed', 'Failures', 'Last success'].map((h) => (
                  <dt key={h} className="ew-caps !tracking-[0.06em]">{h}</dt>
                ))}
                <dd className="m-0 mt-1.5 font-mono font-medium text-sm text-ink2">{s.source_type}</dd>
                <dd className={`m-0 mt-1.5 font-mono font-semibold text-sm ${s.last_http_code === null ? 'text-ink3' : httpOk ? 'text-ok' : 'text-err'}`}>
                  {s.last_http_code ?? '—'}
                </dd>
                <dd className="m-0 mt-1.5 font-mono font-medium text-sm text-ink2">{s.response_time_ms !== null ? `${s.response_time_ms}ms` : '—'}</dd>
                <dd className={`m-0 mt-1.5 font-mono font-semibold text-sm ${s.consecutive_failures ? 'text-err' : 'text-ink3'}`}>{s.consecutive_failures}</dd>
                <dd className="m-0 mt-1.5 font-mono font-medium text-sm text-ink2">{s.last_success_at ? formatWhen(s.last_success_at) : '—'}</dd>
              </dl>
              <div className="flex gap-0.5">
                <IconButton label="Check now" onClick={() => onCheckWatcher(s.watcher_id)} disabled={checking}>
                  <RefreshCw className={`w-[18px] h-[18px] ${checking ? 'ew-spin' : ''}`} strokeWidth={1.8} />
                </IconButton>
                <IconButton label="Test in sandbox" onClick={() => onTestUrl(s.url, s.source_type, [], [])}>
                  <FlaskConical className="w-[18px] h-[18px]" strokeWidth={1.8} />
                </IconButton>
              </div>
            </div>
          );
        })}
        {sources.length === 0 && <div className="p-6 text-sm text-ink3">No sources yet. Add a watcher to start monitoring.</div>}
      </section>
    </>
  );
};
