"""One booking run: connect to the device and book every configured slot."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

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

    if config.mumu_manager:
        MuMu(Path(config.mumu_manager), config.mumu_index).ensure_started(config.boot_timeout)

    logger.info("Connecting to %s", config.device)
    try:
        return uiautomator2.connect(config.device)
    except Exception as exc:  # uiautomator2 raises several unrelated types
        raise DeviceConnectionError(f"Could not connect to {config.device}: {exc}") from exc


def run_booking(
    device: Any,
    config: Config,
    *,
    dry_run: bool = False,
    results: list[RoundResult] | None = None,
) -> list[RoundResult]:
    """Book every slot in ``config.slots``, one round each, and return the results.

    Results are appended to ``results`` as rounds finish, so a caller that is
    interrupted still sees the rounds already done.
    """
    results = [] if results is None else results
    booker = Booker(device, config)

    if device.app_current().get("package") != config.package:
        logger.info("Launching %s", config.package)
        device.app_start(config.package)
        device(**booker.home).wait(timeout=config.timeout * 2)

    target = date.today() + timedelta(days=config.days_ahead)
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
