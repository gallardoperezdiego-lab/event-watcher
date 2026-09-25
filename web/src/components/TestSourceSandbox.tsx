import React, { useState } from 'react';
import { FlaskConical, RefreshCw, CheckCircle2, XCircle, Plus } from 'lucide-react';
import { SourceType, TestSourceResult } from '../types.js';
import { testSourceApi } from '../utils/api.js';
import { Button, TYPE_OPTIONS } from './ui.js';

interface TestSourceSandboxProps {
  initialUrl?: string;
  initialType?: SourceType;
  initialKeywords?: string[];
  initialExclusions?: string[];
  onCreateWatcherFromTest: (data: {
    name: string;
    source_url: string;
    source_type: SourceType;
    keywords: string[];
    exclude_keywords: string[];
  }) => void;
}

const split = (text: string) => text.split(',').map((s) => s.trim()).filter(Boolean);

export const TestSourceSandbox: React.FC<TestSourceSandboxProps> = ({
  initialUrl = 'https://theo2belfast.com/events.json',
  initialType = 'json_feed',
  initialKeywords = [],
  initialExclusions = [],
  onCreateWatcherFromTest,
}) => {
  const [url, setUrl] = useState(initialUrl);
  const [sourceType, setSourceType] = useState<SourceType>(initialType);
  const [keywordsText, setKeywordsText] = useState(initialKeywords.join(', '));
  const [excludeText, setExcludeText] = useState(initialExclusions.join(', '));
  const [isTesting, setIsTesting] = useState(false);
  const [result, setResult] = useState<TestSourceResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleRunTest = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!url.trim()) {
      setErrorMsg('Please enter a website or feed address to test.');
      return;
    }
    setIsTesting(true);
    setErrorMsg(null);
    setResult(null);
    try {
      const res = await testSourceApi({ url: url.trim(), source_type: sourceType, keywords: split(keywordsText), exclude_keywords: split(excludeText) });
      setResult(res);
    } catch (err: any) {
      setErrorMsg(err.message || 'The test could not be run.');
    } finally {
      setIsTesting(false);
    }
  };

  const works = !!result && result.success && result.items_found_count > 0;

  return (
    <>
      <form onSubmit={handleRunTest} className="ew-card p-6 flex flex-col gap-5 max-w-[880px]">
        <label className="flex flex-col gap-2">
          <span className="ew-label">Website or feed address</span>
          <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/events" className="ew-field !font-mono" />
        </label>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
          <label className="flex flex-col gap-2">
            <span className="ew-label">Expected source type</span>
            <select value={sourceType} onChange={(e) => setSourceType(e.target.value as SourceType)} className="ew-field">
              {TYPE_OPTIONS.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-2">
            <span className="ew-label">Keywords to match</span>
            <input type="text" value={keywordsText} onChange={(e) => setKeywordsText(e.target.value)} placeholder="Empty = every event" className="ew-field" />
          </label>
          <label className="flex flex-col gap-2">
            <span className="ew-label">Words to ignore</span>
            <input type="text" value={excludeText} onChange={(e) => setExcludeText(e.target.value)} placeholder="e.g. tribute, cancelled" className="ew-field" />
          </label>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-line">
          <p className="m-0 text-[13px] leading-normal text-ink3">Nothing is saved. Uses your User-Agent and timeout settings.</p>
          <Button
            type="submit"
            variant="primary"
            disabled={isTesting}
            icon={isTesting ? <RefreshCw className="w-4 h-4 ew-spin" /> : <FlaskConical className="w-4 h-4" />}
          >
            {isTesting ? 'Testing…' : 'Run test'}
          </Button>
        </div>
        {errorMsg && <p role="alert" className="m-0 text-sm text-err">{errorMsg}</p>}
      </form>

      {result && (
        <section className="ew-card p-6 flex flex-col gap-5 max-w-[880px]">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 font-serif font-semibold text-xl text-ink">
              {works ? <CheckCircle2 className="w-5 h-5 text-ok" strokeWidth={1.8} /> : <XCircle className="w-5 h-5 text-err" strokeWidth={1.8} />}
              {works ? 'Source works' : result.success ? 'Page read, but no events found' : "Source couldn't be read"}
            </div>
            <div className="font-mono font-medium text-sm text-ink2">
              HTTP {result.http_code ?? '—'} · {result.response_time_ms}ms · {result.items_found_count} items · {result.source_type_detected}
            </div>
          </div>

          {result.error_message && <p className="m-0 text-sm leading-relaxed text-err">{result.error_message}</p>}

          {result.success && (
            <div className="grid grid-cols-[140px_minmax(0,1fr)] gap-x-4 gap-y-2.5 text-sm leading-normal">
              <span className="text-ink3">Page title</span>
              <span className="text-ink">{result.title_found || '—'}</span>
              <span className="text-ink3">Matched</span>
              <span className="font-mono text-ink">{result.matched_keywords.length ? result.matched_keywords.join(', ') : split(keywordsText).length ? 'none' : 'every event (no keywords)'}</span>
              <span className="text-ink3">Ignored</span>
              <span className="font-mono text-ink">{result.matched_exclusions.length ? result.matched_exclusions.join(', ') : 'none'}</span>
            </div>
          )}

          {result.sample_items.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="ew-caps">
                Sample items ({result.sample_items.length} of {result.items_found_count})
              </span>
              <div className="ew-well">
                {result.sample_items.map((it, i) => (
                  <div key={i} className={`py-3 px-4 flex flex-col gap-0.5 ${i ? 'border-t border-edge' : ''}`}>
                    <span className="text-sm font-medium text-ink">{it.title}</span>
                    <span className="text-[13px] text-ink3">{[it.date, it.venue].filter(Boolean).join(' · ') || it.url}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {works && (
            <div className="flex justify-end">
              <Button
                variant="secondary"
                icon={<Plus className="w-4 h-4" />}
                onClick={() =>
                  onCreateWatcherFromTest({
                    name: result.title_found || 'New watcher',
                    source_url: url.trim(),
                    source_type: sourceType,
                    keywords: split(keywordsText),
                    exclude_keywords: split(excludeText),
                  })
                }
              >
                Create watcher from this
              </Button>
            </div>
          )}
        </section>
      )}
    </>
  );
};
