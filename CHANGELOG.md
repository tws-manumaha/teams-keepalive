# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-08-26

### Added
- **Config persistence**: Settings now save to `~/.teams_keepalive/config.json` and survive restarts.
- **Global hotkey**: Press `Ctrl+Shift+K` anywhere to pause/resume the app. Can be disabled in settings.
- **Multiple stop times**: Set a list of auto-stop times (e.g. "12:00 lunch, 17:00 end of day"). The nearest upcoming stop triggers and is then cleared. Optional feature.
- **Randomized jitter**: Activity pings are randomized within +/-15% of the interval to look more human-like. Default: ON.
- **Work hours mode**: Optional. Only runs between a start and end time (e.g. 9:00-17:00). Auto-pauses outside work hours, auto-resumes at start. Supports overnight shifts (e.g. 22:00-06:00).
- **Wayland native support**: On Linux Wayland sessions, uses `ydotool` for mouse jiggle. Falls back to F15 keypress only if ydotool is not installed.
- **Settings GUI**: Tabbed tkinter window with sections for Activity, Stop Times, and Work Hours. All changes save to config immediately.
- **.gitignore**: Added for Python/IDE/generated file exclusions.
- **CONTRIBUTING.md**: Contribution guidelines for the community.
- **CHANGELOG.md**: This file.
- **GitHub issue templates**: Bug report and feature request templates.
- **GitHub Actions CI**: Syntax checking on every push and PR.
- **PyInstaller spec**: Build standalone `.exe` / `.app` / Linux binary.
- **Snap package**: `snap/snapcraft.yaml` for `snap install teams-keepalive`.
- **Flatpak manifest**: For Flatpak distribution.
- **Better icon**: Improved `generate_icon.py` with a cleaner green circle + "K" design.
- **Auto-start on all platforms**: Windows startup shortcut, macOS Login Items (launchd), Linux autostart (.desktop).
- **MIT License**: Open-source, free for all use.

### Changed
- Major rewrite of `teams_keepalive.py` (v1.x -> v2.0).
- Default interval changed from 240s to 60s (more responsive).
- Tray menu restructured with flat items only (no submenus).

### Fixed
- Tray menu freeze caused by tkinter blocking pystray's event loop (v1.x).
- `AttributeError: 'generator'/'list' object has no attribute 'visible'` from pystray submenu constructor (v1.x).
- pynput silently failing to simulate input on Python 3.14 (replaced with ctypes on Windows).
- PowerShell installer crashing on non-ASCII characters (em-dashes, emojis).

## [1.0.0] - 2026-08-25

### Added
- Initial release.
- Cross-platform system tray app (Windows, macOS, Linux).
- F15 keypress + 2px mouse jiggle every 4 minutes (default).
- Click-to-cycle interval presets (2/3/4/5/10 minutes).
- Auto-stop scheduler with 12-hour AM/PM time picker GUI.
- Rotating file logging (`~/.teams_keepalive/keepalive.log`).
- Windows ctypes input (Win32 API), macOS/Linux pynput.
- Desktop shortcut creation (PowerShell + bash installers).
- Icon generation script (`generate_icon.py`).
- `launch.bat` for quick Windows startup.
