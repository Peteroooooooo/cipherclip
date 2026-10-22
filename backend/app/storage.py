from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname
from collections.abc import Iterable

from .models import HistoryRecord
from .models import SettingsState
from .models import default_settings

_MALFORMED_PAYLOAD_ERRORS = (ValueError, TypeError, KeyError, AttributeError)


class AppStorage:
    def __init__(self, *, base_path: Path) -> None:
        self.base_path = Path(base_path)
        self.images_path = self.base_path / "images"
        self.icons_path = self.base_path / "icons"
        self.history_path = self.base_path / "history.json"
        self.settings_path = self.base_path / "settings.json"
        self._ensure_directories()

    def load_settings(self) -> SettingsState:
        self._ensure_directories()
        if not self.settings_path.exists():
            return default_settings(storage_path=str(self.base_path))

        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return SettingsState.from_dict(payload)
        except _MALFORMED_PAYLOAD_ERRORS:
            quarantine_corrupt_file(self.settings_path)
            return default_settings(storage_path=str(self.base_path))

    def save_settings(self, settings: SettingsState) -> None:
        self._ensure_directories()
        atomic_write_text(
            self.settings_path,
            json.dumps(settings.to_dict(), ensure_ascii=False, indent=2),
        )

    def load_records(self) -> list[HistoryRecord]:
        self._ensure_directories()
        if not self.history_path.exists():
            return []

        try:
            payload = json.loads(self.history_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise TypeError("history payload must be a list")
            return [HistoryRecord.from_dict(item) for item in payload]
        except _MALFORMED_PAYLOAD_ERRORS:
            quarantine_corrupt_file(self.history_path)
            return []

    def save_records(self, records: list[HistoryRecord]) -> None:
        self._ensure_directories()
        serialized = [record.to_dict() for record in records]
        atomic_write_text(
            self.history_path,
            json.dumps(serialized, ensure_ascii=False, indent=2),
        )

    def save_image_bytes(self, *, record_id: str, image_bytes: bytes) -> str:
        self._ensure_directories()
        image_path = self.images_path / f"{record_id}.png"
        image_path.write_bytes(image_bytes)
        return image_path.as_uri()

    def import_image_path(self, *, record_id: str, image_path: str | None) -> str | None:
        source_path = resolve_local_path(image_path)
        if source_path is None or not source_path.exists():
            return image_path

        suffix = source_path.suffix or ".png"
        target_path = self.images_path / f"{record_id}{suffix}"
        if source_path.resolve() != target_path.resolve():
            self._ensure_directories()
            shutil.copy2(source_path, target_path)
        return target_path.as_uri()

    def app_icon(self, exe_path: str, *, extract=None) -> str | None:
        """URI of the cached icon of an app's exe, extracting it the first time. Icons are tiny
        and one per app, so they are kept for good (a later clip from the same app reuses it)."""
        key = hashlib.sha1(os.path.normcase(exe_path).encode("utf-8")).hexdigest()[:16]
        icon_path = self.icons_path / f"{key}.png"
        if icon_path.exists():
            return icon_path.as_uri()
        if extract is None:
            from .app_icons import extract_icon_png as extract
        try:
            png = extract(exe_path)
        except OSError:
            png = None
        if not png:
            return None
        self.icons_path.mkdir(parents=True, exist_ok=True)
        icon_path.write_bytes(png)
        return icon_path.as_uri()

    def read_image_bytes(self, image_path: str | None) -> bytes | None:
        source_path = resolve_local_path(image_path)
        if source_path is None or not source_path.exists():
            return None
        return source_path.read_bytes()

    def prune_unreferenced_images(self, image_paths: Iterable[str | None]) -> None:
        self._ensure_directories()
        referenced_paths: set[Path] = set()
        images_root = self.images_path.resolve()

        for image_path in image_paths:
            resolved_path = resolve_local_path(image_path)
            if resolved_path is None:
                continue

            try:
                normalized = resolved_path.resolve()
                normalized.relative_to(images_root)
            except (FileNotFoundError, ValueError):
                continue

            referenced_paths.add(normalized)

        for candidate in self.images_path.iterdir():
            if not candidate.is_file():
                continue
            if candidate.resolve() not in referenced_paths:
                candidate.unlink()

    def _ensure_directories(self) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.images_path.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str, *, replace_attempts: int = 5) -> None:
    file_descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_with_retry(temp_path, path, attempts=replace_attempts)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def quarantine_corrupt_file(path: Path) -> Path | None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.stem}.corrupt-{stamp}{path.suffix}")
    counter = 1
    while target.exists():
        target = path.with_name(f"{path.stem}.corrupt-{stamp}-{counter}{path.suffix}")
        counter += 1

    try:
        os.replace(path, target)
    except OSError:
        return None
    return target


def _replace_with_retry(source: Path, target: Path, *, attempts: int) -> None:
    # Windows briefly locks files that antivirus or indexers are scanning.
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.05)


def resolve_local_path(path: str | None) -> Path | None:
    if not path:
        return None

    parsed = urlparse(path)
    if parsed.scheme in {"http", "https"}:
        return None
    if parsed.scheme == "file":
        # Path.as_uri() writes UNC shares as file://server/share/...; keep the server part.
        # url2pathname does the percent-decoding, so the path must not be unquoted first.
        host = parsed.netloc if parsed.netloc.lower() not in {"", "localhost"} else ""
        location = f"//{host}{parsed.path}" if host else parsed.path
        return Path(url2pathname(location))
    # A one-letter "scheme" is a Windows drive (C:\...), not a URL.
    if parsed.scheme and len(parsed.scheme) > 1:
        return None
    return Path(path)
