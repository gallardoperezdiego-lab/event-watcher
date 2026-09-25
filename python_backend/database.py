"""
Event Watcher - Local SQLite data layer, settings and input validation.
Zero cloud dependencies: everything lives in the local data folder (see paths.py).
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import string
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple

from paths import BASE_DIR, DB_PATH, LOG_PATH, SETTINGS_PATH, ensure_dirs

ensure_dirs()

SOURCE_TYPES = ("rss", "atom", "webpage", "event_listing", "sports_fixture", "calendar_ics", "json_feed", "custom_url")
EVENT_STATUSES = ("unread", "read", "dismissed")
MIN_INTERVAL_MINUTES = 15
MAX_INTERVAL_MINUTES = 1440
MAX_LOG_BYTES = 2 * 1024 * 1024
MAX_LOG_ROWS = 5000

DEFAULT_SETTINGS: Dict[str, Any] = {
    "check_interval_minutes": 60,
    "desktop_notifications": True,
    "sound_alerts": True,
    "start_on_login": False,
    "port": 3847,
    "user_agent": "EventWatcher/1.1 (personal, non-commercial event tracker)",
    "request_timeout_seconds": 15,
    "theme": "dark",
    "backup_folder": "",
    "data_directory": str(BASE_DIR),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    source_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    keywords TEXT NOT NULL DEFAULT '[]',
    exclude_keywords TEXT NOT NULL DEFAULT '[]',
    check_interval_minutes INTEGER NOT NULL DEFAULT 60,
    last_checked_at TEXT,
    last_successful_at TEXT,
    status TEXT NOT NULL DEFAULT 'idle',
    last_content_hash TEXT DEFAULT '',
    notify_desktop INTEGER NOT NULL DEFAULT 1,
    notify_sound INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    watcher_id TEXT NOT NULL,
    title TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    event_date TEXT,
    venue TEXT,
    category TEXT NOT NULL,
    matched_keywords TEXT NOT NULL DEFAULT '[]',
    short_description TEXT,
    content_fingerprint TEXT UNIQUE,
    notification_status TEXT NOT NULL DEFAULT 'unread',
    is_favorite INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (watcher_id) REFERENCES watchers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS source_health (
    watcher_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    last_http_code INTEGER,
    response_time_ms INTEGER,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    last_checked_at TEXT,
    last_success_at TEXT,
    FOREIGN KEY (watcher_id) REFERENCES watchers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    context TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_detected_at ON events(detected_at);
CREATE INDEX IF NOT EXISTS idx_events_watcher ON events(watcher_id);
"""

REQUIRED_TABLES = ("watchers", "events", "source_health", "app_logs")

# One lock serialises every database access so the web server threads, the
# scheduler thread and a backup restore never step on each other.
DB_LOCK = threading.RLock()
_log_lock = threading.Lock()


class ValidationError(ValueError):
    """Raised for user input that cannot be accepted; message is user-facing."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}-{int(time.time() * 1000)}-{suffix}"


def _connect(path=DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    """Locked, auto-committing connection."""
    with DB_LOCK:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db(path=DB_PATH, seed: bool = True) -> None:
    with DB_LOCK:
        conn = _connect(path)
        try:
            conn.executescript(SCHEMA)
            count = conn.execute("SELECT COUNT(*) FROM watchers").fetchone()[0]
            if seed and count == 0:
                _seed_watchers(conn)
            conn.commit()
        finally:
            conn.close()


def _seed_watchers(conn: sqlite3.Connection) -> None:
    from presets import SEED_WATCHERS

    created = now_iso()
    for w in SEED_WATCHERS:
        conn.execute(
            """INSERT INTO watchers (id, name, category, enabled, source_type, source_url, keywords,
               exclude_keywords, check_interval_minutes, status, notify_desktop, notify_sound, created_at)
               VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, 'idle', 1, 1, ?)""",
            (w["id"], w["name"], w["category"], w["source_type"], w["source_url"],
             json.dumps(w["keywords"]), json.dumps(w["exclude_keywords"]),
             w["check_interval_minutes"], created),
        )
        conn.execute(
            "INSERT OR IGNORE INTO source_health (watcher_id, url, consecutive_failures) VALUES (?, ?, 0)",
            (w["id"], w["source_url"]),
        )


# ---------------------------------------------------------------- logging

def log_message(level: str, message: str, context: str = "") -> None:
    timestamp = now_iso()
    message = str(message).replace("\r", " ").replace("\n", " ")[:2000]
    line = f"[{timestamp}] [{level}] {f'[{context}] ' if context else ''}{message}\n"
    with _log_lock:
        try:
            if LOG_PATH.exists() and LOG_PATH.stat().st_size > MAX_LOG_BYTES:
                rotated = LOG_PATH.with_suffix(".log.1")
                os.replace(LOG_PATH, rotated)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError as e:
            print(f"Failed to write to app.log: {e}")
    try:
        with db() as conn:
            conn.execute(
                "INSERT INTO app_logs (timestamp, level, message, context) VALUES (?, ?, ?, ?)",
                (timestamp, level, message, context or None),
            )
            conn.execute(
                "DELETE FROM app_logs WHERE id <= (SELECT MAX(id) FROM app_logs) - ?", (MAX_LOG_ROWS,)
            )
    except sqlite3.Error:
        pass


def get_logs(limit: int = 100) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 1000))
    with db() as conn:
        rows = conn.execute("SELECT * FROM app_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [
        {"id": r["id"], "timestamp": r["timestamp"], "level": r["level"],
         "message": r["message"], "context": r["context"] or None}
        for r in rows
    ]


# ---------------------------------------------------------------- settings

def _as_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    raise ValidationError(f"'{field}' must be true or false.")


def _as_int(value: Any, field: str, lo: int, hi: int) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        raise ValidationError(f"'{field}' must be a number.")
    if number < lo or number > hi:
        raise ValidationError(f"'{field}' must be between {lo} and {hi}.")
    return number


def sanitize_settings(update: Dict[str, Any], strict: bool = True) -> Dict[str, Any]:
    """Validate a partial settings update. Unknown keys are dropped.
    strict=False silently skips invalid values (used when reading files from disk/backups)."""
    if not isinstance(update, dict):
        raise ValidationError("Settings must be a JSON object.")
    clean: Dict[str, Any] = {}
    validators = {
        "check_interval_minutes": lambda v: _as_int(v, "check_interval_minutes", MIN_INTERVAL_MINUTES, MAX_INTERVAL_MINUTES),
        "desktop_notifications": lambda v: _as_bool(v, "desktop_notifications"),
        "sound_alerts": lambda v: _as_bool(v, "sound_alerts"),
        "start_on_login": lambda v: _as_bool(v, "start_on_login"),
        "port": lambda v: _as_int(v, "port", 1024, 65535),
        "request_timeout_seconds": lambda v: _as_int(v, "request_timeout_seconds", 5, 60),
        "user_agent": _clean_user_agent,
        "theme": _clean_theme,
        "backup_folder": _clean_backup_folder,
    }
    for key, validate in validators.items():
        if key not in update:
            continue
        try:
            clean[key] = validate(update[key])
        except ValidationError:
            if strict:
                raise
    return clean


def _clean_user_agent(value: Any) -> str:
    text = " ".join(str(value or "").split())[:200]
    if not text:
        raise ValidationError("User-Agent cannot be empty.")
    if not all(32 <= ord(c) < 127 for c in text):
        raise ValidationError("User-Agent may only contain plain ASCII characters.")
    return text


def _clean_backup_folder(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    folder = os.path.abspath(os.path.expanduser(text))
    if not os.path.isdir(folder):
        raise ValidationError("The extra backup folder does not exist. Create it first or check the path.")
    if not os.access(folder, os.W_OK):
        raise ValidationError("Event Watcher cannot write to the extra backup folder.")
    return folder


def _clean_theme(value: Any) -> str:
    if value not in ("dark", "light"):
        raise ValidationError("Theme must be 'dark' or 'light'.")
    return value


def load_settings() -> Dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                stored = json.load(f)
            settings.update(sanitize_settings(stored, strict=False))
            # Keep the extra backup folder even while it is unavailable (e.g. USB drive unplugged),
            # so the owner is warned instead of the setting silently disappearing.
            if isinstance(stored, dict) and isinstance(stored.get("backup_folder"), str):
                settings["backup_folder"] = stored["backup_folder"].strip()
        except (OSError, ValueError) as e:
            print(f"Error loading settings: {e}")
    settings["data_directory"] = str(BASE_DIR)
    return settings


def write_settings_file(settings: Dict[str, Any]) -> None:
    to_store = {k: v for k, v in settings.items() if k != "data_directory"}
    tmp = SETTINGS_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(to_store, f, indent=2)
    os.replace(tmp, SETTINGS_PATH)


def save_settings(update: Dict[str, Any]) -> Dict[str, Any]:
    clean = sanitize_settings(update)
    current = load_settings()
    current.update(clean)
    write_settings_file(current)
    log_message("INFO", "Settings updated", "Settings")
    return load_settings()


# ---------------------------------------------------------------- watchers

def _row_to_watcher(r: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": r["id"],
        "name": r["name"],
        "category": r["category"],
        "enabled": bool(r["enabled"]),
        "source_type": r["source_type"],
        "source_url": r["source_url"],
        "keywords": _json_list(r["keywords"]),
        "exclude_keywords": _json_list(r["exclude_keywords"]),
        "check_interval_minutes": r["check_interval_minutes"],
        "last_checked_at": r["last_checked_at"],
        "last_successful_at": r["last_successful_at"],
        "status": r["status"],
        "last_content_hash": r["last_content_hash"],
        "notify_desktop": bool(r["notify_desktop"]),
        "notify_sound": bool(r["notify_sound"]),
        "created_at": r["created_at"],
    }


def _json_list(raw: Optional[str]) -> List[str]:
    try:
        value = json.loads(raw or "[]")
        return [str(v) for v in value] if isinstance(value, list) else []
    except ValueError:
        return []


def _clean_keywords(value: Any, field: str) -> List[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        raise ValidationError(f"'{field}' must be a list of words.")
    words: List[str] = []
    for item in value:
        word = " ".join(str(item).split())
        if word and word.lower() not in (w.lower() for w in words):
            if len(word) > 100:
                raise ValidationError(f"Each entry in '{field}' must be under 100 characters.")
            words.append(word)
    if len(words) > 50:
        raise ValidationError(f"'{field}' can contain at most 50 entries.")
    return words


def sanitize_watcher(data: Dict[str, Any], existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from netguard import UnsafeURLError, validate_url

    if not isinstance(data, dict):
        raise ValidationError("Watcher must be a JSON object.")
    merged = dict(existing or {})
    merged.update({k: v for k, v in data.items() if v is not None})

    name = " ".join(str(merged.get("name") or "").split())
    if not name:
        raise ValidationError("Please give the watcher a name.")
    if len(name) > 120:
        raise ValidationError("Watcher name must be under 120 characters.")

    source_type = str(merged.get("source_type") or "")
    if source_type not in SOURCE_TYPES:
        raise ValidationError("Please choose a valid source type.")

    try:
        source_url = validate_url(str(merged.get("source_url") or "").strip())
    except UnsafeURLError as e:
        raise ValidationError(str(e))

    category = " ".join(str(merged.get("category") or "General").split())[:60] or "General"
    interval = merged.get("check_interval_minutes") or 60
    interval = _as_int(interval, "check_interval_minutes", MIN_INTERVAL_MINUTES, MAX_INTERVAL_MINUTES)

    return {
        "name": name,
        "category": category,
        "source_type": source_type,
        "source_url": source_url,
        "keywords": _clean_keywords(merged.get("keywords"), "keywords"),
        "exclude_keywords": _clean_keywords(merged.get("exclude_keywords"), "exclude_keywords"),
        "check_interval_minutes": interval,
        "enabled": _as_bool(merged.get("enabled", True), "enabled"),
        "notify_desktop": _as_bool(merged.get("notify_desktop", True), "notify_desktop"),
        "notify_sound": _as_bool(merged.get("notify_sound", True), "notify_sound"),
    }


def get_all_watchers() -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM watchers ORDER BY created_at DESC").fetchall()
    return [_row_to_watcher(r) for r in rows]


def get_watcher(watcher_id: str) -> Optional[Dict[str, Any]]:
    with db() as conn:
        r = conn.execute("SELECT * FROM watchers WHERE id = ?", (watcher_id,)).fetchone()
    return _row_to_watcher(r) if r else None


def create_watcher(data: Dict[str, Any]) -> Dict[str, Any]:
    w = sanitize_watcher(data)
    watcher_id = new_id("watcher")
    with db() as conn:
        conn.execute(
            """INSERT INTO watchers (id, name, category, enabled, source_type, source_url, keywords,
               exclude_keywords, check_interval_minutes, last_checked_at, last_successful_at, status,
               last_content_hash, notify_desktop, notify_sound, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 'idle', '', ?, ?, ?)""",
            (watcher_id, w["name"], w["category"], int(w["enabled"]), w["source_type"], w["source_url"],
             json.dumps(w["keywords"]), json.dumps(w["exclude_keywords"]), w["check_interval_minutes"],
             int(w["notify_desktop"]), int(w["notify_sound"]), now_iso()),
        )
        conn.execute(
            "INSERT OR REPLACE INTO source_health (watcher_id, url, consecutive_failures) VALUES (?, ?, 0)",
            (watcher_id, w["source_url"]),
        )
    log_message("SUCCESS", f'Created new watcher: "{w["name"]}" ({w["source_type"]})', "Watchers")
    return get_watcher(watcher_id)  # type: ignore[return-value]


def update_watcher(watcher_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    existing = get_watcher(watcher_id)
    if not existing:
        return None
    w = sanitize_watcher(data, existing)
    source_changed = (w["source_url"], w["source_type"]) != (existing["source_url"], existing["source_type"])
    with db() as conn:
        if source_changed:
            # A new source starts with a fresh baseline: what is listed there now is not "news".
            conn.execute("UPDATE watchers SET last_successful_at = NULL, last_content_hash = '' WHERE id = ?",
                         (watcher_id,))
            conn.execute("UPDATE source_health SET consecutive_failures = 0, last_error = NULL WHERE watcher_id = ?",
                         (watcher_id,))
        conn.execute(
            """UPDATE watchers SET name = ?, category = ?, enabled = ?, source_type = ?, source_url = ?,
               keywords = ?, exclude_keywords = ?, check_interval_minutes = ?, notify_desktop = ?,
               notify_sound = ? WHERE id = ?""",
            (w["name"], w["category"], int(w["enabled"]), w["source_type"], w["source_url"],
             json.dumps(w["keywords"]), json.dumps(w["exclude_keywords"]), w["check_interval_minutes"],
             int(w["notify_desktop"]), int(w["notify_sound"]), watcher_id),
        )
        conn.execute("UPDATE source_health SET url = ? WHERE watcher_id = ?", (w["source_url"], watcher_id))
    log_message("INFO", f'Updated watcher: "{w["name"]}"', "Watchers")
    return get_watcher(watcher_id)


def delete_watcher(watcher_id: str) -> None:
    w = get_watcher(watcher_id)
    with db() as conn:
        conn.execute("DELETE FROM events WHERE watcher_id = ?", (watcher_id,))
        conn.execute("DELETE FROM source_health WHERE watcher_id = ?", (watcher_id,))
        conn.execute("DELETE FROM watchers WHERE id = ?", (watcher_id,))
    if w:
        log_message("INFO", f'Deleted watcher: "{w["name"]}"', "Watchers")


def set_watcher_status(watcher_id: str, status: str, checked_at: Optional[str] = None,
                       success_at: Optional[str] = None, content_hash: Optional[str] = None) -> None:
    sets, params = ["status = ?"], [status]
    if checked_at:
        sets.append("last_checked_at = ?")
        params.append(checked_at)
    if success_at:
        sets.append("last_successful_at = ?")
        params.append(success_at)
    if content_hash is not None:
        sets.append("last_content_hash = ?")
        params.append(content_hash)
    params.append(watcher_id)
    with db() as conn:
        conn.execute(f"UPDATE watchers SET {', '.join(sets)} WHERE id = ?", params)


# ---------------------------------------------------------------- events

def _row_to_event(r: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": r["id"],
        "watcher_id": r["watcher_id"],
        "title": r["title"],
        "source_name": r["source_name"],
        "source_url": r["source_url"],
        "detected_at": r["detected_at"],
        "event_date": r["event_date"],
        "venue": r["venue"],
        "category": r["category"],
        "matched_keywords": _json_list(r["matched_keywords"]),
        "short_description": r["short_description"],
        "content_fingerprint": r["content_fingerprint"],
        "notification_status": r["notification_status"],
        "is_favorite": bool(r["is_favorite"]),
    }


def get_events(watcher_id: Optional[str] = None, category: Optional[str] = None, status: Optional[str] = None,
               search: Optional[str] = None, limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    where, params = ["1=1"], []  # type: List[str], List[Any]
    if watcher_id:
        where.append("watcher_id = ?")
        params.append(watcher_id)
    if category and category != "all":
        where.append("category = ?")
        params.append(category)
    if status and status != "all":
        where.append("notification_status = ?")
        params.append(status)
    if search:
        like = f"%{search[:200]}%"
        where.append("(title LIKE ? OR short_description LIKE ? OR venue LIKE ? OR source_name LIKE ?)")
        params.extend([like] * 4)
    clause = " AND ".join(where)
    limit = max(1, min(int(limit), 10000))
    offset = max(0, int(offset))
    with db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM events WHERE {clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM events WHERE {clause} ORDER BY detected_at DESC, rowid DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    return [_row_to_event(r) for r in rows], total


def insert_event(event: Dict[str, Any], status: str = "unread",
                 also_known_as: Tuple[str, ...] = ()) -> Optional[Dict[str, Any]]:
    """Insert unless this event was already seen (its fingerprint, or any older-style
    fingerprint in also_known_as, exists). Returns the event, or None for duplicates."""
    event_id = new_id("event")
    with db() as conn:
        if also_known_as:
            marks = ",".join("?" * len(also_known_as))
            if conn.execute(f"SELECT 1 FROM events WHERE content_fingerprint IN ({marks}) LIMIT 1",
                            also_known_as).fetchone():
                return None
        cur = conn.execute(
            """INSERT OR IGNORE INTO events (id, watcher_id, title, source_name, source_url, detected_at,
               event_date, venue, category, matched_keywords, short_description, content_fingerprint,
               notification_status, is_favorite)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (event_id, event["watcher_id"], event["title"], event["source_name"], event["source_url"],
             event["detected_at"], event.get("event_date"), event.get("venue"), event["category"],
             json.dumps(event.get("matched_keywords") or []), event.get("short_description"),
             event["content_fingerprint"], status),
        )
        if cur.rowcount == 0:
            return None
    if status == "unread":
        log_message("SUCCESS", f'New event found: "{event["title"]}" [{event["category"]}]', event["source_name"])
    return {**event, "id": event_id, "notification_status": status, "is_favorite": False}


def update_event_status(event_id: str, status: str) -> None:
    with db() as conn:
        conn.execute("UPDATE events SET notification_status = ? WHERE id = ?", (status, event_id))


def toggle_event_favorite(event_id: str) -> None:
    with db() as conn:
        conn.execute("UPDATE events SET is_favorite = 1 - is_favorite WHERE id = ?", (event_id,))


def delete_event(event_id: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))


def clear_events() -> None:
    with db() as conn:
        conn.execute("DELETE FROM events")
    log_message("INFO", "Cleared all detected events", "Events")


# ---------------------------------------------------------------- source health

def record_health(watcher_id: str, url: str, http_code: Optional[int], response_time_ms: int,
                  success: bool, error: Optional[str] = None) -> int:
    """Store the outcome of a check. Returns the number of consecutive failures."""
    now = now_iso()
    with db() as conn:
        conn.execute(
            """INSERT INTO source_health (watcher_id, url, last_http_code, response_time_ms,
                   consecutive_failures, last_error, last_checked_at, last_success_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(watcher_id) DO UPDATE SET
                   url = excluded.url,
                   last_http_code = excluded.last_http_code,
                   response_time_ms = excluded.response_time_ms,
                   consecutive_failures = CASE WHEN ? THEN 0 ELSE source_health.consecutive_failures + 1 END,
                   last_error = excluded.last_error,
                   last_checked_at = excluded.last_checked_at,
                   last_success_at = COALESCE(excluded.last_success_at, source_health.last_success_at)""",
            (watcher_id, url, http_code, response_time_ms, 0 if success else 1,
             None if success else (error or "Unknown error")[:500], now, now if success else None,
             1 if success else 0),
        )
        row = conn.execute("SELECT consecutive_failures FROM source_health WHERE watcher_id = ?", (watcher_id,)).fetchone()
    return int(row[0]) if row else 0


def get_source_health() -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            """SELECT w.id AS watcher_id, w.name AS watcher_name, w.category, w.source_url AS url,
                      w.source_type, sh.last_http_code, sh.response_time_ms,
                      COALESCE(sh.consecutive_failures, 0) AS consecutive_failures,
                      sh.last_error, sh.last_checked_at, sh.last_success_at
               FROM watchers w LEFT JOIN source_health sh ON w.id = sh.watcher_id
               ORDER BY consecutive_failures DESC, w.name ASC"""
        ).fetchall()
    result = []
    for r in rows:
        item = dict(r)
        item["is_healthy"] = (item["consecutive_failures"] or 0) < 2
        result.append(item)
    return result


def counts() -> Dict[str, int]:
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM watchers").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM watchers WHERE enabled = 1").fetchone()[0]
        events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM source_health WHERE consecutive_failures >= 2").fetchone()[0]
    return {"total_watchers": total, "active_watchers": active, "total_events": events, "failed_sources": failed}
