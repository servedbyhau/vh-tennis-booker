"""Find ``adb``, make sure its server runs, and connect to the emulator."""

from __future__ import annotations

import logging
import shutil
import socket
import subprocess
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Callable

from court_booker.emulator import Run, run_command
from court_booker.errors import (
    AdbNotFoundError,
    DeviceConnectionError,
    DeviceNotRespondingError,
    MultipleDevicesError,
    NoDeviceError,
)

logger = logging.getLogger(__name__)

Probe = Callable[[str, int], bool]
TimedRun = Callable[[Sequence[str], float], "subprocess.CompletedProcess[str]"]


def run_timed(args: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
    """Run ``args`` limited to ``timeout`` seconds; raises ``TimeoutExpired`` past it."""
    return run_command(args, timeout=timeout)


AUTO = "auto"
LOCALHOST = "127.0.0.1"
SERVER_PORT = 5037
# MuMu 6 (7555) and MuMu 12 instances 0-2, LDPlayer/BlueStacks, Nox.
EMULATOR_PORTS = (7555, 16384, 16416, 16448, 5555, 5557, 5559, 62001)
CONNECT_TIMEOUT = 30.0
_RETRY_INTERVAL = 1.0
_PROBE_TIMEOUT = 0.3
SCREENCAP_TIMEOUT = 20.0
"""Seconds a screenshot may take: about 1 s; a frozen MuMu never answers (2026-11-17)."""
PING_TIMEOUT = 10.0
"""Seconds the ping may take: it answered in 50-220 ms on a working instance (2026-11-19)."""
CLOCK_TIMEOUT = 5.0
"""Seconds a read of Android's clock may take; it is only logged."""
INSTALL_TIMEOUT = 300.0
"""Seconds an app install may take: the Vinhomes app's 175 MB took 16 s (2026-11-26)."""
PING_COMMAND = ("am", "get-current-user")
"""What the ping asks Android: a call to its system server, which answers with the user id.
An ``echo`` is not enough: on 2026-11-19 a hung Android answered ``echo`` in 0.5 s while
``am`` and ``pm`` hung, and the driver could not start."""
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def port_open(host: str, port: int) -> bool:
    """Return whether something accepts TCP connections on ``host:port``."""
    try:
        with socket.create_connection((host, port), timeout=_PROBE_TIMEOUT):
            return True
    except OSError:
        return False


def find_adb(
    adb_path: str = "",
    extra_dirs: Iterable[Path] = (),
    which: Callable[[str], str | None] = shutil.which,
) -> Path:
    """Return the adb executable: ``adb_path``, else ``PATH``, else one in ``extra_dirs``."""
    if adb_path:
        path = Path(adb_path)
        if path.is_file():
            return path
        raise AdbNotFoundError(f"adb_path {adb_path!r} in config.toml does not exist")
    found = which("adb")
    if found:
        return Path(found)
    for directory in extra_dirs:
        for name in ("adb.exe", "adb"):
            if (directory / name).is_file():
                return directory / name
    raise AdbNotFoundError(
        "adb not found; install Google platform-tools and add it to PATH, "
        "or set 'adb_path' in config.toml"
    )


class Adb:
    """Thin wrapper over the adb command line."""

    def __init__(
        self,
        path: Path,
        run: Run = run_command,
        probe: Probe = port_open,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        timed_run: TimedRun = run_timed,
    ) -> None:
        self.path = path
        self._run = run
        self._timed_run = timed_run
        self._probe = probe
        self._clock = clock
        self._sleep = sleep

    def ensure_server(self) -> None:
        """Reuse a running adb server, or start one."""
        if self._probe(LOCALHOST, SERVER_PORT):
            logger.debug("Reusing the adb server on port %d", SERVER_PORT)
            return
        logger.info("Starting the adb server")
        self._call("start-server")

    def devices(self) -> list[str]:
        """Return the serials of devices that are online."""
        serials = []
        for line in self._call("devices").splitlines():
            serial, _, state = line.partition("\t")
            if state.strip() == "device":
                serials.append(serial.strip())
        return serials

    def connect(self, serial: str) -> bool:
        """Run ``adb connect`` and return whether it reported success."""
        output = self._call("connect", serial)
        # Success prints "connected to" or "already connected to"; failures do not.
        return "connected to" in output

    def disconnect(self, serial: str) -> None:
        """Drop the connection to ``serial`` alone; other devices on the server keep theirs."""
        self._call("disconnect", serial)

    def connect_until(self, serial: str, timeout: float = CONNECT_TIMEOUT) -> str:
        """Connect ``serial``, retrying while the device is still starting."""
        deadline = self._clock() + timeout
        while True:
            if serial in self.devices():
                return serial
            if ":" in serial and self.connect(serial) and serial in self.devices():
                logger.info("Connected to %s", serial)
                return serial
            if self._clock() >= deadline:
                raise DeviceConnectionError(f"Could not connect to {serial} in {timeout:.0f} s")
            self._sleep(_RETRY_INTERVAL)

    def shell(self, serial: str, *args: str) -> str:
        """Run ``adb -s serial shell args`` and return its output."""
        return self._call("-s", serial, "shell", *args)

    def ping(self, serial: str, timeout: float = PING_TIMEOUT) -> None:
        """Check that Android on ``serial`` answers, its system server included.

        Raises :class:`DeviceNotRespondingError` when it gives no answer in ``timeout``, as a
        frozen emulator or a hung Android does, and :class:`DeviceConnectionError` when adb
        fails at once, as for a device offline or gone.
        """
        argv = [str(self.path), "-s", serial, "shell", *PING_COMMAND]
        try:
            result = self._timed_run(argv, timeout)
        except subprocess.TimeoutExpired as exc:
            raise DeviceNotRespondingError(
                f"Android on {serial} did not answer adb within {timeout:g} s"
            ) from exc
        except OSError as exc:
            raise DeviceConnectionError(f"adb shell failed: {exc}") from exc
        if not result.stdout.strip().isdigit():
            detail = (result.stderr or result.stdout).strip() or f"exit {result.returncode}"
            raise DeviceConnectionError(f"adb shell on {serial} failed: {detail}")

    def device_time(self, serial: str, timeout: float = CLOCK_TIMEOUT) -> float:
        """Return Android's clock on ``serial``, in seconds since the epoch, to the microsecond.

        Raises :class:`DeviceConnectionError` when adb fails or answers what is not a time.
        """
        argv = [str(self.path), "-s", serial, "shell", "date", "+%s.%N"]
        try:
            result = self._timed_run(argv, timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            raise DeviceConnectionError(f"adb shell date failed: {exc}") from exc
        try:
            return float(result.stdout.strip())
        except ValueError as exc:
            raise DeviceConnectionError(
                f"Unexpected answer of adb shell date: {result.stdout!r}"
            ) from exc

    def forward(self, serial: str, remote: str) -> int:
        """Return a local TCP port forwarded to ``remote`` on ``serial``, reusing one if set."""
        for line in self._call("forward", "--list").splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[0] == serial and parts[2] == remote:
                kind, _, port = parts[1].partition(":")
                if kind == "tcp" and port.isdigit():
                    return int(port)
        output = self._call("-s", serial, "forward", "tcp:0", remote).strip()
        if not output.isdigit():
            raise DeviceConnectionError(f"adb forward to {remote} failed: {output or 'no port'}")
        return int(output)

    def screencap(self, serial: str) -> bytes:
        """Return the screen of ``serial`` as PNG bytes (``adb exec-out screencap -p``)."""
        try:
            result = subprocess.run(
                [str(self.path), "-s", serial, "exec-out", "screencap", "-p"],
                capture_output=True,
                timeout=SCREENCAP_TIMEOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise DeviceConnectionError(f"adb screencap failed: {exc}") from exc
        if not result.stdout.startswith(PNG_SIGNATURE):
            raise DeviceConnectionError("adb screencap gave no PNG")
        return result.stdout

    def forward_remove(self, serial: str, port: int) -> None:
        """Drop the forward of local TCP ``port``."""
        self._call("-s", serial, "forward", "--remove", f"tcp:{port}")

    def install(self, serial: str, apk: Path) -> str:
        """Install or update ``apk`` and return what adb printed, errors included."""
        try:
            result = self._run([str(self.path), "-s", serial, "install", "-r", str(apk)])
        except (OSError, subprocess.SubprocessError) as exc:
            raise DeviceConnectionError(f"adb install failed: {exc}") from exc
        return result.stdout + result.stderr

    def install_all(self, serial: str, apks: Sequence[Path]) -> str:
        """Install or update an app from its APKs (the base and its splits, or one APK), keeping
        its data, and return what adb printed, errors included."""
        command = "install-multiple" if len(apks) > 1 else "install"
        argv = [str(self.path), "-s", serial, command, "-r", *map(str, apks)]
        try:
            result = self._timed_run(argv, INSTALL_TIMEOUT)
        except (OSError, subprocess.SubprocessError) as exc:
            raise DeviceConnectionError(f"adb {command} failed: {exc}") from exc
        return result.stdout + result.stderr

    def discover(self, ports: Sequence[int] = EMULATOR_PORTS) -> list[str]:
        """Return online devices, connecting the first open emulator port if none is."""
        serials = self.devices()
        if serials:
            return serials
        for port in ports:
            if not self._probe(LOCALHOST, port):
                continue
            serial = f"{LOCALHOST}:{port}"
            if self.connect(serial):
                logger.info("Found emulator at %s", serial)
                break
        return self.devices()

    def _call(self, *args: str) -> str:
        try:
            result = self._run([str(self.path), *args])
        except (OSError, subprocess.SubprocessError) as exc:
            raise DeviceConnectionError(f"adb {args[0]} failed: {exc}") from exc
        return result.stdout


def resolve_device(
    adb: Adb, device: str, preferred: str | None = None, timeout: float = CONNECT_TIMEOUT
) -> str:
    """Return the serial to drive.

    An explicit ``device`` is connected alone. ``auto`` uses ``preferred`` (the
    serial reported by the emulator) when known, else scans for a single device. A
    connection is tried for ``timeout`` seconds.
    """
    adb.ensure_server()
    if device != AUTO:
        return adb.connect_until(device, timeout)
    if preferred:
        return adb.connect_until(preferred, timeout)
    serials = adb.discover()
    if not serials:
        raise NoDeviceError("No emulator found; start it or set 'device' in config.toml")
    # MuMu also shows up as "emulator-5554" next to its host:port serial; prefer the latter.
    networked = [serial for serial in serials if ":" in serial]
    if len(networked) == 1:
        return networked[0]
    if len(serials) > 1:
        raise MultipleDevicesError(serials)
    return serials[0]
