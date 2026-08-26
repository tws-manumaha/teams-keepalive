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
  - icon.run() on the main thread (blocking).
  - Tray callbacks run in pystray's internal thread.
  - Settings dialog creates its own Tk() + mainloop() directly from the callback.
    This works on Windows because pystray uses a Win32 message pump that
    handles nested event loops correctly.

Features (v2.0):
  - Config persistence (~/.teams_keepalive/config.json)
  - Global hotkey Ctrl+Shift+K to pause/resume (pynput GlobalHotKeyListener)
  - Multiple stop times (list; nearest upcoming stop triggers, then is cleared)
  - Randomized jitter (+/-15% of interval; default ON)
  - Work hours mode (only run between start/end time; default OFF)
  - Wayland native support (ydotool, fallback F15 only)
  - Settings GUI (tkinter, tabbed sections)
  - Lock-screen aware: skips mouse jiggle when screen is locked (F15 only)
  - Bulletproof logging with fallback paths

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

APP_DIR: str = os.path.join(os.path.expanduser("~"), ".teams_keepalive")
CONFIG_PATH: str = os.path.join(APP_DIR, "config.json")
LOG_PATH: str = os.path.join(APP_DIR, "keepalive.log")
LOG_PATH_FALLBACK: str = os.path.join(os.path.expanduser("~"), "keepalive.log")

HOTKEY_TOGGLE: str = "<ctrl>+<shift>+k"

INTERVAL_PRESETS: List[int] = [60, 120, 180, 300, 600]

INTERVAL_LABELS: Dict[int, str] = {
    60: "1 min",
    120: "2 min",
    180: "3 min",
    300: "5 min",
    600: "10 min",
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "interval": 60,
    "stop_times": [],
    "work_hours_enabled": False,
    "work_start": "09:00",
    "work_end": "17:00",
    "randomized_jitter": True,
    "hotkey_enabled": True,
}

log: logging.Logger = logging.getLogger(APP_NAME)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def _ensure_app_dir() -> bool:
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        return True
    except OSError:
        return False


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if any(getattr(h, "_keepalive", False) for h in root.handlers):
        return

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler = None
    log_path_used = None

    _ensure_app_dir()
    for candidate_path in (LOG_PATH, LOG_PATH_FALLBACK):
        try:
            handler = logging.handlers.RotatingFileHandler(
                candidate_path, maxBytes=512 * 1024, backupCount=3, encoding="utf-8")
            log_path_used = candidate_path
            break
        except Exception:
            handler = None
            continue

    if handler is None:
        for candidate_path in (LOG_PATH, LOG_PATH_FALLBACK):
            try:
                handler = logging.FileHandler(candidate_path, mode="a", encoding="utf-8")
                log_path_used = candidate_path
                break
            except Exception:
                handler = None
                continue

    if handler is None:
        handler = logging.StreamHandler()
    else:
        global LOG_PATH_IN_USE
        LOG_PATH_IN_USE = log_path_used

    handler.setFormatter(formatter)
    handler._keepalive = True  # type: ignore[attr-defined]
    root.addHandler(handler)

    try:
        handler.flush()
    except Exception:
        pass

    log.info("=" * 50)
    log.info("Teams Keepalive logging initialized")
    if log_path_used:
        log.info("Log file: %s", log_path_used)
    else:
        log.info("WARNING: file logging failed; using StreamHandler (stderr)")
    log.info("App dir: %s", APP_DIR)
    log.info("=" * 50)


LOG_PATH_IN_USE: str = LOG_PATH


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------
class Config:
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
        try:
            subprocess.run(["ydotool", "--version"], capture_output=True, check=False, timeout=5)
            return True
        except (FileNotFoundError, OSError):
            return False

    def jiggle(self) -> None:
        try:
            self._press_keepalive_key()
            if self._is_screen_locked():
                log.debug("Screen locked; skipping mouse jiggle (F15 only)")
                return
            self._jiggle_mouse()
        except Exception as exc:
            log.warning("Input jiggle failed: %s", exc)

    @staticmethod
    def _is_screen_locked() -> bool:
        if IS_WINDOWS:
            return InputController._win_is_locked()
        return False

    @staticmethod
    def _win_is_locked() -> bool:
        try:
            import ctypes
            import ctypes.wintypes
            DESKTOP_SWITCHDESKTOP = 0x0100
            hDesktop = ctypes.windll.user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
            if hDesktop:
                result = ctypes.windll.user32.SwitchDesktop(hDesktop)
                ctypes.windll.user32.CloseDesktop(hDesktop)
                if not result:
                    return True
                return InputController._win_screensaver_running()
            else:
                hDesktop = ctypes.windll.user32.OpenDesktopW("Default", 0, False, DESKTOP_SWITCHDESKTOP)
                if hDesktop:
                    result = ctypes.windll.user32.SwitchDesktop(hDesktop)
                    ctypes.windll.user32.CloseDesktop(hDesktop)
                    if not result:
                        return True
                return True
        except Exception as exc:
            log.debug("Lock detection failed: %s", exc)
            try:
                import subprocess
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq logonui.exe", "/NH"],
                    capture_output=True, text=True, timeout=5)
                if "logonui.exe" in result.stdout.lower():
                    return True
            except Exception:
                pass
            return False

    @staticmethod
    def _win_screensaver_running() -> bool:
        try:
            import ctypes
            import ctypes.wintypes
            SPI_GETSCREENSAVERRUNNING = 114
            running = ctypes.wintypes.BOOL(False)
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_GETSCREENSAVERRUNNING, 0, ctypes.byref(running), 0)
            return bool(running.value)
        except Exception:
            return False

    def _press_keepalive_key(self) -> None:
        if IS_WINDOWS:
            self._win_press_f15()
        else:
            self._pynput_press_f15()

    @staticmethod
    def _win_press_f15() -> None:
        import ctypes
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

    def _jiggle_mouse(self) -> None:
        if IS_WINDOWS:
            self._win_jiggle_mouse()
        elif self.backend == "wayland-ydotool":
            self._ydotool_jiggle_mouse()
        elif self.backend == "wayland-f15-only":
            return
        else:
            self._pynput_jiggle_mouse()

    @staticmethod
    def _win_jiggle_mouse() -> None:
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        point = ctypes.wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        user32.SetCursorPos(point.x + 1, point.y)
        user32.SetCursorPos(point.x, point.y)

    @staticmethod
    def _ydotool_jiggle_mouse() -> None:
        try:
            subprocess.run(["ydotool", "move", "--", "1", "0"], capture_output=True, check=False, timeout=5)
            subprocess.run(["ydotool", "move", "--", "-1", "0"], capture_output=True, check=False, timeout=5)
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
    draw.text(((size - tw) / 2, (size - th) / 2 - 2), text, fill="white", font=font)
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _fallback_png(hex_color: str) -> bytes:
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
    try:
        parts = s.strip().split(":")
        if len(parts) != 2:
            return None
        return dtime(int(parts[0]), int(parts[1]))
    except (ValueError, AttributeError):
        return None


def now_time() -> dtime:
    return datetime.now().time()


def next_stop_datetime(stop_times: List[str], now: Optional[datetime] = None) -> Optional[datetime]:
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
        return max(all_today)
    return None


def remove_past_or_matching_stop(stop_times: List[str], target: Optional[datetime]) -> List[str]:
    if target is None:
        return list(stop_times)
    target_str = target.strftime("%H:%M")
    return [s for s in stop_times if s.strip() != target_str]


def is_within_work_hours(start: str, end: str, now: Optional[datetime] = None) -> bool:
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


def next_work_boundary_datetime(start: str, end: str, now: Optional[datetime] = None) -> Optional[datetime]:
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
# Settings GUI (tkinter, opens from tray callback)
# ---------------------------------------------------------------------------
class SettingsDialog:
    """Tkinter settings dialog.

    Creates its own Tk() root + mainloop() directly from the tray callback.
    On Windows, this works because pystray uses a Win32 message pump that
    handles nested event loops. The tray icon stays responsive while the
    dialog is open.
    """

    def __init__(self, config: Config, on_change: Optional[Callable[[], None]]) -> None:
        self.config = config
        self.on_change = on_change

    def run(self) -> None:
        """Build and show the settings dialog with its own Tk root."""
        log.info("SettingsDialog.run(): building dialog")
        import tkinter as tk
        from tkinter import ttk

        root = tk.Tk()
        root.title("Teams Keepalive - Settings")
        root.resizable(False, False)

        interval_var = tk.IntVar(value=int(self.config.get("interval", 60)))
        jitter_var = tk.BooleanVar(value=bool(self.config.get("randomized_jitter", True)))
        hotkey_var = tk.BooleanVar(value=bool(self.config.get("hotkey_enabled", True)))
        wh_enabled_var = tk.BooleanVar(value=bool(self.config.get("work_hours_enabled", False)))
        wh_start_var = tk.StringVar(value=str(self.config.get("work_start", "09:00")))
        wh_end_var = tk.StringVar(value=str(self.config.get("work_end", "17:00")))
        stop_times: List[str] = list(self.config.get("stop_times", []))

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        # --- Tab 1: Activity ---
        tab1 = ttk.Frame(notebook)
        notebook.add(tab1, text="Activity")
        ttk.Label(tab1, text="Ping interval (seconds):").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        spin = tk.Spinbox(tab1, from_=10, to=3600, increment=10, textvariable=interval_var, width=8)
        spin.grid(row=0, column=1, padx=8, pady=8)
        ttk.Label(tab1, text="Presets:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        preset_frame = ttk.Frame(tab1)
        preset_frame.grid(row=1, column=1, padx=8, pady=4, sticky="w")

        def apply_preset(val: int) -> None:
            interval_var.set(val)

        col = 0
        for p in INTERVAL_PRESETS:
            b = ttk.Button(preset_frame, text=INTERVAL_LABELS.get(p, f"{p}s"), command=lambda v=p: apply_preset(v))
            b.grid(row=0, column=col, padx=2)
            col += 1

        ttk.Checkbutton(tab1, text="Randomized jitter (+/-15%)", variable=jitter_var).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=8, pady=8)
        ttk.Checkbutton(tab1, text="Enable global hotkey Ctrl+Shift+K", variable=hotkey_var).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=8, pady=4)

        # --- Tab 2: Stop times ---
        tab2 = ttk.Frame(notebook)
        notebook.add(tab2, text="Stop times")
        ttk.Label(tab2, text="Auto-stop at these times (nearest upcoming one is used):").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 4))
        listbox = tk.Listbox(tab2, height=8, width=12)
        listbox.grid(row=1, column=0, rowspan=3, padx=8, pady=4)
        new_time_var = tk.StringVar(value="12:00")

        def refresh_listbox() -> None:
            listbox.delete(0, tk.END)
            for s in stop_times:
                listbox.insert(tk.END, s)
        refresh_listbox()

        ttk.Label(tab2, text="Add (HH:MM):").grid(row=1, column=1, sticky="w", padx=4)
        ttk.Entry(tab2, textvariable=new_time_var, width=8).grid(row=2, column=1, padx=4)

        def add_stop() -> None:
            val = new_time_var.get().strip()
            if parse_hhmm(val) is None:
                err_label.config(text="Invalid time (use HH:MM)")
                return
            if val not in stop_times:
                stop_times.append(val)
                stop_times.sort(key=lambda s: parse_hhmm(s) or dtime(0, 0))
            err_label.config(text="")
            refresh_listbox()

        def remove_stop() -> None:
            sel = listbox.curselection()
            if sel:
                del stop_times[sel[0]]
                refresh_listbox()

        ttk.Button(tab2, text="Add", command=add_stop).grid(row=3, column=1, padx=4, sticky="ew")
        ttk.Button(tab2, text="Remove", command=remove_stop).grid(row=4, column=0, padx=8, pady=4, sticky="w")
        err_label = ttk.Label(tab2, text="", foreground="red")
        err_label.grid(row=5, column=0, columnspan=2, sticky="w", padx=8)

        # --- Tab 3: Work hours ---
        tab3 = ttk.Frame(notebook)
        notebook.add(tab3, text="Work hours")
        ttk.Checkbutton(tab3, text="Only run during work hours", variable=wh_enabled_var).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=8)
        ttk.Label(tab3, text="Start (HH:MM):").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(tab3, textvariable=wh_start_var, width=8).grid(row=1, column=1, padx=8, pady=4)
        ttk.Label(tab3, text="End (HH:MM):").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(tab3, textvariable=wh_end_var, width=8).grid(row=2, column=1, padx=8, pady=4)
        ttk.Label(tab3, text="Outside work hours the app auto-pauses; it resumes at start.").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(4, 8))

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

        ttk.Button(btn_frame, text="Apply", command=on_apply).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side="right", padx=4)

        # Center on screen
        root.update_idletasks()
        x = (root.winfo_screenwidth() - root.winfo_width()) // 2
        y = (root.winfo_screenheight() - root.winfo_height()) // 2
        root.geometry(f"+{x}+{y}")
        log.info("SettingsDialog.run(): dialog ready, entering mainloop")

        root.mainloop()
        log.info("SettingsDialog.run(): mainloop exited")


# ---------------------------------------------------------------------------
# Core keepalive app
# ---------------------------------------------------------------------------
class KeepaliveApp:
    """Owns the config, input controller, scheduler thread, and tray icon.

    Architecture (v2.0.9 - reverted to the working v2.0.5 pattern):
      - Main thread: runs pystray icon.run() (blocking, Win32 message pump).
      - Daemon thread: runs _scheduler_loop() (activity jiggles).
      - Tray callbacks: run in pystray's internal thread.
        Settings dialog creates its own Tk() + mainloop() directly.
        Quit calls icon.stop() which causes icon.run() to return.
    """

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

        # Start the hotkey listener (if enabled).
        if self.config.get("hotkey_enabled", True):
            self._start_hotkey_listener()

        # Start the scheduler thread (activity jiggles).
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop, name="keepalive-scheduler", daemon=True)
        self._scheduler_thread.start()

        # Run the tray icon on the main thread (blocking).
        # This call blocks until icon.stop() is called.
        self._run_tray()

        # Cleanup after tray exits.
        self.running.clear()
        try:
            if self._hotkey_listener is not None:
                self._hotkey_listener.stop()
        except Exception:
            pass

    def _run_tray(self) -> None:
        try:
            import pystray
            from PIL import Image as PilImage
            import io
        except Exception as exc:
            log.error("pystray/PIL unavailable; cannot create tray icon: %s", exc)
            self._show_error_dialog(
                "Teams Keep-Alive - Tray Error",
                ("Failed to create the system tray icon.\n\n"
                 "Error: {}\n\nCheck the log file at:\n  {}").format(exc, LOG_PATH_IN_USE))
            return

        green_img = PilImage.open(io.BytesIO(self._tray_icon_green))
        grey_img = PilImage.open(io.BytesIO(self._tray_icon_grey))
        self._tray_icon_green_img = green_img
        self._tray_icon_grey_img = grey_img

        icon = pystray.Icon(
            APP_NAME, icon=green_img, title=APP_NAME, menu=self._build_menu())
        self._tray = icon
        log.info("Tray icon created; entering main loop")
        icon.run()
        log.info("Tray main loop exited")

    # -- pause/resume ------------------------------------------------------
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

    # -- hotkey ------------------------------------------------------------
    def _start_hotkey_listener(self) -> None:
        def run_listener() -> None:
            try:
                from pynput import keyboard
                # pynput API changed in newer versions; try both import paths
                ListenerClass = getattr(keyboard, 'GlobalHotKeyListener', None)
                if ListenerClass is None:
                    from pynput.keyboard import GlobalHotKeyListener as ListenerClass
                self._hotkey_listener = ListenerClass({
                    HOTKEY_TOGGLE: lambda: self._on_hotkey()})
                self._hotkey_listener.start()
                log.info("Hotkey listener started (Ctrl+Shift+K)")
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

    # -- scheduler ---------------------------------------------------------
    def _recompute_stop_target(self) -> None:
        with self._stop_lock:
            stops = list(self.config.get("stop_times", []))
            self._current_stop_target = next_stop_datetime(stops)

    def _scheduler_loop(self) -> None:
        while self.running.is_set():
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

            if self.paused.is_set():
                time.sleep(1.0)
                continue

            self.input.jiggle()
            log.info("Activity ping (interval=%ss)", self.config.get("interval", 60))

            interval = int(self.config.get("interval", 60))
            if self.config.get("randomized_jitter", True):
                delta = interval * 0.15
                sleep_for = random.uniform(interval - delta, interval + delta)
            else:
                sleep_for = float(interval)
            self._interruptible_sleep(max(sleep_for, 1.0))

    def _interruptible_sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while self.running.is_set() and time.monotonic() < end:
            if self.paused.is_set():
                return  # paused - return immediately
            with self._stop_lock:
                target = self._current_stop_target
            if target is not None and datetime.now() >= target:
                return  # stop time arrived - return so main loop triggers it
            time.sleep(min(1.0, end - time.monotonic() + 1e-3))  # check every 1s

    def _sleep_until_work_boundary(self, start: str, end: str) -> None:
        boundary = next_work_boundary_datetime(start, end)
        if boundary is None:
            time.sleep(5.0)
            return
        while self.running.is_set():
            remaining = (boundary - datetime.now()).total_seconds()
            if remaining <= 0:
                break
            time.sleep(min(5.0, max(0.5, remaining)))

    # -- tray --------------------------------------------------------------
    def _build_menu(self) -> Any:
        import pystray
        interval = int(self.config.get("interval", 60))
        interval_label = INTERVAL_LABELS.get(interval, f"{interval}s")
        menu_items = [
            pystray.MenuItem(f"Status: {'Paused' if self.paused.is_set() else 'Active'}", None, enabled=False),
            pystray.MenuItem(f"Interval: {interval_label}", self._on_cycle_interval),
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

    # -- tray callbacks ----------------------------------------------------
    def _on_cycle_interval(self, icon: Any, item: Any) -> None:
        log.info("Tray callback: Cycle interval clicked")
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
        log.info("Tray callback: Pause/Resume clicked")
        self.toggle_pause(reason="manual")
        self._rebuild_menu()

    def _on_open_settings(self, icon: Any, item: Any) -> None:
        log.info("Tray callback: Settings... clicked, opening dialog")
        try:
            SettingsDialog(self.config, on_change=self._on_settings_changed).run()
            log.info("Settings dialog closed")
        except Exception as exc:
            log.error("Settings dialog failed: %s", exc, exc_info=True)

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
        log.info("Tray callback: Quit clicked")
        self.running.clear()
        icon.stop()

    def _on_open_log(self, icon: Any, item: Any) -> None:
        log.info("Tray callback: Open log file clicked")
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
                "Cannot set up logging:\n{}\n\nMake sure ~/.teams_keepalive/ is writable.".format(exc))
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
            ("Failed to initialize the app.\n\nError: {}\n\n"
             "Check the log file at:\n  {}").format(exc, LOG_PATH_IN_USE))
        sys.exit(1)

    try:
        app.start()
    except KeyboardInterrupt:
        log.info("Interrupted by user")
        app.running.clear()
    except Exception as exc:
        log.error("Fatal error in main loop: %s", exc, exc_info=True)
        KeepaliveApp._show_error_dialog(
            "Teams Keep-Alive - Fatal Error",
            ("The app crashed:\n\nError: {}\n\n"
             "Check the log file at:\n  {}").format(exc, LOG_PATH_IN_USE))
        sys.exit(1)


if __name__ == "__main__":
    main()
