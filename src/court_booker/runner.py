"""One booking run: connect to the device and book every configured slot."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from court_booker.clock import NtpClock, wait_until
from court_booker.config import DAYS_AHEAD, Config
from court_booker.credentials import Login
from court_booker.errors import (
    BookingError,
    BookingRejectedError,
    DeviceNotRespondingError,
    QuotaFullError,
    SlotUnavailableError,
)
from court_booker.events import EventKind, Reporter
from court_booker.flow import Booker, log_screen
from court_booker.ready import Supervisor, setup_deadline

logger = logging.getLogger(__name__)

LOCATE_AHEAD = timedelta(seconds=2)
"""How long before the start time the utilities entry is read again."""
WARM_UP_REPAIRS_END = timedelta(seconds=15)
"""How long before the start time repairs at the warm-up stop: the app made ready again takes
6-10 s (a restart and its home screen, 2026-11-19), and the list is read again 2 s before."""
OPENING_MARGIN = timedelta(seconds=0.1)
"""How long after the start time a timed run taps first.

The app answered an early tap with a notice on 2026-10-19 (up to 0.76 s early). The
0.1 s margin reduces that risk, but a notice still appeared on 2026-10-20 with the PC
clock behind NTP. Which clock the app uses for opening hours remains unverified.
The 06:00 logs show where the tap fell ("Start reached"); retaps handle a notice."""
SCREENS_KEPT = 30
"""Screenshots of failures kept in the log folder's ``screens``; each holds personal data, so
they stay on this PC and the oldest go."""
QUOTA_SKIPPED = "Skipped: the booking quota is used up"
"""Why a round after the app's quota notice failed without running."""


@dataclass
class RoundResult:
    """Outcome of one booking round."""

    slot: str
    ok: bool
    detail: str
    seconds: float
    court: str | None = None
    """The court the confirmation page named, if the round read it: the one booked, which
    once differed from the configured one."""


def explained(error: BaseException) -> bool:
    """Tell whether the app itself said why a round failed: then no screenshot is needed.

    A full slot or court and a notice of the app (the quota, a slot taken first) are in the log
    word for word; anything else stopped the run on a screen the log may not explain.
    """
    return isinstance(error, (SlotUnavailableError, BookingRejectedError))


def save_screen(device: Any, folder: Path | None, report: Reporter, mumu_index: int) -> None:
    """Save the screen as a PNG in ``folder``, keeping the newest :data:`SCREENS_KEPT`.

    Called only when a real run stopped on a failure the app did not explain, so a normal
    run never takes one. It costs about a second; a failure only logs, except a frozen
    emulator, which ends the run as such (the device's worker thread is stuck).
    """
    if folder is None:
        return
    path = folder / f"{datetime.now():%Y-%m-%d-%H%M%S}-mumu{mumu_index}.png"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        device.screenshot(str(path))
    except DeviceNotRespondingError:
        raise
    except Exception:  # a screenshot never costs the run
        logger.warning("Could not save the screen", exc_info=True)
        return
    logger.info("Saved the screen at the failure: %s", path)
    report(EventKind.SCREEN_SAVED, path=str(path))
    for old in sorted(folder.glob("*.png"))[:-SCREENS_KEPT]:
        old.unlink(missing_ok=True)


def log_last_screen(booker: Booker) -> None:
    """Log every element of the last screen ``booker`` read, to diagnose a failure.

    A failure that happens only at the opening time, or only on the last days of a
    month, can then be fixed from the log of a single run.
    """
    log_screen(booker.last_screen, "Last screen read")


def run_booking(
    device: Any,
    config: Config,
    *,
    dry_run: bool = False,
    start: datetime | None = None,
    clock: NtpClock | None = None,
    results: list[RoundResult] | None = None,
    report: Reporter | None = None,
    login_for: Callable[[], Login | None] | None = None,
    screens: Path | None = None,
    supervisor: Supervisor | None = None,
    on_booker: Callable[[Booker], None] | None = None,
) -> list[RoundResult]:
    """Get ready, wait for ``start`` if given, then book every configured slot.

    ``supervisor`` brings MuMu, ADB, the driver and the app up, repairing what fails until a
    minute before the warm-up (:mod:`court_booker.ready`); without one, ``device`` is driven
    as it is and only the app is repaired. The rounds drive ``supervisor.device``.
    The wait goes by ``clock`` (the PC clock if not given), measured again at the warm-up,
    and ends :data:`OPENING_MARGIN` after ``start``. The target date is
    :data:`~court_booker.config.DAYS_AHEAD` after the start date. After the app's quota
    notice the slots left fail unrun. Results are appended to ``results`` as rounds finish,
    so an interrupted caller still sees them; progress goes to ``report`` as events.
    ``login_for`` reads the saved login, typed in if the app logged out.

    A real run that stops on a failure the app did not explain saves the screen in
    ``screens`` (:func:`save_screen`): when the app is not made ready, or when such a failure
    ends the last round. One in an earlier round saves none, to keep the next round on time;
    a dry run and a frozen emulator save none.

    ``on_booker`` gets the booker before anything runs, for a caller that goes on with
    the app after the rounds (:mod:`court_booker.tickets`).
    """
    results = [] if results is None else results
    report = Reporter() if report is None else report
    clock = NtpClock() if clock is None else clock
    if supervisor is None:
        supervisor = Supervisor(config, report=report, device=device, now=clock.now)
    device = supervisor.device
    booker = Booker(device, config, report, login_for=login_for)
    if on_booker is not None:
        on_booker(booker)
    shots = None if dry_run else screens
    deadline = setup_deadline(start, config.warm_up_seconds, clock.now())
    try:
        supervisor.prepare(booker, deadline)
        report(EventKind.APP_READY)
        if start is not None:
            report(EventKind.WAITING, until=start.isoformat(timespec="seconds"))
            # Wait on the home screen, checked every minute until the deadline, then load the
            # utilities list shortly before the start, so the app has just talked to its
            # server when the first tap comes.
            supervisor.watch(booker, deadline, lambda moment: wait_until(moment, clock.now))
            wait_until(start - timedelta(seconds=config.warm_up_seconds), clock.now)
            # A fresh answer leaves the counter only the warm-up to drift, and the log shows
            # how far Windows set the PC clock since the first one.
            clock.measure()
            # A failure here is repaired as one while getting ready (the 2026-11-17 popup, a
            # driver lost after the last check), with time left for the read before the start.
            supervisor.run_step(booker, booker.locate_entry, start - WARM_UP_REPAIRS_END)
            wait_until(start - LOCATE_AHEAD, clock.now)
            booker.locate_entry()
            wait_until(start + OPENING_MARGIN, clock.now)
            logger.info("Start reached at %s", clock.reading())
    except Exception as exc:  # the caller logs the error itself
        log_last_screen(booker)
        if not isinstance(exc, DeviceNotRespondingError) and getattr(device, "connected", True):
            save_screen(device, shots, report, config.mumu_index)
        raise
    target = (start or datetime.now()).date() + timedelta(days=DAYS_AHEAD)
    logger.info(
        "Target date %s, slots: %s%s",
        target.isoformat(),
        ", ".join(config.slots),
        " (dry run)" if dry_run else "",
    )
    report(
        EventKind.BOOKING_STARTED,
        date=target.isoformat(),
        sport=config.sport,
        court=config.court,
        slots=list(config.slots),
        dry_run=dry_run,
    )

    for index, slot in enumerate(config.slots, start=1):
        logger.info("Round %d/%d: %s", index, len(config.slots), slot)
        report(EventKind.SLOT_STARTED, slot=slot, round=index, rounds=len(config.slots))
        started = time.perf_counter()
        commands = booker.commands
        shown: dict[str, Any] = {}
        frozen: DeviceNotRespondingError | None = None
        quota_full = False
        unexplained = False
        try:
            shown = booker.book(slot, target, dry_run=dry_run).event_data()
        except DeviceNotRespondingError as exc:
            # A frozen emulator answers no later round either: end the run after this one.
            log_last_screen(booker)
            ok, detail, frozen = False, str(exc), exc
        except BookingError as exc:
            logger.error("%s", exc)
            log_last_screen(booker)
            ok, detail = False, str(exc)
            quota_full = isinstance(exc, QuotaFullError)
            unexplained = not explained(exc)
        except Exception as exc:  # keep later rounds running on device glitches
            logger.exception("Unexpected error")
            log_last_screen(booker)
            ok, detail = False, repr(exc)
            unexplained = True
        else:
            ok, detail = True, "dry run passed" if dry_run else "booked"
        if unexplained and shots is not None:
            if index == len(config.slots):
                save_screen(device, shots, report, config.mumu_index)
            else:
                logger.info("Screen not saved: the next round goes first (the log holds it)")
        seconds = time.perf_counter() - started
        used = booker.commands - commands
        results.append(RoundResult(slot, ok, detail, seconds, shown.get("shown_court")))
        logger.debug("Round %d used %d device commands", index, used)
        if ok:
            report(
                EventKind.SLOT_BOOKED,
                slot=slot,
                seconds=round(seconds, 1),
                commands=used,
                dry_run=dry_run,
                **shown,
            )
        else:
            report(
                EventKind.SLOT_FAILED,
                slot=slot,
                reason=detail,
                seconds=round(seconds, 1),
                commands=used,
            )
        if frozen is not None:
            raise frozen
        if quota_full:
            skip_rounds(config.slots[index:], results, report)
            break
    return results


def skip_rounds(slots: list[str], results: list[RoundResult], report: Reporter) -> None:
    """Fail ``slots`` without running them: the app's quota notice would refuse each one."""
    if slots:
        logger.warning("Booking quota used up; skipping %s", ", ".join(slots))
    for slot in slots:
        results.append(RoundResult(slot, False, QUOTA_SKIPPED, 0.0))
        report(EventKind.SLOT_FAILED, slot=slot, reason=QUOTA_SKIPPED, seconds=0.0, commands=0)
