#!/usr/bin/env python3
"""
teams_keepalive.py v2.0
=======================
Cross-platform system-tray app that keeps Microsoft Teams status "Available"
by simulating minimal user activity.

Platforms:
  - Windows : ctypes (keybd_event F15, SetCursorPos mouse jiggle)
  - macOS   : pynput (keyboard + mouse control)
  - Linux   : pynput on X11; ydotool on Wayland (mouse jiggle); F15 keypress fallback

Tray:
  - pystray with FLAT MenuItem items only (no submenus).

Features (v2.0):
  - Config persistence (~/.teams_keepalive/config.json)
  - Global hotkey Ctrl+Shift+K to pause/resume (pynput GlobalHotKeyListener)
  - Multiple stop times (list; nearest upcoming stop triggers, then is cleared)
  - Randomized jitter (+/-15% of interval; default ON)
  - Work hours mode (only run between start/end time; default OFF)
  - Wayland native support (ydotool, fallback F15 only)
  - Settings GUI (tkinter, separate thread, tabbed sections)
  - Lock-screen aware: skips mouse jiggle when screen is locked (F15 only)

Python 3.8+ compatible.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import platform
import random
import subprocess
import sys
import threading
import time
from datetime import datetime, time as dtime, timedelta
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
IS_WINDOWS: bool = sys.platform.startswith("win")
IS_MACOS: bool = sys.platform == "darwin"
IS_LINUX: bool = sys.platform.startswith("linux")

# Wayland detection (Linux only). Check XDG_SESSION_TYPE and WAYLAND_DISPLAY.
_IS_WAYLAND: bool = False
if IS_LINUX:
    _session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    _wayland_display = os.environ.get("WAYLAND_DISPLAY", "")
    if _session_type == "wayland" or bool(_wayland_display):
        _IS_WAYLAND = True

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
APP_NAME: str = "Teams Keep-Alive"
APP_VERSION: str = "2.0"

# App data directory and files.
APP_DIR: str = os.path.join(os.path.expanduser("~"), ".teams_keepalive")
CONFIG_PATH: str = os.path.join(APP_DIR, "config.json")
LOG_PATH: str = os.path.join(APP_DIR, "keepalive.log")
# Fallback log path if the app directory is not writable.
LOG_PATH_FALLBACK: str = os.path.join(os.path.expanduser("~"), "keepalive.log")

# Tray green/grey icons are generated as PNG byte strings.
HOTKEY_TOGGLE: str = "<ctrl>+<shift>+k"

# Cycle presets for the interval menu (seconds).
INTERVAL_PRESETS: List[int] = [60, 120, 180, 300, 600]

# Tray color labels for presets.
INTERVAL_LABELS: Dict[int, str] = {
    60: "1 min",
    120: "2 min",
    180: "3 min",
    300: "5 min",
    600: "10 min",
}

# Default config.
DEFAULT_CONFIG: Dict[str, Any] = {
    "interval": 60,
    "stop_times": [],          # list of "HH:MM" strings
    "work_hours_enabled": False,
    "work_start": "09:00",     # "HH:MM"
    "work_end": "17:00",       # "HH:MM"
    "randomized_jitter": True,
    "hotkey_enabled": True,
}

log: logging.Logger = logging.getLogger(APP_NAME)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def _ensure_app_dir() -> bool:
    """Create the app data directory. Returns True on success."""
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        return True
    except OSError:
        return False


def setup_logging() -> None:
    """Configure rotating file logging to ~/.teams_keepalive/keepalive.log.

    Falls back to ~/keepalive.log if the app directory is not writable.
    Falls back to stderr if no file is writable (useful when a console exists).
    With pythonw.exe (no console), file logging is the only option, so we
    try hard to make it work.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Avoid duplicate handlers on re-init.
    if any(getattr(h, "_keepalive", False) for h in root.handlers):
        return

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s")

    handler = None
    log_path_used = None

    # Try the primary log path first.
    _ensure_app_dir()
    for candidate_path in (LOG_PATH, LOG_PATH_FALLBACK):
        try:
            handler = logging.handlers.RotatingFileHandler(
                candidate_path, maxBytes=512 * 1024,
                backupCount=3, encoding="utf-8")
            log_path_used = candidate_path
            break
        except Exception:
            handler = None
            continue

    if handler is None:
        # Last resort: plain FileHandler without rotation.
        for candidate_path in (LOG_PATH, LOG_PATH_FALLBACK):
            try:
                handler = logging.FileHandler(
                    candidate_path, mode="a", encoding="utf-8")
                log_path_used = candidate_path
                break
            except Exception:
                handler = None
                continue

    if handler is None:
        # Absolute last resort: StreamHandler (only useful with a console).
        handler = logging.StreamHandler()
    else:
        # Store the log path for reference in diagnostics.
        global LOG_PATH_IN_USE
        LOG_PATH_IN_USE = log_path_used

    handler.setFormatter(formatter)
    handler._keepalive = True  # type: ignore[attr-defined]
    root.addHandler(handler)

    # Force-flush so the file appears on disk immediately.
    try:
        handler.flush()
    except Exception:
        pass

    # Log the startup banner so the user can confirm the file exists.
    log.info("=" * 50)
    log.info("Teams Keepalive logging initialized")
    if log_path_used:
        log.info("Log file: %s", log_path_used)
    else:
        log.info("WARNING: file logging failed; using StreamHandler (stderr)")
    log.info("App dir: %s", APP_DIR)
    log.info("=" * 50)


# Path where the log file was actually created (may differ from LOG_PATH
# if the primary location was not writable).
LOG_PATH_IN_USE: str = LOG_PATH


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------
class Config:
    """Thread-safe config persistence to config.json."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    # Merge with defaults so missing keys are filled in.
                    merged = dict(DEFAULT_CONFIG)
                    merged.update(data)
                    self._data = merged
                    log.info("Config loaded from %s", CONFIG_PATH)
            except FileNotFoundError:
                log.info("No config file found; using defaults")
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Could not load config (%s); using defaults", exc)

    def save(self) -> None:
        with self._lock:
            try:
                os.makedirs(APP_DIR, exist_ok=True)
                tmp_path = CONFIG_PATH + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as fh:
                    json.dump(self._data, fh, indent=2, sort_keys=True)
                os.replace(tmp_path, CONFIG_PATH)
                log.info("Config saved to %s", CONFIG_PATH)
            except OSError as exc:
                log.warning("Could not save config (%s)", exc)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any, persist: bool = True) -> None:
        with self._lock:
            self._data[key] = value
        if persist:
            self.save()

    def as_dict(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)


# ---------------------------------------------------------------------------
# Input simulation
# ---------------------------------------------------------------------------
class InputController:
    """Abstract-ish input controller. Picks a backend per platform/session."""

    def __init__(self) -> None:
        self.backend: str = "unknown"
        self._init_backend()

    def _init_backend(self) -> None:
        if IS_WINDOWS:
            self.backend = "windows-ctypes"
        elif IS_MACOS:
            self.backend = "macos-pynput"
        elif IS_LINUX and _IS_WAYLAND:
            if self._has_ydotool():
                self.backend = "wayland-ydotool"
            else:
                self.backend = "wayland-f15-only"
        elif IS_LINUX:
            self.backend = "linux-pynput"
        else:
            self.backend = "noop"
        log.info("Input backend: %s (wayland=%s)", self.backend, _IS_WAYLAND)

    @staticmethod
    def _has_ydotool() -> bool:
        """Return True if ydotool is callable via subprocess."""
        try:
            subprocess.run(["ydotool", "--version"],
                            capture_output=True, check=False, timeout=5)
            return True
        except (FileNotFoundError, OSError):
            return False

    # -- public API --------------------------------------------------------
    def jiggle(self) -> None:
        """Perform one minimal-activity event (key + optional mouse).

        When the screen is locked (Windows) or screensaver is active,
        only the F15 keypress is sent. Mouse jiggle is skipped because
        SetCursorPos wakes the Windows lock screen, causing the login
        screen to flash on every cycle.
        """
        try:
            self._press_keepalive_key()
            # Skip mouse jiggle if the screen is locked or screensaver active.
            if self._is_screen_locked():
                log.debug("Screen locked; skipping mouse jiggle (F15 only)")
                return
            self._jiggle_mouse()
        except Exception as exc:  # never let input errors kill the loop
            log.warning("Input jiggle failed: %s", exc)

    @staticmethod
    def _is_screen_locked() -> bool:
        """Return True if the screen is locked or screensaver is running.

        On Windows: uses OpenInputDesktop + SwitchDesktop to detect lock.
        On macOS/Linux: returns False (those platforms typically do not
        wake the screen the way Windows does).
        Returns False if detection fails (safe default = jiggle anyway).
        """
        if IS_WINDOWS:
            return InputController._win_is_locked()
        return False

    @staticmethod
    def _win_is_locked() -> bool:
        """Detect if the Windows workstation is locked.

        Uses the OpenInputDesktop/SwitchDesktop technique: when the
        workstation is locked, SwitchDesktop returns False.
        Also checks for the LogonUI process as a fallback.
        """
        try:
            import ctypes

            DESKTOP_SWITCHDESKTOP = 0x0100
            # Try to open the current input desktop.
            hDesktop = ctypes.windll.user32.OpenInputDesktop(
                0, False, DESKTOP_SWITCHDESKTOP)
            if hDesktop:
                # Can we switch to it? If not, workstation is locked.
                result = ctypes.windll.user32.SwitchDesktop(hDesktop)
                ctypes.windll.user32.CloseDesktop(hDesktop)
                if not result:
                    return True  # locked
                # Also check if screensaver is running.
                return InputController._win_screensaver_running()
            else:
                # Could not open input desktop; try the Default desktop.
                hDesktop = ctypes.windll.user32.OpenDesktopW(
                    "Default", 0, False, DESKTOP_SWITCHDESKTOP)
                if hDesktop:
                    result = ctypes.windll.user32.SwitchDesktop(hDesktop)
                    ctypes.windll.user32.CloseDesktop(hDesktop)
                    if not result:
                        return True  # locked
                return True  # can't open any desktop = probably locked
        except Exception as exc:
            log.debug("Lock detection failed: %s", exc)
            # Check for LogonUI process as fallback.
            try:
                import subprocess
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq logonui.exe",
                     "/NH"],
                    capture_output=True, text=True, timeout=5)
                if "logonui.exe" in result.stdout.lower():
                    return True
            except Exception:
                pass
            return False  # detection failed; assume not locked

    @staticmethod
    def _win_screensaver_running() -> bool:
        """Check if the Windows screensaver is currently running."""
        try:
            import ctypes
            SPI_GETSCREENSAVERRUNNING = 114
            running = ctypes.wintypes.BOOL(False)
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_GETSCREENSAVERRUNNING, 0,
                ctypes.byref(running), 0)
            return bool(running.value)
        except Exception:
            return False

    # -- key ---------------------------------------------------------------
    def _press_keepalive_key(self) -> None:
        if IS_WINDOWS:
            self._win_press_f15()
        else:
            self._pynput_press_f15()

    @staticmethod
    def _win_press_f15() -> None:
        import ctypes  # local import; Windows-only

        VK_F15 = 0x7E
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(VK_F15, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_F15, 0, KEYEVENTF_KEYUP, 0)

    @staticmethod
    def _pynput_press_f15() -> None:
        try:
            from pynput.keyboard import Controller as KbController, Key
        except Exception:
            return
        kb = KbController()
        try:
            kb.press(Key.f15)
            kb.release(Key.f15)
        except Exception as exc:
            log.warning("pynput F15 keypress failed: %s", exc)

    # -- mouse -------------------------------------------------------------
    def _jiggle_mouse(self) -> None:
        if IS_WINDOWS:
            self._win_jiggle_mouse()
        elif self.backend == "wayland-ydotool":
            self._ydotool_jiggle_mouse()
        elif self.backend == "wayland-f15-only":
            return  # skip mouse on Wayland without ydotool
        else:
            self._pynput_jiggle_mouse()

    @staticmethod
    def _win_jiggle_mouse() -> None:
        import ctypes

        user32 = ctypes.windll.user32
        point = ctypes.wintypes.POINT()
        # Read current cursor position.
        user32.GetCursorPos(ctypes.byref(point))
        # Move 1 pixel right then back.
        user32.SetCursorPos(point.x + 1, point.y)
        user32.SetCursorPos(point.x, point.y)

    @staticmethod
    def _ydotool_jiggle_mouse() -> None:
        try:
            subprocess.run(
                ["ydotool", "move", "--", "1", "0"],
                capture_output=True, check=False, timeout=5)
            subprocess.run(
                ["ydotool", "move", "--", "-1", "0"],
                capture_output=True, check=False, timeout=5)
        except (FileNotFoundError, OSError) as exc:
            log.warning("ydotool mouse jiggle failed: %s", exc)

    @staticmethod
    def _pynput_jiggle_mouse() -> None:
        try:
            from pynput.mouse import Controller as MouseController
        except Exception:
            return
        mouse = MouseController()
        try:
            pos = mouse.position
            mouse.position = (pos[0] + 1, pos[1])
            mouse.position = (pos[0], pos[1])
        except Exception as exc:
            log.warning("pynput mouse jiggle failed: %s", exc)


# ---------------------------------------------------------------------------
# Tray icon images
# ---------------------------------------------------------------------------
def _solid_circle_png(hex_color: str) -> bytes:
    """Return a PNG byte string of a solid colored circle with letter K."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return _fallback_png(hex_color)
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size - 2, size - 2], fill=hex_color)
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
    text = "K"
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        tw, th = 20, 24
    draw.text(((size - tw) / 2, (size - th) / 2 - 2), text,
              fill="white", font=font)
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _fallback_png(hex_color: str) -> bytes:
    """Tiny 1x1 PNG as last-resort icon."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    else:
        r, g, b = 0, 200, 0
    import struct, zlib
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
        return c + crc
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    raw = bytes([0, r, g, b, 255])
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def make_active_icon() -> bytes:
    return _solid_circle_png("#1ec874")


def make_paused_icon() -> bytes:
    return _solid_circle_png("#9aa0a6")


# ---------------------------------------------------------------------------
# Scheduler logic helpers
# ---------------------------------------------------------------------------
def parse_hhmm(s: str) -> Optional[dtime]:
    """Parse "HH:MM" into a datetime.time. Returns None on failure."""
    try:
        parts = s.strip().split(":")
        if len(parts) != 2:
            return None
        return dtime(int(parts[0]), int(parts[1]))
    except (ValueError, AttributeError):
        return None


def now_time() -> dtime:
    return datetime.now().time()


def next_stop_datetime(stop_times: List[str], now: Optional[datetime] = None
                       ) -> Optional[datetime]:
    """Return the nearest upcoming stop datetime from a list of "HH:MM".

    None if the list is empty. If any times are in the future today, the
    nearest one is returned. If all times are in the past today, the most
    recent past time is returned so it triggers immediately (instead of
    silently rolling to tomorrow and never stopping).
    """
    if not stop_times:
        return None
    if now is None:
        now = datetime.now()
    all_today: List[datetime] = []
    future_today: List[datetime] = []
    for raw in stop_times:
        t = parse_hhmm(raw)
        if t is None:
            continue
        candidate = datetime.combine(now.date(), t)
        all_today.append(candidate)
        if candidate > now:
            future_today.append(candidate)
    if future_today:
        return min(future_today)
    if all_today:
        return max(all_today)  # most recent past time -> triggers now
    return None


def remove_past_or_matching_stop(stop_times: List[str],
                                 target: Optional[datetime]) -> List[str]:
    """Return a new list with the stop time matching `target` removed."""
    if target is None:
        return list(stop_times)
    target_str = target.strftime("%H:%M")
    return [s for s in stop_times if s.strip() != target_str]


def is_within_work_hours(start: str, end: str,
                         now: Optional[datetime] = None) -> bool:
    """Return True if `now` is within [start, end) work hours."""
    if now is None:
        now = datetime.now()
    st = parse_hhmm(start)
    en = parse_hhmm(end)
    if st is None or en is None:
        return True
    cur = now.time()
    if st < en:
        return st <= cur < en
    elif st > en:
        return cur >= st or cur < en
    else:
        return True


def next_work_boundary_datetime(start: str, end: str,
                                now: Optional[datetime] = None
                                ) -> Optional[datetime]:
    """Return the next datetime the work-hours state flips."""
    if now is None:
        now = datetime.now()
    st = parse_hhmm(start)
    en = parse_hhmm(end)
    if st is None or en is None:
        return None
    candidates: List[datetime] = []
    for t in (st, en):
        candidate = datetime.combine(now.date(), t)
        if candidate <= now:
            candidate = datetime.combine(now.date() + timedelta(days=1), t)
        candidates.append(candidate)
    return min(candidates)


# ---------------------------------------------------------------------------
# Settings GUI (tkinter, runs in its own thread)
# ---------------------------------------------------------------------------
class SettingsDialog:
    """Tkinter settings dialog with sections for all v2.0 options."""

    _lock = threading.Lock()
    _open = False

    def __init__(self, config: Config, on_change: Optional[Callable[[], None]]
                 ) -> None:
        self.config = config
        self.on_change = on_change
        self.root: Any = None

    def run(self) -> None:
        with SettingsDialog._lock:
            if SettingsDialog._open:
                log.info("Settings dialog already open")
                return
            SettingsDialog._open = True
        try:
            self._build_and_run()
        except Exception as exc:
            log.warning("Settings GUI error: %s", exc)
        finally:
            with SettingsDialog._lock:
                SettingsDialog._open = False

    def _build_and_run(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        root = tk.Tk()
        self.root = root
        root.title("Teams Keepalive - Settings")
        root.resizable(False, False)

        interval_var = tk.IntVar(value=int(self.config.get("interval", 60)))
        jitter_var = tk.BooleanVar(
            value=bool(self.config.get("randomized_jitter", True)))
        hotkey_var = tk.BooleanVar(
            value=bool(self.config.get("hotkey_enabled", True)))
        wh_enabled_var = tk.BooleanVar(
            value=bool(self.config.get("work_hours_enabled", False)))
        wh_start_var = tk.StringVar(value=str(self.config.get("work_start", "09:00")))
        wh_end_var = tk.StringVar(value=str(self.config.get("work_end", "17:00")))
        stop_times: List[str] = list(self.config.get("stop_times", []))
        stop_list_var = tk.StringVar(value=self._stop_list_text(stop_times))

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        # --- Tab 1: Activity ---
        tab1 = ttk.Frame(notebook)
        notebook.add(tab1, text="Activity")
        ttk.Label(tab1, text="Ping interval (seconds):").grid(
            row=0, column=0, sticky="w", padx=8, pady=8)
        spin = tk.Spinbox(tab1, from_=10, to=3600, increment=10,
                          textvariable=interval_var, width=8)
        spin.grid(row=0, column=1, padx=8, pady=8)
        ttk.Label(tab1, text="Presets:").grid(row=1, column=0, sticky="w",
                                              padx=8, pady=4)
        preset_frame = ttk.Frame(tab1)
        preset_frame.grid(row=1, column=1, padx=8, pady=4, sticky="w")

        def apply_preset(val: int) -> None:
            interval_var.set(val)

        col = 0
        for p in INTERVAL_PRESETS:
            b = ttk.Button(preset_frame,
                           text=INTERVAL_LABELS.get(p, f"{p}s"),
                           command=lambda v=p: apply_preset(v))
            b.grid(row=0, column=col, padx=2)
            col += 1

        ttk.Checkbutton(tab1, text="Randomized jitter (+/-15%)",
                        variable=jitter_var).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=8, pady=8)
        ttk.Checkbutton(tab1, text="Enable global hotkey Ctrl+Shift+K",
                        variable=hotkey_var).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=8, pady=4)

        # --- Tab 2: Stop times ---
        tab2 = ttk.Frame(notebook)
        notebook.add(tab2, text="Stop times")
        ttk.Label(tab2,
                  text="Auto-stop at these times (nearest upcoming one is used):"
                  ).grid(row=0, column=0, columnspan=3, sticky="w",
                         padx=8, pady=(8, 4))
        listbox = tk.Listbox(tab2, height=8, width=12)
        listbox.grid(row=1, column=0, rowspan=3, padx=8, pady=4)
        new_time_var = tk.StringVar(value="12:00")

        def refresh_listbox() -> None:
            listbox.delete(0, tk.END)
            for s in stop_times:
                listbox.insert(tk.END, s)
            stop_list_var.set(self._stop_list_text(stop_times))

        refresh_listbox()
        ttk.Label(tab2, text="Add (HH:MM):").grid(row=1, column=1, sticky="w",
                                                  padx=4)
        ttk.Entry(tab2, textvariable=new_time_var, width=8).grid(
            row=2, column=1, padx=4)

        def add_stop() -> None:
            val = new_time_var.get().strip()
            if parse_hhmm(val) is None:
                err_label.config(text="Invalid time (use HH:MM)")
                return
            if val not in stop_times:
                stop_times.append(val)
                stop_times.sort(
                    key=lambda s: parse_hhmm(s) or dtime(0, 0))
            err_label.config(text="")
            refresh_listbox()

        def remove_stop() -> None:
            sel = listbox.curselection()
            if sel:
                del stop_times[sel[0]]
                refresh_listbox()

        ttk.Button(tab2, text="Add", command=add_stop).grid(
            row=3, column=1, padx=4, sticky="ew")
        ttk.Button(tab2, text="Remove", command=remove_stop).grid(
            row=4, column=0, padx=8, pady=4, sticky="w")
        err_label = ttk.Label(tab2, text="", foreground="red")
        err_label.grid(row=5, column=0, columnspan=2, sticky="w", padx=8)

        # --- Tab 3: Work hours ---
        tab3 = ttk.Frame(notebook)
        notebook.add(tab3, text="Work hours")
        ttk.Checkbutton(tab3, text="Only run during work hours",
                        variable=wh_enabled_var).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=8)
        ttk.Label(tab3, text="Start (HH:MM):").grid(
            row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(tab3, textvariable=wh_start_var, width=8).grid(
            row=1, column=1, padx=8, pady=4)
        ttk.Label(tab3, text="End (HH:MM):").grid(
            row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(tab3, textvariable=wh_end_var, width=8).grid(
            row=2, column=1, padx=8, pady=4)
        ttk.Label(tab3,
                  text="Outside work hours the app auto-pauses; it resumes at start."
                  ).grid(row=3, column=0, columnspan=2, sticky="w",
                         padx=8, pady=(4, 8))

        # --- Bottom buttons ---
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", padx=8, pady=8)

        def apply_changes() -> None:
            try:
                iv = int(interval_var.get())
                if iv < 10:
                    iv = 10
            except (TypeError, ValueError):
                iv = int(self.config.get("interval", 60))
            self.config.set("interval", iv)
            self.config.set("randomized_jitter", bool(jitter_var.get()))
            self.config.set("hotkey_enabled", bool(hotkey_var.get()))
            self.config.set("work_hours_enabled", bool(wh_enabled_var.get()))
            ws = wh_start_var.get().strip()
            we = wh_end_var.get().strip()
            if parse_hhmm(ws) is not None:
                self.config.set("work_start", ws)
            if parse_hhmm(we) is not None:
                self.config.set("work_end", we)
            self.config.set("stop_times", list(stop_times))
            if self.on_change:
                try:
                    self.on_change()
                except Exception as exc:
                    log.warning("on_change callback error: %s", exc)

        def on_apply() -> None:
            apply_changes()
            err_label.config(text="Saved.")
            root.after(1500, lambda: err_label.config(text=""))

        def on_ok() -> None:
            apply_changes()
            root.destroy()

        def on_cancel() -> None:
            root.destroy()

        ttk.Button(btn_frame, text="Apply", command=on_apply).pack(
            side="left", padx=4)
        ttk.Button(btn_frame, text="OK", command=on_ok).pack(
            side="left", padx=4)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(
            side="right", padx=4)
        root.mainloop()

    @staticmethod
    def _stop_list_text(times: List[str]) -> str:
        return ", ".join(times)


def open_settings_async(config: Config,
                        on_change: Optional[Callable[[], None]] = None) -> None:
    """Launch the settings GUI in its own thread."""
    t = threading.Thread(target=lambda: SettingsDialog(config, on_change).run(),
                         name="keepalive-settings", daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Core keepalive app
# ---------------------------------------------------------------------------
class KeepaliveApp:
    """Owns the config, input controller, scheduler thread, and tray."""

    def __init__(self) -> None:
        self.config = Config()
        self.input = InputController()
        self.running = threading.Event()
        self.running.set()
        self.paused = threading.Event()
        self._pause_reason: str = ""
        self._hotkey_listener: Any = None
        self._hotkey_thread: Optional[threading.Thread] = None
        self._scheduler_thread: Optional[threading.Thread] = None
        self._tray: Any = None
        self._tray_icon_green: bytes = make_active_icon()
        self._tray_icon_grey: bytes = make_paused_icon()
        self._stop_lock = threading.Lock()
        self._current_stop_target: Optional[datetime] = None
        self._recompute_stop_target()

    def start(self) -> None:
        log.info("Teams Keepalive v%s starting", APP_VERSION)
        if self.config.get("hotkey_enabled", True):
            self._start_hotkey_listener()
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="keepalive-scheduler", daemon=True)
        self._scheduler_thread.start()
        self._run_tray()

    def stop(self) -> None:
        log.info("Stopping Teams Keepalive")
        self.running.clear()
        try:
            if self._hotkey_listener is not None:
                self._hotkey_listener.stop()
        except Exception:
            pass
        try:
            if self._tray is not None:
                self._tray.stop()
        except Exception:
            pass

    def _set_paused(self, paused: bool, reason: str) -> None:
        was = self.paused.is_set()
        self.paused.set() if paused else self.paused.clear()
        self._pause_reason = reason if paused else ""
        if was != paused:
            state = "paused" if paused else "resumed"
            extra = f" ({reason})" if paused and reason else ""
            log.info("Activity %s%s", state, extra)
        self._update_tray_icon()

    def toggle_pause(self, reason: str = "manual") -> None:
        if self.paused.is_set():
            self._set_paused(False, "")
        else:
            self._set_paused(True, reason)

    def _start_hotkey_listener(self) -> None:
        def run_listener() -> None:
            try:
                from pynput import keyboard
                self._hotkey_listener = keyboard.GlobalHotKeyListener({
                    HOTKEY_TOGGLE: lambda: self._on_hotkey()
                })
                self._hotkey_listener.start()
                self._hotkey_listener.join()
            except Exception as exc:
                log.warning("Hotkey listener failed: %s", exc)
        self._hotkey_thread = threading.Thread(
            target=run_listener, name="keepalive-hotkey", daemon=True)
        self._hotkey_thread.start()

    def _on_hotkey(self) -> None:
        if not self.config.get("hotkey_enabled", True):
            return
        self.toggle_pause(reason="hotkey")

    def _recompute_stop_target(self) -> None:
        with self._stop_lock:
            stops = list(self.config.get("stop_times", []))
            self._current_stop_target = next_stop_datetime(stops)

    def _scheduler_loop(self) -> None:
        """Main activity loop: jiggles at interval (+/-jitter), handles
        stop times and work hours, sleeps in small slices so it can react
        to config/pause changes quickly."""
        while self.running.is_set():
            # Work hours check.
            if self.config.get("work_hours_enabled", False):
                ws = str(self.config.get("work_start", "09:00"))
                we = str(self.config.get("work_end", "17:00"))
                if not is_within_work_hours(ws, we):
                    if not self.paused.is_set() or self._pause_reason != "work_hours":
                        self._set_paused(True, "work_hours")
                    self._sleep_until_work_boundary(ws, we)
                    continue
                else:
                    if self.paused.is_set() and self._pause_reason == "work_hours":
                        self._set_paused(False, "")

            # Stop-time check.
            # Recompute the target, then immediately check if it has arrived.
            # next_stop_datetime returns past times as well (so they trigger
            # immediately instead of rolling to tomorrow).
            self._recompute_stop_target()
            with self._stop_lock:
                target = self._current_stop_target
            if target is not None and datetime.now() >= target:
                log.info("Reached stop time %s; pausing", target.strftime("%H:%M"))
                stops = remove_past_or_matching_stop(
                    list(self.config.get("stop_times", [])), target)
                self.config.set("stop_times", stops)
                self._current_stop_target = None
                self._set_paused(True, "stop_time")
                continue

            # If paused (by stop_time, hotkey, or manual), just sleep briefly.
            # The app stays in the tray but does NOT jiggle.
            if self.paused.is_set():
                time.sleep(1.0)
                continue

            # Perform the activity jiggle.
            self.input.jiggle()
            log.info("Activity ping (interval=%ss)", self.config.get("interval", 60))

            # Compute next sleep with optional jitter.
            interval = int(self.config.get("interval", 60))
            if self.config.get("randomized_jitter", True):
                delta = interval * 0.15
                sleep_for = random.uniform(interval - delta, interval + delta)
            else:
                sleep_for = float(interval)
            self._interruptible_sleep(max(sleep_for, 1.0))

    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep for `seconds`, waking every 1s to check running/pause/stop."""
        end = time.monotonic() + seconds
        while self.running.is_set() and time.monotonic() < end:
            if self.paused.is_set():
                return  # paused - return immediately so main loop can handle it
            with self._stop_lock:
                target = self._current_stop_target
            if target is not None and datetime.now() >= target:
                return  # stop time arrived - return so main loop triggers it
            time.sleep(min(1.0, end - time.monotonic() + 1e-3))

    def _sleep_until_work_boundary(self, start: str, end: str) -> None:
        """Sleep until the next work-hours boundary, in interruptible slices."""
        boundary = next_work_boundary_datetime(start, end)
        if boundary is None:
            time.sleep(5.0)
            return
        while self.running.is_set():
            remaining = (boundary - datetime.now()).total_seconds()
            if remaining <= 0:
                break
            time.sleep(min(5.0, max(0.5, remaining)))

    def _run_tray(self) -> None:
        try:
            import pystray
            from PIL import Image as PilImage
        except Exception as exc:
            log.error("pystray/PIL unavailable; cannot create tray icon: %s", exc)
            self._show_error_dialog(
                "Teams Keep-Alive - Cannot Start",
                ("Failed to load the system tray library (pystray/Pillow).\n\n"
                 "Error: {}\n\n"
                 "Please install dependencies:\n"
                 "  pip install pystray Pillow pynput\n\n"
                 "The app will now exit.").format(exc)
            )
            return

        try:
            import io
            green_img = PilImage.open(io.BytesIO(self._tray_icon_green))
            grey_img = PilImage.open(io.BytesIO(self._tray_icon_grey))
            self._tray_icon_green_img = green_img
            self._tray_icon_grey_img = grey_img

            icon = pystray.Icon(
                APP_NAME,
                icon=green_img,
                title=APP_NAME,
                menu=self._build_menu(),
            )
            self._tray = icon
            log.info("Tray icon created; entering main loop")
            icon.run()
        except Exception as exc:
            log.error("Tray icon creation failed: %s", exc, exc_info=True)
            self._show_error_dialog(
                "Teams Keep-Alive - Tray Error",
                ("Failed to create the system tray icon.\n\n"
                 "Error: {}\n\n"
                 "Check the log file at:\n"
                 "  {}\n\n"
                 "The app will now exit.").format(exc, LOG_PATH_IN_USE)
            )

    def _build_menu(self) -> Any:
        import pystray
        interval = int(self.config.get("interval", 60))
        interval_label = INTERVAL_LABELS.get(interval, f"{interval}s")
        menu_items = [
            pystray.MenuItem(
                f"Status: {'Paused' if self.paused.is_set() else 'Active'}",
                None, enabled=False),
            pystray.MenuItem(
                f"Interval: {interval_label}",
                self._on_cycle_interval),
            pystray.MenuItem("Pause / Resume", self._on_toggle_pause),
            pystray.MenuItem("Settings...", self._on_open_settings),
            pystray.MenuItem("Open log file", self._on_open_log),
            pystray.MenuItem("Quit", self._on_quit),
        ]
        return pystray.Menu(*menu_items)

    def _rebuild_menu(self) -> None:
        if self._tray is not None:
            try:
                self._tray.update_menu()
            except Exception:
                pass

    def _update_tray_icon(self) -> None:
        if self._tray is not None:
            try:
                if self.paused.is_set():
                    icon_img = getattr(self, "_tray_icon_grey_img", None)
                    if icon_img is None:
                        import io
                        from PIL import Image as PilImage
                        icon_img = PilImage.open(io.BytesIO(self._tray_icon_grey))
                        self._tray_icon_grey_img = icon_img
                else:
                    icon_img = getattr(self, "_tray_icon_green_img", None)
                    if icon_img is None:
                        import io
                        from PIL import Image as PilImage
                        icon_img = PilImage.open(io.BytesIO(self._tray_icon_green))
                        self._tray_icon_green_img = icon_img
                self._tray.icon = icon_img
                self._tray.update_menu()
            except Exception:
                pass

    def _on_cycle_interval(self, icon: Any, item: Any) -> None:
        current = int(self.config.get("interval", 60))
        if current in INTERVAL_PRESETS:
            idx = INTERVAL_PRESETS.index(current)
            new_val = INTERVAL_PRESETS[(idx + 1) % len(INTERVAL_PRESETS)]
        else:
            new_val = INTERVAL_PRESETS[0]
        self.config.set("interval", new_val)
        log.info("Interval cycled to %ss", new_val)
        self._rebuild_menu()

    def _on_toggle_pause(self, icon: Any, item: Any) -> None:
        self.toggle_pause(reason="manual")
        self._rebuild_menu()

    def _on_open_settings(self, icon: Any, item: Any) -> None:
        open_settings_async(self.config, on_change=self._on_settings_changed)

    def _on_settings_changed(self) -> None:
        hotkey_enabled = bool(self.config.get("hotkey_enabled", True))
        if hotkey_enabled and self._hotkey_listener is None:
            self._start_hotkey_listener()
        elif not hotkey_enabled and self._hotkey_listener is not None:
            try:
                self._hotkey_listener.stop()
            except Exception:
                pass
            self._hotkey_listener = None
        self._recompute_stop_target()
        self._rebuild_menu()

    def _on_quit(self, icon: Any, item: Any) -> None:
        self.stop()

    def _on_open_log(self, icon: Any, item: Any) -> None:
        """Open the log file in the default text editor."""
        log_path = LOG_PATH_IN_USE if LOG_PATH_IN_USE else LOG_PATH
        if not os.path.exists(log_path):
            log.warning("Log file not found: %s", log_path)
            return
        try:
            if IS_WINDOWS:
                os.startfile(log_path)  # type: ignore[attr-defined]
            elif IS_MACOS:
                subprocess.run(["open", log_path], check=False)
            else:
                subprocess.run(["xdg-open", log_path], check=False)
        except Exception as exc:
            log.warning("Could not open log file: %s", exc)

    @staticmethod
    def _show_error_dialog(title: str, message: str) -> None:
        """Show a modal error dialog (tkinter). Works even without a tray icon."""
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            messagebox.showerror(title, message, parent=root)
            root.destroy()
        except Exception:
            import traceback
            traceback.print_exc()
            print(message, file=sys.stderr)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    try:
        setup_logging()
    except Exception as exc:
        print("FATAL: Cannot set up logging: {}".format(exc), file=sys.stderr)
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Teams Keep-Alive - Fatal Error",
                "Cannot set up logging:\n{}\n\n"
                "Make sure ~/.teams_keepalive/ is writable.".format(exc)
            )
            root.destroy()
        except Exception:
            pass
        sys.exit(1)

    log.info("=== Teams Keepalive v%s ===", APP_VERSION)
    log.info("Platform: %s | Python: %s | Wayland: %s",
             platform.platform(), sys.version.split()[0], _IS_WAYLAND)

    try:
        app = KeepaliveApp()
    except Exception as exc:
        log.error("Failed to initialize app: %s", exc, exc_info=True)
        KeepaliveApp._show_error_dialog(
            "Teams Keep-Alive - Startup Error",
            ("Failed to initialize the app.\n\n"
             "Error: {}\n\n"
             "Check the log file at:\n"
             "  {}").format(exc, LOG_PATH_IN_USE)
        )
        sys.exit(1)

    try:
        app.start()
    except KeyboardInterrupt:
        log.info("Interrupted by user")
        app.stop()
    except Exception as exc:
        log.error("Fatal error in main loop: %s", exc, exc_info=True)
        KeepaliveApp._show_error_dialog(
            "Teams Keep-Alive - Fatal Error",
            ("The app crashed:\n\n"
             "Error: {}\n\n"
             "Check the log file at:\n"
             "  {}").format(exc, LOG_PATH_IN_USE)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
