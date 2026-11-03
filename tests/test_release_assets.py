"""Tests for the release page's files; no GitHub calls."""

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "release_assets.py"
_spec = importlib.util.spec_from_file_location("release_assets", TOOL)
assets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(assets)

CHANGELOG = """# Changelog

## [Unreleased]

## [1.0.0] - 2026-11-04

### Added
- The update button.

## [0.19.0] - 2026-11-03

### Added
- The installer.
"""
NOW = datetime(2026, 11, 4, 9, 30, tzinfo=timezone.utc)


@pytest.fixture
def bundle(tmp_path):
    folder = tmp_path / "nsis"
    folder.mkdir()
    (folder / "Court Booker_1.0.0_x64-setup.exe").write_bytes(b"installer")
    (folder / "Court Booker_1.0.0_x64-setup.exe.sig").write_text("c2lnbmF0dXJl\n", "utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    return folder, changelog


def test_the_notes_are_the_version_s_section():
    assert assets.changelog_section(CHANGELOG, "1.0.0") == "### Added\n- The update button."
    assert assets.changelog_section(CHANGELOG, "0.19.0") == "### Added\n- The installer."


def test_a_version_without_a_section_is_refused():
    with pytest.raises(ValueError, match=r"no section for 2\.0\.0"):
        assets.changelog_section(CHANGELOG, "2.0.0")


def test_the_installer_keeps_one_name_and_the_manifest_points_at_it(bundle, tmp_path):
    folder, changelog = bundle
    out = tmp_path / "out"

    written = assets.gather("v1.0.0", folder, out, changelog, NOW)

    assert [path.name for path in written] == ["CourtBooker-setup.exe", "latest.json"]
    assert (out / "assets" / "CourtBooker-setup.exe").read_bytes() == b"installer"
    manifest = json.loads((out / "assets" / "latest.json").read_text("utf-8"))
    assert manifest == {
        "version": "1.0.0",
        "notes": "### Added\n- The update button.",
        "pub_date": "2026-11-04T09:30:00Z",
        "platforms": {
            "windows-x86_64": {
                "signature": "c2lnbmF0dXJl",
                "url": "https://github.com/servedbyhau/vh-tennis-booker/releases/download/"
                "v1.0.0/CourtBooker-setup.exe",
            }
        },
    }
    assert (out / "notes.md").read_text("utf-8") == "### Added\n- The update button.\n"


def test_an_unsigned_installer_is_refused(bundle, tmp_path):
    folder, changelog = bundle
    (folder / "Court Booker_1.0.0_x64-setup.exe.sig").unlink()

    with pytest.raises(FileNotFoundError, match="signing key"):
        assets.gather("v1.0.0", folder, tmp_path / "out", changelog, NOW)


def test_main_reports_a_missing_installer(tmp_path, capsys):
    assert assets.main(["v9.9.9", "--bundle", str(tmp_path), "--out", str(tmp_path / "o")]) == 1
    assert "No installer" in capsys.readouterr().err
