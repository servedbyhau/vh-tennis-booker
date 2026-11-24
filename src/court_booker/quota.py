"""What is left of the account's booking quota, read from the app's history page.

The app takes :data:`MONTH_LIMIT` bookings of a utility a month and :data:`DAY_LIMIT` a day,
counted by the day of play. Every ticket counts but one cancelled ("Đã huỷ"), whoever
cancelled it: the resident, or the management the morning after a rainy day (proven from 486
tickets on 2026-11-23, ``docs/field-notes.md``). The bookings the app made are not counted
here, as residents book and cancel by hand too: the history page is the one truth.

Read while getting ready (no booking can be made from 21:00 to 06:00, so what it reads then is
what the app checks at the opening) and again after the tickets. Reading only reports: it
never changes what a run books, and a failure only logs.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from court_booker.app_language import ENGLISH_SPORTS
from court_booker.config import DAYS_AHEAD, SPORTS
from court_booker.events import EventKind, Reporter
from court_booker.flow import Booker
from court_booker.screen import Screen
from court_booker.tickets import CANCELLED, Ticket, TicketReader, cards

logger = logging.getLogger(__name__)

MONTH_LIMIT = 8
DAY_LIMIT = 2
"""The app's quota of one utility, per month and per day of play."""
QUOTA_SECONDS = 60.0
"""How long a read may take; a month took 5-9 s on each of three machines (2026-11-23)."""
BEFORE = "before"
AFTER = "after"
CANCEL = "cancel"
"""Read once a ticket was cancelled (:mod:`court_booker.cancel`)."""
ASKED = "asked"
"""Read when the user asked for it (:mod:`court_booker.quota_command`)."""
"""When a read was made: while getting ready, or after the tickets."""

_PAGES = 25
"""Swipes at most: a month holds 18 cards at most, about three to a swipe."""
_SETTLE = 0.25
_SETTLE_TIMEOUT = 3.0
"""The page is read every :data:`_SETTLE` s until two reads place its cards alike."""
_LOAD_WAIT = 1.5
"""Pause before reading once more a page that a swipe brought nothing new on: the list loads
as it is scrolled."""
_ENDED_AFTER = 2
"""Swipes in a row that bring no card, for the list to count as ended."""


@dataclass(frozen=True)
class Quota:
    """What an account used of a utility's quota, as its history page showed it."""

    utility: str
    month: str
    """``YYYY-MM``, the month of play."""
    used: int
    """Tickets of the month, all but cancelled ones."""
    play_date: str
    """ISO date of the day the run books for."""
    day_used: int
    """Tickets of that day, all but cancelled ones."""

    @property
    def left(self) -> int:
        """Return the slots the app still takes on the day of play."""
        return max(0, min(MONTH_LIMIT - self.used, DAY_LIMIT - self.day_used))

    def event_data(self, moment: str, slots: int | None = None) -> dict[str, Any]:
        """Return the fields of a :attr:`~EventKind.QUOTA_READ` event; ``slots`` the run wants."""
        data: dict[str, Any] = {
            "moment": moment,
            "utility": self.utility,
            "month": self.month,
            "used": self.used,
            "month_limit": MONTH_LIMIT,
            "play_date": self.play_date,
            "day_used": self.day_used,
            "day_limit": DAY_LIMIT,
            "left": self.left,
        }
        if slots is not None:
            data["slots"] = slots
        return data


def sport_of(utility: str) -> str | None:
    """Return the sport whose tile is ``utility``, in either language; ``None`` if none."""
    for names in (SPORTS, ENGLISH_SPORTS):
        for sport, name in names.items():
            if name.casefold() == utility.casefold():
                return sport
    return None


def counted(ticket: Ticket, utility: str) -> bool:
    """Return whether ``ticket`` takes a booking of ``utility``'s quota."""
    return ticket.status != CANCELLED and ticket.utility.casefold() == utility.casefold()


def count(tickets: Sequence[Ticket], utility: str, play_date: date) -> Quota:
    """Return what ``tickets`` use of ``utility``'s quota for ``play_date``."""
    month = play_date.isoformat()[:7]
    day = play_date.isoformat()
    mine = [ticket for ticket in tickets if counted(ticket, utility)]
    return Quota(
        utility=utility,
        month=month,
        used=sum(ticket.play_date[:7] == month for ticket in mine),
        play_date=day,
        day_used=sum(ticket.play_date == day for ticket in mine),
    )


def next_short(quota: Quota, slots: int) -> int | None:
    """Return what the run a day later has left, if fewer than the ``slots`` it books.

    For ``quota`` read after the tickets: nothing can be booked yet for the next day of play,
    so only the month counts; ``None`` also when that day is in another month, whose quota
    is whole.
    """
    following = date.fromisoformat(quota.play_date) + timedelta(days=1)
    if following.isoformat()[:7] != quota.month:
        return None
    left = max(0, MONTH_LIMIT - quota.used)
    return left if left < slots else None


def first_booking_day(play_date: date) -> date:
    """Return the first day a ticket of ``play_date``'s month can have been booked on."""
    return play_date.replace(day=1) - timedelta(days=DAYS_AHEAD)


def read_back(
    booker: Booker,
    reader: TicketReader,
    since: date,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> list[Ticket] | None:
    """Return the tickets the history page lists down to those booked before ``since``.

    The page lists them in the order they were booked, newest first, and loads more as it is
    scrolled. It is read to its first card booked before ``since``, or to its end: a swipe
    that brought no card, then one more. ``None`` if neither came within the swipes and the
    time of ``reader``, since tickets left unread would show more of the quota left than there
    is.
    """
    oldest = since.isoformat()
    found: dict[str, Ticket] = {}
    screen = reader.open_history()
    idle = 0
    for _ in range(_PAGES + 1):
        listed = [ticket for ticket, _ in cards(screen)]
        new = [ticket for ticket in listed if ticket.code not in found]
        found.update((ticket.code, ticket) for ticket in listed)
        if any(t.created_at is not None and t.created_at[:10] < oldest for t in listed):
            return list(found.values())
        idle = 0 if new else idle + 1
        if idle >= _ENDED_AFTER:
            return list(found.values())
        if clock() >= reader.deadline:
            break
        if idle:
            sleep(_LOAD_WAIT)
        booker.scroll_page(screen)
        screen = settled_page(booker, clock, sleep)
    logger.warning("The history page was not read back to %s", oldest)
    return None


def settled_page(
    booker: Booker, clock: Callable[[], float], sleep: Callable[[float], None]
) -> Screen:
    """Read the page until two reads place its cards alike: a swipe goes on for a moment."""
    until = clock() + _SETTLE_TIMEOUT
    before = None
    while True:
        sleep(_SETTLE)
        screen = booker.snapshot()
        places = [(ticket.code, node.box) for ticket, node in cards(screen)]
        if places == before or clock() >= until:
            return screen
        before = places


def read_quotas(
    booker: Booker,
    play_date: date,
    moment: str,
    report: Reporter,
    account_id: str | None = None,
) -> list[Quota] | None:
    """Read the quota for ``play_date`` of every utility the account plays, in one read.

    That is the config's utility and each other one with a ticket in that month of play; each
    is reported as :func:`read_quota` does. ``None`` when the page was not read far enough.
    """
    reader = TicketReader(booker, Path(), time.monotonic() + QUOTA_SECONDS)
    tickets = read_back(booker, reader, first_booking_day(play_date))
    if tickets is None:
        return None
    month = play_date.isoformat()[:7]
    utilities = [booker.labels.utility]
    for ticket in tickets:
        known = {utility.casefold() for utility in utilities}
        if ticket.play_date[:7] == month and ticket.utility.casefold() not in known:
            utilities.append(ticket.utility)
    found = []
    for utility in utilities:
        quota = count(tickets, utility, play_date)
        logger.info("%s", describe(quota))
        data = quota.event_data(moment)
        if account_id is not None:
            data["account_id"] = account_id
        own = utility == booker.labels.utility
        sport = booker.config.sport if own else sport_of(utility)
        report(EventKind.QUOTA_READ, **data, sport=sport)
        found.append(quota)
    return found


def describe(quota: Quota, slots: int | None = None) -> str:
    """Return a log line that tells the quota read."""
    text = (
        f"Quota of {quota.utility}: {quota.used}/{MONTH_LIMIT} used in {quota.month},"
        f" {quota.day_used}/{DAY_LIMIT} on {quota.play_date}, {quota.left} slot(s) left"
    )
    if slots is not None and slots > quota.left:
        text += f", {slots} wanted: {slots - quota.left} short"
    return text


def read_quota(
    booker: Booker,
    play_date: date,
    moment: str,
    report: Reporter,
    slots: int | None = None,
    *,
    utility: str | None = None,
    sport: str | None = None,
    account_id: str | None = None,
) -> Quota | None:
    """Read what the account used of the quota for ``play_date`` and report it.

    Starts from any screen and leaves the history page shown, within :data:`QUOTA_SECONDS`.
    ``None`` when the page was not read far enough. Raises what the device raises.
    ``utility`` and ``sport`` are those of the config unless given; ``account_id`` goes into
    the event for a reading without a run, which knows whose account it is of.
    """
    reader = TicketReader(booker, Path(), time.monotonic() + QUOTA_SECONDS)
    tickets = read_back(booker, reader, first_booking_day(play_date))
    if tickets is None:
        return None
    quota = count(tickets, utility or booker.labels.utility, play_date)
    shown = describe(quota, slots)
    if slots is not None and slots > quota.left:
        logger.warning("%s", shown)
    else:
        logger.info("%s", shown)
    data = quota.event_data(moment, slots)
    if account_id is not None:
        data["account_id"] = account_id
    report(EventKind.QUOTA_READ, **data, sport=sport or booker.config.sport)
    return quota
