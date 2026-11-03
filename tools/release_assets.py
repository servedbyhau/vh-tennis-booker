"""Gather what a version's GitHub release page holds: the installer, the update file, the notes.

The `Desktop` workflow runs it after building the installer of a tag. The installer keeps one
name for every version, so the README's download link always gets the newest one; the app's
update button reads ``latest.json`` from the newest release.

Usage:
    python tools/release_assets.py v1.0.0 --bundle <nsis folder> --out <folder>
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHANGELOG = REPO / "CHANGELOG.md"
GITHUB = "https://github.com/servedbyhau/vh-tennis-booker"
PRODUCT = "Court Booker"
INSTALLER = "CourtBooker-setup.exe"
"""The installer's name on every release page; GitHub would turn a space into a dot."""
MANIFEST = "latest.json"
PLATFORM = "windows-x86_64"


def changelog_section(text: str, version: str) -> str:
    """Return the entries of ``version`` in the changelog, without its heading."""
    heading = f"## [{version}]"
    start = text.find(heading)
    if start == -1:
        raise ValueError(f"CHANGELOG.md has no section for {version}")
    body = text[text.index("\n", start) + 1 :]
    end = body.find("\n## [")
    return (body if end == -1 else body[:end]).strip()


def update_manifest(
    version: str, notes: str, signature: str, tag: str, published: datetime
) -> dict[str, object]:
    """Return the update file the app reads: the version and where its signed installer is."""
    return {
        "version": version,
        "notes": notes,
        "pub_date": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platforms": {
            PLATFORM: {
                "signature": signature.strip(),
                "url": f"{GITHUB}/releases/download/{tag}/{INSTALLER}",
            }
        },
    }


def gather(tag: str, bundle: Path, out: Path, changelog: Path, now: datetime) -> list[Path]:
    """Write the release page's files into ``out/assets`` and its notes to ``out/notes.md``."""
    version = tag[1:] if tag.startswith("v") else tag
    installer = bundle / f"{PRODUCT}_{version}_x64-setup.exe"
    if not installer.is_file():
        raise FileNotFoundError(f"No installer {installer}")
    signature = installer.with_name(installer.name + ".sig")
    if not signature.is_file():
        raise FileNotFoundError(f"No signature {signature}: is the signing key set?")
    notes = changelog_section(changelog.read_text(encoding="utf-8"), version)
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(installer, assets / INSTALLER)
    manifest = update_manifest(
        version, notes, signature.read_text(encoding="utf-8"), tag, now.astimezone(timezone.utc)
    )
    (assets / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out / "notes.md").write_text(notes + "\n", encoding="utf-8")
    return [assets / INSTALLER, assets / MANIFEST]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag", help="the version's tag, e.g. v1.0.0")
    parser.add_argument("--bundle", type=Path, required=True, help="Tauri's nsis output folder")
    parser.add_argument("--out", type=Path, required=True, help="where to write the files")
    args = parser.parse_args(argv)
    try:
        written = gather(args.tag, args.bundle, args.out, CHANGELOG, datetime.now(timezone.utc))
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    for path in written:
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
