"""
Event Watcher - File locations.

Two kinds of locations matter:
  * resource_dir(): read-only files shipped with the app (the built web UI in dist/).
  * data_dir():     the user's own data (database, settings, logs, backups).

Data never lives inside the program or the project folder (the packaged app and a run
from source use the same data folder), so updating or copying the program never
carries or overwrites personal data.
Set EVENTWATCHER_DATA_DIR to put the data somewhere else (e.g. a USB stick).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "EventWatcher"
SOURCE_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return SOURCE_ROOT


def web_dist_dir() -> Path:
    if is_frozen():
        return resource_dir() / "dist"
    return SOURCE_ROOT / "web" / "dist"


def _platform_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
    return Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / APP_NAME


def data_dir() -> Path:
    override = os.environ.get("EVENTWATCHER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return _platform_data_dir()


BASE_DIR = data_dir()
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"
LOGS_DIR = BASE_DIR / "logs"
BACKUPS_DIR = BASE_DIR / "backups"
DB_PATH = DATA_DIR / "eventwatcher.db"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
LOG_PATH = LOGS_DIR / "app.log"


def ensure_dirs() -> None:
    for folder in (DATA_DIR, CONFIG_DIR, LOGS_DIR, BACKUPS_DIR):
        folder.mkdir(parents=True, exist_ok=True)
