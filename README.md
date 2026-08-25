# Teams Keep-Alive

A cross-platform Python system-tray app that keeps your Microsoft Teams status **Available** by simulating minimal, non-disruptive user activity at a regular interval.

It presses the **F15 key** (a key no application responds to) and jiggles the mouse **2 pixels** every few minutes. The OS sees fresh input, so Teams never marks you as "Away".

Works on **Windows**, **macOS**, and **Linux** (X11 and Wayland). Installs to your home directory — no admin privileges needed.

---

## Table of Contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
   - [Windows](#windows)
   - [macOS](#macos)
   - [Linux](#linux)
   - [Build from Binary (PyInstaller)](#build-from-binary-pyinstaller)
   - [Snap (Linux)](#snap-linux)
4. [How to Use](#how-to-use)
   - [Starting the App](#starting-the-app)
   - [Tray Icon Colors](#tray-icon-colors)
   - [Tray Menu Options](#tray-menu-options)
   - [Global Hotkey](#global-hotkey)
   - [Settings GUI](#settings-gui)
     - [Activity Tab](#activity-tab)
     - [Stop Times Tab](#stop-times-tab)
     - [Work Hours Tab](#work-hours-tab)
5. [Settings Reference](#settings-reference)
6. [How It Works](#how-it-works)
7. [Auto-Start on Boot](#auto-start-on-boot)
8. [Log Files](#log-files)
9. [Files in This Repo](#files-in-this-repo)
10. [Troubleshooting](#troubleshooting)
11. [Contributing](#contributing)
12. [Changelog](#changelog)
13. [License](#license)

---

## Features

### Core
- **System tray app** — runs quietly in the background, right-click the tray icon for options
- **Cross-platform** — Windows uses ctypes (Win32 API), macOS/Linux use pynput, Wayland uses ydotool
- **Rotating log file** — debug logs at `~/.teams_keepalive/keepalive.log`
- **No admin privileges** — installs to your home directory

### v2.0 Features
- **Config persistence** — all settings saved to `~/.teams_keepalive/config.json` and survive restarts
- **Global hotkey** — press `Ctrl+Shift+K` anywhere to pause/resume (can be disabled)
- **Multiple stop times** — set a list of auto-stop times (e.g. "12:00 lunch, 17:00 end of day"). Nearest upcoming triggers, then clears
- **Randomized jitter** — pings randomized +/-15% of interval for human-like patterns (default: ON)
- **Work hours mode** — only run between set hours (e.g. 9:00-17:00). Auto-pauses outside hours, auto-resumes at start. Supports overnight shifts
- **Wayland native support** — uses `ydotool` for mouse jiggle on Wayland sessions, F15 keypress fallback
- **Settings GUI** — tabbed tkinter window for all settings (Activity, Stop Times, Work Hours)

---

## Requirements

- **Python 3.8 or newer** (tested on 3.8, 3.10, 3.12, 3.14)
- **pip** (comes with Python)
- **Internet connection** for initial install (downloads packages)

### Platform-specific notes

| Platform | Requirement | Notes |
|----------|-------------|-------|
| Windows | Python 3.8+ | ctypes is built-in, no extra permissions needed |
| macOS | Python 3.8+ | Must grant Accessibility permission (see [macOS install](#macos)) |
| Linux (X11) | Python 3.8+ | Works out of the box |
| Linux (Wayland) | Python 3.8+ + ydotool | `sudo apt install ydotool` for mouse jiggle (F15 key works without it) |

---

## Installation

### Windows

**Step 1: Download the project**

```powershell
cd $HOME
git clone https://github.com/tws-manumaha/teams-keepalive.git
cd teams-keepalive
```

Or download the ZIP from [GitHub](https://github.com/tws-manumaha/teams-keepalive) and extract it.

**Step 2: Run the installer**

```powershell
powershell -ExecutionPolicy Bypass -File install_windows.ps1
```

The installer will:
1. Check that Python is installed and accessible
2. Install Python dependencies (`pystray`, `Pillow`, `pynput`)
3. Generate the desktop icon (`teams_keepalive.ico`)
4. Create a Desktop shortcut (with icon, no console window)
5. Ask if you want to add it to Windows Startup (so it launches on boot)

**Step 3: Launch the app**

Double-click the **Teams Keep-Alive** shortcut on your Desktop. A green circle with "K" icon appears in your system tray.

**Alternative: Run without installer**

```powershell
pip install -r requirements.txt
python generate_icon.py
pythonw teams_keepalive.py
```

Use `pythonw` (not `python`) to run without a console window.

---

### macOS

**Step 1: Download the project**

```bash
cd ~
git clone https://github.com/tws-manumaha/teams-keepalive.git
cd teams-keepalive
```

**Step 2: Run the installer**

```bash
chmod +x install.sh
./install.sh
```

The installer will:
1. Install Python dependencies
2. Generate the icon (`.icns`)
3. Create a `.app` bundle in `~/Applications/` or `/Applications/`
4. Ask if you want to add it to Login Items (auto-start on boot)

**Step 3: Grant Accessibility permission**

macOS requires you to grant Accessibility permission so the app can simulate keyboard and mouse input:

1. Open **System Settings** > **Privacy & Security** > **Accessibility**
2. Click the **+** button
3. Navigate to the `.app` bundle and add it
4. Toggle the switch to **ON**

**Alternative: Run without installer**

```bash
pip3 install -r requirements.txt
python3 generate_icon.py
python3 teams_keepalive.py
```

---

### Linux

**Step 1: Download the project**

```bash
cd ~
git clone https://github.com/tws-manumaha/teams-keepalive.git
cd teams-keepalive
```

**Step 2: Run the installer**

```bash
chmod +x install.sh
./install.sh
```

The installer will:
1. Install Python dependencies
2. Generate the icon (`.png`)
3. Create a `.desktop` file in `~/.local/share/applications/` (app menu entry)
4. Ask if you want to add it to autostart (`.config/autostart/`)

**Step 3: Wayland users only — install ydotool**

On Wayland sessions, pynput cannot control the mouse. Install `ydotool` for full mouse jiggle:

```bash
sudo apt install ydotool       # Debian/Ubuntu
sudo dnf install ydotool       # Fedora
sudo pacman -S ydotool         # Arch
```

Without ydotool, the app still works (F15 keypress only), but mouse jiggle is skipped.

**Step 4: GNOME users — enable AppIndicator**

If you don't see the tray icon on GNOME, install the AppIndicator extension:

```bash
sudo apt install gnome-shell-extension-appindicator
```

Then log out and log back in.

**Alternative: Run without installer**

```bash
pip3 install -r requirements.txt
python3 generate_icon.py
python3 teams_keepalive.py
```

---

### Build from Binary (PyInstaller)

If you want a standalone executable (no Python installation needed on the target machine):

**Step 1: Install PyInstaller**

```bash
pip install pyinstaller
```

**Step 2: Generate the icon**

```bash
python generate_icon.py
```

**Step 3: Build**

```bash
pyinstaller teams_keepalive.spec
```

Output is in `dist/`:
- Windows: `dist/teams-keepalive.exe`
- macOS: `dist/teams-keepalive`
- Linux: `dist/teams-keepalive`

You can distribute this binary directly. Users just double-click it — no Python needed.

---

### Snap (Linux)

```bash
snap install teams-keepalive
```

Then launch from your app menu or run `teams-keepalive` in terminal.

---

## How to Use

### Starting the App

After installation, start the app using any of these methods:

| Method | How |
|--------|-----|
| **Desktop shortcut** (Windows) | Double-click "Teams Keep-Alive" on your Desktop |
| **App bundle** (macOS) | Double-click "Teams Keep-Alive.app" in Applications |
| **App menu** (Linux) | Search "Teams Keep-Alive" in your application launcher |
| **Terminal** | `python teams_keepalive.py` (or `pythonw` on Windows) |
| **Auto-start** | Enable during install, or see [Auto-Start on Boot](#auto-start-on-boot) |

Once running, a **green circle with "K"** icon appears in your system tray (bottom-right on Windows, top-right on macOS, top-right on Linux).

### Tray Icon Colors

| Icon Color | Meaning |
|------------|---------|
| **Green circle with "K"** | App is **Active** — simulating activity at the set interval |
| **Grey circle with "K"** | App is **Paused** — no activity is being simulated |

The icon changes color instantly when you pause or resume.

### Tray Menu Options

**Right-click** the tray icon to see the menu:

| Menu Item | What it does |
|-----------|--------------|
| **Status: Active** (or Paused) | Shows current state (read-only, cannot click) |
| **Interval: 1 min** | Shows current ping interval. **Click to cycle** through presets: 1 min, 2 min, 3 min, 5 min, 10 min |
| **Pause / Resume** | Pauses or resumes activity simulation immediately |
| **Settings...** | Opens the Settings GUI window |
| **Quit** | Stops the app completely |

### Global Hotkey

Press **`Ctrl+Shift+K`** anywhere on your system to instantly pause or resume the app. You don't need to interact with the tray icon at all.

- The hotkey works even when the app is in the background
- It works system-wide (not just when Teams is focused)
- You can **disable** the hotkey in the Settings GUI if it conflicts with another app
- When the hotkey triggers, the tray icon color changes immediately

### Settings GUI

Open the Settings GUI by right-clicking the tray icon and selecting **Settings...**

The window has **three tabs** at the top. All changes are saved to `~/.teams_keepalive/config.json` immediately when you click **Apply** or **OK**.

#### Activity Tab

Controls the core activity simulation behavior.

| Setting | What it does | Default |
|---------|--------------|---------|
| **Ping interval (seconds)** | How often the app simulates activity. Type a number or use the spinner. Lower = more frequent pings. | 60 |
| **Presets** | Quick buttons to set common intervals: 1 min (60s), 2 min (120s), 3 min (180s), 5 min (300s), 10 min (600s) | — |
| **Randomized jitter (+/-15%)** | When checked, the actual ping interval is randomized within +/-15% of the set interval. This makes the activity pattern look more human-like and less robotic. Example: with interval=60s, pings happen between 51s and 69s randomly. | ON |
| **Enable global hotkey Ctrl+Shift+K** | When checked, the Ctrl+Shift+K hotkey is active. Uncheck to disable the hotkey entirely. | ON |

**Recommended interval:** 60 seconds (1 minute). Teams typically marks you "Away" after 5 minutes of inactivity, so 1-minute pings provide a comfortable margin.

#### Stop Times Tab

Set automatic stop times for breaks, lunch, end of day, etc.

| Control | What it does |
|---------|--------------|
| **List box** | Shows all configured stop times (sorted chronologically) |
| **Add (HH:MM)** | Type a time in 24-hour format (e.g. `12:00`, `17:00`, `17:30`) and click "Add" |
| **Remove** | Select a time in the list and click "Remove" to delete it |
| **Error label** | Shows "Invalid time" if you enter a bad format, or "Saved." on success |

**How stop times work:**

1. You set multiple stop times, e.g. `12:00` (lunch) and `17:00` (end of day)
2. The app finds the **nearest upcoming** stop time
3. When that time arrives, the app **auto-pauses** and **removes that stop time** from the list
4. The app stays paused until you manually resume (via tray menu or hotkey)
5. The remaining stop times are preserved for future use

**Example scenario:**
- Start of day: stop_times = ["12:00", "17:00"]
- At 12:00: app pauses, stop_times = ["17:00"]
- You resume after lunch via Ctrl+Shift+K
- At 17:00: app pauses again, stop_times = []
- Next day, you add new stop times via Settings

**Note:** Stop times are one-shot — each triggers once and is then cleared. This is by design, so you don't get paused every day at the same time unless you re-add the time.

**To disable:** Leave the list empty (the default). No auto-stop will occur.

#### Work Hours Tab

Set a schedule so the app only runs during your work hours.

| Control | What it does | Default |
|---------|--------------|---------|
| **Only run during work hours** | Checkbox to enable/disable work hours mode | OFF |
| **Start (HH:MM)** | Time your work hours begin (24-hour format) | 09:00 |
| **End (HH:MM)** | Time your work hours end (24-hour format) | 17:00 |

**How work hours mode works:**

- When enabled, the app checks the current time against your work hours
- **During work hours:** App runs normally (simulates activity)
- **Outside work hours:** App auto-pauses (grey icon) and sleeps until the next work-hours boundary
- At the start of your work hours, the app **auto-resumes** (green icon)
- At the end of your work hours, the app **auto-pauses** (grey icon)

**Overnight shift support:**

If your start time is later than your end time (e.g. start=22:00, end=06:00), the app treats it as an overnight shift. It runs from 22:00 to 06:00 (next day).

**Example scenarios:**

| Start | End | Active during |
|-------|-----|---------------|
| 09:00 | 17:00 | 9 AM to 5 PM (standard office hours) |
| 22:00 | 06:00 | 10 PM to 6 AM (night shift) |
| 08:00 | 20:00 | 8 AM to 8 PM (extended hours) |

**To disable:** Uncheck the checkbox. The app will run 24/7 regardless of time.

**Note:** Work hours mode and stop times can be used together. Work hours controls when the app is allowed to run; stop times control when it should pause within those hours.

---

## Settings Reference

All settings are stored in `~/.teams_keepalive/config.json` and can be edited directly or via the Settings GUI.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `interval` | integer | 60 | Seconds between activity pings (10-3600) |
| `stop_times` | array of strings | [] | List of "HH:MM" auto-stop times (24-hour format) |
| `work_hours_enabled` | boolean | false | Only run during work hours |
| `work_start` | string | "09:00" | Work hours start time (HH:MM) |
| `work_end` | string | "17:00" | Work hours end time (HH:MM) |
| `randomized_jitter` | boolean | true | Randomize ping interval +/-15% |
| `hotkey_enabled` | boolean | true | Enable Ctrl+Shift+K global hotkey |

**Example config.json:**

```json
{
  "interval": 120,
  "stop_times": ["12:30", "18:00"],
  "work_hours_enabled": true,
  "work_start": "09:00",
  "work_end": "18:00",
  "randomized_jitter": true,
  "hotkey_enabled": true
}
```

You can edit this file directly (when the app is stopped) or use the Settings GUI. Changes via the GUI take effect immediately.

---

## How It Works

1. **Activity simulation:** Every `interval` seconds, the app:
   - Presses the **F15 key** (a function key that no application responds to — it's invisible to the user)
   - Jiggles the mouse **1 pixel right, then back** (imperceptible movement)
2. **Platform backends:**
   - **Windows:** Uses Win32 API via ctypes (`keybd_event` for F15, `SetCursorPos` for mouse). No external libraries needed for input.
   - **macOS:** Uses `pynput` for both keyboard and mouse control. Requires Accessibility permission.
   - **Linux X11:** Uses `pynput` for both keyboard and mouse.
   - **Linux Wayland:** Uses `ydotool` for mouse (if installed). F15 keypress works via pynput. If ydotool is not available, only F15 is sent (mouse jiggle is skipped).
3. **Randomized jitter:** When enabled, the actual sleep duration is `interval +/- 15%`, picked randomly each cycle. This prevents predictable, robotic ping patterns.
4. **Interruptible sleep:** The scheduler sleeps in 1-second slices so it can react immediately to pause/resume, config changes, or quit.
5. **Config persistence:** Every setting change is immediately written to `config.json` with an atomic write-then-rename, so settings are never corrupted even if the app crashes.

---

## Auto-Start on Boot

### Windows

The installer asks if you want to add the app to Windows Startup. If you said yes, a shortcut was placed in:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```

To add/remove manually:
1. Press `Win+R`, type `shell:startup`, press Enter
2. Copy or delete the "Teams Keep-Alive" shortcut

### macOS

The installer asks if you want to add the app to Login Items. If you said yes, it was added via:

**System Settings** > **General** > **Login Items** > **Open at Login**

To add/remove manually:
1. Open System Settings > General > Login Items
2. Click + under "Open at Login"
3. Select the `.app` bundle

### Linux

The installer asks if you want to add the app to autostart. If you said yes, a `.desktop` file was placed in:

```
~/.config/autostart/teams-keepalive.desktop
```

To add/remove manually:
1. Create/edit `~/.config/autostart/teams-keepalive.desktop`
2. Or delete the file to remove autostart

---

## Log Files

The app writes debug logs to:

```
~/.teams_keepalive/keepalive.log
```

The log file **rotates** automatically (max 512KB, 3 backup copies kept).

**What gets logged:**
- App startup (version, platform, Python version, Wayland status)
- Input backend selection (which method is being used)
- Each activity ping (interval, jitter)
- Pause/resume events (with reason: manual, hotkey, stop_time, work_hours)
- Config save/load events
- Stop time triggers
- Work hours boundary crossings
- Errors and warnings

**To check logs:**

```bash
# Windows (PowerShell)
Get-Content "$HOME\.teams_keepalive\keepalive.log" -Tail 50

# macOS / Linux
tail -50 ~/.teams_keepalive/keepalive.log
```

---

## Files in This Repo

| File | Purpose |
|------|---------|
| `teams_keepalive.py` | The tray application (main script, v2.0) |
| `requirements.txt` | Python dependencies |
| `generate_icon.py` | Generates desktop icons (`.ico`, `.png`, `.icns`) |
| `install_windows.ps1` | One-click installer for Windows |
| `install.sh` | One-click installer for macOS and Linux |
| `launch.bat` | Quick double-click launcher for Windows |
| `teams_keepalive.spec` | PyInstaller spec for building standalone binaries |
| `snap/snapcraft.yaml` | Snap package definition |
| `com.teams-keepalive.app.json` | Flatpak manifest |
| `.github/workflows/ci.yml` | GitHub Actions CI (syntax checks on 3.8, 3.10, 3.12) |
| `.github/ISSUE_TEMPLATE/bug_report.md` | Bug report template |
| `.github/ISSUE_TEMPLATE/feature_request.md` | Feature request template |
| `CONTRIBUTING.md` | Contribution guidelines |
| `CHANGELOG.md` | Version history |
| `LICENSE` | MIT License |
| `.gitignore` | Git ignore rules |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "No module named pystray" | `pip install -r requirements.txt` |
| No tray icon on Linux (GNOME) | Install AppIndicator extension: `sudo apt install gnome-shell-extension-appindicator` |
| No tray icon on Linux (KDE) | Should work by default. If not, check that `python3-pystray` is installed |
| Mouse doesn't jiggle on macOS | Grant Accessibility permission: System Settings > Privacy & Security > Accessibility |
| Mouse doesn't jiggle on Wayland | Install ydotool: `sudo apt install ydotool` |
| Status still goes "Away" | Lower the interval to 1-2 minutes. Check the log file for errors |
| Tray menu freezes | Already fixed in v2.0 (flat menu only, no submenus). Make sure you're running v2.0+ |
| Ctrl+Shift+K doesn't work | Make sure hotkey is enabled in Settings. On macOS, pynput may need Accessibility permission |
| App doesn't start on boot (Windows) | Check `shell:startup` for the shortcut. Re-run the installer and say yes to startup |
| App doesn't start on boot (macOS) | Check System Settings > General > Login Items |
| App doesn't start on boot (Linux) | Check `~/.config/autostart/teams-keepalive.desktop` exists |
| Settings don't persist | Check that `~/.teams_keepalive/` directory exists and is writable |
| Python 3.14 issues | v2.0 uses ctypes on Windows (no pynput dependency for input). On macOS/Linux, pynput should work on 3.14+ |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines, code style, testing instructions, and architecture notes. PRs welcome!

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

---

## License

MIT License — see [LICENSE](LICENSE). Use it freely, modify it, share it.
