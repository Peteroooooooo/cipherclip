from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping


APP_NAME = "ClipDeck"
# The app's name before ClipDeck: its WebView2 data folder is moved over (see below).
LEGACY_APP_NAME = "CipherClip"
START_HIDDEN_FLAG = "--start-hidden"


def is_frozen_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def resolve_default_storage_path(
    *,
    project_root: Path,
    executable: Path | str | None = None,
    frozen: bool | None = None,
    env: Mapping[str, str] | None = None,
    app_name: str = APP_NAME,
) -> Path:
    frozen_runtime = is_frozen_runtime() if frozen is None else frozen
    if not frozen_runtime:
        return project_root / "data"

    runtime_executable = Path(executable or sys.executable).resolve()
    return runtime_executable.parent / "data"


def resolve_webview_data_path(*, env: Mapping[str, str] | None = None, app_name: str = APP_NAME) -> Path:
    """Where WebView2 keeps its data between runs.

    pywebview's default is a new temporary folder every launch, which throws away WebView2's GPU
    shader cache: every launch then recompiled the panel's glass shaders on the first summon, which
    is why that summon stuttered. Only browser data lives here (the page runs in private mode, so no
    cookies or site storage are kept); the clipboard history stays in the app's data folder.
    """
    environment = env if env is not None else os.environ
    base = Path(environment.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local"))
    path = base / app_name / "WebView2"
    # Kept from before the rename, so the shader cache (and with it a smooth first summon) survives.
    legacy = base / LEGACY_APP_NAME
    if app_name != LEGACY_APP_NAME and legacy.is_dir() and not path.parent.exists():
        try:
            legacy.rename(path.parent)
        except OSError:
            pass
    return path


def resolve_window_icon(*, project_root: Path, frozen: bool | None = None) -> str | None:
    """The ClipDeck icon for the window and its taskbar button when running from source.

    pywebview otherwise takes the icon of the running exe, which from source is python.exe's. The
    packaged ClipDeck.exe carries the right icon itself, so it needs nothing here.
    """
    if is_frozen_runtime() if frozen is None else frozen:
        return None
    icon = project_root / "assets" / "clipdeck.ico"
    return str(icon) if icon.is_file() else None


def use_own_taskbar_identity(app_id: str = f"{APP_NAME}.{APP_NAME}") -> None:
    """From source, give the process its own taskbar identity: otherwise Windows files its window
    under Python and shows Python's icon on the taskbar button. Must run before any window exists.
    Not for the packaged exe, whose identity must stay the exe's (pinned shortcuts rely on it)."""
    if os.name != "nt" or is_frozen_runtime():
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError):
        pass


def resolve_startup_command(
    *,
    project_root: Path,
    executable: Path | str | None = None,
    frozen: bool | None = None,
) -> str:
    runtime_executable = Path(executable or sys.executable)
    frozen_runtime = is_frozen_runtime() if frozen is None else frozen
    if frozen_runtime:
        return f'"{runtime_executable}" {START_HIDDEN_FLAG}'

    launcher = runtime_executable.with_name("pythonw.exe")
    script_path = project_root / "backend" / "main.py"
    return f'"{launcher}" "{script_path}" {START_HIDDEN_FLAG}'
