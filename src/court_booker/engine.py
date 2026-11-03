"""How to start the engine as a process of its own, from the sources or the packaged app."""

from __future__ import annotations

import sys
from pathlib import Path


def windowless_python(executable: Path) -> Path:
    """Return ``pythonw.exe`` next to ``executable`` if present, so no console opens."""
    candidate = executable.with_name("pythonw.exe")
    return candidate if candidate.is_file() else executable


def engine_command(*, windowless: bool = False) -> list[str]:
    """Return the command that starts the engine, to which its arguments are added.

    The packaged app has no ``-m``: its ``sys.executable`` is the app itself, which opens no
    console. From the sources ``windowless`` picks ``pythonw.exe``, for a process nobody sees.
    """
    executable = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return [str(executable)]
    python = windowless_python(executable) if windowless else executable
    return [str(python), "-m", "court_booker"]
