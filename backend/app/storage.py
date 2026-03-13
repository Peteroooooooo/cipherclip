from __future__ import annotations

import json
import shutil
from pathlib import Path
from urllib.parse import unquote
from urllib.parse import urlparse
from urllib.request import url2pathname
from collections.abc import Iterable

from .models import HistoryRecord
from .models import SettingsState
from .models import default_settings


class AppStorage:
    def __init__(self, *, base_path: Path) -> None:
        self.base_path = Path(base_path)
        self.images_path = self.base_path / "images"
        self.history_path = self.base_path / "history.json"
        self.settings_path = self.base_path / "settings.json"
        self._ensure_directories()

    def load_settings(self) -> SettingsState:
        self._ensure_directories()
        if not self.settings_path.exists():
            return default_settings(storage_path=str(self.base_path))

        payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        return SettingsState.from_dict(payload)

    def save_settings(self, settings: SettingsState) -> None:
        self._ensure_directories()
        self.settings_path.write_text(
            json.dumps(settings.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_records(self) -> list[HistoryRecord]:
        self._ensure_directories()
        if not self.history_path.exists():
            return []

        payload = json.loads(self.history_path.read_text(encoding="utf-8"))
        return [HistoryRecord.from_dict(item) for item in payload]

    def save_records(self, records: list[HistoryRecord]) -> None:
        self._ensure_directories()
        serialized = [record.to_dict() for record in records]
        self.history_path.write_text(
            json.dumps(serialized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save_image_bytes(self, *, record_id: str, image_bytes: bytes) -> str:
        self._ensure_directories()
        image_path = self.images_path / f"{record_id}.png"
        image_path.write_bytes(image_bytes)
        return image_path.as_uri()

    def import_image_path(self, *, record_id: str, image_path: str | None) -> str | None:
        source_path = self._resolve_local_path(image_path)
        if source_path is None or not source_path.exists():
            return image_path

        suffix = source_path.suffix or ".png"
        target_path = self.images_path / f"{record_id}{suffix}"
        if source_path.resolve() != target_path.resolve():
            self._ensure_directories()
            shutil.copy2(source_path, target_path)
        return target_path.as_uri()

    def read_image_bytes(self, image_path: str | None) -> bytes | None:
        source_path = self._resolve_local_path(image_path)
        if source_path is None or not source_path.exists():
            return None
        return source_path.read_bytes()

    def prune_unreferenced_images(self, image_paths: Iterable[str | None]) -> None:
        self._ensure_directories()
        referenced_paths: set[Path] = set()
        images_root = self.images_path.resolve()

        for image_path in image_paths:
            resolved_path = self._resolve_local_path(image_path)
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

    @staticmethod
    def _resolve_local_path(image_path: str | None) -> Path | None:
        if not image_path:
            return None

        parsed = urlparse(image_path)
        if parsed.scheme in {"http", "https"}:
            return None
        if parsed.scheme == "file":
            return Path(url2pathname(unquote(parsed.path)))
        if parsed.scheme:
            return None
        return Path(image_path)
