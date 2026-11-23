"""Start the MuMu Player emulator through its ``MuMuManager.exe`` command line."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Callable

from court_booker import processes
from court_booker.errors import EmulatorError, MuMuNotFoundError

logger = logging.getLogger(__name__)

Run = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]

DEVICE_PROCESS = "MuMuNxDevice.exe"
"""The process that runs one MuMu instance, ``--vm MuMuPlayerGlobal-15.0-<index>``."""
_POLL_INTERVAL = 2.0
_STOP_POLL_INTERVAL = 0.5
_COMMAND_TIMEOUT = 60.0
MUMU_TIMEOUT = 20.0
"""Seconds a MuMuManager command may take: each answers in under a second (``control launch``
returns before Android boots). A frozen instance makes ``info`` hang (2026-11-19, a suspended
``MuMuNxDevice``), so a longer limit only delays the repair."""
CALL_ATTEMPTS = 3
"""Tries a run gives each MuMuManager command. On 2026-11-19 ``control launch`` failed at once
with "nemu-api init failed" (exit -500) while the other instance's process started its own
MuMu; the other one launched. A failure is passing, and the run has 15 minutes to spare."""
RETRY_DELAY = 2.0
"""Seconds between two tries of a MuMuManager command."""
# Keep the console window of a scheduled run from flashing for every call.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run_command(
    args: Sequence[str], timeout: float = _COMMAND_TIMEOUT
) -> subprocess.CompletedProcess[str]:
    """Run ``args`` and capture its text output."""
    return subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=_NO_WINDOW,
        check=False,
    )


def run_mumu_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run a MuMuManager command, limited to :data:`MUMU_TIMEOUT`."""
    return run_command(args, timeout=MUMU_TIMEOUT)


class MuMu:
    """One MuMu Player instance, addressed by its index.

    ``attempts`` is how often a failed MuMuManager command is tried in all: a run passes
    :data:`CALL_ATTEMPTS`; the setup checks and the backend keep one, to answer at once.
    """

    def __init__(
        self,
        manager: Path,
        index: int = 0,
        run: Run = run_mumu_command,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        attempts: int = 1,
    ) -> None:
        self.manager = manager
        self.index = index
        self.attempts = max(1, attempts)
        self._run = run
        self._clock = clock
        self._sleep = sleep

    def sibling(self, index: int) -> MuMu:
        """Return MuMu instance ``index`` of the same MuMuManager, asked once a call."""
        return MuMu(self.manager, index, self._run, self._clock, self._sleep)

    def info(self) -> dict[str, Any]:
        """Return the instance state reported by ``MuMuManager.exe info``."""
        output = self._call("info")
        try:
            data = json.loads(output)
        except ValueError as exc:
            raise EmulatorError(f"Unexpected output from MuMuManager info: {output!r}") from exc
        # A single index returns the instance itself; several indexes are keyed by index.
        if isinstance(data, dict) and "index" not in data and str(self.index) in data:
            data = data[str(self.index)]
        if not isinstance(data, dict):
            raise EmulatorError(f"Unexpected output from MuMuManager info: {output!r}")
        return data

    def is_started(self) -> bool:
        """Return whether Android inside the instance has finished booting."""
        return bool(self.info().get("is_android_started"))

    def is_process_started(self) -> bool:
        """Return whether the instance's process runs, booted or not."""
        return bool(self.info().get("is_process_started"))

    def adb_serial(self) -> str | None:
        """Return the ``host:port`` ADB serial of the running instance, if reported."""
        info = self.info()
        host, port = info.get("adb_host_ip"), info.get("adb_port")
        return f"{host}:{port}" if host and port else None

    def launch(self) -> None:
        """Ask MuMu to start the instance; returns before Android has booted."""
        self._call("control", "launch")

    def restart(self) -> None:
        """Ask MuMu to restart the instance; returns before Android has booted."""
        self._call("control", "restart")

    def shutdown(self) -> None:
        """Ask MuMu to shut the instance down."""
        self._call("control", "shutdown")

    def settings(self, *keys: str) -> dict[str, str]:
        """Return the instance settings named ``keys``; readable while the instance is off."""
        output = self._call("setting", *[arg for key in keys for arg in ("-k", key)])
        try:
            data = json.loads(output)
        except ValueError as exc:
            raise EmulatorError(f"Unexpected output from MuMuManager setting: {output!r}") from exc
        if not isinstance(data, dict):
            raise EmulatorError(f"Unexpected output from MuMuManager setting: {output!r}")
        return {str(key): str(value) for key, value in data.items()}

    def change_settings(self, values: Mapping[str, str]) -> None:
        """Write instance settings; screen settings apply when the instance starts next."""
        self._call(
            "setting", *[arg for key, value in values.items() for arg in ("-k", key, "-val", value)]
        )

    def ensure_started(self, timeout: float) -> None:
        """Launch the instance unless running, then wait until Android has booted."""
        if self.is_started():
            logger.info("MuMu instance %d already running", self.index)
            return
        logger.info("Launching MuMu instance %d", self.index)
        started = self._clock()
        self.launch()
        while self._clock() - started < timeout:
            self._sleep(_POLL_INTERVAL)
            if self.is_started():
                logger.info("Android started after %.1f s", self._clock() - started)
                return
        raise EmulatorError(f"MuMu instance {self.index} did not finish booting in {timeout:.0f} s")

    def kill(
        self,
        find: Callable[[str], list[tuple[int, str]]] = processes.command_lines,
        stop: Callable[[int], None] = processes.stop,
    ) -> bool:
        """End the instance's ``MuMuNxDevice`` process; return whether one was found.

        MuMuManager is not asked: a frozen instance makes its commands hang (2026-11-19). The
        process is the one whose command line ends in ``--vm <name>-<index>``.
        """
        pattern = re.compile(rf"--vm\s+\S+-{self.index}\s*$")
        found = False
        for pid, command in find(DEVICE_PROCESS):
            if not pattern.search(command):
                continue
            found = True
            logger.warning("Ending MuMu instance %d's process %d", self.index, pid)
            try:
                stop(pid)
            except OSError as exc:
                logger.warning("Could not end process %d: %s", pid, exc)
        return found

    def wait_stopped(self, timeout: float) -> bool:
        """Return whether the instance's process ended within ``timeout`` seconds.

        A read that fails counts as still running: a frozen instance makes ``info`` hang.
        """
        started = self._clock()
        while True:
            try:
                if not self.is_process_started():
                    return True
            except EmulatorError as exc:
                logger.debug("MuMu instance %d state unknown: %s", self.index, exc)
            if self._clock() - started >= timeout:
                return False
            self._sleep(_STOP_POLL_INTERVAL)

    def _call(self, command: str, *args: str) -> str:
        """Run a MuMuManager command, tried up to ``attempts`` times while it fails."""
        if not self.manager.is_file():
            raise MuMuNotFoundError(
                f"MuMuManager not found at {self.manager}; set 'mumu_manager' in config.toml, "
                "or leave it empty to skip starting the emulator"
            )
        argv = [str(self.manager), command, "-v", str(self.index), *args]
        for attempt in range(1, self.attempts + 1):
            try:
                return self._call_once(command, argv)
            except EmulatorError as exc:
                if attempt == self.attempts:
                    raise
                logger.warning(
                    "%s; trying again in %g s (%d of %d)",
                    exc,
                    RETRY_DELAY,
                    attempt + 1,
                    self.attempts,
                )
                self._sleep(RETRY_DELAY)
        raise AssertionError("unreachable: the last attempt returns or raises")

    def _call_once(self, command: str, argv: list[str]) -> str:
        try:
            result = self._run(argv)
        except (OSError, subprocess.SubprocessError) as exc:
            raise EmulatorError(f"MuMuManager {command} failed: {exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise EmulatorError(f"MuMuManager {command} exited with {result.returncode}: {detail}")
        return result.stdout
