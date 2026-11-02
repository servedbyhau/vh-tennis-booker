"""Build the packaged app: the UI, then the PyInstaller folder that needs no Python.

Needs the ``app`` and ``build`` extras and ``npm ci`` in ``ui/``. The Tauri shell in ``desktop/``
takes the folder as a resource.

Usage:
    python tools/build_app.py                  # builds dist/court-booker
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = REPO / "packaging" / "court-booker.spec"
UI = REPO / "ui"
OUTPUT = REPO / "dist"
WORK = REPO / "build" / "pyinstaller"
APP_NAME = "court-booker"


def commands(npm: str, python: str, output: Path, work: Path) -> list[tuple[list[str], Path]]:
    """Return the commands of the build, each with the folder it runs in."""
    return [
        ([npm, "run", "build"], UI),
        (
            [
                *[python, "-m", "PyInstaller", str(SPEC), "--noconfirm"],
                *["--distpath", str(output), "--workpath", str(work)],
            ],
            REPO,
        ),
    ]


def expected_files(folder: Path) -> list[Path]:
    """Return the files the app cannot run without, inside the built ``folder``."""
    data = folder / "_internal"
    return [
        folder / f"{APP_NAME}.exe",
        data / "court_booker" / "assets" / "court-driver.apk",
        data / "court_booker" / "ui" / "index.html",
        data / "uiautomator2" / "assets" / "u2.jar",
        data / "adbutils" / "binaries" / "adb.exe",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the packaged app's folder.")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="default: %(default)s")
    args = parser.parse_args(argv)
    npm = shutil.which("npm")
    if npm is None:
        print("npm not found; install Node.js", file=sys.stderr)
        return 1
    for command, folder in commands(npm, sys.executable, args.output.resolve(), WORK):
        subprocess.run(command, cwd=folder, check=True)
    folder = args.output.resolve() / APP_NAME
    missing = [path for path in expected_files(folder) if not path.is_file()]
    if missing:
        print(f"Not built: {', '.join(str(path) for path in missing)}", file=sys.stderr)
        return 1
    print(f"Built {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
