@echo off
REM ============================================================
REM  Teams Keep-Alive — Desktop Launcher
REM  Double-click this file to start the app.
REM  Put this file and teams_keepalive.py in the same folder.
REM ============================================================

cd /d "%~dp0"

REM Try "pythonw" first (no console window), fall back to "py" (Windows Python Launcher)
where pythonw >nul 2>nul
if %ERRORLEVEL% == 0 (
    pythonw teams_keepalive.py
) else (
    where pyw >nul 2>nul
    if %ERRORLEVEL% == 0 (
        pyw teams_keepalive.py
    ) else (
        echo Python not found! Please install Python from https://www.python.org/downloads/
        pause
    )
)
