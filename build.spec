# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Tutoring Scheduler app.

Build a standalone Windows executable with:

    pyinstaller build.spec

The result is created under ``dist/TutoringScheduler/``.
"""

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Bundle the QSS stylesheets next to the code so resource_dir() can find them.
datas = [
    ("app/resources/styles/light.qss", "app/resources/styles"),
    ("app/resources/styles/dark.qss", "app/resources/styles"),
]

hiddenimports = collect_submodules("app.models")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="TutoringScheduler",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed GUI app (no console window)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TutoringScheduler",
)
