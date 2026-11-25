"""Make another machine's MuMu instance: ``court-booker new-machine``.

MuMu Player makes an instance a copy of another (``MuMuManager clone``), its own phone to the
app (its own IMEI and model) with the app and its login copied: the first machine's instance is
copied, and the account the new machine is given logs in at its first run, as a changed account
does. The copy then gets the settings a run needs (:data:`MACHINE_SETTINGS`).

A PC has room for a machine while it keeps :data:`WINDOWS_GB` for Windows besides each
instance's :data:`MACHINE_GB`, and its disk holds another copy of the first instance's. It is a
task of the app's, as a cancel is: refused around the scheduled run and while a run goes on (the
first machine's run lock is held), and the first instance is shut while it is copied, then
started again if it ran.
"""

from __future__ import annotations

import argparse
import ctypes
import logging
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Callable

from court_booker.config import load_config
from court_booker.device_setup import SCREEN_SETTINGS
from court_booker.emulator import MUMU_TIMEOUT, MuMu, Run, instance_indexes, run_command
from court_booker.errors import CourtBookerError, EmulatorError, RequestError

logger = logging.getLogger(__name__)

MACHINE_GB = 2
"""RAM each instance is given; Android used 1.1-1.3 GB of it while booking (field notes)."""
WINDOWS_GB = 4
"""RAM left to Windows, MuMu's own processes and the app: 8 GB holds two instances."""
DISK_SPARE_BYTES = 2 * 1024**3
"""Free disk left besides the copy, which grows as its Android runs."""
MACHINE_SETTINGS = {
    **SCREEN_SETTINGS,
    "performance_mode": "custom",
    "performance_cpu.custom": "2",
    "performance_mem.custom": str(MACHINE_GB),
    "renderer_mode": "vk",
}
"""What a machine's instance runs with: the screen the flow reads, 2 cores (1 was too slow,
4 no faster), 2 GB, and the Vulkan renderer."""
CLONE_SECONDS = 900.0
"""Longest a copy may take: a 6.8 GB instance took under 30 s on 2026-11-25."""
POLL_SECONDS = 5.0
STABLE_READS = 3
"""Reads of the same disk size in a row that tell the copy is over."""
EMPTY_SECONDS = 90.0
"""How long a copy may keep an empty disk before it counts as failed."""
STOP_SECONDS = 60.0


def run_in_mumu(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run a MuMuManager command in its own folder: the copy writes a ``configs`` folder into
    the folder it is asked from (2026-11-25), which is then MuMu's own."""
    return run_command(args, timeout=MUMU_TIMEOUT, cwd=Path(args[0]).parent)


class NoRoomError(RequestError):
    """The PC has not the RAM or the disk for another instance."""


def total_ram_gb() -> float:
    """Return the PC's RAM in GB; 0 where it cannot be read (not Windows)."""
    if sys.platform != "win32":
        return 0.0

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("load", ctypes.c_ulong),
            ("total", ctypes.c_ulonglong),
            ("available", ctypes.c_ulonglong),
            ("total_page", ctypes.c_ulonglong),
            ("available_page", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
        return 0.0
    return status.total / 1024**3


def free_disk_bytes(path: Path) -> int:
    """Return the free space of the drive that holds ``path``."""
    return shutil.disk_usage(path.anchor or path).free


def check_room(
    manager: Path,
    source: int,
    ram_gb: Callable[[], float] = total_ram_gb,
    free_disk: Callable[[Path], int] = free_disk_bytes,
    run: Run = run_in_mumu,
) -> int:
    """Return how many instances there will be once one more is made; raises
    :class:`NoRoomError` when the RAM or the disk of the PC has no room for it.

    MuMu keeps its instances beside MuMuManager (``vms``), on the same drive.
    """
    count = len(instance_indexes(manager, run)) + 1
    ram = ram_gb()
    needed = count * MACHINE_GB + WINDOWS_GB
    if ram and ram < needed:
        raise NoRoomError(
            f"{count} MuMu instances need {needed} GB of RAM; this PC has {ram:.0f} GB"
        )
    size = int(MuMu(manager, source, run).info().get("disk_size_bytes") or 0)
    free = free_disk(manager)
    if free < size + DISK_SPARE_BYTES:
        raise NoRoomError(
            f"A copy of MuMu instance {source} needs {(size + DISK_SPARE_BYTES) / 1024**3:.0f} GB"
            f" of disk; {free / 1024**3:.0f} GB are free"
        )
    return count


def make_machine(
    manager: Path,
    source: int,
    run: Run = run_in_mumu,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Copy MuMu instance ``source`` into a new one with :data:`MACHINE_SETTINGS`; return its
    index. ``source`` is shut while copied and started again if it ran. A copy that does not
    come is deleted again."""
    original = MuMu(manager, source, run, clock, sleep)
    before = set(instance_indexes(manager, run))
    was_running = original.is_process_started()
    if was_running:
        logger.info("Shutting MuMu instance %d down to copy it", source)
        original.shutdown()
        if not original.wait_stopped(STOP_SECONDS):
            raise EmulatorError(f"MuMu instance {source} did not shut down to be copied")
    try:
        logger.info("Copying MuMu instance %d (a few minutes)", source)
        try:
            original.clone()
        except EmulatorError as exc:  # MuMu goes on copying after the command gave up
            logger.info("MuMu answered %s; waiting for the copy", exc)
        index = _wait_for_copy(original, before, run, sleep, clock)
        machine = original.sibling(index)
        machine.change_settings(MACHINE_SETTINGS)
        written = machine.settings(*MACHINE_SETTINGS)
        kept = {
            key: written.get(key)
            for key, value in MACHINE_SETTINGS.items()
            if not _same(written.get(key), value)
        }
        if kept:
            raise EmulatorError(f"MuMu instance {index} kept its settings: {kept}")
        logger.info("MuMu instance %d made from %d, set up for booking", index, source)
        return index
    finally:
        if was_running:
            try:
                original.launch()
            except CourtBookerError as exc:
                logger.warning("MuMu instance %d not started again: %s", source, exc)


def _wait_for_copy(
    original: MuMu,
    before: set[int],
    run: Run,
    sleep: Callable[[float], None],
    clock: Callable[[], float],
) -> int:
    """Return the instance MuMu made beside ``before`` once its disk stopped growing.

    A copy whose disk stays empty for :data:`EMPTY_SECONDS` failed (MuMu Player's own process
    took no command on 2026-11-25, until it was started again): it is deleted.
    """
    started = clock()
    sizes: list[int] = []
    index: int | None = None
    while clock() - started < CLONE_SECONDS:
        sleep(POLL_SECONDS)
        if index is None:
            made = sorted(set(instance_indexes(original.manager, run)) - before)
            if len(made) > 1:
                raise EmulatorError(f"MuMu made instances {made} in place of one")
            if not made:
                continue
            index = made[0]
        size = int(original.sibling(index).info().get("disk_size_bytes") or 0)
        sizes.append(size)
        if size == 0 and clock() - started >= EMPTY_SECONDS:
            _delete(original.sibling(index))
            raise EmulatorError(
                "MuMu made an empty instance: close MuMu Player (its window too) and try again"
            )
        if size > 0 and len(sizes) >= STABLE_READS and len(set(sizes[-STABLE_READS:])) == 1:
            return index
    if index is not None:
        _delete(original.sibling(index))
    raise EmulatorError(f"MuMu did not copy the instance in {CLONE_SECONDS:.0f} s")


def _delete(copy: MuMu) -> None:
    """Delete ``copy``, an instance that did not come out right; a refusal only logs."""
    try:
        copy.delete()
        logger.info("MuMu instance %d deleted", copy.index)
    except CourtBookerError as exc:
        logger.warning("MuMu instance %d not deleted: %s", copy.index, exc)


def _same(actual: str | None, wanted: str) -> bool:
    """Return whether a setting MuMu reads back is ``wanted`` (it writes 2 as 2.000000)."""
    if actual is None:
        return False
    try:
        return float(actual) == float(wanted)
    except ValueError:
        return actual == wanted


def main(argv: list[str]) -> int:
    """Run ``court-booker new-machine``; exit codes as a run's (0 made, 1 not, 2 refused,
    3 MuMu failed, 5 a run goes on)."""
    from court_booker import cli
    from court_booker.lock import RunLock, check_quiet_time
    from court_booker.logging_setup import add_file_handler, configure_logging
    from court_booker.paths import data_folder
    from court_booker.ready import find_manager

    parser = argparse.ArgumentParser(
        prog="court-booker new-machine",
        description="Make another MuMu instance, a copy of the first machine's, set up to book.",
    )
    parser.add_argument("--config", default="config.toml", help="config file")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug output")
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)
    lock: RunLock | None = None
    try:
        config = load_config(args.config)
        if config.log_dir:
            folder = Path(args.config).resolve().parent / config.log_dir
            add_file_handler(folder, suffix="-new-machine")
        check_quiet_time(datetime.now(), config.wake_at, config.start_at, "new machine")
        manager = find_manager(config.mumu_manager)
        lock = RunLock(data_folder().lock)
        lock.acquire("new_machine")
        check_room(manager, config.mumu_index)
        make_machine(manager, config.mumu_index)
        return cli.EXIT_OK
    except CourtBookerError as exc:
        logger.error("%s", exc)
        return cli.exit_code(exc)
    except Exception:  # the task must still log
        logger.exception("Unexpected error")
        return cli.EXIT_ROUND_FAILED
    finally:
        if lock is not None:
            lock.release()
