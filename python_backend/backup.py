"""
Event Watcher - "Export Everything" and "Import Backup".

Export: a ZIP with a consistent SQLite snapshot, settings, logs and readable JSON copies.
Import: the archive is size-checked, the database is verified (SQLite header, integrity
check, expected tables) in a temporary file, and only then swapped in atomically. The
database that was replaced is kept in backups/ so a restore can always be undone.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import database
from paths import BACKUPS_DIR, DATA_DIR, DB_PATH, LOG_PATH

FORMAT_VERSION = 2
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 300 * 1024 * 1024
MAX_ENTRIES = 100
MAX_JSON_BYTES = 50 * 1024 * 1024
KEEP_BACKUPS = 10
KEEP_AUTO_BACKUPS = 14
AUTO_BACKUP_HOURS = 24

README = """EVENT WATCHER - LOCAL BACKUP ARCHIVE
Created: {created}

CONTENTS
  data/eventwatcher.db    SQLite database: watchers, detected events, source health
  config/settings.json    Your settings (intervals, notifications, theme)
  logs/app.log            Recent activity log
  export/*.json           The same records as readable JSON, for any other tool

HOW TO RESTORE
  Open Event Watcher > Backup & Transfer > Import Backup and choose this ZIP file.

No account, subscription or API key is needed. This file is entirely yours.
"""


class BackupError(ValueError):
    """User-facing restore problem."""


def _snapshot_db(target: Path) -> None:
    with database.DB_LOCK:
        src = sqlite3.connect(str(DB_PATH))
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()


def create_backup(automatic: bool = False) -> Tuple[str, bytes]:
    created = datetime.now()
    kind = "AutoBackup" if automatic else "Backup"
    filename = f"EventWatcher-{kind}-{created.strftime('%Y-%m-%d_%H%M%S')}.zip"
    events, _ = database.get_events(limit=10000)

    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / "eventwatcher.db"
        _snapshot_db(snapshot)
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(snapshot, "data/eventwatcher.db")
            settings = {k: v for k, v in database.load_settings().items() if k != "data_directory"}
            zf.writestr("config/settings.json", json.dumps(settings, indent=2))
            if LOG_PATH.exists():
                with open(LOG_PATH, "rb") as f:
                    f.seek(max(0, LOG_PATH.stat().st_size - 1024 * 1024))
                    zf.writestr("logs/app.log", f.read())
            zf.writestr("export/watchers.json", json.dumps(database.get_all_watchers(), indent=2))
            zf.writestr("export/events.json", json.dumps(events, indent=2))
            zf.writestr("export/source_health.json", json.dumps(database.get_source_health(), indent=2))
            zf.writestr("manifest.json", json.dumps(
                {"app": "Event Watcher", "format_version": FORMAT_VERSION, "created_at": created.isoformat()}, indent=2))
            zf.writestr("README.txt", README.format(created=created.isoformat(timespec="seconds")))
    data = buf.getvalue()

    targets = [BACKUPS_DIR]
    extra = database.load_settings().get("backup_folder")
    if extra:
        targets.append(Path(extra))
    for folder in targets:
        try:
            (folder / filename).write_bytes(data)
            _prune(folder, f"EventWatcher-{kind}-*.zip", KEEP_AUTO_BACKUPS if automatic else KEEP_BACKUPS)
        except OSError as e:
            database.log_message("ERROR" if folder != BACKUPS_DIR else "WARN",
                                 f"Could not save a backup copy in {folder}: {e}", "Backup")
    database.log_message("SUCCESS", f"Created {'automatic' if automatic else 'full'} backup: {filename} "
                                    f"({len(data) / 1024:.1f} KB)", "Backup")
    return filename, data


def _prune(folder: Path, pattern: str, keep: int) -> None:
    for stale in sorted(folder.glob(pattern))[:-keep]:
        stale.unlink()


def last_automatic_backup() -> Optional[datetime]:
    newest = max(BACKUPS_DIR.glob("EventWatcher-AutoBackup-*.zip"), key=lambda p: p.stat().st_mtime, default=None)
    return datetime.fromtimestamp(newest.stat().st_mtime) if newest else None


def automatic_backup_if_due() -> bool:
    """Once a day, save a full backup (and a copy in the extra backup folder, if set)."""
    last = last_automatic_backup()
    if last and datetime.now() - last < timedelta(hours=AUTO_BACKUP_HOURS):
        return False
    extra = database.load_settings().get("backup_folder")
    if extra and not Path(extra).is_dir():
        from notifier import send_desktop_notification

        database.log_message("ERROR", f"Extra backup folder is not available: {extra}", "Backup")
        send_desktop_notification("Event Watcher: backup folder not available",
                                  f"Could not reach {extra}.\nIs the drive connected? A backup was still saved on this computer.")
    try:
        create_backup(automatic=True)
        return True
    except Exception as e:
        database.log_message("ERROR", f"Automatic backup failed: {e}", "Backup")
        return False


def _read_member(zf: zipfile.ZipFile, name: str, limit: int) -> bytes:
    with zf.open(name) as f:
        data = f.read(limit + 1)
    if len(data) > limit:
        raise BackupError(f"'{name}' inside the backup is unexpectedly large.")
    return data


def _verify_database(path: Path) -> None:
    with open(path, "rb") as f:
        if f.read(16) != b"SQLite format 3\x00":
            raise BackupError("The backup does not contain a valid Event Watcher database.")
    conn = sqlite3.connect(str(path))
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise BackupError("The database inside the backup is damaged and was not restored.")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not {"watchers", "events"}.issubset(tables):
            raise BackupError("The backup database is missing Event Watcher records.")
        cols = {r[1] for r in conn.execute("PRAGMA table_info(watchers)")}
        if not {"id", "name", "source_url", "source_type"}.issubset(cols):
            raise BackupError("The backup database has an unknown layout.")
    except sqlite3.DatabaseError as e:
        raise BackupError(f"The backup database could not be read: {e}")
    finally:
        conn.close()
    database.init_db(path, seed=False)  # adds any tables/indexes a newer version expects


def _rebuild_from_json(zf: zipfile.ZipFile, target: Path) -> None:
    """Restore from export/*.json when an archive has no raw database."""
    database.init_db(target, seed=False)
    watchers = json.loads(_read_member(zf, "export/watchers.json", MAX_JSON_BYTES))
    events = json.loads(_read_member(zf, "export/events.json", MAX_JSON_BYTES)) if "export/events.json" in zf.namelist() else []
    if not isinstance(watchers, list) or not isinstance(events, list):
        raise BackupError("The JSON records in the backup are not in the expected format.")
    conn = sqlite3.connect(str(target))
    try:
        for w in watchers:
            try:
                clean = database.sanitize_watcher(w)
            except database.ValidationError:
                continue
            conn.execute(
                """INSERT OR IGNORE INTO watchers (id, name, category, enabled, source_type, source_url, keywords,
                   exclude_keywords, check_interval_minutes, status, notify_desktop, notify_sound, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'idle', ?, ?, ?)""",
                (str(w.get("id") or database.new_id("watcher")), clean["name"], clean["category"], int(clean["enabled"]),
                 clean["source_type"], clean["source_url"], json.dumps(clean["keywords"]),
                 json.dumps(clean["exclude_keywords"]), clean["check_interval_minutes"],
                 int(clean["notify_desktop"]), int(clean["notify_sound"]), str(w.get("created_at") or database.now_iso())))
        known = {r[0] for r in conn.execute("SELECT id FROM watchers")}
        for e in events:
            if not isinstance(e, dict) or e.get("watcher_id") not in known or not e.get("title"):
                continue
            status = e.get("notification_status") if e.get("notification_status") in database.EVENT_STATUSES else "read"
            conn.execute(
                """INSERT OR IGNORE INTO events (id, watcher_id, title, source_name, source_url, detected_at, event_date,
                   venue, category, matched_keywords, short_description, content_fingerprint, notification_status, is_favorite)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(e.get("id") or database.new_id("event")), e["watcher_id"], str(e["title"])[:300],
                 str(e.get("source_name") or ""), str(e.get("source_url") or ""), str(e.get("detected_at") or database.now_iso()),
                 e.get("event_date"), e.get("venue"), str(e.get("category") or "General"),
                 json.dumps(e.get("matched_keywords") or []), e.get("short_description"),
                 e.get("content_fingerprint") or database.new_id("fp"), status, 1 if e.get("is_favorite") else 0))
        conn.commit()
    finally:
        conn.close()


def restore_backup(payload: bytes) -> Dict[str, Any]:
    if not payload:
        raise BackupError("No backup file was received.")
    if len(payload) > MAX_ARCHIVE_BYTES:
        raise BackupError("The backup file is larger than 50 MB.")
    try:
        zf = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile:
        raise BackupError("That file is not a ZIP backup created by Event Watcher.")

    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_UNCOMPRESSED_BYTES:
            raise BackupError("The backup archive is too large to restore safely.")
        names = set(zf.namelist())
        if "data/eventwatcher.db" not in names and "export/watchers.json" not in names:
            raise BackupError("Invalid backup archive: it has no database or watcher records.")

        settings_update: Dict[str, Any] = {}
        if "config/settings.json" in names:
            try:
                raw_settings = json.loads(_read_member(zf, "config/settings.json", 1024 * 1024))
                settings_update = database.sanitize_settings(raw_settings, strict=False)
            except ValueError:
                settings_update = {}

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix="restore-", suffix=".db", dir=str(DATA_DIR))
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            if "data/eventwatcher.db" in names:
                info = zf.getinfo("data/eventwatcher.db")
                with zf.open(info) as src, open(tmp_path, "wb") as dst:
                    copied = 0
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        copied += len(chunk)
                        if copied > MAX_UNCOMPRESSED_BYTES:
                            raise BackupError("The database inside the backup is too large.")
                        dst.write(chunk)
                _verify_database(tmp_path)
            else:
                tmp_path.unlink()
                _rebuild_from_json(zf, tmp_path)
                _verify_database(tmp_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    safety_copy = BACKUPS_DIR / f"pre-restore-{stamp}.db"
    n = 1
    while safety_copy.exists():
        n += 1
        safety_copy = BACKUPS_DIR / f"pre-restore-{stamp}-{n}.db"
    with database.DB_LOCK:
        if DB_PATH.exists():
            _snapshot_db(safety_copy)
        os.replace(tmp_path, DB_PATH)

    # Settings: keep this computer's port, login item and backup folder; take the rest from the backup.
    settings_update.pop("port", None)
    settings_update.pop("start_on_login", None)
    settings_update.pop("backup_folder", None)
    current = database.load_settings()
    current.update(settings_update)
    database.write_settings_file(current)

    c = database.counts()
    database.log_message("SUCCESS", f"Backup restored: {c['total_watchers']} watchers, {c['total_events']} events. "
                                    f"Previous database saved as {safety_copy.name}", "Backup")
    return {
        "success": True,
        "message": "Backup restored successfully.",
        "restoredWatchersCount": c["total_watchers"],
        "restoredEventsCount": c["total_events"],
        "previousDatabaseSavedAs": safety_copy.name if safety_copy.exists() else None,
    }
