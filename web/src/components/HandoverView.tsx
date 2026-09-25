import React, { useState, useEffect } from 'react';
import { ShieldCheck, CheckCircle2 } from 'lucide-react';
import { fetchHandoverInfo } from '../utils/api.js';

export const HandoverView: React.FC = () => {
  const [checklist, setChecklist] = useState<Array<{ id: string; title: string; status: boolean; detail: string }>>([]);

  useEffect(() => {
    fetchHandoverInfo()
      .then((data) => setChecklist(data.checklist || []))
      .catch((err) => console.error('Handover info fetch failed:', err));
  }, []);

  const verified = checklist.filter((c) => c.status).length;

  return (
    <div className="flex flex-col gap-6 max-w-[960px]">
      <section className="ew-card p-6 flex flex-col gap-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <span className="w-12 h-12 rounded-[14px] flex items-center justify-center bg-ok-soft text-ok">
              <ShieldCheck className="w-6 h-6" strokeWidth={1.8} />
            </span>
            <div className="flex flex-col gap-1">
              <div className="font-serif font-semibold text-[22px] leading-tight text-ink">Fully independent</div>
              <div className="text-sm text-ink3">Keeps running even if every developer account is deleted.</div>
            </div>
          </div>
          {checklist.length > 0 && (
            <span className="ew-stat !text-ok">
              {verified}
              <span className="font-medium text-base text-ink3"> / {checklist.length} verified</span>
            </span>
          )}
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-x-8">
          {checklist.map((c) => (
            <div key={c.id} className="flex gap-3 py-3.5 border-t border-line">
              <CheckCircle2 className={`w-5 h-5 shrink-0 mt-px ${c.status ? 'text-ok' : 'text-err'}`} strokeWidth={1.8} />
              <div className="flex flex-col gap-[3px] min-w-0">
                <span className="text-[15px] font-medium text-ink">{c.title}</span>
                <span className="text-[13px] leading-normal text-ink3 [overflow-wrap:anywhere]">{c.detail}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="ew-card p-6 flex flex-col gap-4">
        <h2 className="m-0 font-serif font-semibold text-xl text-ink">Where your data lives</h2>
        <p className="m-0 text-sm leading-relaxed text-ink3">
          Everything is in one folder on this computer (Backup &amp; transfer → Open data folder). Mac:{' '}
          <span className="font-mono text-ink2">~/Library/Application Support/EventWatcher</span> · Windows:{' '}
          <span className="font-mono text-ink2">%APPDATA%\EventWatcher</span>
        </p>
        <pre className="m-0 py-4 px-5 ew-well font-mono text-[13px] leading-[1.7] text-ink2 overflow-x-auto">
{`EventWatcher/
├── data/
│   └── eventwatcher.db     `}<span className="text-ink3"># SQLite 3 database</span>{`
├── config/
│   └── settings.json       `}<span className="text-ink3"># intervals, user-agent, notifications</span>{`
├── logs/
│   └── app.log             `}<span className="text-ink3"># local activity log</span>{`
└── backups/                `}<span className="text-ink3"># daily and exported ZIP backups</span>
        </pre>
      </section>

      <section className="ew-card p-6 flex flex-col gap-4">
        <h2 className="m-0 font-serif font-semibold text-xl text-ink">Running without the packaged app</h2>
        <p className="m-0 text-sm leading-relaxed text-ink3">
          Easiest is <span className="font-mono text-ink2">EventWatcher.app</span> / <span className="font-mono text-ink2">EventWatcher.exe</span>. From the
          source folder you only need Python 3.9+ (no extra packages):
        </p>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-3">
          <div className="py-3.5 px-4 ew-well flex flex-col gap-1.5">
            <span className="ew-caps">Windows</span>
            <code className="font-mono text-sm text-ink">python_backend\run.bat</code>
          </div>
          <div className="py-3.5 px-4 ew-well flex flex-col gap-1.5">
            <span className="ew-caps">macOS / Linux</span>
            <code className="font-mono text-sm text-ink">python_backend/run.sh</code>
          </div>
        </div>
        <p className="m-0 text-[13px] leading-normal text-ink3">
          Starts the local server on <span className="font-mono text-ink2">http://localhost:3847</span> and opens your browser.
        </p>
      </section>
    </div>
  );
};
