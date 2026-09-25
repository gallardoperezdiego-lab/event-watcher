"""
Event Watcher - Monitoring engine.

Downloads a watcher's source, turns it into candidate events (see extractors.py), filters
them by keywords, stores each event once and sends desktop notifications.

  * First successful check of a watcher = baseline: everything already listed is stored
    quietly (marked as read) and one summary notification is shown. Only events announced
    after that trigger "New event found" alerts.
  * Duplicates are recognised by a fingerprint of the event's own link and date (or title
    and date when the page has no per-event link), so ticket-status changes such as
    "Sold Out" never re-announce an event.
  * A source that keeps failing, or suddenly yields nothing readable (usually a website
    redesign), triggers one "needs attention" notification instead of failing silently.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import database
from extractors import clean_html, detect_date, detect_venue, extract  # noqa: F401  (re-exported for tests)
from netguard import FetchResult, safe_fetch
from notifier import send_desktop_notification

MAX_NOTIFICATIONS_PER_CHECK = 3
MAX_PAGES = 6
ATTENTION_AFTER_FAILURES = 3
_check_locks: Dict[str, threading.Lock] = {}
_check_locks_guard = threading.Lock()


def generate_fingerprint(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()


def test_keywords(content: str, includes: List[str], excludes: List[str]) -> Tuple[bool, List[str], List[str]]:
    lower = content.lower()
    matched_ex = [e.strip() for e in excludes if e.strip() and e.strip().lower() in lower]
    if matched_ex:
        return False, [], matched_ex
    if not includes:
        return True, [], []
    matched = [i.strip() for i in includes if i.strip() and i.strip().lower() in lower]
    return bool(matched), matched, []


def _fingerprints(item: Dict[str, Any], page_url: str) -> Tuple[str, Tuple[str, ...]]:
    """(fingerprint, older fingerprints that also mean 'already seen')."""
    date = item.get("date_raw") or ""
    title = " ".join(item["title"].split()).lower()
    link = item.get("link") or page_url
    primary = generate_fingerprint(f"{link}|{date}" if link != page_url else f"{page_url}|{title}|{date}")
    legacy = generate_fingerprint(f"{link}|{title}|{date}")  # scheme used by version 1.1.0
    return primary, (legacy,)


def fetch_items(url: str, source_type: str, settings: Dict[str, Any], max_pages: int = MAX_PAGES
                ) -> Tuple[FetchResult, str, List[Dict[str, Any]], int]:
    """Download a source (following same-site 'next page' links of JSON feeds) and extract items.
    Returns (first_response, detected_type, items, items_read)."""
    timeout = settings["request_timeout_seconds"]
    first = safe_fetch(url, settings["user_agent"], timeout)
    if not first.ok:
        return first, source_type, [], 0
    detected, items, next_url, read = extract(first.text, source_type, first.final_url or url)
    seen_pages = {url, first.final_url}
    pages = 1
    while next_url and pages < max_pages and next_url not in seen_pages:
        seen_pages.add(next_url)
        time.sleep(1)  # be polite between pages
        res = safe_fetch(next_url, settings["user_agent"], timeout)
        if not res.ok:
            break
        _, more, next_url, more_read = extract(res.text, source_type, res.final_url or next_url)
        items.extend(more)
        read += more_read
        pages += 1
    return first, detected, items, read


# ---------------------------------------------------------------- source tester (no writes)

def test_source(url: str, source_type: str, keywords: List[str], excludes: List[str]) -> Dict[str, Any]:
    settings = dict(database.load_settings())
    settings["request_timeout_seconds"] = min(settings["request_timeout_seconds"], 20)
    res, detected, items, read = fetch_items(url, source_type, settings, max_pages=3)
    base = {"url": url, "http_code": res.status, "response_time_ms": res.response_time_ms,
            "source_type_detected": detected}
    if not res.ok:
        return {**base, "success": False, "title_found": None, "sample_extracted_text": "",
                "matched_keywords": [], "matched_exclusions": [], "items_found_count": 0,
                "sample_items": [], "error_message": res.error or f"HTTP error {res.status}"}

    title_m = re.search(r"<title\b[^>]*>(.*?)</title\s*>", res.text, re.IGNORECASE | re.DOTALL)
    inc_all, exc_all, samples = set(), set(), []
    for item in items:
        ok, inc, exc = test_keywords(f"{item['title']} {item.get('description') or ''} {item.get('venue') or ''}",
                                     keywords, excludes)
        inc_all.update(inc)
        exc_all.update(exc)
        if ok and len(samples) < 10:
            samples.append({"title": item["title"], "description": (item.get("description") or "")[:300],
                            "date": item.get("date") or None, "venue": item.get("venue") or None,
                            "url": item.get("link") or None})
    result = {**base, "success": True,
              "title_found": clean_html(title_m.group(1)).strip()[:200] if title_m else None,
              "sample_extracted_text": clean_html(res.text)[:1000] if not res.text.lstrip().startswith(("{", "["))
              else res.text[:1000],
              "matched_keywords": sorted(inc_all), "matched_exclusions": sorted(exc_all),
              "items_found_count": len(items), "sample_items": samples}
    if not items:
        result["error_message"] = (f"The page was read ({read} item(s)), but none are upcoming events."
                                   if read else "No events could be read from this page. It may build its "
                                   "listings with JavaScript; look for an RSS, iCal or JSON feed instead.")
    return result


# ---------------------------------------------------------------- real checks

def _lock_for(watcher_id: str) -> threading.Lock:
    with _check_locks_guard:
        return _check_locks.setdefault(watcher_id, threading.Lock())


def check_single_watcher(watcher_id: str) -> Tuple[int, Optional[str]]:
    """Fetch one watcher, store new events and notify. Returns (new_events, error)."""
    lock = _lock_for(watcher_id)
    if not lock.acquire(blocking=False):
        return 0, "A check for this watcher is already running."
    try:
        return _check(watcher_id)
    finally:
        lock.release()


def _fail(watcher: Dict[str, Any], settings: Dict[str, Any], now: str, res: FetchResult, error: str) -> Tuple[int, str]:
    database.set_watcher_status(watcher["id"], "error", checked_at=now)
    failures = database.record_health(watcher["id"], watcher["source_url"], res.status, res.response_time_ms, False, error)
    database.log_message("WARN", f'Check failed for "{watcher["name"]}": {error}', "WatcherEngine")
    if failures == ATTENTION_AFTER_FAILURES and settings["desktop_notifications"]:
        ok, detail = send_desktop_notification(
            "Event Watcher: a source needs attention",
            f'"{watcher["name"]}" has failed {failures} checks in a row.\n{error}\nOpen Event Watcher > Sources')
        if not ok:
            database.log_message("ERROR", f"Desktop notification failed: {detail}", "Notifier")
    return 0, error


def _check(watcher_id: str) -> Tuple[int, Optional[str]]:
    watcher = database.get_watcher(watcher_id)
    if not watcher:
        return 0, "Watcher not found"
    settings = database.load_settings()
    database.set_watcher_status(watcher_id, "checking")
    database.log_message("INFO", f'Starting check for watcher: "{watcher["name"]}" ({watcher["source_url"]})', "WatcherEngine")

    try:
        res, _, items, read = fetch_items(watcher["source_url"], watcher["source_type"], settings)
    except Exception as e:  # a parsing bug must never stop the scheduler
        database.log_message("ERROR", f'Reading "{watcher["name"]}" failed: {e}', "WatcherEngine")
        return _fail(watcher, settings, database.now_iso(), FetchResult(False, None, "", 0), f"Could not read page content: {e}")
    now = database.now_iso()
    if not res.ok:
        return _fail(watcher, settings, now, res, res.error or f"HTTP error {res.status}")
    if read == 0:
        return _fail(watcher, settings, now, res, "The page loaded but no events could be read from it. "
                                                  "The website may have changed its layout.")

    baseline = not watcher.get("last_successful_at")
    page_url = res.final_url or watcher["source_url"]
    new_events: List[Dict[str, Any]] = []
    for item in items:
        ok, matched, _ = test_keywords(f"{item['title']} {item.get('description') or ''} {item.get('venue') or ''}",
                                       watcher["keywords"], watcher["exclude_keywords"])
        if not ok:
            continue
        fingerprint, older = _fingerprints(item, page_url)
        inserted = database.insert_event({
            "watcher_id": watcher_id,
            "title": item["title"][:300],
            "source_name": watcher["name"],
            "source_url": item.get("link") or watcher["source_url"],
            "detected_at": now,
            "event_date": (item.get("date") or None) and str(item["date"])[:100],
            "venue": item.get("venue"),
            "category": watcher["category"],
            "matched_keywords": matched,
            "short_description": (item.get("description") or "")[:350],
            "content_fingerprint": fingerprint,
        }, status="read" if baseline else "unread", also_known_as=older)
        if inserted:
            new_events.append(inserted)

    database.set_watcher_status(watcher_id, "active", checked_at=now, success_at=now,
                                content_hash=generate_fingerprint("|".join(i["title"] for i in items)))
    database.record_health(watcher_id, watcher["source_url"], res.status, res.response_time_ms, True)

    if baseline:
        database.log_message("SUCCESS", f'Started watching "{watcher["name"]}": {len(new_events)} matching event(s) '
                                        f"already listed, saved as the starting point", "WatcherEngine")
        if settings["desktop_notifications"] and watcher["notify_desktop"]:
            _notify("Now watching " + watcher["name"],
                    f"{len(new_events)} matching event(s) already listed.\nYou will be notified when new ones are announced.")
        return 0, None

    database.log_message("SUCCESS", f'Completed check for "{watcher["name"]}": {len(new_events)} new event(s) '
                                    f"out of {len(items)} upcoming items", "WatcherEngine")
    if new_events and settings["desktop_notifications"] and watcher["notify_desktop"]:
        notify_new_events(watcher["name"], new_events)
    return len(new_events), None


def _notify(title: str, body: str) -> None:
    ok, detail = send_desktop_notification(title, body)
    if not ok:
        database.log_message("ERROR", f"Desktop notification failed: {detail}", "Notifier")


def notify_new_events(watcher_name: str, events: List[Dict[str, Any]]) -> None:
    if len(events) > MAX_NOTIFICATIONS_PER_CHECK:
        _notify("New events found",
                f"{len(events)} new events from {watcher_name}\nLatest: {events[0]['title']}\nOpen Event Watcher for details")
        return
    for e in events:
        where = " · ".join(p for p in (e.get("venue") or watcher_name, e.get("event_date") or "") if p)
        _notify("New event found", f"{e['title']}\n{where}\nOpen Event Watcher for details")
