import React, { useState, useRef, useEffect } from 'react';
import { Download, Upload, Folder, CheckCircle2, RefreshCw } from 'lucide-react';
import { uploadBackupZip, openDataFolderApi, fetchSystemStatus, fetchSettings, saveSettingsApi } from '../utils/api.js';
import { Button } from './ui.js';

interface BackupViewProps {
  onRefreshAllData: () => void;
}

const TRANSFER_STEPS: Array<[string, string]> = [
  ['Export on the old computer', 'Click “Download full backup” above to save your watchers, filters and event history in one file.'],
  ['Open on the new computer', 'Download Event Watcher there and double-click EventWatcher.app (Mac) or EventWatcher.exe (Windows). No account or installation needed.'],
  ['Import and carry on', 'Open Backup & transfer, choose “Import backup” and pick your zip. Monitoring resumes where it left off.'],
];

export const BackupView: React.FC<BackupViewProps> = ({ onRefreshAllData }) => {
  const [isImporting, setIsImporting] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [importResult, setImportResult] = useState<{ message: string; watchers: number; events: number; previous?: string | null } | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [lastAutoBackup, setLastAutoBackup] = useState<string | null>(null);
  const [backupFolder, setBackupFolder] = useState('');
  const [folderMessage, setFolderMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const loadAutoBackupInfo = async () => {
    try {
      const [status, settings] = await Promise.all([fetchSystemStatus(), fetchSettings()]);
      setLastAutoBackup(status.storage?.last_automatic_backup ?? null);
      setBackupFolder(settings.backup_folder || '');
    } catch (err) {
      console.error('Failed to load backup info:', err);
    }
  };

  useEffect(() => {
    loadAutoBackupInfo();
  }, []);

  const handleSaveBackupFolder = async () => {
    setFolderMessage(null);
    try {
      await saveSettingsApi({ backup_folder: backupFolder.trim() });
      setFolderMessage({ ok: true, text: backupFolder.trim() ? 'Saved. Each daily backup will also be copied to this folder.' : 'Extra copy turned off.' });
      loadAutoBackupInfo();
    } catch (err: any) {
      setFolderMessage({ ok: false, text: err.message });
    }
  };

  const restore = async (file: File) => {
    setIsImporting(true);
    setErrorMessage(null);
    setImportResult(null);
    try {
      const res = await uploadBackupZip(file);
      setImportResult({ message: res.message, watchers: res.restoredWatchersCount, events: res.restoredEventsCount, previous: res.previousDatabaseSavedAs });
      onRefreshAllData();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to restore backup archive.');
    } finally {
      setIsImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) restore(file);
  };

  return (
    <div className="flex flex-col gap-6 max-w-[960px]">
      {importResult && (
        <div role="status" className="flex items-start gap-2.5 py-3.5 px-[18px] rounded-xl bg-ok-soft text-sm">
          <CheckCircle2 className="w-5 h-5 text-ok shrink-0" strokeWidth={1.8} />
          <div className="flex flex-col gap-1">
            <span className="font-semibold text-ink">{importResult.message}</span>
            <span className="text-ink2">Restored {importResult.watchers} watchers and {importResult.events} events.</span>
            {importResult.previous && (
              <span className="text-[13px] text-ink3">Your previous data was kept as backups/{importResult.previous} in case you need it.</span>
            )}
          </div>
        </div>
      )}
      {errorMessage && (
        <div role="alert" className="py-3.5 px-[18px] rounded-xl bg-err-soft border border-err-edge text-err text-sm font-medium">{errorMessage}</div>
      )}

      <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-6">
        <section className="ew-card p-6 flex flex-col gap-4">
          <div className="flex items-center gap-2.5">
            <Download className="w-[18px] h-[18px] text-accent" strokeWidth={1.8} />
            <h2 className="m-0 font-serif font-semibold text-xl text-ink">Export everything</h2>
          </div>
          <p className="m-0 text-sm leading-relaxed text-ink3">
            One timestamped <span className="font-mono text-ink2">.zip</span> with your database, settings, log and readable JSON copies.
          </p>
          <ul className="m-0 py-3 pr-4 pl-8 ew-well font-mono text-[13px] leading-[1.8] text-ink2">
            <li>data/eventwatcher.db</li>
            <li>config/settings.json</li>
            <li>logs/app.log</li>
            <li>export/watchers.json &amp; events.json</li>
          </ul>
          <div className="mt-auto">
            <Button variant="primary" fullWidth icon={<Download className="w-[18px] h-[18px]" />} onClick={() => (window.location.href = '/api/backup/export')}>
              Download full backup
            </Button>
          </div>
        </section>

        <section className="ew-card p-6 flex flex-col gap-4">
          <div className="flex items-center gap-2.5">
            <Upload className="w-[18px] h-[18px] text-accent" strokeWidth={1.8} />
            <h2 className="m-0 font-serif font-semibold text-xl text-ink">Import backup</h2>
          </div>
          <p className="m-0 text-sm leading-relaxed text-ink3">Restore a previous export. Your current database is kept as a copy first.</p>
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={onDrop}
            className={`flex-1 min-h-[110px] rounded-xl border border-dashed flex flex-col items-center justify-center gap-1.5 p-4 text-center ${
              isDragging ? 'border-accent bg-accent-soft' : 'border-field-edge'
            }`}
          >
            {isImporting ? <RefreshCw className="w-5 h-5 text-accent ew-spin" /> : <Folder className="w-5 h-5 text-ink3" strokeWidth={1.8} />}
            <span className="text-sm font-medium text-ink">{isImporting ? 'Restoring…' : 'Drop an Event Watcher backup ZIP'}</span>
            <span className="font-mono text-[13px] text-ink3">EventWatcher-Backup-YYYY-MM-DD.zip</span>
          </div>
          <input ref={fileInputRef} type="file" accept=".zip,application/zip" className="hidden" onChange={(e) => e.target.files?.[0] && restore(e.target.files[0])} />
          <Button variant="secondary" fullWidth icon={<Upload className="w-[18px] h-[18px]" />} disabled={isImporting} onClick={() => fileInputRef.current?.click()}>
            Choose file to restore
          </Button>
        </section>
      </div>

      <section className="ew-card p-6 flex flex-col gap-4">
        <h2 className="m-0 font-serif font-semibold text-xl text-ink">Automatic daily backups</h2>
        <p className="m-0 text-sm leading-relaxed text-ink3">
          A full backup is saved once a day; the last 14 are kept in the data folder. Last automatic backup:{' '}
          <span className="text-ink font-medium">{lastAutoBackup ? new Date(lastAutoBackup).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' }) : 'not yet (runs shortly after start-up)'}</span>.
        </p>
        <label className="flex flex-col gap-2">
          <span className="ew-label">
            Also copy each backup to this folder <span className="font-normal text-ink3">(optional)</span>
          </span>
          <div className="flex gap-2 flex-wrap">
            <input
              type="text"
              value={backupFolder}
              onChange={(e) => setBackupFolder(e.target.value)}
              placeholder="e.g. a USB drive, or a company OneDrive / Dropbox folder"
              className="ew-field !font-mono flex-[1_1_280px] !w-auto"
            />
            <Button variant="secondary" onClick={handleSaveBackupFolder}>Save folder</Button>
          </div>
          <span className="ew-help">Use a location the business owns, so a lost computer never means lost data. Leave empty to turn off.</span>
          {folderMessage && <span className={`text-[13px] ${folderMessage.ok ? 'text-ok' : 'text-err'}`}>{folderMessage.text}</span>}
        </label>
      </section>

      <section className="ew-card p-6 flex flex-col gap-5">
        <h2 className="m-0 font-serif font-semibold text-xl text-ink">Move to another computer</h2>
        <ol className="m-0 p-0 list-none grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-6">
          {TRANSFER_STEPS.map(([title, body], i) => (
            <li key={title} className="flex flex-col gap-2">
              <span className="w-8 h-8 rounded-[10px] flex items-center justify-center bg-accent-soft text-accent font-display font-semibold text-[15px]">{i + 1}</span>
              <span className="font-semibold text-[15px] text-ink">{title}</span>
              <span className="text-sm leading-relaxed text-ink3">{body}</span>
            </li>
          ))}
        </ol>
        <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-line">
          <span className="text-[13px] text-ink3">Your data folder lives on this computer only.</span>
          <Button variant="secondary" icon={<Folder className="w-5 h-5" strokeWidth={1.8} />} onClick={() => openDataFolderApi().catch((err) => setErrorMessage(err.message))}>
            Open data folder
          </Button>
        </div>
      </section>
    </div>
  );
};
