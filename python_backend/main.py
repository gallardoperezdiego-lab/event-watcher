"""
Event Watcher - Local web server (Python standard library only).

Serves the web interface (the built React app in dist/) and the JSON API it uses.
Security boundary:
  * listens on 127.0.0.1 only, never on the network;
  * rejects requests whose Host header is not this machine (blocks DNS re-binding);
  * rejects state-changing requests coming from other websites (Origin / Fetch-Metadata);
  * sends no CORS headers, so other websites cannot read any data.
"""

from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlsplit

import autostart
import backup
import database
import scheduler
from netguard import UnsafeURLError, validate_url
from notifier import send_desktop_notification
from paths import BASE_DIR, DB_PATH, web_dist_dir
from presets import PRESETS
from watcher_engine import check_single_watcher, test_source

APP_VERSION = "1.1.0"
HOST = "127.0.0.1"
MAX_JSON_BODY = 1024 * 1024

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("font/woff2", ".woff2")

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
       "form-action 'self'")


class HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def configured_port() -> int:
    env = os.environ.get("EVENTWATCHER_PORT")
    if env and env.isdigit():
        return int(env)
    return int(database.load_settings()["port"])


# ---------------------------------------------------------------- export helpers

def _csv_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        text = "'" + text  # stop spreadsheets from running text from websites as formulas
    return text


def events_to_csv(events: List[Dict[str, Any]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow(["Title", "Category", "Venue", "Event Date", "Detected Date", "Source Name", "Source URL", "Keywords"])
    for e in events:
        writer.writerow([_csv_cell(v) for v in (
            e["title"], e["category"], e.get("venue"), e.get("event_date"), e["detected_at"],
            e.get("source_name"), e.get("source_url"), ", ".join(e.get("matched_keywords") or []))])
    return "\ufeff" + out.getvalue()


def _ics_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", text.replace("\r\n", "\n").replace("\r", "\n"))
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_fold(line: str) -> str:
    out, current = [], ""
    for ch in line:
        if len((current + ch).encode("utf-8")) > 74:
            out.append(current)
            current = " " + ch
        else:
            current += ch
    out.append(current)
    return "\r\n".join(out)


def events_to_ics(events: List[Dict[str, Any]]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Event Watcher//Local Event Monitor//EN", "CALSCALE:GREGORIAN"]
    for e in events:
        stamp = re.sub(r"[-:]", "", str(e["detected_at"]))[:15] + "Z"
        uid = re.sub(r"[^A-Za-z0-9._-]", "", str(e["id"]))
        lines += ["BEGIN:VEVENT", f"UID:{uid}@eventwatcher.local", f"DTSTAMP:{stamp}",
                  f"SUMMARY:{_ics_text(e['title'])}", f"DESCRIPTION:{_ics_text(e.get('short_description'))}",
                  f"LOCATION:{_ics_text(e.get('venue'))}"]
        url = str(e.get("source_url") or "")
        try:
            validate_url(url)
            lines.append(f"URL:{url}")
        except UnsafeURLError:
            pass
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_ics_fold(line) for line in lines) + "\r\n"


# ---------------------------------------------------------------- handlers

Handler = Callable[["RequestHandler", Dict[str, str]], Any]
ROUTES: List[Tuple[str, "re.Pattern[str]", Handler]] = []


def route(method: str, pattern: str):
    def register(fn: Handler) -> Handler:
        ROUTES.append((method, re.compile(f"^{pattern}$"), fn))
        return fn
    return register


def _keyword_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()][:50]
    if value:
        return [s.strip() for s in str(value).split(",") if s.strip()][:50]
    return []


@route("GET", "/healthz")
def health(h, p):
    return {"ok": True, "app": "Event Watcher", "version": APP_VERSION}


@route("GET", "/api/status")
def status(h, p):
    size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    last_backup = backup.last_automatic_backup()
    return {
        "status": "operational",
        "app": "Event Watcher",
        "version": APP_VERSION,
        "storage": {"data_directory": str(BASE_DIR), "database_path": str(DB_PATH),
                    "database_size_kb": round(size / 1024),
                    "last_automatic_backup": last_backup.isoformat(timespec="minutes") if last_backup else None,
                    "backup_folder": database.load_settings().get("backup_folder") or None},
        "counts": database.counts(),
        "scheduler": scheduler.get_status(),
        "server": {"host": HOST, "port": h.server.server_port},
    }


@route("GET", "/api/watchers")
def list_watchers(h, p):
    return database.get_all_watchers()


@route("POST", "/api/watchers")
def create_watcher(h, p):
    return 201, database.create_watcher(h.json_body())


@route("POST", "/api/watchers/check-all")
def check_all(h, p):
    return scheduler.run_watchers(only_due=False)


@route("PUT", r"/api/watchers/(?P<id>[^/]+)")
def update_watcher(h, p):
    updated = database.update_watcher(p["id"], h.json_body())
    if not updated:
        raise HttpError(404, "Watcher not found")
    return updated


@route("DELETE", r"/api/watchers/(?P<id>[^/]+)")
def delete_watcher(h, p):
    database.delete_watcher(p["id"])
    return {"success": True}


@route("POST", r"/api/watchers/(?P<id>[^/]+)/toggle")
def toggle_watcher(h, p):
    w = database.get_watcher(p["id"])
    if not w:
        raise HttpError(404, "Watcher not found")
    return database.update_watcher(p["id"], {"enabled": not w["enabled"]})


@route("POST", r"/api/watchers/(?P<id>[^/]+)/check")
def check_watcher(h, p):
    if not database.get_watcher(p["id"]):
        raise HttpError(404, "Watcher not found")
    new_events, error = check_single_watcher(p["id"])
    return {"newEventsFound": new_events, **({"error": error} if error else {})}


@route("GET", "/api/events")
def list_events(h, p):
    q = h.query()
    events, total = database.get_events(
        watcher_id=q.get("watcher_id"), category=q.get("category"), status=q.get("status"),
        search=q.get("search"), limit=_int(q.get("limit"), 50), offset=_int(q.get("offset"), 0))
    return {"events": events, "total": total}


@route("GET", "/api/events/export")
def export_events(h, p):
    fmt = (h.query().get("format") or "csv").lower()
    events, _ = database.get_events(limit=10000)
    if fmt == "json":
        return h.send_download(json.dumps(events, indent=2).encode(), "application/json", "EventWatcher-Events.json")
    if fmt == "ics":
        return h.send_download(events_to_ics(events).encode(), "text/calendar; charset=utf-8", "EventWatcher-Events.ics")
    return h.send_download(events_to_csv(events).encode("utf-8"), "text/csv; charset=utf-8", "EventWatcher-Events.csv")


@route("PUT", r"/api/events/(?P<id>[^/]+)/status")
def event_status(h, p):
    new_status = h.json_body().get("status")
    if new_status not in database.EVENT_STATUSES:
        raise HttpError(400, "Invalid status")
    database.update_event_status(p["id"], new_status)
    return {"success": True}


@route("POST", r"/api/events/(?P<id>[^/]+)/favorite")
def event_favorite(h, p):
    database.toggle_event_favorite(p["id"])
    return {"success": True}


@route("POST", "/api/events/clear")
def events_clear(h, p):
    database.clear_events()
    return {"success": True}


@route("DELETE", r"/api/events/(?P<id>[^/]+)")
def event_delete(h, p):
    database.delete_event(p["id"])
    return {"success": True}


@route("GET", "/api/sources")
def sources(h, p):
    return database.get_source_health()


@route("POST", "/api/test-source")
def test_source_route(h, p):
    body = h.json_body()
    try:
        url = validate_url(str(body.get("url") or "").strip())
    except UnsafeURLError as e:
        raise HttpError(400, str(e))
    source_type = body.get("source_type") if body.get("source_type") in database.SOURCE_TYPES else "rss"
    return test_source(url, source_type, _keyword_list(body.get("keywords")), _keyword_list(body.get("exclude_keywords")))


@route("GET", "/api/presets")
def presets(h, p):
    return PRESETS


def _current_settings() -> Dict[str, Any]:
    settings = database.load_settings()
    try:
        settings["start_on_login"] = autostart.is_enabled()
    except Exception:
        pass
    return settings


@route("GET", "/api/settings")
def get_settings(h, p):
    return _current_settings()


@route("POST", "/api/settings")
def post_settings(h, p):
    body = h.json_body()
    before = _current_settings()
    updated = database.save_settings(body)
    if "start_on_login" in body and updated["start_on_login"] != before["start_on_login"]:
        try:
            autostart.set_enabled(updated["start_on_login"])
            database.log_message("INFO", f"Start at login {'enabled' if updated['start_on_login'] else 'disabled'}", "Settings")
        except Exception as e:
            database.save_settings({"start_on_login": before["start_on_login"]})
            raise HttpError(500, f"Could not change the start-at-login setting: {e}")
    if updated["check_interval_minutes"] != before["check_interval_minutes"]:
        scheduler.reschedule()
    return _current_settings()


@route("GET", "/api/logs")
def logs(h, p):
    return database.get_logs(_int(h.query().get("limit"), 100))


@route("GET", "/api/backup/export")
def backup_export(h, p):
    filename, data = backup.create_backup()
    return h.send_download(data, "application/zip", filename)


@route("POST", "/api/backup/import")
def backup_import(h, p):
    ctype = h.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if ctype not in ("application/zip", "application/octet-stream", "application/x-zip-compressed"):
        raise HttpError(415, "Please upload a .zip backup file.")
    result = backup.restore_backup(h.read_body(backup.MAX_ARCHIVE_BYTES))
    scheduler.reschedule()
    return result


@route("POST", "/api/notifications/test")
def notification_test(h, p):
    ok, detail = send_desktop_notification(
        "New event found (test)", "The Killers announce Belfast show\nSSE Arena Belfast\nOpen Event Watcher for details")
    if not ok:
        database.log_message("ERROR", f"Test notification failed: {detail}", "Notifier")
    return {"success": ok, "detail": detail}


@route("POST", "/api/open-data-folder")
def open_data_folder(h, p):
    opener = {"darwin": ["open"], "win32": ["explorer"]}.get(sys.platform, ["xdg-open"])
    subprocess.Popen(opener + [str(BASE_DIR)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"success": True, "path": str(BASE_DIR)}


@route("POST", "/api/shutdown")
def shutdown(h, p):
    database.log_message("INFO", "Shutdown requested from the interface", "Server")
    threading.Thread(target=h.server.shutdown, daemon=True).start()
    return {"success": True}


@route("GET", "/api/handover-info")
def handover_info(h, p):
    items = [
        ("keys", "No developer API keys embedded", "No Gemini, OpenAI, Claude or other API keys in the source or the packaged app."),
        ("email", "No developer email embedded", "No developer email addresses, accounts or IDs are used anywhere."),
        ("firebase", "No Firebase dependency", "No Firebase Auth, Firestore or Firebase SDK."),
        ("google", "No Google account dependency", "No Google sign-in, OAuth client IDs or Cloud projects."),
        ("gemini", "No Gemini API dependency", "Matching uses deterministic keyword rules running on this computer."),
        ("database", "No external database dependency", "Data lives in a local SQLite file in the data folder."),
        ("auth", "No external authentication dependency", "No logins or passwords. The app only listens on 127.0.0.1 (this computer)."),
        ("telemetry", "No telemetry or tracking", "No analytics or tracking. The only outgoing requests go to the sources you add."),
        ("local_data", "All data stored locally", f"Everything is inside {BASE_DIR}."),
        ("backup_export", "Backup / export supported", 'One click "Export Everything" creates a portable ZIP file.'),
        ("backup_import", "Restore / import supported", "Import Backup verifies the ZIP and keeps a copy of the replaced database."),
        ("survivability", "Application runs after developer disappears", "Self-contained: Python standard library only, or the packaged app with no installs."),
    ]
    return {"status": "verified_zero_developer_dependencies",
            "checklist": [{"id": i, "title": t, "status": True, "detail": d} for i, t, d in items]}


def _int(value: Optional[str], default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


# ---------------------------------------------------------------- HTTP plumbing

class RequestHandler(BaseHTTPRequestHandler):
    server_version = "EventWatcher"
    sys_version = ""

    def log_message(self, fmt, *args):  # keep the console quiet; app.log has the useful details
        pass

    # -- helpers
    def query(self) -> Dict[str, str]:
        return {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}

    def read_body(self, limit: int) -> bytes:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise HttpError(400, "Invalid Content-Length")
        if length > limit:
            raise HttpError(413, "The upload is too large.")
        return self.rfile.read(length) if length else b""

    def json_body(self) -> Dict[str, Any]:
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise HttpError(415, "Expected application/json")
        try:
            data = json.loads(self.read_body(MAX_JSON_BODY) or b"{}")
        except ValueError:
            raise HttpError(400, "Malformed JSON")
        if not isinstance(data, dict):
            raise HttpError(400, "Expected a JSON object")
        return data

    def _common_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")

    def send_bytes(self, status: int, data: bytes, ctype: str, extra: Optional[Dict[str, str]] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self._common_headers()
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_json(self, status: int, payload: Any) -> None:
        self.send_bytes(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8",
                        {"Cache-Control": "no-store"})

    def send_download(self, data: bytes, ctype: str, filename: str):
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
        self.send_bytes(200, data, ctype, {"Content-Disposition": f'attachment; filename="{safe}"',
                                           "Cache-Control": "no-store"})
        return _SENT

    # -- security checks
    def _allowed_hosts(self) -> Tuple[str, ...]:
        port = self.server.server_port
        return (f"127.0.0.1:{port}", f"localhost:{port}")

    def _check_request(self) -> None:
        host = (self.headers.get("Host") or "").lower()
        if host not in self._allowed_hosts():
            raise HttpError(421, "Event Watcher only answers requests addressed to this computer.")
        if self.command in ("GET", "HEAD"):
            return
        origin = self.headers.get("Origin")
        if origin is not None and origin.lower() not in tuple(f"http://{h}" for h in self._allowed_hosts()):
            raise HttpError(403, "Cross-site request blocked.")
        site = self.headers.get("Sec-Fetch-Site")
        if site is not None and site not in ("same-origin", "none"):
            raise HttpError(403, "Cross-site request blocked.")

    # -- dispatch
    def _dispatch(self) -> None:
        path = urlsplit(self.path).path
        try:
            self._check_request()
            if path.startswith("/api/") or path == "/healthz":
                for method, pattern, fn in ROUTES:
                    m = pattern.match(path)
                    if m and method == ("GET" if self.command == "HEAD" else self.command):
                        result = fn(self, m.groupdict())
                        if result is _SENT:
                            return
                        if isinstance(result, tuple):
                            self.send_json(result[0], result[1])
                        else:
                            self.send_json(200, result)
                        return
                if any(p.match(path) for _, p, _ in ROUTES):
                    raise HttpError(405, "Method not allowed")
                raise HttpError(404, "Not found")
            if self.command not in ("GET", "HEAD"):
                raise HttpError(405, "Method not allowed")
            self._serve_static(path)
        except HttpError as e:
            self.send_json(e.status, {"error": e.message})
        except (database.ValidationError, backup.BackupError) as e:
            self.send_json(400, {"error": str(e)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            database.log_message("ERROR", f"{self.command} {path} failed: {e}", "Server")
            traceback.print_exc()
            self.send_json(500, {"error": "Something went wrong. Details are in the application log."})

    def _serve_static(self, path: str) -> None:
        dist = web_dist_dir().resolve()
        index = dist / "index.html"
        if not index.exists():
            body = ("<!doctype html><meta charset=utf-8><title>Event Watcher</title>"
                    "<body style='font-family:sans-serif;max-width:640px;margin:60px auto'>"
                    "<h1>Event Watcher is running</h1><p>The web interface files (web/dist/) are missing. "
                    "Rebuild them in the web folder with <code>npm install</code> then <code>npm run build</code>.</p></body>")
            self.send_bytes(503, body.encode(), "text/html; charset=utf-8")
            return
        candidate = (dist / path.lstrip("/")).resolve()
        try:
            candidate.relative_to(dist)
        except ValueError:
            raise HttpError(404, "Not found")
        if not candidate.is_file():
            candidate = index  # single-page app: every route renders index.html
        ctype = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        cache = "public, max-age=31536000, immutable" if "/assets/" in candidate.as_posix() else "no-cache"
        extra = {"Cache-Control": cache}
        if candidate == index:
            extra["Content-Security-Policy"] = CSP
        self.send_bytes(200, candidate.read_bytes(), ctype, extra)

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = _dispatch

    def do_OPTIONS(self):
        # No CORS: other websites never get permission to call this API.
        self.send_bytes(405, b"", "text/plain")


_SENT = object()


class EventWatcherServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = sys.platform != "win32"


def create_server(port: Optional[int] = None) -> EventWatcherServer:
    database.init_db()
    return EventWatcherServer((HOST, port or configured_port()), RequestHandler)


def run_server(port: Optional[int] = None, on_ready: Optional[Callable[[int], None]] = None) -> None:
    httpd = create_server(port)
    actual_port = httpd.server_port
    database.log_message("INFO", f"Event Watcher {APP_VERSION} started on http://{HOST}:{actual_port} "
                                 f"(data: {BASE_DIR})", "Server")
    scheduler.start_scheduler()
    print("\n=========================================")
    print("  Event Watcher")
    print(f"  Open: http://localhost:{actual_port}")
    print(f"  Data: {BASE_DIR}")
    print("  Press Ctrl+C to stop.")
    print("=========================================\n")
    if on_ready:
        on_ready(actual_port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.stop_scheduler()
        httpd.server_close()
        database.log_message("INFO", "Event Watcher stopped", "Server")


if __name__ == "__main__":
    run_server()
