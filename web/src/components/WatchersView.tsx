import React, { useState } from 'react';
import { Search, Plus, RefreshCw, FlaskConical, Power, Pencil, Trash2 } from 'lucide-react';
import { Watcher, SourceType } from '../types.js';
import { Button, IconButton, EmptyState, TYPE_SHORT, formatWhen, intervalLabel } from './ui.js';

interface WatchersViewProps {
  watchers: Watcher[];
  onOpenCreateModal: () => void;
  onEditWatcher: (watcher: Watcher) => void;
  onDeleteWatcher: (id: string) => void;
  onToggleWatcher: (id: string) => void;
  onCheckWatcher: (id: string) => void;
  onTestUrl: (url: string, type: SourceType, keywords: string[], exclusions: string[]) => void;
  checkingWatcherId: string | null;
}

export const WatchersView: React.FC<WatchersViewProps> = ({
  watchers,
  onOpenCreateModal,
  onEditWatcher,
  onDeleteWatcher,
  onToggleWatcher,
  onCheckWatcher,
  onTestUrl,
  checkingWatcherId,
}) => {
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');

  const categories = Array.from(new Set(watchers.map((w) => w.category).filter(Boolean)));
  const q = search.toLowerCase();
  const filtered = watchers.filter(
    (w) =>
      (!q || w.name.toLowerCase().includes(q) || w.source_url.toLowerCase().includes(q) || w.keywords.some((k) => k.toLowerCase().includes(q))) &&
      (categoryFilter === 'all' || w.category === categoryFilter),
  );

  const status = (w: Watcher): [string, string, string] => {
    if (!w.enabled) return ['Paused', 'text-ink3', 'bg-ink3'];
    if (checkingWatcherId === w.id || w.status === 'checking') return ['Checking…', 'text-accent', 'bg-accent'];
    if (w.status === 'error') return ['Error', 'text-err', 'bg-err'];
    if (!w.last_successful_at) return ['Waiting for first check', 'text-ink2', 'bg-ink3'];
    return ['Active', 'text-ok', 'bg-ok'];
  };

  return (
    <>
      <div className="flex flex-wrap gap-3 items-center">
        <label className="relative flex-[1_1_280px] max-w-[420px] block">
          <Search className="absolute left-3.5 top-[13px] w-[18px] h-[18px] text-ink3" strokeWidth={1.8} />
          <input
            type="search"
            aria-label="Search watchers"
            placeholder="Search watchers, URLs or keywords…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="ew-field !pl-[42px]"
          />
        </label>
        <select aria-label="Category" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="ew-field !w-auto">
          <option value="all">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <div className="flex-1" />
        <Button variant="primary" icon={<Plus className="w-4 h-4" />} onClick={onOpenCreateModal}>Add new watcher</Button>
      </div>

      <div className="flex flex-col gap-3">
        {filtered.map((w) => {
          const [label, color, dot] = status(w);
          const checking = checkingWatcherId === w.id;
          return (
            <article key={w.id} className="ew-card py-5 px-6 flex flex-wrap gap-x-6 gap-y-4 items-center">
              <div className={`flex-[1_1_420px] min-w-0 flex flex-col gap-2 ${w.enabled ? '' : 'opacity-60'}`}>
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-ink3">
                  <span className={`inline-flex items-center gap-1.5 font-semibold ${color}`}>
                    {checking ? <RefreshCw className="w-3.5 h-3.5 ew-spin" /> : <span className={`w-2 h-2 rounded-full ${dot}`} />}
                    {label}
                  </span>
                  <span aria-hidden="true">·</span>
                  <span className="text-ink2 font-medium">{w.category}</span>
                  <span aria-hidden="true">·</span>
                  <span>{TYPE_SHORT[w.source_type] || w.source_type}</span>
                  <span aria-hidden="true">·</span>
                  <span>Every {intervalLabel(w.check_interval_minutes)}</span>
                </div>
                <h3 className="m-0 font-serif font-semibold text-[19px] leading-snug text-ink">{w.name}</h3>
                <a href={w.source_url} target="_blank" rel="noopener noreferrer" className="font-mono text-[13px] text-ink3 no-underline truncate max-w-full hover:text-accent">
                  {w.source_url}
                </a>
                <div className="flex flex-wrap gap-x-5 gap-y-1 text-[13px] leading-normal text-ink3">
                  <span>
                    Includes <span className="font-mono text-ink2">{w.keywords.length ? w.keywords.join(', ') : 'every event'}</span>
                  </span>
                  {w.exclude_keywords.length > 0 && (
                    <span>Excludes <span className="font-mono text-ink2">{w.exclude_keywords.join(', ')}</span></span>
                  )}
                  <span>Last checked {formatWhen(w.last_checked_at)}</span>
                </div>
              </div>
              <div className="flex items-center gap-0.5 ml-auto">
                <Button
                  variant="secondary"
                  icon={<RefreshCw className={`w-4 h-4 ${checking ? 'ew-spin' : ''}`} />}
                  onClick={() => onCheckWatcher(w.id)}
                  disabled={checking || !w.enabled}
                  title="Check now for updates"
                >
                  Check now
                </Button>
                <IconButton label="Test source in sandbox" onClick={() => onTestUrl(w.source_url, w.source_type, w.keywords, w.exclude_keywords)}>
                  <FlaskConical className="w-[18px] h-[18px]" strokeWidth={1.8} />
                </IconButton>
                <IconButton
                  label={w.enabled ? 'Pause watcher' : 'Resume watcher'}
                  aria-pressed={w.enabled}
                  onClick={() => onToggleWatcher(w.id)}
                  className={w.enabled ? '!text-ok' : '!text-ink3'}
                >
                  <Power className="w-[18px] h-[18px]" strokeWidth={1.8} />
                </IconButton>
                <IconButton label="Edit watcher" onClick={() => onEditWatcher(w)}>
                  <Pencil className="w-[18px] h-[18px]" strokeWidth={1.8} />
                </IconButton>
                <IconButton
                  label="Delete watcher"
                  tone="danger"
                  onClick={() => {
                    if (window.confirm(`Delete watcher "${w.name}" and its recorded events?`)) onDeleteWatcher(w.id);
                  }}
                >
                  <Trash2 className="w-[18px] h-[18px]" strokeWidth={1.8} />
                </IconButton>
              </div>
            </article>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <EmptyState title={watchers.length ? 'No watchers matched your search' : 'No watchers yet'}>
          <p className="m-0 max-w-[420px] text-sm leading-relaxed text-ink3">
            {watchers.length
              ? 'Try another search or category, or create a new watcher for a website or RSS feed.'
              : 'Add a watcher for a venue website or feed, or use one of the ready-made presets on the dashboard.'}
          </p>
        </EmptyState>
      )}
    </>
  );
};
