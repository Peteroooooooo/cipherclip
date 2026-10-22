# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_dynamic_libs


project_root = Path(SPEC).resolve().parent
frontend_dist = project_root / "frontend" / "dist"

datas = collect_data_files("webview")
datas.append((str(frontend_dist), "frontend/dist"))

binaries = collect_dynamic_libs("webview")

# Live glass helper (built by scripts/build-native.ps1). Optional: without it the app falls back
# to snapshot glass, so a missing DLL must not break the build.
live_backdrop_dll = project_root / "backend" / "native" / "bin" / "clipdeck_backdrop.dll"
if live_backdrop_dll.exists():
    binaries.append((str(live_backdrop_dll), "native"))
# The DLL starts this helper from its own folder for the filtered (capture + blur) live glass.
capture_helper = project_root / "backend" / "native" / "bin" / "clipdeck_capture.exe"
if capture_helper.exists():
    binaries.append((str(capture_helper), "native"))

a = Analysis(
    ["backend/main.py"],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    exclude_binaries=False,
    name="ClipDeck",
    icon=str(project_root / "assets" / "clipdeck.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
