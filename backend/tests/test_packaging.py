from pathlib import Path


def test_release_spec_uses_onefile_packaging() -> None:
    spec_path = Path("CipherClip.spec")
    spec = spec_path.read_text(encoding="utf-8")

    assert "exclude_binaries=False" in spec
    assert "a.binaries," in spec
    assert "a.datas," in spec
    assert "COLLECT(" not in spec


def test_release_script_cleans_stale_onedir_outputs() -> None:
    script_path = Path("scripts/build-release.ps1")
    script = script_path.read_text(encoding="utf-8")

    assert "Remove-Item" in script
    assert "dist\\CipherClip" in script
