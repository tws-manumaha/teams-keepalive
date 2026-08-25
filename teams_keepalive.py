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
  - Cycle the activity interval (2 / 3 / 4 / 5 / 10 minutes)
  - Quit the app

Tested on Windows 10/11, macOS, and Linux (with AppIndicator / tray support).

---------------------------------------------------------------
DISCLAIMER
---------------------------------------------------------------
This tool simulates user input to prevent the OS / Teams from
marking you as "Away".  Use it responsibly and in accordance with
your organisation's IT and acceptable-use policies.
"""

import os
import threading
import time
import sys
import logging
from logging.handlers import RotatingFileHandler

# --- Third-party libraries -------------------------------------------------
# pystray      – system-tray icon and menu
# Pillow       – required by pystray for the icon image
# pynput       – cross-platform keyboard & mouse control

from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
from pynput.keyboard import Controller as KeyboardController, Key as KbdKey
from pynput.mouse import Controller as MouseController

# --- Configuration ---------------------------------------------------------

APP_NAME = "Teams Keep-Alive"

# Interval choices in seconds (cycled by clicking the Interval menu item)
INTERVALS = [120, 180, 240, 300, 600]  # 2, 3, 4, 5, 10 minutes
DEFAULT_INTERVAL_IDX = 2  # 240 seconds = 4 minutes

MIN_INTERVAL = 30
MAX_INTERVAL = 1800

# --- Logging ---------------------------------------------------------------

LOG_DIR = os.path.join(os.path.expanduser("~"), ".teams_keepalive")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "keepalive.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(LOG_FILE, maxBytes=512_000, backupCount=3),
    ],
)
log = logging.getLogger("keepalive")

log.info("=" * 60)
log.info("Teams Keep-Alive starting up")
log.info("Log file: %s", LOG_FILE)


# --- Activity simulator ----------------------------------------------------

class KeepAlive:
    """Runs in a background thread and periodically jiggles input."""

    def __init__(self):
        self.interval = INTERVALS[DEFAULT_INTERVAL_IDX]
        self.interval_idx = DEFAULT_INTERVAL_IDX
        self.running = False
        self._thread = None
        self._stop_event = threading.Event()
        self.keyboard = KeyboardController()
        self.mouse = MouseController()

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

    def cycle_interval(self):
        """Advance to the next interval in the list and restart if running."""
        self.interval_idx = (self.interval_idx + 1) % len(INTERVALS)
        self.interval = INTERVALS[self.interval_idx]
        log.info("Interval cycled to %ss (%s min)", self.interval, self.interval // 60)
        if self.running:
            self.stop()
            self.start()

    def _simulate_activity(self):
        """Press F15 (harmless) and jiggle the mouse by 1 px."""
        try:
            self.keyboard.press(KbdKey.f15)
            self.keyboard.release(KbdKey.f15)
            log.debug("F15 key pressed")
        except Exception as e:
            log.warning("Keyboard simulate failed: %s", e)

        try:
            pos = self.mouse.position
            self.mouse.position = (pos[0] + 1, pos[1] + 1)
            time.sleep(0.05)
            self.mouse.position = (pos[0], pos[1])
            log.debug("Mouse jiggled from %s", pos)
        except Exception as e:
            log.warning("Mouse simulate failed: %s", e)

    def _loop(self):
        self._simulate_activity()
        while not self._stop_event.is_set():
            if self._stop_event.wait(self.interval):
                break
            self._simulate_activity()
        log.debug("Keep-alive loop exiting")


# --- Tray icon -------------------------------------------------------------

def create_icon_image(active: bool) -> Image.Image:
    """Draw a simple tray icon: green circle when active, grey when idle."""
    img = Image.new("RGB", (64, 64), (30, 30, 30))
    draw = ImageDraw.Draw(img)
    colour = (76, 175, 80) if active else (120, 120, 120)
    draw.ellipse((12, 12, 52, 52), fill=colour)
    draw.line((28, 20, 28, 44), fill=(255, 255, 255), width=3)
    draw.line((28, 32, 40, 20), fill=(255, 255, 255), width=3)
    draw.line((28, 32, 40, 44), fill=(255, 255, 255), width=3)
    return img


# --- Main app --------------------------------------------------------------

def main():
    keepalive = KeepAlive()

    def on_toggle(icon, item):
        keepalive.toggle()
        icon.icon = create_icon_image(keepalive.running)
        icon.update_menu()

    def on_cycle_interval(icon, item):
        keepalive.cycle_interval()
        icon.update_menu()

    def on_quit(icon, item):
        log.info("Quit requested by user")
        keepalive.stop()
        icon.stop()

    # All flat menu items — no submenus, no lists, no generators.
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
                lambda item: f"⏱  Interval: {keepalive.interval // 60} min  (click to change)",
                on_cycle_interval,
            ),
            Menu.SEPARATOR,
            MenuItem(
                lambda item: f"Status: {'Running' if keepalive.running else 'Paused'}",
                None,
                enabled=False,
            ),
            Menu.SEPARATOR,
            MenuItem("❌  Quit", on_quit),
        ),
    )

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
