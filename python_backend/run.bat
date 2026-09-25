@echo off
title Event Watcher
echo Starting Event Watcher...
cd /d "%~dp0"
where py >nul 2>nul && (py -3 launcher.py %*) || (python launcher.py %*)
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Python 3.9+ was not found or Event Watcher stopped with an error.
    echo Install Python from https://www.python.org/downloads/ or use EventWatcher.exe.
    pause
)
