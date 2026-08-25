#!/usr/bin/env python3
"""
Teams Keep-Alive Tray App
=========================
A cross-platform system-tray application that keeps your Microsoft Teams
status "Available" by simulating minimal user activity at a regular interval.

It combines two non-disruptive signals:
  1. Presses the F15 key (a virtually unused key that triggers no action on
     any normal application).
  2. Jiggles the mouse by 1 pixel and back (imperceptible during real work).

Runs quietly in the system tray.  Right-click the icon to:
  - Toggle the keep-alive on / off
  - Change the activity interval (default 4 minutes)
  - Quit the app

Tested on Windows 10/11, macOS, and Linux (with AppIndicator / tray support).

---------------------------------------------------------------
DISCLAIMER
---------------------------------------------------------------
This tool simulates user input to prevent the OS / Teams from
marking you as "Away".  Use it responsibly and in accordance with
your organisation's IT and acceptable-use policies.
"""

import threading
import time
import sys
import logging

# --- Third-party libraries -------------------------------------------------
# pystray      – system-tray icon and menu
# Pillow       – required by pystray for the icon image
# pynput       – cross-platform keyboard & mouse control
# tkinter      – for the simple interval-input dialog (stdlib, no pip install)

from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Controller as MouseController

# --- Configuration ---------------------------------------------------------

DEFAULT_INTERVAL = 240          # seconds between activity (4 min)
MIN_INTERVAL = 30                # safety floor
MAX_INTERVAL = 1800              # 30 min ceiling

APP_NAME = "Teams Keep-Alive"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("keepalive")


# --- Activity simulator ----------------------------------------------------

class KeepAlive:
    """Runs in a background thread and periodically jiggles input."""

    def __init__(self):
        self.interval = DEFAULT_INTERVAL
        self.running = False
        self._thread = None
        self._stop_event = threading.Event()
        self.keyboard = KeyboardController()
        self.mouse = MouseController()

    # -- thread control ----------------------------------------------------

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info("Keep-alive started (interval %ss)", self.interval)

    def stop(self):
        if not self.running:
            return
        self.running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        log.info("Keep-alive stopped")

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def set_interval(self, seconds: int):
        seconds = max(MIN_INTERVAL, min(MAX_INTERVAL, seconds))
        self.interval = seconds
        log.info("Interval set to %ss", seconds)

    # -- the actual activity simulation ------------------------------------

    def _simulate_activity(self):
        """Press F15 (harmless) and jiggle the mouse by 1 px."""
        try:
            # F15 is a non-action key on essentially all software
            self.keyboard.press(__import__('pynput').keyboard.Key.f15)
            self.keyboard.release(__import__('pynput').keyboard.Key.f15)
        except Exception as e:
            log.warning("Keyboard simulate failed: %s", e)

        try:
            pos = self.mouse.position
            self.mouse.position = (pos[0] + 1, pos[1] + 1)
            time.sleep(0.05)
            self.mouse.position = (pos[0], pos[1])
        except Exception as e:
            log.warning("Mouse simulate failed: %s", e)

    def _loop(self):
        # Send one ping immediately so status updates quickly
        self._simulate_activity()
        while not self._stop_event.is_set():
            # Wait for interval, but wake early if stop is signalled
            if self._stop_event.wait(self.interval):
                break
            self._simulate_activity()
        log.debug("Keep-alive loop exiting")


# --- Tray icon -------------------------------------------------------------

def create_icon_image(active: bool) -> Image.Image:
    """Draw a simple tray icon: green circle when active, grey when idle."""
    img = Image.new("RGB", (64, 64), (30, 30, 30))
    draw = ImageDraw.Draw(img)
    colour = (76, 175, 80) if active else (120, 120, 120)  # green / grey
    draw.ellipse((12, 12, 52, 52), fill=colour)
    # simple "K" mark
    draw.line((28, 20, 28, 44), fill=(255, 255, 255), width=3)
    draw.line((28, 32, 40, 20), fill=(255, 255, 255), width=3)
    draw.line((28, 32, 40, 44), fill=(255, 255, 255), width=3)
    return img


# --- Interval dialog (tiny tkinter popup) ----------------------------------

def ask_interval(default: int) -> int:
    """Pop up a minimal dialog asking for the interval in minutes."""
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except Exception:
        log.warning("tkinter not available; keeping current interval")
        return default

    root = tk.Tk()
    root.withdraw()
    val = simpledialog.askinteger(
        APP_NAME,
        "Activity interval (minutes):",
        initialvalue=max(1, default // 60),
        minvalue=1,
        maxvalue=30,
    )
    root.destroy()
    return val * 60 if val else default


# --- Main app --------------------------------------------------------------

def main():
    keepalive = KeepAlive()

    def status_text():
        return "Running" if keepalive.running else "Paused"

    def on_toggle(icon, item):
        keepalive.toggle()
        icon.icon = create_icon_image(keepalive.running)
        icon.update_menu()

    def on_set_interval(icon, item):
        new = ask_interval(keepalive.interval)
        keepalive.set_interval(new)
        was_running = keepalive.running
        if was_running:
            keepalive.stop()
            keepalive.start()
        icon.update_menu()

    def on_quit(icon, item):
        keepalive.stop()
        icon.stop()

    # build the tray icon — note `icon` is referenced inside callbacks
    icon = Icon(
        APP_NAME,
        icon=create_icon_image(False),
        title=APP_NAME,
        menu=Menu(
            MenuItem(
                lambda item: ("⏸  Pause" if keepalive.running else "▶  Start"),
                on_toggle,
            ),
            MenuItem(
                "⏱  Set Interval…",
                on_set_interval,
            ),
            Menu.SEPARATOR,
            MenuItem(
                lambda item: f"Status: {status_text()}",
                None,
                enabled=False,
            ),
            MenuItem(
                lambda item: f"Interval: {keepalive.interval // 60} min",
                None,
                enabled=False,
            ),
            Menu.SEPARATOR,
            MenuItem("❌  Quit", on_quit),
        ),
    )

    # auto-start on launch
    keepalive.start()
    icon.icon = create_icon_image(True)

    log.info("%s running.  Right-click the tray icon for options.", APP_NAME)
    icon.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Interrupted by user")
        sys.exit(0)
