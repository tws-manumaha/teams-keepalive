# Teams Keep-Alive

A lightweight Python system-tray app that keeps your Microsoft Teams status
**Available** by simulating minimal, non-disruptive user activity at a
regular interval.

## How it works

Every few minutes (default 4) it:

1. Presses the **F15** key — a key that virtually no application responds to,
   so nothing opens or triggers on your screen.
2. Jiggles the mouse by **1 pixel** and immediately back — imperceptible
   while you work.

Because the operating system sees fresh input, Teams never transitions you to
"Away" while the app is running.

## Files

| File | Purpose |
|------|---------|
| `teams_keepalive.py` | The tray application (main script) |
| `requirements.txt`   | Python dependencies            |

## Setup

### 1. Install Python

Requires **Python 3.8+** (3.10+ recommended). Download from
<https://www.python.org/downloads/>.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
python teams_keepalive.py
```

A tray icon appears (a green "K" circle when active).  Right-click it to:

- **Start / Pause** the keep-alive
- **Set Interval** — change how often activity is simulated (1–30 min)
- **Quit** the app

The app auto-starts on launch.

---

## Platform-specific notes

### Windows (10 / 11)

- Works out of the box after `pip install`.
- To make it **run at startup**: place a shortcut to the script (or a
  `.bat` file launching `python teams_keepalive.py`) in
  `Win+R → shell:startup`.
- The F15 keypress is handled by Windows' input stack; no driver needed.
- If you prefer no visible console window, rename your launcher to
  `teams_keepalive.pyw` and run with `pythonw`.

### macOS

- **Accessibility permission required.**  On first run macOS will block
  synthetic input.  Go to:
  **System Settings → Privacy & Security → Accessibility**
  and enable the terminal (or Python) you are running the script from.
- The tray icon appears in the menu-bar extras area.
- To run at login: add the script to
  **System Settings → General → Login Items** or wrap it in a small
  `launchd` plist.

### Linux

- Requires a tray/appindicator implementation.  Install one if missing:
  ```bash
  # Ubuntu / Debian
  sudo apt install gnome-shell-extension-appindicator  # GNOME
  # or use a desktop environment with native tray (KDE, XFCE, Cinnamon)
  ```
- On Wayland, `pynput` mouse control may be limited; F15 keypress usually
  still works.  On X11 everything works as expected.
- To run at startup: add `python teams_keepalive.py` to your desktop
  environment's "Autostart" settings, or create a `.desktop` file in
  `~/.config/autostart/`.

---

## Configuration

The default interval is **4 minutes** (240 seconds), which comfortably
covers the ~5-minute inactivity window Teams uses before marking you Away.

You can change the interval at runtime via the tray menu, or edit
`DEFAULT_INTERVAL` at the top of the script.

## Safety & responsible use

This tool simulates user input to prevent the OS/Teams from marking you as
"Away".  Use it responsibly and in accordance with your organisation's IT
and acceptable-use policies.  It does **not** interact with the Teams
application directly or bypass any authentication — it only produces OS-level
input events identical to real keyboard/mouse activity.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "No module named pystray" | `pip install -r requirements.txt` |
| No tray icon on Linux | Install an AppIndicator extension (see above) |
| Mouse doesn't jiggle on macOS | Grant Accessibility permission (see above) |
| Status still goes Away | Lower the interval to 2–3 minutes; ensure the app is running (green icon) |
| F15 opens something unexpected | Change the key in `_simulate_activity()` to another unused key like `Key.scroll_lock` |
