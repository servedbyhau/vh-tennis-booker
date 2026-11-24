"""Cancel a ticket in the Vinhomes app, as a resident does: ``court-booker cancel <code>``.

From any screen: the history page (as :class:`~court_booker.tickets.TicketReader` opens it),
the ticket's card, its page, "Hủy tiện ích" at its top right, then "Xác nhận" in the dialog
that asks "Bạn chắc chắn muốn hủy tiện ích?". The app says "Huỷ tiện ích thành công" and shows
the history page again, its card still with the old status until the page is opened again
(field notes, "History page"). So a ticket counts as cancelled only once a page opened after
the tap shows it so; the history then takes its status, and the quota of its utility is read
again (a cancelled ticket counts no more).

It is a task on the machine's app (:mod:`court_booker.machine_task`): no run in the history,
its steps in the activity log, the machine's run lock held, refused around the scheduled run.
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from court_booker.config import Config
from court_booker.errors import (
    DeviceNotRespondingError,
    NavigationError,
    TicketNotCancelledError,
)
from court_booker.events import EventKind, Reporter
from court_booker.flow import Booker
from court_booker.history import History
from court_booker.machine_task import account_of, run_task, task_parser
from court_booker.quota import CANCEL, read_quota, settled_page, sport_of
from court_booker.screen import Match, Node, Screen
from court_booker.tickets import CANCELLED, Ticket, TicketReader, cards, ticket_details

logger = logging.getLogger(__name__)

CANCEL_SECONDS = 60.0
"""Longest time from the history page to the ticket shown cancelled."""
_CARD_PAGES = 3
"""Swipes down the history page to find the card: a ticket still to be played was booked at
most two days before, so it is among the newest."""
_DIALOG_WAIT = 5.0
_GONE_WAIT = 10.0
"""How long the question may stay after "Xác nhận"."""
_CHECKS = 3
"""Times the history page is opened again to see the ticket cancelled."""
_CHECK_PAUSE = 1.0


def cancel_ticket(
    booker: Booker,
    code: str,
    deadline: float,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> list[Ticket]:
    """Cancel ticket ``code`` before ``deadline`` on ``clock``; return the cards read after.

    Those are the cards of a history page opened after the cancel, which show it cancelled.
    One cancelled already is left as it is. Raises :class:`NavigationError` when a screen of
    the way does not show (nothing was confirmed then) and :class:`TicketNotCancelledError`
    when the ticket still reads as before after "Xác nhận".
    """
    reader = TicketReader(booker, Path(), deadline, clock, sleep)
    ticket, card, listed = _find(booker, reader, code, clock, sleep)
    if ticket.status == CANCELLED:
        logger.info("Ticket %s is cancelled already", code)
        return listed
    labels = booker.labels

    def left() -> float:
        return max(0.0, deadline - clock())

    booker.tap(card)
    shown = booker.wait_for(
        lambda screen: _cancel_button(screen, code, labels.cancel_ticket), left()
    )
    if shown is None:
        raise NavigationError(f"Ticket {code} did not show its cancel button")
    booker.tap(shown[0])
    asked = booker.wait_for(
        lambda screen: _confirm_button(screen, labels.cancel_question, labels.confirm),
        min(_DIALOG_WAIT, left()),
    )
    if asked is None:
        raise NavigationError("The question before cancelling did not show")
    booker.tap(asked[0])
    logger.info("Cancelling ticket %s confirmed", code)
    gone = booker.wait_for(
        lambda screen: (
            None if _confirm_button(screen, labels.cancel_question, labels.confirm) else True
        ),
        min(_GONE_WAIT, left()),
    )
    if gone is None:
        raise TicketNotCancelledError("The question before cancelling stayed after the confirm")
    status = ticket.status_text
    for _ in range(_CHECKS):
        try:
            now, _, listed = _find(booker, reader, code, clock, sleep)
        except NavigationError as exc:  # read again, as the page may not have loaded
            logger.warning("%s", exc)
        else:
            status = now.status_text
            if now.status == CANCELLED:
                logger.info("Ticket %s cancelled: %s", code, status)
                return listed
        if clock() >= deadline:
            break
        sleep(_CHECK_PAUSE)
    raise TicketNotCancelledError(f"Ticket {code} still reads {status!r} after the cancel")


def _find(
    booker: Booker,
    reader: TicketReader,
    code: str,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> tuple[Ticket, Node, list[Ticket]]:
    """Return ticket ``code`` and its card from the history page, with the cards read."""
    screen = reader.open_history()
    for _ in range(_CARD_PAGES + 1):
        listed = cards(screen)
        for ticket, node in listed:
            if ticket.code == code:
                return ticket, node, [shown for shown, _ in listed]
        if clock() >= reader.deadline:
            break
        booker.scroll_page(screen)
        screen = settled_page(booker, clock, sleep)
    raise NavigationError(f"Ticket {code} is not among the newest on the history page")


def _cancel_button(screen: Screen, code: str, label: str) -> Node | None:
    """Return the cancel button if ``screen`` is the page of ticket ``code``."""
    if ticket_details(screen, code) is None:
        return None
    return screen.find(Match(desc=label, clickable=True))


def _confirm_button(screen: Screen, question: str, confirm: str) -> Node | None:
    """Return the dialog's confirm button if ``screen`` asks whether to cancel."""
    if screen.find(Match(contains=question)) is None:
        return None
    return screen.find(Match(desc=confirm, clickable=True))


def build_parser() -> argparse.ArgumentParser:
    parser = task_parser(
        "court-booker cancel",
        "Cancel a ticket in the Vinhomes app of a MuMu instance, then read its quota.",
    )
    parser.add_argument("code", help="the ticket's booking code (Mã đặt)")
    return parser


def main(argv: list[str]) -> int:
    """Run ``court-booker cancel``; the exit codes are a run's (0 cancelled, 1 not)."""
    args = build_parser().parse_args(argv)

    def work(booker: Booker, config: Config, history: History | None, report: Reporter) -> int:
        listed = cancel_ticket(booker, args.code, time.monotonic() + CANCEL_SECONDS)
        ticket = next(shown for shown in listed if shown.code == args.code)
        report(
            EventKind.TICKET_CANCELLED,
            code=ticket.code,
            utility=ticket.utility,
            court=ticket.court,
            play_date=ticket.play_date,
            slot=ticket.slot,
        )
        if history is not None:
            history.save_tickets(config.mumu_index, listed, {}, datetime.now())
        try:
            read_quota(
                booker,
                date.fromisoformat(ticket.play_date),
                CANCEL,
                report,
                utility=ticket.utility,
                sport=sport_of(ticket.utility),
                account_id=account_of(history),
            )
        except DeviceNotRespondingError:
            raise
        except Exception as exc:  # the ticket is cancelled: this only logs
            logger.warning("Quota not read after the cancel: %s", exc)
        return 0

    return run_task(args, "cancel", work, EventKind.TICKET_NOT_CANCELLED, {"code": args.code})
