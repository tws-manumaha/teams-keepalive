# Teams Keep-Alive

A cross-platform Python system-tray app that keeps your Microsoft Teams status **Available** by simulating minimal, non-disruptive user activity at a regular interval.

It presses the **F15 key** (a key no application responds to) and jiggles the mouse **2 pixels** every few minutes. The OS sees fresh input, so Teams never marks you as "Away".

Works on **Windows**, **macOS**, and **Linux**. Installs to your home directory — no admin privileges needed.

## Features

- **System tray app** — runs quietly in the background, right-click the tray icon for options
- **Auto-stop scheduler** — set a clock time (e.g. 5 PM) and the app stops itself
- **Configurable interval** — click to cycle between 2 / 3 / 4 / 5 / 10 minute presets
- **Rotating log file** — debug logs at `~/.teams_keepalive/keepalive.log`
- **Cross-platform** — Windows uses ctypes (Win32 API), macOS/Linux use pynput

## Quick Install

### Windows

```powershell
# Clone the repo
git clone https://github.com/tws-manumaha/teams-keepalive.git
cd teams-keepalive

# Run the installer (right-click → Run with PowerShell also works)
powershell -ExecutionPolicy Bypass -File install_windows.ps1
```

The installer will:
1. Check that Python is installed
2. Install Python dependencies (`pystray`, `Pillow`, `pynput`)
3. Generate the desktop icon (`teams_keepalive.ico`)
4. Create a **"Teams Keep-Alive"** shortcut on your Desktop (with icon, no console window)
5. Optionally add it to Windows Startup (so it launches on boot)

### macOS

```bash
git clone https://github.com/tws-manumaha/teams-keepalive.git
cd teams-keepalive
chmod +x install.sh
./install.sh
```

The installer will:
1. Check that Python 3 is installed
2. Install Python dependencies
3. Generate the desktop icon
4. Create a `.app` bundle in `~/Applications` (with icon)
5. Create a Desktop alias

**Important for macOS:** You must grant **Accessibility** permission to the Terminal or Python app under **System Settings → Privacy & Security → Accessibility**, otherwise synthetic input is blocked.

### Linux

```bash
git clone https://github.com/tws-manumaha/teams-keepalive.git
cd teams-keepalive
chmod +x install.sh
./install.sh
```

The installer will:
1. Check that Python 3 and pip are installed
2. Install Python dependencies
3. Generate the desktop icon
4. Create a `.desktop` file in `~/.local/share/applications` (shows in your app menu)
5. Create a desktop shortcut
6. Optionally add it to Autostart

**Linux requirements:**
- A tray/appindicator implementation (GNOME needs `gnome-shell-extension-appindicator`, KDE/XFCE/Cinnamon work out of the box)
- On Wayland, mouse control may be limited; F15 keypress usually still works

## Manual Install (any platform)

If you prefer to set things up yourself:

```bash
git clone https://github.com/tws-manumaha/teams-keepalive.git
cd teams-keepalive

# Install dependencies
pip install -r requirements.txt

# Generate the desktop icon
python generate_icon.py

# Run the app
python teams_keepalive.py
```

## Files

| File | Purpose |
|------|---------|
| `teams_keepalive.py` | The tray application (main script) |
| `requirements.txt` | Python dependencies |
| `generate_icon.py` | Generates the desktop icon (`teams_keepalive.ico`) |
| `install_windows.ps1` | One-click installer for Windows |
| `install.sh` | One-click installer for macOS and Linux |
| `launch.bat` | Simple double-click launcher for Windows |
| `create_desktop_shortcut.ps1` | Creates just the desktop shortcut (Windows) |

## Where it installs

The app runs from wherever you cloned it — no system directories, no admin privileges:

| Platform | App location | Log file | Desktop integration |
|----------|-------------|----------|-------------------|
| Windows | Your clone folder | `%USERPROFILE%\.teams_keepalive\keepalive.log` | Desktop `.lnk` shortcut |
| macOS | Your clone folder | `~/.teams_keepalive/keepalive.log` | `.app` bundle + Desktop alias |
| Linux | Your clone folder | `~/.teams_keepalive/keepalive.log` | `.desktop` file in app menu |

## Configuration

- **Default interval:** 4 minutes (240 seconds) — covers Teams' ~5-minute inactivity window
- Change at runtime via the tray menu (click "Interval" to cycle presets)
- Or edit `INTERVALS` and `DEFAULT_INTERVAL_IDX` at the top of `teams_keepalive.py`

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "No module named pystray" | `pip install -r requirements.txt` |
| No tray icon on Linux | Install an AppIndicator extension (see above) |
| Mouse doesn't jiggle on macOS | Grant Accessibility permission (see above) |
| Status still goes Away | Lower the interval to 2–3 minutes |
| F15 opens something unexpected | Edit `teams_keepalive.py`, change `VK_F15` to another key code |
| Tray menu freezes | Already fixed — the menu uses flat items only, no submenus |

## How it works

Every few minutes (default 4):
1. Presses **F15** — a key that virtually no application responds to
2. Jiggles the mouse **2 pixels** and immediately back — imperceptible during work

On Windows, input is simulated via the Win32 API (`ctypes`) with zero third-party dependency. On macOS/Linux, `pynput` is used.

## Safety & responsible use

This tool simulates user input to prevent the OS/Teams from marking you as "Away". Use it responsibly and in accordance with your organisation's IT and acceptable-use policies. It does **not** interact with the Teams application directly or bypass any authentication — it only produces OS-level input events identical to real keyboard/mouse activity.

## License

MIT License — see [LICENSE](LICENSE). Use it freely, modify it, share it.
