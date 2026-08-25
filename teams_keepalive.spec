# -*- mode: python ; coding: utf-8 -*-
# ============================================================
#  PyInstaller spec for Teams Keep-Alive
#  Build a standalone binary (no Python installation required)
#
#  Usage:
#    pip install pyinstaller
#    pyinstaller teams_keepalive.spec
#
#  Output: dist/teams-keepalive (Linux/macOS) or dist/teams-keepalive.exe (Windows)
# ============================================================

import sys

block_cipher = None

a = Analysis(
    ['teams_keepalive.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include the icon if it exists
        ('teams_keepalive.ico', '.'),
    ],
    hiddenimports=[
        'pystray._win32',
        'pystray._darwin',
        'pystray._xorg',
        'pynput',
        'pynput.keyboard',
        'pynput.keyboard._win32',
        'pynput.keyboard._darwin',
        'pynput.keyboard._x11',
        'pynput.mouse',
        'pynput.mouse._win32',
        'pynput.mouse._darwin',
        'pynput.mouse._x11',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='teams-keepalive',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='teams_keepalive.ico' if sys.platform.startswith('win') else None,
)
