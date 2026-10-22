from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping


APP_NAME = "CipherClip"
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
    base = environment.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / app_name / "WebView2"


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
