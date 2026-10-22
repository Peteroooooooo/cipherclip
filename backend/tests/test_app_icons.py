from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image

from backend.app import app_icons
from backend.app.clipboard import ClipboardCapture
from backend.app.state import AppState
from backend.app.storage import AppStorage

WINDOWS = sys.platform == "win32"
EXPLORER = Path(os.environ.get("WINDIR", r"C:\Windows")) / "explorer.exe"


def test_icon_is_extracted_once_and_reused(tmp_path: Path) -> None:
    storage = AppStorage(base_path=tmp_path / "data")
    calls: list[str] = []

    def fake_extract(path: str) -> bytes:
        calls.append(path)
        return b"png-bytes"

    first = storage.app_icon(r"C:\Apps\Tool.exe", extract=fake_extract)
    again = storage.app_icon(r"c:\apps\tool.EXE", extract=fake_extract)

    assert first is not None and first.startswith("file:")
    assert again == first
    assert calls == [r"C:\Apps\Tool.exe"]


def test_no_icon_is_cached_when_the_exe_has_none(tmp_path: Path) -> None:
    storage = AppStorage(base_path=tmp_path / "data")

    assert storage.app_icon(r"C:\Apps\NoIcon.exe", extract=lambda _path: None) is None
    assert not (storage.icons_path.exists() and any(storage.icons_path.iterdir()))


def test_new_clip_gives_its_name_and_icon_to_older_clips_of_the_same_app(tmp_path: Path, monkeypatch) -> None:
    storage = AppStorage(base_path=tmp_path / "data")
    monkeypatch.setattr(storage, "app_icon", lambda exe_path: "file:///icons/code.png")
    state = AppState(storage=storage)

    # Saved before proper names: labelled with the exe's stem and no icon.
    state.ingest_capture(ClipboardCapture(text="old clip", source_app="Code"), captured_at="2026-10-01T10:00:00")
    state.ingest_capture(ClipboardCapture(text="other app", source_app="chrome"), captured_at="2026-10-01T10:01:00")
    snapshot = state.ingest_capture(
        ClipboardCapture(
            text="new clip",
            source_app="Visual Studio Code",
            source_exe=r"C:\Users\me\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        ),
        captured_at="2026-10-22T10:00:00",
    )

    by_text = {record["plainText"]: record for record in snapshot["recentRecords"]}
    assert by_text["new clip"]["sourceIcon"] == "file:///icons/code.png"
    assert by_text["old clip"]["sourceApp"] == "Visual Studio Code"
    assert by_text["old clip"]["sourceIcon"] == "file:///icons/code.png"
    assert by_text["other app"]["sourceApp"] == "chrome"
    assert by_text["other app"]["sourceIcon"] is None


def test_source_icon_survives_a_save_and_reload(tmp_path: Path, monkeypatch) -> None:
    storage = AppStorage(base_path=tmp_path / "data")
    monkeypatch.setattr(storage, "app_icon", lambda exe_path: "file:///icons/qq.png")
    state = AppState(storage=storage)
    state.ingest_capture(ClipboardCapture(text="hi", source_app="QQ", source_exe=r"D:\QQ\QQ.exe"))

    reloaded = AppState(storage=AppStorage(base_path=tmp_path / "data"))

    assert reloaded.snapshot()["recentRecords"][0]["sourceIcon"] == "file:///icons/qq.png"


@pytest.mark.skipif(not WINDOWS or not EXPLORER.exists(), reason="needs a Windows exe with an icon")
def test_reads_a_real_exe_name_and_icon() -> None:
    png = app_icons.extract_icon_png(str(EXPLORER))
    assert png is not None
    image = Image.open(io.BytesIO(png))
    assert image.size == (app_icons.ICON_SIZE, app_icons.ICON_SIZE)
    assert image.mode == "RGBA"
    # Real pixels, with transparent corners round the folder.
    assert image.getbbox() is not None
    assert image.getpixel((0, 0))[3] < 255

    name = app_icons.display_name(str(EXPLORER))
    assert name and name.casefold() != "explorer"


def test_display_name_falls_back_to_the_exe_stem(monkeypatch) -> None:
    monkeypatch.setattr(app_icons, "file_description", lambda _path: None)
    assert app_icons.display_name(r"C:\Tools\snipping_tool.exe") == "snipping tool"

    monkeypatch.setattr(app_icons, "file_description", lambda _path: "A very long description that reads like a sentence")
    assert app_icons.display_name(r"C:\Tools\Paint.exe") == "Paint"
