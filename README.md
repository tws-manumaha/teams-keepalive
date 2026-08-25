# Teams Keep-Alive

A cross-platform Python system-tray app that keeps your Microsoft Teams status **Available** by simulating minimal, non-disruptive user activity at a regular interval.

It presses the **F15 key** (a key no application responds to) and jiggles the mouse **2 pixels** every few minutes. The OS sees fresh input, so Teams never marks you as "Away".

Works on **Windows**, **macOS**, and **Linux** (X11 and Wayland). Installs to your home directory — no admin privileges needed.

## Features

### Core
- **System tray app** — runs quietly in the background, right-click the tray icon for options
- **Cross-platform** — Windows uses ctypes (Win32 API), macOS/Linux use pynput, Wayland uses ydotool
- **Rotating log file** — debug logs at `~/.teams_keepalive/keepalive.log`

### v2.0 Features
- **Config persistence** — all settings saved to `~/.teams_keepalive/config.json` and survive restarts
- **Global hotkey** — press `Ctrl+Shift+K` anywhere to pause/resume (can be disabled)
- **Multiple stop times** — set a list of auto-stop times (e.g. "12:00 lunch, 17:00 end of day"). Nearest upcoming triggers, then clears
- **Randomized jitter** — pings randomized +/-15% of interval for human-like patterns (default: ON)
- **Work hours mode** — only run between set hours (e.g. 9:00-17:00). Auto-pauses outside hours, auto-resumes at start. Supports overnight shifts
- **Wayland native support** — uses `ydotool` for mouse jiggle on Wayland sessions, F15 keypress fallback
- **Settings GUI** — tabbed tkinter window for all settings (Activity, Stop Times, Work Hours)

## Quick Install

### Windows

```powershell
git clone https://github.com/tws-manumaha/teams-keepalive.git
cd teams-keepalive
powershell -ExecutionPolicy Bypass -File install_windows.ps1
```

The installer:
1. Checks Python, installs dependencies
2. Generates the desktop icon (`.ico`)
3. Creates a Desktop shortcut (with icon, no console window)
4. Optionally adds to Windows Startup

### macOS

```bash
git clone https://github.com/tws-manumaha/teams-keepalive.git
cd teams-keepalive
chmod +x install.sh
./install.sh
```

Creates a `.app` bundle with icon. Requires **Accessibility** permission: System Settings -> Privacy & Security -> Accessibility.

### Linux

```bash
git clone https://github.com/tws-manumaha/teams-keepalive.git
cd teams-keepalive
chmod +x install.sh
./install.sh
```

Creates a `.desktop` file (app menu entry). On Wayland, install `ydotool` for mouse jiggle:
```bash
sudo apt install ydotool
```

### Build from binary (no Python needed)

```bash
# Download pre-built binary from GitHub Releases
# https://github.com/tws-manumaha/teams-keepalive/releases
```

Or build yourself with PyInstaller:
```bash
pip install pyinstaller
pyinstaller teams_keepalive.spec
```

### Snap (Linux)

```bash
snap install teams-keepalive
```

## Settings

All settings persist in `~/.teams_keepalive/config.json`:

| Setting | Default | Description |
|---------|---------|-------------|
| `interval` | 60 | Seconds between activity pings |
| `stop_times` | [] | List of "HH:MM" auto-stop times |
| `work_hours_enabled` | false | Only run during work hours |
| `work_start` | "09:00" | Work hours start |
| `work_end` | "17:00" | Work hours end |
| `randomized_jitter` | true | Randomize ping interval +/-15% |
| `hotkey_enabled` | true | Enable Ctrl+Shift+K hotkey |

Access the Settings GUI from the tray menu, or edit `config.json` directly.

## Files

| File | Purpose |
|------|---------|
| `teams_keepalive.py` | The tray application (main script, v2.0) |
| `requirements.txt` | Python dependencies |
| `generate_icon.py` | Generates desktop icons (`.ico`, `.png`, `.icns`) |
| `install_windows.ps1` | One-click installer for Windows |
| `install.sh` | One-click installer for macOS and Linux |
| `teams_keepalive.spec` | PyInstaller spec for building standalone binaries |
| `snap/snapcraft.yaml` | Snap package definition |
| `com.teams-keepalive.app.json` | Flatpak manifest |
| `.github/workflows/ci.yml` | GitHub Actions CI (syntax checks) |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "No module named pystray" | `pip install -r requirements.txt` |
| No tray icon on Linux | Install AppIndicator extension (GNOME) |
| Mouse doesn't jiggle on macOS | Grant Accessibility permission |
| Mouse doesn't jiggle on Wayland | `sudo apt install ydotool` |
| Status still goes Away | Lower the interval to 1-2 minutes |
| Tray menu freezes | Already fixed in v2.0 (flat menu only, no submenus) |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome!

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT License — see [LICENSE](LICENSE). Use it freely, modify it, share it.
