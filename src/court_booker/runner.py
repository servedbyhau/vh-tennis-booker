"""One booking run: connect to the device and book every configured slot."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from court_booker.adb import Adb, find_adb, resolve_device
from court_booker.clock import wait_until
from court_booker.config import Config
from court_booker.emulator import MuMu
from court_booker.errors import BookingError, DeviceConnectionError
from court_booker.flow import Booker

logger = logging.getLogger(__name__)


@dataclass
class RoundResult:
    """Outcome of one booking round."""

    slot: str
    ok: bool
    detail: str
    seconds: float


def connect_device(config: Config) -> Any:
    """Start the emulator if configured and return a uiautomator2 device."""
    import uiautomator2  # deferred so tests do not require the dependency

    preferred = None
    extra_dirs = []
    if config.mumu_manager:
        mumu = MuMu(Path(config.mumu_manager), config.mumu_index)
        mumu.ensure_started(config.boot_timeout)
        preferred = mumu.adb_serial()
        extra_dirs.append(mumu.manager.parent)

    adb = Adb(find_adb(config.adb_path, extra_dirs))
    serial = resolve_device(adb, config.device, preferred)
    logger.info("Connecting to %s", serial)
    try:
        return uiautomator2.connect(serial)
    except Exception as exc:  # uiautomator2 raises several unrelated types
        raise DeviceConnectionError(f"Could not connect to {serial}: {exc}") from exc


def run_booking(
    device: Any,
    config: Config,
    *,
    dry_run: bool = False,
    start: datetime | None = None,
    offset: float = 0.0,
    results: list[RoundResult] | None = None,
) -> list[RoundResult]:
    """Prepare the app, wait for ``start`` if given, then book every configured slot.

    ``offset`` corrects the local clock (see :func:`clock.ntp_offset`). The target
    date is ``days_ahead`` after the start date. Results are appended to
    ``results`` as rounds finish, so an interrupted caller still sees them.
    """
    results = [] if results is None else results
    booker = Booker(device, config)
    booker.prepare()

    if start is not None:
        wait_until(start, offset)
    target = (start or datetime.now()).date() + timedelta(days=config.days_ahead)
    logger.info(
        "Target date %s, slots: %s%s",
        target.isoformat(),
        ", ".join(config.slots),
        " (dry run)" if dry_run else "",
    )

    for index, slot in enumerate(config.slots, start=1):
        logger.info("Round %d/%d: %s", index, len(config.slots), slot)
        started = time.perf_counter()
        try:
            booker.book(slot, target, dry_run=dry_run)
        except BookingError as exc:
            logger.error("%s", exc)
            results.append(RoundResult(slot, False, str(exc), time.perf_counter() - started))
        except Exception as exc:  # keep later rounds running on device glitches
            logger.exception("Unexpected error")
            results.append(RoundResult(slot, False, repr(exc), time.perf_counter() - started))
        else:
            detail = "dry run passed" if dry_run else "booked"
            results.append(RoundResult(slot, True, detail, time.perf_counter() - started))
    return results
