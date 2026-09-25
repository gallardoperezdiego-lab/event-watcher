"""
Event Watcher - Background scheduler.

Wakes up on the global interval from Settings and checks every enabled watcher whose own
interval has elapsed. The first pass runs shortly after start-up so watchers that became
due while the computer was off are caught up. Requests are spaced out to stay polite.
It also saves the automatic daily backup.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import backup
import database
from watcher_engine import check_single_watcher

STARTUP_DELAY_SECONDS = 20
PAUSE_BETWEEN_SOURCES = 1.0

_state_lock = threading.Lock()
_run_lock = threading.Lock()
_wake = threading.Event()
_stop = threading.Event()
_thread: Optional[threading.Thread] = None
_state: Dict[str, Any] = {"lastCheckTime": None, "nextCheckTime": None}


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_status() -> Dict[str, Any]:
    with _state_lock:
        return {
            "isActive": _thread is not None and _thread.is_alive(),
            "isCheckInProgress": _run_lock.locked(),
            "lastCheckTime": _state["lastCheckTime"],
            "nextCheckTime": _state["nextCheckTime"],
        }


def run_watchers(only_due: bool) -> Dict[str, Any]:
    """Check enabled watchers. Returns totals; refuses to overlap with another run."""
    if not _run_lock.acquire(blocking=False):
        return {"totalWatchersChecked": 0, "totalNewEvents": 0, "errors": ["A check cycle is already in progress."]}
    try:
        with _state_lock:
            _state["lastCheckTime"] = _iso(datetime.now(timezone.utc))
        now = datetime.now(timezone.utc)
        watchers: List[Dict[str, Any]] = [w for w in database.get_all_watchers() if w["enabled"]]
        if only_due:
            watchers = [w for w in watchers if _is_due(w, now)]
        database.log_message("INFO", f"Check cycle started for {len(watchers)} watcher(s)", "Scheduler")
        total_new, errors = 0, []
        for i, w in enumerate(watchers):
            if _stop.is_set():
                break
            try:
                new_events, err = check_single_watcher(w["id"])
                total_new += new_events
                if err:
                    errors.append(f"{w['name']}: {err}")
            except Exception as e:  # keep the loop alive whatever happens
                errors.append(f"{w['name']}: {e}")
                database.log_message("ERROR", f"Error checking {w['name']}: {e}", "Scheduler")
            if i < len(watchers) - 1:
                time.sleep(PAUSE_BETWEEN_SOURCES)
        database.log_message("INFO", f"Check cycle complete. Found {total_new} new event(s).", "Scheduler")
        return {"totalWatchersChecked": len(watchers), "totalNewEvents": total_new, "errors": errors}
    finally:
        _run_lock.release()


def _is_due(w: Dict[str, Any], now: datetime) -> bool:
    last = _parse(w.get("last_checked_at"))
    if last is None:
        return True
    # 1 minute of slack so a watcher with the same interval as the scheduler is not skipped
    return now - last >= timedelta(minutes=max(1, int(w["check_interval_minutes"]) - 1))


def _worker() -> None:
    delay = STARTUP_DELAY_SECONDS
    while not _stop.is_set():
        with _state_lock:
            _state["nextCheckTime"] = _iso(datetime.now(timezone.utc) + timedelta(seconds=delay))
        _wake.wait(timeout=delay)
        _wake.clear()
        if _stop.is_set():
            break
        try:
            run_watchers(only_due=True)
        except Exception as e:
            database.log_message("ERROR", f"Scheduled check failed: {e}", "Scheduler")
        backup.automatic_backup_if_due()
        delay = int(database.load_settings()["check_interval_minutes"]) * 60


def start_scheduler() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_worker, name="EventWatcherScheduler", daemon=True)
    _thread.start()
    interval = database.load_settings()["check_interval_minutes"]
    database.log_message("INFO", f"Scheduler started ({interval}-minute interval)", "Scheduler")


def reschedule() -> None:
    """Apply a new interval now: wake the worker so it recomputes its timer."""
    _wake.set()


def stop_scheduler() -> None:
    _stop.set()
    _wake.set()
