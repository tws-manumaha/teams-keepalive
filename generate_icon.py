#!/usr/bin/env python3
"""
Generate the Teams Keep-Alive desktop icon (teams_keepalive.ico).

Creates a polished green circle with a white "K" letter-mark,
with subtle shadow and gradient. Generates multiple sizes for
Windows (.ico), macOS (.icns), and Linux (.png) compatibility.

Run once:
    python generate_icon.py
"""

from PIL import Image, ImageDraw, ImageFilter
import os


def create_icon(size: int) -> Image.Image:
    """Draw the Teams Keep-Alive icon at a given size.

    Design: rounded green circle with a subtle darker ring,
    white "K" letter-mark in the center with a soft shadow.
    """
    # Use 4x supersampling for smooth edges, then downscale
    ss = 4
    s = size * ss
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Margins (proportional to size)
    m = max(ss, s // 16)
    outer_r = s - m * 2

    # Shadow (offset down-right, blurred)
    shadow_offset = max(ss, s // 50)
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse(
        (m + shadow_offset, m + shadow_offset,
         m + outer_r + shadow_offset, m + outer_r + shadow_offset),
        fill=(0, 80, 0, 100)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(s // 60))
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)

    # Outer ring (darker green)
    ring_w = max(ss, s // 40)
    draw.ellipse(
        (m, m, m + outer_r, m + outer_r),
        fill=(45, 125, 50)  # Dark green ring
    )

    # Inner circle (main green)
    inner_m = m + ring_w
    inner_r = outer_r - ring_w * 2
    draw.ellipse(
        (inner_m, inner_m, inner_m + inner_r, inner_m + inner_r),
        fill=(76, 175, 80)  # Material Green 500
    )

    # Subtle highlight (lighter green at top-left)
    highlight = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    hl_draw = ImageDraw.Draw(highlight)
    hl_r = int(inner_r * 0.6)
    hl_draw.ellipse(
        (inner_m + inner_r // 5, inner_m + inner_r // 8,
         inner_m + inner_r // 5 + hl_r, inner_m + inner_r // 8 + hl_r),
        fill=(129, 199, 132, 80)  # Light green, semi-transparent
    )
    highlight = highlight.filter(ImageFilter.GaussianBlur(s // 25))
    img = Image.alpha_composite(img, highlight)
    draw = ImageDraw.Draw(img)

    # White "K" letter-mark
    cx = (inner_m + inner_m + inner_r) // 2
    top = inner_m + int(inner_r * 0.25)
    bot = inner_m + int(inner_r * 0.75)
    mid = (top + bot) // 2
    right = cx + int(inner_r * 0.28)
    lw = max(ss, inner_r // 14)

    # K shadow
    so = max(ss, s // 80)
    draw.line((cx - inner_r // 6 + so, top + so,
               cx - inner_r // 6 + so, bot + so),
              fill=(0, 60, 0, 120), width=lw)
    draw.line((cx - inner_r // 6 + so, mid + so,
               right + so, top + so),
              fill=(0, 60, 0, 120), width=lw)
    draw.line((cx - inner_r // 6 + so, mid + so,
               right + so, bot + so),
              fill=(0, 60, 0, 120), width=lw)

    # K white strokes
    draw.line((cx - inner_r // 6, top, cx - inner_r // 6, bot),
              fill=(255, 255, 255), width=lw)
    draw.line((cx - inner_r // 6, mid, right, top),
              fill=(255, 255, 255), width=lw)
    draw.line((cx - inner_r // 6, mid, right, bot),
              fill=(255, 255, 255), width=lw)

    # Downscale for anti-aliasing
    img = img.resize((size, size), Image.LANCZOS)
    return img


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    icon = create_icon(256)

    output_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(output_dir, "teams_keepalive.ico")

    # Save .ico (Windows)
    icon.save(ico_path, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"Icon (ICO): {ico_path} ({os.path.getsize(ico_path)} bytes)")

    # Save .png (Linux) at 256px
    png_path = os.path.join(output_dir, "teams_keepalive.png")
    icon.save(png_path, format="PNG")
    print(f"Icon (PNG): {png_path} ({os.path.getsize(png_path)} bytes)")

    # Save .icns (macOS) if supported
    try:
        icns_path = os.path.join(output_dir, "teams_keepalive.icns")
        icon.save(icns_path, format="ICNS")
        print(f"Icon (ICNS): {icns_path} ({os.path.getsize(icns_path)} bytes)")
    except Exception:
        print("ICNS not supported on this platform (skipped)")


if __name__ == "__main__":
    main()
