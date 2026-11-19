"""Tell whether a process is still running, and stop one.

Windows reuses process ids, so a process is named by its id and its start time: a later
process with the same id is a different one. The start time is read on Windows only (the
app's platform); elsewhere any running process with the id counts, which is enough for CI.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
from typing import Any

logger = logging.getLogger(__name__)

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_ERROR_ACCESS_DENIED = 5
_FILETIME_TO_UNIX = 11_644_473_600  # seconds from 1601-01-01 to 1970-01-01
_SAME_START = 0.01
"""Start times this close (seconds) belong to the same process."""


def start_time(pid: int) -> float | None:
    """Return when process ``pid`` started (seconds since 1970), or ``None`` if none runs.

    Raises ``PermissionError`` when the process runs but cannot be inspected.
    """
    if sys.platform == "win32":
        return _windows_start_time(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    return 0.0


def current() -> tuple[int, float]:
    """Return the id and start time of this process."""
    pid = os.getpid()
    started = start_time(pid)
    return pid, 0.0 if started is None else started


def is_running(pid: int, started: float) -> bool:
    """Return whether the process ``pid`` that started at ``started`` still runs.

    A process that cannot be inspected counts as running: a lock it holds is never taken
    from it by mistake.
    """
    try:
        actual = start_time(pid)
    except PermissionError:
        return True
    return actual is not None and abs(actual - started) < _SAME_START


def stop(pid: int) -> None:
    """Stop process ``pid`` at once (``TerminateProcess`` on Windows)."""
    os.kill(pid, signal.SIGTERM)


def powershell() -> str:
    """Return Windows PowerShell's full path, so no other powershell.exe on PATH runs."""
    root = os.environ.get("SYSTEMROOT", "C:\\Windows")
    return os.path.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")


_LIST_TIMEOUT = 20.0
"""Seconds the process list may take: PowerShell answers in one or two."""
_LIST_SCRIPT = (
    "Get-CimInstance Win32_Process -Filter \"Name='{name}'\" | "
    'ForEach-Object {{ "$($_.ProcessId)`t$($_.CommandLine)" }}'
)


def command_lines(name: str) -> list[tuple[int, str]]:
    """Return the id and command line of each running process named ``name``.

    Empty outside Windows, and when the list cannot be read (logged): a caller then finds
    nothing to stop.
    """
    if sys.platform != "win32":
        return []
    script = _LIST_SCRIPT.format(name=name.replace("'", "''"))
    try:
        result = subprocess.run(
            [powershell(), "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_LIST_TIMEOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Could not list the %s processes: %s", name, exc)
        return []
    return parse_command_lines(result.stdout)


def parse_command_lines(text: str) -> list[tuple[int, str]]:
    """Return ``(pid, command line)`` from lines of a pid, a tab and the command line."""
    found = []
    for line in text.splitlines():
        pid, _, command = line.partition("\t")
        if pid.strip().isdigit():
            found.append((int(pid), command.strip()))
    return found


def _kernel32() -> Any:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    # Handles are pointer-sized; the default int result would cut them on 64-bit Windows.
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.GetProcessTimes.argtypes = (wintypes.HANDLE, *[ctypes.POINTER(wintypes.FILETIME)] * 4)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    return kernel32


def _windows_start_time(pid: int) -> float | None:
    import ctypes
    from ctypes import wintypes

    kernel32 = _kernel32()
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        if ctypes.get_last_error() == _ERROR_ACCESS_DENIED:
            raise PermissionError(f"Process {pid} cannot be inspected")
        return None
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise PermissionError(f"Process {pid} cannot be inspected")
        if code.value != _STILL_ACTIVE:
            return None
        created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            raise PermissionError(f"Process {pid} cannot be inspected")
        ticks = (created.dwHighDateTime << 32) | created.dwLowDateTime  # 100 ns since 1601
        return ticks / 10_000_000 - _FILETIME_TO_UNIX
    finally:
        kernel32.CloseHandle(handle)
