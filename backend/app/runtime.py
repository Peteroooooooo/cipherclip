from __future__ import annotations

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
