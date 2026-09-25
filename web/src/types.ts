export type SourceType = 
  | 'rss' 
  | 'atom' 
  | 'webpage' 
  | 'event_listing' 
  | 'sports_fixture' 
  | 'calendar_ics' 
  | 'json_feed'
  | 'custom_url';

export type WatcherStatus = 'idle' | 'checking' | 'active' | 'error' | 'paused';

export interface Watcher {
  id: string;
  name: string;
  category: string;
  enabled: boolean;
  source_type: SourceType;
  source_url: string;
  keywords: string[];
  exclude_keywords: string[];
  check_interval_minutes: number;
  last_checked_at: string | null;
  last_successful_at: string | null;
  status: WatcherStatus;
  last_content_hash?: string;
  notify_desktop: boolean;
  notify_sound: boolean;
  created_at: string;
}

export interface DetectedEvent {
  id: string;
  watcher_id: string;
  title: string;
  source_name: string;
  source_url: string;
  detected_at: string;
  event_date: string | null;
  venue: string | null;
  category: string;
  matched_keywords: string[];
  short_description: string | null;
  content_fingerprint: string;
  notification_status: 'unread' | 'read' | 'dismissed';
  is_favorite: boolean;
}

export interface SourceHealth {
  watcher_id: string;
  watcher_name: string;
  category: string;
  url: string;
  source_type: SourceType;
  last_http_code: number | null;
  response_time_ms: number | null;
  consecutive_failures: number;
  last_error: string | null;
  last_checked_at: string | null;
  last_success_at: string | null;
  is_healthy: boolean;
}

export interface AppSettings {
  check_interval_minutes: number;
  desktop_notifications: boolean;
  sound_alerts: boolean;
  start_on_login: boolean;
  port: number;
  user_agent: string;
  request_timeout_seconds: number;
  theme: 'dark' | 'light';
  backup_folder?: string;
  data_directory: string;
}

export interface AppLogEntry {
  id: number;
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS';
  message: string;
  context?: string;
}

export interface TestSourceResult {
  success: boolean;
  url: string;
  http_code: number | null;
  response_time_ms: number;
  source_type_detected: string;
  title_found: string | null;
  sample_extracted_text: string;
  matched_keywords: string[];
  matched_exclusions: string[];
  items_found_count: number;
  sample_items: Array<{
    title: string;
    description?: string;
    date?: string;
    venue?: string;
    url?: string;
  }>;
  error_message?: string;
}

export interface PresetWatcher {
  id: string;
  name: string;
  category: string;
  source_type: SourceType;
  source_url: string;
  keywords: string[];
  exclude_keywords: string[];
  check_interval_minutes: number;
  description: string;
}
