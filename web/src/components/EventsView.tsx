import React, { useState } from 'react';
import { Search, MapPin, Star, Check, Trash2, Calendar } from 'lucide-react';
import { DetectedEvent, Watcher } from '../types.js';
import { Button, IconButton, DateTile, EmptyState, Segmented } from './ui.js';

interface EventsViewProps {
  events: DetectedEvent[];
  watchers: Watcher[];
  onToggleFavorite: (id: string) => void;
  onUpdateStatus: (id: string, status: 'unread' | 'read' | 'dismissed') => void;
  onDeleteEvent: (id: string) => void;
  onClearAll: () => void;
}

type StatusFilter = 'all' | 'unread' | 'favorite' | 'read';

export const EventsView: React.FC<EventsViewProps> = ({ events, onToggleFavorite, onUpdateStatus, onDeleteEvent, onClearAll }) => {
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  const categories = Array.from(new Set(events.map((e) => e.category).filter(Boolean)));
  const q = search.toLowerCase();
  const filtered = events.filter(
    (e) =>
      (!q || [e.title, e.short_description, e.venue, e.source_name].some((v) => v && v.toLowerCase().includes(q))) &&
      (categoryFilter === 'all' || e.category === categoryFilter) &&
      (statusFilter === 'all' || (statusFilter === 'favorite' ? e.is_favorite : e.notification_status === statusFilter)),
  );

  const detected = (ts: string) => {
    const d = new Date(ts);
    return isNaN(d.getTime())
      ? ts
      : `${d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })} · ${d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}`;
  };

  const handleExport = (format: 'csv' | 'ics' | 'json') => {
    window.location.href = `/api/events/export?format=${format}`;
  };

  const handleClear = () => {
    if (window.confirm('Clear all detected event history? Watchers will keep finding future announcements.')) onClearAll();
  };

  return (
    <>
      <div className="flex flex-wrap gap-3 items-center">
        <label className="relative flex-[1_1_280px] max-w-[420px] block">
          <Search className="absolute left-3.5 top-[13px] w-[18px] h-[18px] text-ink3" strokeWidth={1.8} />
          <input
            type="search"
            aria-label="Search events"
            placeholder="Search events, venues, descriptions…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="ew-field !pl-[42px]"
          />
        </label>
        <Segmented<StatusFilter>
          label="Filter by status"
          value={statusFilter}
          onChange={setStatusFilter}
          options={[['all', 'All'], ['unread', 'New'], ['favorite', 'Starred'], ['read', 'Read']]}
        />
        <select aria-label="Category" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="ew-field !w-auto">
          <option value="all">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <div className="flex-1" />
        <div role="group" aria-label="Export" className="flex items-center gap-1">
          <span className="text-[13px] font-medium text-ink3 pr-1">Export</span>
          <Button variant="secondary" title="Download CSV spreadsheet" onClick={() => handleExport('csv')}>CSV</Button>
          <Button variant="secondary" title="Export iCalendar (.ics) for Google, Apple or Outlook Calendar" onClick={() => handleExport('ics')}>iCal</Button>
          <Button variant="secondary" title="Export raw JSON" onClick={() => handleExport('json')}>JSON</Button>
          <IconButton label="Clear event history" tone="danger" onClick={handleClear} disabled={events.length === 0}>
            <Trash2 className="w-[18px] h-[18px]" strokeWidth={1.8} />
          </IconButton>
        </div>
      </div>

      <div className="text-sm text-ink3 -mb-4">
        {filtered.length} {filtered.length === 1 ? 'event' : 'events'}
      </div>

      {filtered.length > 0 ? (
        <div className="flex flex-col gap-3">
          {filtered.map((e) => {
            const isNew = e.notification_status === 'unread';
            return (
              <article key={e.id} className={`ew-card p-5 flex gap-5 items-start flex-wrap ${isNew ? '!border-accent-edge' : ''}`}>
                <DateTile date={e.event_date} compact />
                <div className="flex-[1_1_360px] min-w-0 flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-ink3">
                    {isNew && <span className="ew-caps !text-accent pr-1">New</span>}
                    <span className="font-semibold text-ink2">{e.category}</span>
                    <span aria-hidden="true">·</span>
                    <span>{e.source_name}</span>
                  </div>
                  <a href={e.source_url} target="_blank" rel="noopener noreferrer" className="font-serif font-semibold text-[19px] leading-snug text-ink no-underline hover:text-accent [text-wrap:pretty]">
                    {e.title}
                  </a>
                  {e.venue && (
                    <div className="flex items-center gap-1.5 text-sm font-medium text-ink2">
                      <MapPin className="w-4 h-4 text-ink3" strokeWidth={1.8} />
                      {e.venue}
                    </div>
                  )}
                  {e.short_description && <p className="m-0 max-w-[760px] text-sm leading-relaxed text-ink3">{e.short_description}</p>}
                  <div className="flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-ink3 pt-0.5">
                    {e.matched_keywords.length > 0 && (
                      <span>Matched <span className="font-mono text-ink2">{e.matched_keywords.join(', ')}</span></span>
                    )}
                    <span>Detected {detected(e.detected_at)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-0.5 ml-auto">
                  <IconButton
                    label={e.is_favorite ? 'Remove star' : 'Star this event'}
                    aria-pressed={e.is_favorite}
                    onClick={() => onToggleFavorite(e.id)}
                    className={e.is_favorite ? '!text-accent' : '!text-ink3'}
                  >
                    <Star className="w-[18px] h-[18px]" strokeWidth={1.8} fill={e.is_favorite ? 'currentColor' : 'none'} />
                  </IconButton>
                  <IconButton
                    label={isNew ? 'Mark as read' : 'Mark as unread'}
                    onClick={() => onUpdateStatus(e.id, isNew ? 'read' : 'unread')}
                    className={isNew ? '!text-ink3' : '!text-ok'}
                  >
                    <Check className="w-[18px] h-[18px]" strokeWidth={1.8} />
                  </IconButton>
                  <IconButton label="Remove from history" tone="danger" onClick={() => onDeleteEvent(e.id)}>
                    <Trash2 className="w-[18px] h-[18px]" strokeWidth={1.8} />
                  </IconButton>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <EmptyState icon={<Calendar className="w-7 h-7" strokeWidth={1.8} />} title="No events matched">
          <p className="m-0 max-w-[420px] text-sm leading-relaxed text-ink3">
            {events.length === 0 ? 'Nothing detected yet. Run a check or add a watcher to start.' : 'Try another search or clear the filters.'}
          </p>
        </EmptyState>
      )}
    </>
  );
};
