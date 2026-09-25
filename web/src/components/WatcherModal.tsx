import React, { useState, useEffect } from 'react';
import { X, FlaskConical, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import { Watcher, SourceType, TestSourceResult } from '../types.js';
import { testSourceApi } from '../utils/api.js';
import { Button, IconButton, TYPE_OPTIONS, INTERVAL_OPTIONS } from './ui.js';

interface WatcherModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (watcherData: Partial<Watcher>) => Promise<void>;
  initialData?: Watcher | null;
}

const split = (text: string) => text.split(',').map((s) => s.trim()).filter(Boolean);

export const WatcherModal: React.FC<WatcherModalProps> = ({ isOpen, onClose, onSave, initialData }) => {
  const [name, setName] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceType, setSourceType] = useState<SourceType>('rss');
  const [category, setCategory] = useState('Concerts');
  const [keywordsText, setKeywordsText] = useState('');
  const [excludeText, setExcludeText] = useState('');
  const [intervalMinutes, setIntervalMinutes] = useState(60);
  const [notifyDesktop, setNotifyDesktop] = useState(true);
  const [notifySound, setNotifySound] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestSourceResult | null>(null);

  useEffect(() => {
    if (initialData) {
      setName(initialData.name);
      setSourceUrl(initialData.source_url);
      setSourceType(initialData.source_type);
      setCategory(initialData.category);
      setKeywordsText(initialData.keywords.join(', '));
      setExcludeText(initialData.exclude_keywords.join(', '));
      setIntervalMinutes(initialData.check_interval_minutes);
      setNotifyDesktop(initialData.notify_desktop);
      setNotifySound(initialData.notify_sound);
    } else {
      setName('');
      setSourceUrl('');
      setSourceType('event_listing');
      setCategory('Concerts');
      setKeywordsText('');
      setExcludeText('');
      setIntervalMinutes(180);
      setNotifyDesktop(true);
      setNotifySound(true);
    }
    setErrorMsg(null);
    setTestResult(null);
  }, [initialData, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;
  const isEditing = !!initialData?.id;

  const handleTestNow = async () => {
    if (!sourceUrl.trim()) {
      setErrorMsg('Please enter a website or feed address to test.');
      return;
    }
    setErrorMsg(null);
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await testSourceApi({ url: sourceUrl.trim(), source_type: sourceType, keywords: split(keywordsText), exclude_keywords: split(excludeText) });
      setTestResult(res);
      if (!name && res.title_found) setName(res.title_found);
    } catch (err: any) {
      setErrorMsg(`Test failed: ${err.message}`);
    } finally {
      setIsTesting(false);
    }
  };

  const handleSubmit = async () => {
    if (!name.trim()) return setErrorMsg('Please give the watcher a name.');
    if (!sourceUrl.trim()) return setErrorMsg('Please enter a website or feed address.');
    try {
      new URL(sourceUrl);
    } catch {
      return setErrorMsg('Please enter a full web address, starting with https:// or http://.');
    }
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await onSave({
        ...(initialData?.id ? { id: initialData.id } : {}),
        name: name.trim(),
        source_url: sourceUrl.trim(),
        source_type: sourceType,
        category: category.trim() || 'General',
        keywords: split(keywordsText),
        exclude_keywords: split(excludeText),
        check_interval_minutes: Number(intervalMinutes) || 60,
        notify_desktop: notifyDesktop,
        notify_sound: notifySound,
      });
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'The watcher could not be saved.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const works = !!testResult && testResult.success && testResult.items_found_count > 0;

  return (
    <div onClick={onClose} className="fixed inset-0 z-50 bg-[var(--scrim)] backdrop-blur-[4px] flex items-start justify-center py-12 px-4 overflow-y-auto">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="ew-modal-title"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[600px] bg-card border border-edge rounded-[20px] shadow-[var(--pop-shadow)] flex flex-col"
      >
        <div className="flex items-start gap-3 pt-6 px-6 pb-4">
          <div className="flex-1 flex flex-col gap-1">
            <h2 id="ew-modal-title" className="m-0 font-serif font-semibold text-2xl text-ink">{isEditing ? 'Edit watcher' : 'New watcher'}</h2>
            <p className="m-0 text-sm text-ink3">What to watch, which words matter, and how often to check.</p>
          </div>
          <IconButton label="Close" onClick={onClose}>
            <X className="w-5 h-5" strokeWidth={1.8} />
          </IconButton>
        </div>

        <div className="pt-2 px-6 pb-6 flex flex-col gap-[18px]">
          <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
            <label className="flex flex-col gap-2">
              <span className="ew-label">Name</span>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Belfast arena concerts" className="ew-field" />
            </label>
            <label className="flex flex-col gap-2">
              <span className="ew-label">Category</span>
              <input type="text" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Concerts, Football, Festivals…" className="ew-field" />
            </label>
          </div>
          <label className="flex flex-col gap-2">
            <span className="ew-label">Website or feed address</span>
            <input type="url" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="https://example.com/events or an RSS feed" className="ew-field !font-mono" />
          </label>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
            <label className="flex flex-col gap-2">
              <span className="ew-label">Source type</span>
              <select value={sourceType} onChange={(e) => setSourceType(e.target.value as SourceType)} className="ew-field">
                {TYPE_OPTIONS.map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2">
              <span className="ew-label">Check frequency</span>
              <select value={intervalMinutes} onChange={(e) => setIntervalMinutes(Number(e.target.value))} className="ew-field">
                {INTERVAL_OPTIONS.map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </label>
          </div>
          <label className="flex flex-col gap-2">
            <span className="ew-label">
              Include keywords <span className="font-normal text-ink3">(comma-separated, optional)</span>
            </span>
            <input type="text" value={keywordsText} onChange={(e) => setKeywordsText(e.target.value)} placeholder="e.g. Belfast, concert, announced — leave empty for every event" className="ew-field" />
            <span className="ew-help">An event matches if any of these words appear. Not case-sensitive. Empty = every event from this source.</span>
          </label>
          <label className="flex flex-col gap-2">
            <span className="ew-label">
              Exclusion keywords <span className="font-normal text-ink3">(comma-separated)</span>
            </span>
            <input type="text" value={excludeText} onChange={(e) => setExcludeText(e.target.value)} placeholder="e.g. tribute, cancelled, postponed" className="ew-field" />
            <span className="ew-help">Anything containing these words is ignored.</span>
          </label>
          <div className="flex flex-wrap gap-x-7 gap-y-3 pt-1">
            {([['Desktop notification', notifyDesktop, setNotifyDesktop], ['Sound alert', notifySound, setNotifySound]] as const).map(([label, on, set]) => (
              <label key={label} className="flex items-center gap-2.5 min-h-8 text-sm font-medium text-ink cursor-pointer">
                <input type="checkbox" checked={on} onChange={() => set(!on)} className="w-[18px] h-[18px] m-0" />
                {label}
              </label>
            ))}
          </div>

          {testResult && (
            <div className={`py-3.5 px-4 rounded-xl flex flex-col gap-1.5 ${works ? 'bg-ok-soft' : 'bg-err-soft'}`}>
              <div className="flex flex-wrap justify-between gap-2 text-sm font-semibold text-ink">
                <span className="flex items-center gap-2">
                  {works ? <CheckCircle2 className="w-5 h-5 text-ok" strokeWidth={1.8} /> : <AlertCircle className="w-5 h-5 text-err" strokeWidth={1.8} />}
                  {works ? 'Source works' : 'No events could be read'}
                </span>
                <span className="font-mono font-medium text-[13px] text-ink2">
                  HTTP {testResult.http_code ?? '—'} · {testResult.response_time_ms}ms · {testResult.items_found_count} items
                </span>
              </div>
              {works && testResult.sample_items[0] && <span className="text-[13px] leading-normal text-ink2">Sample: “{testResult.sample_items[0].title}”</span>}
              {!works && testResult.error_message && <span className="text-[13px] leading-normal text-err">{testResult.error_message}</span>}
            </div>
          )}
          {errorMsg && <p role="alert" className="m-0 text-sm text-err">{errorMsg}</p>}
        </div>

        <div className="flex flex-wrap items-center gap-2 py-4 px-6 border-t border-line">
          <Button
            variant="ghost"
            onClick={handleTestNow}
            disabled={isTesting}
            icon={isTesting ? <RefreshCw className="w-4 h-4 ew-spin" /> : <FlaskConical className="w-4 h-4" />}
          >
            {isTesting ? 'Testing…' : 'Test source now'}
          </Button>
          <div className="flex-1" />
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? 'Saving…' : isEditing ? 'Save changes' : 'Create watcher'}
          </Button>
        </div>
      </div>
    </div>
  );
};
