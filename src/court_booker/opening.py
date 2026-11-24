"""The clocks at the opening, for the log: what the app's 06:00 is likely checked against.

The app answered taps a moment after 06:00 by NTP time with "chỉ nhận đăng ký từ 06:00" on
about half the days since 2026-11-04, each costing 0.5-1 s, while the PC clock ran behind NTP
time. The app most likely checks the opening against Android's clock (field notes, "Dialogs"),
which follows the PC clock. Before changing when the first tap comes, a few days of these
facts are gathered: how far the PC clock and Android's are from NTP time, when the first tap
came and when the calendar opened, and how many taps the notice took.

Nothing here costs the booking: Android's clock is read through adb during the warm-up and
again once the rounds are over, and during the rounds only the time of two steps is noted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from court_booker.clock import format_time
from court_booker.events import EventKind, Reporter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceClock:
    """Android's clock against NTP time, from one read through adb."""

    offset: float
    """Seconds Android's clock is ahead of NTP time (behind when negative)."""
    spread: float
    """Half the read's round trip: the offset is off by this much at most."""


CLOCK_READS = 3
"""Reads of Android's clock each time: the one of the shortest round trip is kept, as an adb
call takes 0.07-0.14 s and its offset is off by half of that at most."""


def read_device_clock(
    read: Callable[[], float], now: Callable[[], datetime], reads: int = CLOCK_READS
) -> DeviceClock | None:
    """Return Android's clock against ``now`` (NTP time) from ``read`` (its epoch seconds).

    The read of the shortest round trip of ``reads``; ``None`` when none succeeds: it only goes
    to the log, so it never stops the run.
    """
    best: DeviceClock | None = None
    for _ in range(reads):
        try:
            before = now()
            android = read()
            after = now()
        except Exception as exc:  # the log only: the run goes on without it
            logger.debug("Android's clock not read: %s", exc)
            continue
        middle = before + (after - before) / 2
        offset = (datetime.fromtimestamp(android) - middle).total_seconds()
        found = DeviceClock(round(offset, 3), round((after - before).total_seconds() / 2, 3))
        if best is None or found.spread < best.spread:
            best = found
    return best


class OpeningWatch:
    """Note when the first round's calendar opened, passing every event on to ``report``.

    It stands for the booker's reporter during the first round; noting a time costs a few
    microseconds, nothing more is done there.
    """

    def __init__(self, report: Reporter, now: Callable[[], datetime]) -> None:
        self.report = report
        self.now = now
        self.opened: datetime | None = None
        self.attempt: int | None = None

    def __call__(self, kind: EventKind, **data: Any) -> None:
        if kind is EventKind.CALENDAR_OPENED and self.opened is None:
            self.opened = self.now()
            attempt = data.get("attempt")
            self.attempt = attempt if isinstance(attempt, int) else None
        self.report(kind, **data)


@dataclass(frozen=True)
class Opening:
    """What the clocks and the first round told at the opening."""

    start: datetime
    """The start time, by NTP time."""
    pc_offset: float | None
    """Seconds the PC clock was behind NTP time at the warm-up's answer."""
    before: DeviceClock | None
    """Android's clock at the warm-up."""
    after: DeviceClock | None
    """Android's clock once the rounds were over."""
    first_tap: datetime | None
    """When the first round began, by NTP time: its first tap follows within milliseconds."""
    opened: datetime | None
    """When the first round's calendar opened, by NTP time."""
    attempt: int | None
    """The attempt that opened it: the attempts before met the notice or a calendar without
    the day."""

    def event_data(self) -> dict[str, Any]:
        """Return the fields of an :attr:`~EventKind.OPENING_MEASURED` event."""

        def at(moment: datetime | None) -> str | None:
            return None if moment is None else moment.isoformat(timespec="milliseconds")

        def clock(read: DeviceClock | None) -> dict[str, float] | None:
            return None if read is None else {"offset": read.offset, "spread": read.spread}

        return {
            "start": at(self.start),
            "pc_offset": self.pc_offset,
            "device_before": clock(self.before),
            "device_after": clock(self.after),
            "first_tap": at(self.first_tap),
            "device_first_tap": at(self.device_time(self.first_tap)),
            "calendar_opened": at(self.opened),
            "seconds_to_calendar": self.seconds_to_calendar(),
            "attempt": self.attempt,
        }

    def device_time(self, moment: datetime | None) -> datetime | None:
        """Return ``moment`` by Android's clock, as read at the warm-up."""
        if moment is None or self.before is None:
            return None
        return moment + timedelta(seconds=self.before.offset)

    def seconds_to_calendar(self) -> float | None:
        """Return the seconds from the first round's start to its calendar."""
        if self.first_tap is None or self.opened is None:
            return None
        return round((self.opened - self.first_tap).total_seconds(), 3)

    def describe(self) -> str:
        """Return the log line of the opening."""

        def clock(read: DeviceClock | None) -> str:
            return "not read" if read is None else f"{read.offset:+.3f} s (±{read.spread:.3f})"

        def when(moment: datetime | None) -> str:
            return "-" if moment is None else format_time(moment)

        pc = "not known" if self.pc_offset is None else f"{-self.pc_offset:+.3f} s"
        device = self.device_time(self.first_tap)
        return (
            f"Opening: PC clock {pc} from NTP, Android {clock(self.before)} at the warm-up and"
            f" {clock(self.after)} after the rounds; first tap at {when(self.first_tap)} NTP"
            f" ({when(device)} on Android), calendar at {when(self.opened)} NTP"
            f" after {self.seconds_to_calendar()} s, attempt {self.attempt}"
        )
