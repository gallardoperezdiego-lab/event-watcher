"""
Event Watcher - One-click launcher.

Double-click (or run.bat / run.sh / the packaged app) to start the local server and open
the interface in the default browser. If Event Watcher is already running, it just opens
the browser again instead of starting a second copy.

  --background   start without opening the browser (used by "Start when I log in")
"""

from __future__ import annotations

import json
import sys
import threading
import urllib.request
import webbrowser

import database
from main import configured_port, run_server
from notifier import send_desktop_notification


def _already_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as resp:
            return json.loads(resp.read().decode("utf-8")).get("app") == "Event Watcher"
    except Exception:
        return False


def main() -> None:
    background = "--background" in sys.argv
    port = configured_port()
    url = f"http://localhost:{port}"

    if _already_running(port):
        if not background:
            webbrowser.open(url)
        return

    def on_ready(actual_port: int) -> None:
        if not background:
            threading.Timer(0.8, webbrowser.open, args=(f"http://localhost:{actual_port}",)).start()

    try:
        run_server(port, on_ready=on_ready)
    except OSError as e:
        message = (f"Port {port} is already used by another program. "
                   f"Close that program or change 'port' in {database.load_settings()['data_directory']}/config/settings.json.")
        database.log_message("ERROR", f"Could not start server: {e}. {message}", "Server")
        send_desktop_notification("Event Watcher could not start", message)
        print(message)
        sys.exit(1)


if __name__ == "__main__":
    main()
