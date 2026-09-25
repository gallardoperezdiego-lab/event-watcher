import React, { useState, useEffect, useRef } from 'react';
import { Plus, RefreshCw, Sun, Moon } from 'lucide-react';
import { Sidebar } from './components/Sidebar.js';
import { Button, IconButton } from './components/ui.js';
import { DashboardView } from './components/DashboardView.js';
import { WatchersView } from './components/WatchersView.js';
import { EventsView } from './components/EventsView.js';
import { SourcesView } from './components/SourcesView.js';
import { TestSourceSandbox } from './components/TestSourceSandbox.js';
import { SettingsView } from './components/SettingsView.js';
import { BackupView } from './components/BackupView.js';
import { HandoverView } from './components/HandoverView.js';
import { WatcherModal } from './components/WatcherModal.js';

import { 
  Watcher, 
  DetectedEvent, 
  SourceHealth, 
  AppSettings, 
  PresetWatcher, 
  SourceType 
} from './types.js';

import { 
  fetchSystemStatus, 
  fetchWatchers, 
  fetchEvents, 
  fetchSources, 
  fetchPresets, 
  fetchSettings, 
  saveSettingsApi, 
  createWatcher, 
  updateWatcher, 
  deleteWatcherApi, 
  toggleWatcherApi, 
  checkWatcherApi, 
  checkAllWatchersApi, 
  updateEventStatusApi, 
  toggleEventFavoriteApi, 
  deleteEventApi, 
  clearAllEventsApi 
} from './utils/api.js';

import { playNotificationChime } from './utils/audio.js';

const PAGES: Record<string, [string, string]> = {
  dashboard: ['Dashboard', 'New announcements from the venues you watch.'],
  events: ['Events', 'Everything your watchers have found.'],
  watchers: ['Watchers', 'The websites and feeds being checked for you.'],
  sources: ['Sources', 'Is every website reachable?'],
  test_sandbox: ['Test a source', 'Try any website or feed before adding it. Nothing is saved.'],
  settings: ['Settings', 'Schedule, alerts and the activity log.'],
  backup: ['Backup & transfer', 'Keep a copy of your data or move it to a new computer.'],
  handover: ['Handover & ownership', 'Proof that this app belongs entirely to you.'],
};

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [watchers, setWatchers] = useState<Watcher[]>([]);
  const [events, setEvents] = useState<DetectedEvent[]>([]);
  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [presets, setPresets] = useState<PresetWatcher[]>([]);
  const [settings, setSettings] = useState<AppSettings>({
    check_interval_minutes: 60,
    desktop_notifications: true,
    sound_alerts: true,
    start_on_login: false,
    port: 3847,
    user_agent: 'EventWatcher/1.0',
    request_timeout_seconds: 15,
    theme: 'dark',
    data_directory: '',
  });
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null);
  const [eventTotal, setEventTotal] = useState(0);

  // Operation states
  const [isCheckingAll, setIsCheckingAll] = useState(false);
  const [checkingWatcherId, setCheckingWatcherId] = useState<string | null>(null);

  // Modal states
  const [isWatcherModalOpen, setIsWatcherModalOpen] = useState(false);
  const [editingWatcher, setEditingWatcher] = useState<Watcher | null>(null);

  // Sandbox prepopulation state
  const [sandboxInitial, setSandboxInitial] = useState<{
    url?: string;
    type?: SourceType;
    keywords?: string[];
    exclusions?: string[];
  }>({});

  const previousEventCountRef = useRef<number>(0);

  // Load all initial data
  const loadData = async () => {
    try {
      const [wList, eRes, sList, pList, setts, status] = await Promise.all([
        fetchWatchers(),
        fetchEvents({ limit: 100 }),
        fetchSources(),
        fetchPresets(),
        fetchSettings(),
        fetchSystemStatus(),
      ]);

      setWatchers(wList);
      setEvents(eRes.events);
      setSources(sList);
      setPresets(pList);
      setSettings(setts);
      setSchedulerStatus(status.scheduler);
      setEventTotal(eRes.total);

      // Desktop notifications are sent natively by the local backend (they work even
      // with this page closed). While the page is open, also play the in-app chime.
      if (previousEventCountRef.current > 0 && eRes.total > previousEventCountRef.current && setts.sound_alerts) {
        playNotificationChime();
      }
      previousEventCountRef.current = eRes.total;
    } catch (err) {
      console.error('Failed to load application data:', err);
    }
  };

  useEffect(() => {
    loadData();
    // Background polling every 12 seconds
    const interval = setInterval(loadData, 12000);
    return () => clearInterval(interval);
  }, []);

  const handleCheckAll = async () => {
    setIsCheckingAll(true);
    try {
      const res = await checkAllWatchersApi();
      await loadData();
      if (res.totalNewEvents > 0 && settings.sound_alerts) playNotificationChime();
    } catch (err) {
      console.error('Check all failed:', err);
    } finally {
      setIsCheckingAll(false);
    }
  };

  const handleCheckWatcher = async (id: string) => {
    setCheckingWatcherId(id);
    try {
      const res = await checkWatcherApi(id);
      await loadData();
      if (res.newEventsFound > 0) {
        if (settings.sound_alerts) playNotificationChime();
      }
    } catch (err) {
      console.error('Single check failed:', err);
    } finally {
      setCheckingWatcherId(null);
    }
  };

  const handleToggleWatcher = async (id: string) => {
    try {
      await toggleWatcherApi(id);
      await loadData();
    } catch (err) {
      console.error('Toggle watcher failed:', err);
    }
  };

  const handleDeleteWatcher = async (id: string) => {
    try {
      await deleteWatcherApi(id);
      await loadData();
    } catch (err) {
      console.error('Delete watcher failed:', err);
    }
  };

  const handleSaveWatcher = async (watcherData: Partial<Watcher>) => {
    if (watcherData.id) {
      await updateWatcher(watcherData.id, watcherData);
    } else {
      await createWatcher(watcherData);
    }
    await loadData();
  };

  const handleToggleEventFavorite = async (id: string) => {
    try {
      await toggleEventFavoriteApi(id);
      setEvents(events.map(e => e.id === id ? { ...e, is_favorite: !e.is_favorite } : e));
    } catch (err) {
      console.error('Toggle favorite failed:', err);
    }
  };

  const handleUpdateEventStatus = async (id: string, status: 'unread' | 'read' | 'dismissed') => {
    try {
      await updateEventStatusApi(id, status);
      setEvents(events.map(e => e.id === id ? { ...e, notification_status: status } : e));
    } catch (err) {
      console.error('Update event status failed:', err);
    }
  };

  const handleDeleteEvent = async (id: string) => {
    try {
      await deleteEventApi(id);
      setEvents(events.filter(e => e.id !== id));
    } catch (err) {
      console.error('Delete event failed:', err);
    }
  };

  const handleClearAllEvents = async () => {
    try {
      await clearAllEventsApi();
      setEvents([]);
    } catch (err) {
      console.error('Clear events failed:', err);
    }
  };

  const handleTestUrlInSandbox = (
    url: string, 
    type: SourceType, 
    keywords: string[] = [], 
    exclusions: string[] = []
  ) => {
    setSandboxInitial({ url, type, keywords, exclusions });
    selectTab('test_sandbox');
  };

  const handleUsePreset = (preset: PresetWatcher) => {
    setEditingWatcher({
      id: '',
      name: preset.name,
      category: preset.category,
      enabled: true,
      source_type: preset.source_type,
      source_url: preset.source_url,
      keywords: preset.keywords,
      exclude_keywords: preset.exclude_keywords,
      check_interval_minutes: preset.check_interval_minutes,
      last_checked_at: null,
      last_successful_at: null,
      status: 'idle',
      notify_desktop: true,
      notify_sound: true,
      created_at: new Date().toISOString(),
    });
    setIsWatcherModalOpen(true);
  };

  const handleCreateWatcherFromTest = (data: {
    name: string;
    source_url: string;
    source_type: SourceType;
    keywords: string[];
    exclude_keywords: string[];
  }) => {
    setEditingWatcher({
      id: '',
      name: data.name,
      category: 'General',
      enabled: true,
      source_type: data.source_type,
      source_url: data.source_url,
      keywords: data.keywords,
      exclude_keywords: data.exclude_keywords,
      check_interval_minutes: 60,
      last_checked_at: null,
      last_successful_at: null,
      status: 'idle',
      notify_desktop: true,
      notify_sound: true,
      created_at: new Date().toISOString(),
    });
    setIsWatcherModalOpen(true);
  };

  const handleToggleTheme = () => {
    const nextTheme: 'dark' | 'light' = settings.theme === 'dark' ? 'light' : 'dark';
    const updated: AppSettings = { ...settings, theme: nextTheme };
    setSettings(updated);
    saveSettingsApi({ theme: nextTheme });
  };

  const handleUpdateSettings = async (newSettings: Partial<AppSettings>) => {
    const updated = await saveSettingsApi(newSettings);
    setSettings(updated);
  };

  const failedSourcesCount = sources.filter(s => !s.is_healthy).length;
  const unreadCount = events.filter(e => e.notification_status === 'unread').length;
  const openNewWatcher = () => { setEditingWatcher(null); setIsWatcherModalOpen(true); };
  const selectTab = (tab: string) => { setActiveTab(tab); window.scrollTo(0, 0); };
  const page = PAGES[activeTab] || PAGES.dashboard;

  useEffect(() => {
    document.documentElement.dataset.theme = settings.theme;
  }, [settings.theme]);

  return (
    <div className="min-h-screen grid grid-cols-[auto_minmax(0,1fr)] text-ink font-sans">
      <Sidebar
        activeTab={activeTab}
        onSelectTab={selectTab}
        unreadCount={unreadCount}
        failingCount={failedSourcesCount}
        nextCheckTime={schedulerStatus?.nextCheckTime}
      />

      <div className="min-w-0 flex flex-col">
        <header className="sticky top-0 z-20 flex items-center gap-4 py-3.5 px-[clamp(20px,3vw,40px)] min-h-[76px] box-border border-b border-line bg-bar backdrop-blur-[14px]">
          <div className="flex-1 min-w-0 flex flex-col gap-1">
            <h1 className="m-0 font-serif font-semibold text-[26px] leading-tight text-ink truncate">{page[0]}</h1>
            <p className="m-0 text-sm text-ink3 truncate hidden min-[820px]:block">{page[1]}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
<span className="hidden min-[820px]:inline-flex">
            <Button
              variant="secondary"
              onClick={handleCheckAll}
              disabled={isCheckingAll}
              title="Check all active watchers now"
              icon={<RefreshCw className={`w-4 h-4 ${isCheckingAll ? 'ew-spin' : ''}`} />}
            >
              {isCheckingAll ? 'Checking…' : 'Check all now'}
            </Button>
            </span>
            <IconButton label="Check all now" tone="bordered" onClick={handleCheckAll} disabled={isCheckingAll} className="min-[820px]:hidden">
              <RefreshCw className={`w-4 h-4 ${isCheckingAll ? 'ew-spin' : ''}`} />
            </IconButton>
            <Button variant="primary" onClick={openNewWatcher} icon={<Plus className="w-4 h-4" />}>New watcher</Button>
            <IconButton
              label={settings.theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              tone="bordered"
              onClick={handleToggleTheme}
            >
              {settings.theme === 'dark' ? <Sun className="w-[18px] h-[18px]" /> : <Moon className="w-[18px] h-[18px]" />}
            </IconButton>
          </div>
        </header>

      {/* Main Viewport Content Container */}
      <main className="w-full max-w-[1160px] box-border pt-8 pb-16 px-[clamp(20px,3vw,40px)] flex flex-col gap-8">
        {activeTab === 'dashboard' && (
          <DashboardView
            watchers={watchers}
            events={events}
            sources={sources}
            schedulerStatus={schedulerStatus}
            eventTotal={eventTotal}
            onSelectTab={selectTab}
            onOpenNewWatcher={openNewWatcher}
            onCheckAll={handleCheckAll}
            isCheckingAll={isCheckingAll}
            onToggleEventFavorite={handleToggleEventFavorite}
            onMarkEventRead={(id) => handleUpdateEventStatus(id, 'read')}
            presets={presets}
            onUsePreset={handleUsePreset}
          />
        )}

        {activeTab === 'watchers' && (
          <WatchersView
            watchers={watchers}
            onOpenCreateModal={openNewWatcher}
            onEditWatcher={(w) => { setEditingWatcher(w); setIsWatcherModalOpen(true); }}
            onDeleteWatcher={handleDeleteWatcher}
            onToggleWatcher={handleToggleWatcher}
            onCheckWatcher={handleCheckWatcher}
            onTestUrl={handleTestUrlInSandbox}
            checkingWatcherId={checkingWatcherId}
          />
        )}

        {activeTab === 'events' && (
          <EventsView
            events={events}
            watchers={watchers}
            onToggleFavorite={handleToggleEventFavorite}
            onUpdateStatus={handleUpdateEventStatus}
            onDeleteEvent={handleDeleteEvent}
            onClearAll={handleClearAllEvents}
          />
        )}

        {activeTab === 'sources' && (
          <SourcesView
            sources={sources}
            onTestUrl={handleTestUrlInSandbox}
            onCheckWatcher={handleCheckWatcher}
            checkingWatcherId={checkingWatcherId}
          />
        )}

        {activeTab === 'test_sandbox' && (
          <TestSourceSandbox
            initialUrl={sandboxInitial.url}
            initialType={sandboxInitial.type}
            initialKeywords={sandboxInitial.keywords}
            initialExclusions={sandboxInitial.exclusions}
            onCreateWatcherFromTest={handleCreateWatcherFromTest}
          />
        )}

        {activeTab === 'settings' && (
          <SettingsView
            settings={settings}
            onUpdateSettings={handleUpdateSettings}
          />
        )}

        {activeTab === 'backup' && (
          <BackupView
            onRefreshAllData={loadData}
          />
        )}

        {activeTab === 'handover' && (
          <HandoverView />
        )}
      </main>
      </div>

      {/* Watcher Modal (Add / Edit) */}
      <WatcherModal
        isOpen={isWatcherModalOpen}
        onClose={() => setIsWatcherModalOpen(false)}
        onSave={handleSaveWatcher}
        initialData={editingWatcher}
      />
    </div>
  );
}
