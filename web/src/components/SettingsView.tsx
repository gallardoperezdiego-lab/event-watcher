import React, { useState, useEffect } from 'react';
import { CheckCircle2, Power, RefreshCw } from 'lucide-react';
import { AppSettings, AppLogEntry } from '../types.js';
import { fetchLogs, sendTestNotificationApi, shutdownAppApi } from '../utils/api.js';
import { playNotificationChime } from '../utils/audio.js';
import { Button, IconButton, Segmented, Switch, INTERVAL_OPTIONS } from './ui.js';

interface SettingsViewProps {
  settings: AppSettings;
  onUpdateSettings: (settings: Partial<AppSettings>) => Promise<void>;
}

type LogLevel = 'ALL' | 'INFO' | 'SUCCESS' | 'WARN' | 'ERROR';
const LEVEL_COLOR: Record<string, string> = { INFO: 'text-ink2', SUCCESS: 'text-ok', WARN: 'text-ink', ERROR: 'text-err' };

export const SettingsView: React.FC<SettingsViewProps> = ({ settings, onUpdateSettings }) => {
  const [form, setForm] = useState<AppSettings>(settings);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [notificationResult, setNotificationResult] = useState<{ success: boolean; detail: string } | null>(null);
  const [isStopped, setIsStopped] = useState(false);
  const [logs, setLogs] = useState<AppLogEntry[]>([]);
  const [logFilter, setLogFilter] = useState<LogLevel>('ALL');
  const [isLoadingLogs, setIsLoadingLogs] = useState(false);

  useEffect(() => {
    setForm(settings);
  }, [settings]);

  useEffect(() => {
    loadLogs();
  }, []);

  const loadLogs = async () => {
    setIsLoadingLogs(true);
    try {
      setLogs(await fetchLogs(80));
    } catch (err) {
      console.error('Failed to load logs:', err);
    } finally {
      setIsLoadingLogs(false);
    }
  };

  const handleTestNotification = async () => {
    setNotificationResult(null);
    try {
      setNotificationResult(await sendTestNotificationApi());
    } catch (err: any) {
      setNotificationResult({ success: false, detail: err.message });
    }
  };

  const handleStop = async () => {
    if (!window.confirm('Stop Event Watcher? Sources will not be checked until you open the app again.')) return;
    try {
      await shutdownAppApi();
      setIsStopped(true);
    } catch (err) {
      console.error('Stop failed:', err);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaved(false);
    setSaveError(null);
    try {
      // Backup folder and data location are managed elsewhere; never resend them from here.
      const { backup_folder: _folder, data_directory: _dir, ...changes } = form;
      await onUpdateSettings(changes);
      setSaved(true);
      window.scrollTo(0, 0);
      setTimeout(() => setSaved(false), 3000);
      loadLogs();
    } catch (err: any) {
      setSaveError(err.message || 'Settings could not be saved.');
    } finally {
      setIsSaving(false);
    }
  };

  const switchRows: Array<{ id: keyof AppSettings; label: string; help: string; extra?: React.ReactNode }> = [
    {
      id: 'desktop_notifications',
      label: 'Desktop notifications',
      help: 'A system notification when new matching events are found — even with this page closed.',
      extra: (
        <>
          <div className="pt-1">
            <Button variant="ghost" className="!pl-0" onClick={handleTestNotification}>Send test notification</Button>
          </div>
          {notificationResult && (
            <span role="status" className={`text-[13px] leading-normal ${notificationResult.success ? 'text-ink2' : 'text-err'}`}>
              {notificationResult.success
                ? 'Sent. If nothing appeared, allow notifications for Event Watcher (macOS: System Settings › Notifications › Script Editor; Windows: Settings › System › Notifications).'
                : `Could not show a notification: ${notificationResult.detail}`}
            </span>
          )}
        </>
      ),
    },
    {
      id: 'sound_alerts',
      label: 'Sound alert',
      help: 'A soft two-tone chime while this page is open. No sound files needed.',
      extra: (
        <div className="pt-1">
          <Button variant="ghost" className="!pl-0" onClick={playNotificationChime}>Play test sound</Button>
        </div>
      ),
    },
    {
      id: 'start_on_login',
      label: 'Start Event Watcher when I log in',
      help: 'Runs quietly in the background each time you log in to this computer. Saved when you press Save settings.',
    },
  ];

  const filteredLogs = logs.filter((l) => logFilter === 'ALL' || l.level === logFilter);

  return (
    <div className="flex flex-col gap-6 max-w-[880px]">
      {saved && (
        <div role="status" className="flex items-center gap-2.5 py-3.5 px-[18px] rounded-xl bg-ok-soft text-ink text-sm font-medium">
          <CheckCircle2 className="w-5 h-5 text-ok" strokeWidth={1.8} />
          Settings saved.
        </div>
      )}
      {saveError && (
        <div role="alert" className="py-3.5 px-[18px] rounded-xl bg-err-soft border border-err-edge text-err text-sm font-medium">{saveError}</div>
      )}

      <section className="ew-card p-6 flex flex-col gap-5">
        <h2 className="m-0 font-serif font-semibold text-xl text-ink">Checking schedule</h2>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-5">
          <label className="flex flex-col gap-2">
            <span className="ew-label">How often to check</span>
            <select
              value={form.check_interval_minutes}
              onChange={(e) => setForm({ ...form, check_interval_minutes: Number(e.target.value) })}
              className="ew-field"
            >
              {INTERVAL_OPTIONS.map(([v, l]) => (
                <option key={v} value={v}>{v === 60 ? `${l} (recommended)` : l}</option>
              ))}
            </select>
            <span className="ew-help">Polite spacing avoids overloading venue websites. Each watcher also has its own frequency.</span>
          </label>
          <label className="flex flex-col gap-2">
            <span className="ew-label">Request timeout (seconds)</span>
            <input
              type="number"
              min={5}
              max={60}
              value={form.request_timeout_seconds}
              onChange={(e) => setForm({ ...form, request_timeout_seconds: Number(e.target.value) })}
              className="ew-field !font-mono"
            />
            <span className="ew-help">Give up if a website takes longer than this.</span>
          </label>
        </div>
      </section>

      <section className="ew-card py-2 px-6">
        <h2 className="mt-4 mb-2 font-serif font-semibold text-xl text-ink">Alerts</h2>
        {switchRows.map((r, i) => (
          <div key={r.id} className={`flex items-start gap-5 py-[18px] ${i ? 'border-t border-line' : ''}`}>
            <div className="flex-1 min-w-0 flex flex-col gap-1.5">
              <span id={`sw-${r.id}`} className="text-[15px] font-medium text-ink">{r.label}</span>
              <span className="ew-help">{r.help}</span>
              {r.extra}
            </div>
            <Switch checked={Boolean(form[r.id])} onChange={(v) => setForm({ ...form, [r.id]: v })} labelledBy={`sw-${r.id}`} />
          </div>
        ))}
      </section>

      <section className="ew-card p-6 flex flex-col gap-3">
        <h2 className="m-0 mb-2 font-serif font-semibold text-xl text-ink">Advanced</h2>
        <label className="flex flex-col gap-2">
          <span className="ew-label">User-Agent header</span>
          <input type="text" value={form.user_agent} onChange={(e) => setForm({ ...form, user_agent: e.target.value })} className="ew-field !font-mono" />
          <span className="ew-help">Identifies Event Watcher as an honest, non-aggressive personal client.</span>
        </label>
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button variant="danger" icon={<Power className="w-[18px] h-[18px]" />} onClick={handleStop} disabled={isStopped}>
          {isStopped ? 'Stopped — you can close this tab' : 'Stop Event Watcher'}
        </Button>
        <Button variant="primary" onClick={handleSave} disabled={isSaving}>{isSaving ? 'Saving…' : 'Save settings'}</Button>
      </div>

      <section className="ew-card p-6 flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex-[1_1_240px] flex flex-col gap-1">
            <h2 className="m-0 font-serif font-semibold text-xl text-ink">Activity log</h2>
            <span className="font-mono text-[13px] text-ink3">EventWatcher/logs/app.log</span>
          </div>
          <Segmented<LogLevel> mono label="Filter log" value={logFilter} onChange={setLogFilter} options={[['ALL', 'ALL'], ['INFO', 'INFO'], ['SUCCESS', 'SUCCESS'], ['WARN', 'WARN'], ['ERROR', 'ERROR']]} />
          <IconButton label="Refresh log" onClick={loadLogs} disabled={isLoadingLogs}>
            <RefreshCw className={`w-[18px] h-[18px] ${isLoadingLogs ? 'ew-spin' : ''}`} strokeWidth={1.8} />
          </IconButton>
        </div>
        <div className="max-h-[280px] overflow-y-auto py-3 px-4 ew-well flex flex-col gap-1.5">
          {filteredLogs.length === 0 ? (
            <div className="py-4 text-center text-[13px] text-ink3">No log entries for this filter.</div>
          ) : (
            filteredLogs.map((l) => (
              <div key={l.id} className="grid grid-cols-[72px_76px_minmax(0,1fr)] gap-3 font-mono text-[13px] leading-normal">
                <span className="text-ink3">{new Date(l.timestamp).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</span>
                <span className={`font-semibold ${LEVEL_COLOR[l.level] || 'text-ink2'}`}>{l.level}</span>
                <span className="text-ink2 break-words">{l.context ? `[${l.context}] ` : ''}{l.message}</span>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
};
