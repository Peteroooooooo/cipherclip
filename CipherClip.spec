# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_dynamic_libs


project_root = Path(SPEC).resolve().parent
frontend_dist = project_root / "frontend" / "dist"

datas = collect_data_files("webview")
datas.append((str(frontend_dist), "frontend/dist"))

binaries = collect_dynamic_libs("webview")

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
    [],
    exclude_binaries=True,
    name="CipherClip",
    icon=str(project_root / "assets" / "cipherclip.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CipherClip",
)
