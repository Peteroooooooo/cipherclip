from pathlib import Path


def test_static_build_uses_relative_asset_paths() -> None:
    index_path = Path("frontend/dist/index.html")
    html = index_path.read_text(encoding="utf-8")

    assert 'src="./assets/' in html
    assert 'href="./assets/' in html
