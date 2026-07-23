# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for N1MM Field Day Tracker.

Build (from the project root, on Windows):
    pyinstaller packaging\\tracker.spec

Produces dist\\N1MMFieldDayTracker\\N1MMFieldDayTracker.exe (one folder).
We use one-folder (not one-file) so Windows Defender is friendlier and
startup is faster; the Inno Setup installer packs the whole folder.
"""

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# The web UI (index.html, app.js, style.css) must ship inside the exe bundle;
# config.static_view_dir() reads them from sys._MEIPASS at runtime.
datas = [
    ("app/view/static", "app/view/static"),
]

# keyring uses dynamically imported backends; make sure they are included.
hiddenimports = (
    collect_submodules("keyring")
    + collect_submodules("keyring.backends")
    + ["win32ctypes.pywin32"]  # keyring's Windows backend dependency
)

a = Analysis(
    ["launcher.py"],
    pathex=[os.path.abspath(os.path.join(os.getcwd()))],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "_pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="N1MMFieldDayTracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # keep a console window so the user can see status
    icon=os.path.join("packaging", "tracker.ico")
        if os.path.exists(os.path.join("packaging", "tracker.ico")) else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="N1MMFieldDayTracker",
)
