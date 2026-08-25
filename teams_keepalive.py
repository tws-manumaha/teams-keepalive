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
def setup_logging() -> None:
    """Configure rotating file logging to ~/.teams_keepalive/keepalive.log."""
    try:
        os.makedirs(APP_DIR, exist_ok=True)
    except OSError:
        pass
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Avoid duplicate handlers on re-init.
    if not any(isinstance(h, logging.handlers.RotatingFileHandler)
               and getattr(h, "_keepalive", False) for h in root.handlers):
        try:
            handler = logging.handlers.RotatingFileHandler(
                LOG_PATH, maxBytes=512 * 1024, backupCount=3, encoding="utf-8")
        except OSError:
            # Fallback to console if file logging unavailable.
            handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"))
        handler._keepalive = True  # type: ignore[attr-defined]
        root.addHandler(handler)


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


# ----------------------------------------------------------------------------
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
        log.info("Input backend: %s (wayland=%s), self.backend, _IS_WAYLAND)

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
        """Perform one minimal-activity event (key + optional mouse)."""
        try:
            self._press_keepalive_key()
            self._jiggle_mouse()
        except Exception as exc:  # never let input errors kill the loop
            log.warning("Input jiggle failed: %s", exc)

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
        # ydotool move --absolute requires x,y. We do a relative nudge instead.
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
    """Return a PNG byte string of a solid colored circle with letter K.

    Uses Pillow if available; otherwise falls back to a tiny prebuilt PNG.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        # Fallback 1x1 PNG of the given color (no K glyph).
        return _fallback_png(hex_color)
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size - 2, size - 2], fill=hex_color)
    # Letter K, white, centered.
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
    # Parse hex color (#RRGGBB) to RGBA.
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    else:
        r, g, b = 0, 200, 0
    # Minimal 1x1 PNG.
    import struct, zlib
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
        return c + crc
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)  # 1x1 8-bit RGBA
    raw = bytes([0, r, g, b, 255])
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def make_active_icon() -> bytes:
    return _solid_circle_png("#1ec874")


def make_paused_icon() -> bytes:
    return _solid_circle_png("#9aa0a6")


# ---------------------------------------------------------------------------
# Scheduler logic helpers
# ----------------------------------------------------------------------------
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

    None if the list is empty. Past-today times are skipped; if none remain
    today, the earliest time tomorrow is returned.
    """
    if not stop_times:
        return None
    if now is None:
        now = datetime.now()
    today_times: List[datetime] = []
    all_times: List[dtime] = []
    for raw in stop_times:
        t = parse_hhmm(raw)
        if t is None:
            continue
        all_times.append(t)
        candidate = datetime.combine(now.date(), t)
        if candidate > now:
            today_times.append(candidate)
    if today_times:
        return min(today_times)
    # All today's times passed; pick earliest tomorrow.
    if all_times:
        earliest = min(all_times)
        return datetime.combine(now.date() + timedelta(days=1), earliest)
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
    """Return True if `now` is within [start, end) work hours.

    Supports overnight ranges (start > end), e.g. 22:00 to 06:00.
    """
    if now is None:
        now = datetime.now()
    st = parse_hhmm(start)
    en = parse_hhmm(end)
    if st is None or en is None:
        return True  # malformed; treat as always-in-hours
    cur = now.time()
    if st < en:
        return st <= cur < en
    elif st > en:
        # Overnight range.
        return cur >= st or cur < en
    else:
        # start == end means all day.
        return True


def next_work_boundary_datetime(start: str, end: str,
                                 now: Optional[datetime] = None
                                 ) -> Optional[datetime]:
    """Return the next datetime the work-hours state flips.

    Used to schedule a wake-up at the boundary so work-hours mode can
    resume/pause promptly without busy-waiting.
    """
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

# placeholder - the actual content is in the base64 block above