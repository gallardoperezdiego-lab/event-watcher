#!/usr/bin/env bash
# Event Watcher - macOS / Linux launcher (runs from source; needs Python 3.9+, no extra packages)
cd "$(dirname "$0")" || exit 1
echo "Starting Event Watcher..."
if command -v python3 >/dev/null 2>&1; then
    exec python3 launcher.py "$@"
elif command -v python >/dev/null 2>&1; then
    exec python launcher.py "$@"
else
    echo "Python 3 is required to run Event Watcher from source."
    echo "Install it from https://www.python.org/downloads/ or use the packaged EventWatcher.app."
    exit 1
fi
