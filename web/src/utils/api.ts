import { 
  Watcher, 
  DetectedEvent, 
  SourceHealth, 
  AppSettings, 
  AppLogEntry, 
  TestSourceResult, 
  PresetWatcher 
} from '../types.js';

export async function fetchSystemStatus() {
  const res = await fetch('/api/status');
  if (!res.ok) throw new Error('Failed to fetch system status');
  return res.json();
}

export async function fetchWatchers(): Promise<Watcher[]> {
  const res = await fetch('/api/watchers');
  if (!res.ok) throw new Error('Failed to fetch watchers');
  return res.json();
}

export async function createWatcher(watcher: Partial<Watcher>): Promise<Watcher> {
  const res = await fetch('/api/watchers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(watcher),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to create watcher');
  }
  return res.json();
}

export async function updateWatcher(id: string, watcher: Partial<Watcher>): Promise<Watcher> {
  const res = await fetch(`/api/watchers/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(watcher),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to update watcher');
  }
  return res.json();
}

export async function deleteWatcherApi(id: string): Promise<void> {
  const res = await fetch(`/api/watchers/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete watcher');
}

export async function toggleWatcherApi(id: string): Promise<Watcher> {
  const res = await fetch(`/api/watchers/${id}/toggle`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to toggle watcher');
  return res.json();
}

export async function checkWatcherApi(id: string): Promise<{ newEventsFound: number; error?: string }> {
  const res = await fetch(`/api/watchers/${id}/check`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to check watcher');
  return res.json();
}

export async function checkAllWatchersApi(): Promise<{
  totalWatchersChecked: number;
  totalNewEvents: number;
  errors: string[];
}> {
  const res = await fetch('/api/watchers/check-all', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to run check cycle');
  return res.json();
}

export async function fetchEvents(params?: {
  watcher_id?: string;
  category?: string;
  status?: string;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<{ events: DetectedEvent[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.watcher_id) query.set('watcher_id', params.watcher_id);
  if (params?.category) query.set('category', params.category);
  if (params?.status) query.set('status', params.status);
  if (params?.search) query.set('search', params.search);
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));

  const res = await fetch(`/api/events?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch events');
  return res.json();
}

export async function updateEventStatusApi(id: string, status: 'unread' | 'read' | 'dismissed'): Promise<void> {
  const res = await fetch(`/api/events/${id}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error('Failed to update event status');
}

export async function toggleEventFavoriteApi(id: string): Promise<void> {
  const res = await fetch(`/api/events/${id}/favorite`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to toggle favorite');
}

export async function deleteEventApi(id: string): Promise<void> {
  const res = await fetch(`/api/events/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete event');
}

export async function clearAllEventsApi(): Promise<void> {
  const res = await fetch('/api/events/clear', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to clear events');
}

export async function fetchSources(): Promise<SourceHealth[]> {
  const res = await fetch('/api/sources');
  if (!res.ok) throw new Error('Failed to fetch sources');
  return res.json();
}

export async function testSourceApi(payload: {
  url: string;
  source_type?: string;
  keywords?: string[];
  exclude_keywords?: string[];
}): Promise<TestSourceResult> {
  const res = await fetch('/api/test-source', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Source test failed');
  }
  return res.json();
}

export async function fetchPresets(): Promise<PresetWatcher[]> {
  const res = await fetch('/api/presets');
  if (!res.ok) throw new Error('Failed to fetch presets');
  return res.json();
}

export async function fetchSettings(): Promise<AppSettings> {
  const res = await fetch('/api/settings');
  if (!res.ok) throw new Error('Failed to fetch settings');
  return res.json();
}

export async function saveSettingsApi(settings: Partial<AppSettings>): Promise<AppSettings> {
  const res = await fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to save settings');
  }
  return res.json();
}

export async function fetchLogs(limit = 100): Promise<AppLogEntry[]> {
  const res = await fetch(`/api/logs?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch logs');
  return res.json();
}

export async function uploadBackupZip(file: File): Promise<{
  success: boolean;
  message: string;
  restoredWatchersCount: number;
  restoredEventsCount: number;
  previousDatabaseSavedAs?: string | null;
}> {
  const buffer = await file.arrayBuffer();
  const res = await fetch('/api/backup/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/zip' },
    body: buffer,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to import backup');
  }
  return res.json();
}

export async function fetchHandoverInfo() {
  const res = await fetch('/api/handover-info');
  if (!res.ok) throw new Error('Failed to fetch handover verification');
  return res.json();
}

export async function sendTestNotificationApi(): Promise<{ success: boolean; detail: string }> {
  const res = await fetch('/api/notifications/test', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to send test notification');
  return res.json();
}

export async function openDataFolderApi(): Promise<{ success: boolean; path: string }> {
  const res = await fetch('/api/open-data-folder', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to open data folder');
  return res.json();
}

export async function shutdownAppApi(): Promise<void> {
  const res = await fetch('/api/shutdown', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to stop Event Watcher');
}
