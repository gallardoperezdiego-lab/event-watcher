"""
Event Watcher - Optional "Start Event Watcher when I log in".

Only ever changed when the user ticks the box in Settings. Uses the per-user mechanism
of each OS, so no administrator rights are needed:
  * macOS:   ~/Library/LaunchAgents/org.eventwatcher.desktop.plist
  * Windows: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
  * Linux:   ~/.config/autostart/eventwatcher.desktop
At login the app starts in the background (no browser window) and keeps watching.
"""

from __future__ import annotations

import plistlib
import shlex
import sys
from pathlib import Path
from typing import List

from paths import SOURCE_ROOT, is_frozen

LABEL = "org.eventwatcher.desktop"
_MAC_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
_LINUX_DESKTOP = Path.home() / ".config" / "autostart" / "eventwatcher.desktop"
_WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WIN_VALUE = "EventWatcher"


def _command() -> List[str]:
    if is_frozen():
        return [sys.executable, "--background"]
    python = sys.executable
    if sys.platform == "win32":
        pythonw = Path(python).with_name("pythonw.exe")
        if pythonw.exists():
            python = str(pythonw)
    return [python, str(SOURCE_ROOT / "python_backend" / "launcher.py"), "--background"]


def is_enabled() -> bool:
    if sys.platform == "darwin":
        return _MAC_PLIST.exists()
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY) as key:
                winreg.QueryValueEx(key, _WIN_VALUE)
            return True
        except OSError:
            return False
    return _LINUX_DESKTOP.exists()


def set_enabled(enabled: bool) -> None:
    if sys.platform == "darwin":
        if enabled:
            _MAC_PLIST.parent.mkdir(parents=True, exist_ok=True)
            with open(_MAC_PLIST, "wb") as f:
                plistlib.dump({"Label": LABEL, "ProgramArguments": _command(), "RunAtLoad": True,
                               "ProcessType": "Interactive"}, f)
        else:
            _MAC_PLIST.unlink(missing_ok=True)
    elif sys.platform == "win32":
        import subprocess
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, _WIN_VALUE, 0, winreg.REG_SZ, subprocess.list2cmdline(_command()))
            else:
                try:
                    winreg.DeleteValue(key, _WIN_VALUE)
                except FileNotFoundError:
                    pass
    else:
        if enabled:
            _LINUX_DESKTOP.parent.mkdir(parents=True, exist_ok=True)
            _LINUX_DESKTOP.write_text(
                "[Desktop Entry]\nType=Application\nName=Event Watcher\n"
                f"Exec={' '.join(shlex.quote(p) for p in _command())}\nX-GNOME-Autostart-enabled=true\n",
                encoding="utf-8")
        else:
            _LINUX_DESKTOP.unlink(missing_ok=True)
