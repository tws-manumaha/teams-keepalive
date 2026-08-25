#!/usr/bin/env python3
"""
Generate the Teams Keep-Alive desktop icon (teams_keepalive.ico).

Run this once to create the icon file:
    python generate_icon.py

It creates teams_keepalive.ico in the current directory.
"""

from PIL import Image, ImageDraw
import os


def create_icon(size):
    """Draw the Teams Keep-Alive icon at a given size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Green circle background (same as tray icon)
    margin = max(1, size // 16)
    draw.ellipse((margin, margin, size - margin, size - margin), fill=(76, 175, 80))
    # White "K" mark — scaled to size
    cx = size // 2
    top = int(size * 0.30)
    bot = int(size * 0.70)
    mid = int(size * 0.50)
    right = int(size * 0.68)
    lw = max(2, size // 20)
    # Vertical stroke
    draw.line((cx - size // 8, top, cx - size // 8, bot), fill=(255, 255, 255), width=lw)
    # Upper diagonal
    draw.line((cx - size // 8, mid, right, top), fill=(255, 255, 255), width=lw)
    # Lower diagonal
    draw.line((cx - size // 8, mid, right, bot), fill=(255, 255, 255), width=lw)
    return img


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    icon = create_icon(256)
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "teams_keepalive.ico")
    icon.save(output_path, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"Icon created: {output_path} ({os.path.getsize(output_path)} bytes)")


if __name__ == "__main__":
    main()
