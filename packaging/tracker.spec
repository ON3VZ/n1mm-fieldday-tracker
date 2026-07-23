# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for N1MM Field Day Tracker.

Build (from the project root, on Windows):
    pyinstaller packaging\\tracker.spec

Produces dist\\N1MMFieldDayTracker\\N1MMFieldDayTracker.exe (one folder).
We use one-folder (not one-file) so Windows Defender is friendlier and
startup is faster; the Inno Setup installer packs the whole folder.
"""

import os
import sys as _sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# PyInstaller resolves relative paths in a spec against the SPEC file's own
# directory (packaging/), not the directory you run it from. Build absolute
# paths from the project root so the build works from anywhere — including CI.
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

# The web UI (index.html, app.js, style.css) must ship inside the exe bundle;
# config.static_view_dir() reads them from sys._MEIPASS at runtime.
datas = [
    (os.path.join(PROJECT_ROOT, "app", "view", "static"), "app/view/static"),
]

# keyring uses dynamically imported backends; make sure they are included.
# The pywin32-ctypes helper only exists on Windows, so add it conditionally —
# otherwise the Linux build in CI fails on a missing module.
hiddenimports = (
    collect_submodules("keyring")
    + collect_submodules("keyring.backends")
)
if _sys.platform == "win32":
    hiddenimports += ["win32ctypes.pywin32"]

a = Analysis(
    [os.path.join(SPECPATH, "launcher.py")],
    pathex=[PROJECT_ROOT],
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
    icon=(os.path.join(SPECPATH, "tracker.ico")
          if os.path.exists(os.path.join(SPECPATH, "tracker.ico")) else None),
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
