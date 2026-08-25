@echo off
REM Teams Keep-Alive - Windows Launcher
REM Double-click this file to start the app

cd /d "%~dp0"

REM Try pythonw first (no console window), fall back to python
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0teams_keepalive.py"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        start "" python "%~dp0teams_keepalive.py"
    ) else (
        echo ERROR: Python not found. Please install Python 3.8+ from https://python.org
        pause
    )
)
