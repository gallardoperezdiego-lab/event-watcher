"""
Event Watcher - Native desktop notifications (macOS, Windows, Linux).

Uses only tools that ship with the operating system; no accounts or cloud services.
Text from monitored websites is untrusted, so it is never pasted into script source:
  * macOS:   osascript receives the text as separate argv items ("on run argv").
  * Windows: PowerShell reads the text from environment variables.
  * Linux:   notify-send receives the text as plain arguments.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Tuple

APP_NAME = "Event Watcher"

_MAC_SCRIPT = """on run argv
display notification (item 2 of argv) with title (item 1 of argv) subtitle (item 3 of argv)
end run"""

# Windows 10/11 only shows toasts for a registered AppUserModelID; PowerShell's own
# ID is always registered, so notifications appear even for an unsigned .exe.
_WIN_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
_WIN_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$nodes = $template.GetElementsByTagName('text')
$nodes.Item(0).AppendChild($template.CreateTextNode($env:EW_TITLE)) > $null
$nodes.Item(1).AppendChild($template.CreateTextNode($env:EW_BODY)) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:EW_APPID).Show($toast)
"""


def _clean(text: str, limit: int) -> str:
    text = "".join(ch if ch.isprintable() or ch == "\n" else " " for ch in str(text or ""))
    return text.strip()[:limit]


def send_desktop_notification(title: str, message: str) -> Tuple[bool, str]:
    """Show a native notification. Returns (success, detail)."""
    title = _clean(title, 120) or APP_NAME
    message = _clean(message, 400)
    try:
        if sys.platform == "darwin":
            proc = subprocess.run(
                ["osascript", "-e", _MAC_SCRIPT, title, message.replace("\n", " · "), APP_NAME],
                capture_output=True, timeout=15,
            )
            if proc.returncode != 0:
                return False, proc.stderr.decode("utf-8", "replace").strip() or "osascript failed"
            return True, "macOS Notification Center"
        if sys.platform == "win32":
            env = dict(os.environ, EW_TITLE=title, EW_BODY=message, EW_APPID=_WIN_APP_ID)
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _WIN_SCRIPT],
                env=env, capture_output=True, timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode != 0:
                return False, proc.stderr.decode("utf-8", "replace").strip()[:300] or "PowerShell toast failed"
            return True, "Windows notification"
        if shutil.which("notify-send"):
            proc = subprocess.run(["notify-send", "-a", APP_NAME, "--", title, message],
                                  capture_output=True, timeout=15)
            if proc.returncode != 0:
                return False, proc.stderr.decode("utf-8", "replace").strip() or "notify-send failed"
            return True, "notify-send"
        return False, "No notification tool found (install libnotify / notify-send)."
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
