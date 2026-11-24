"""Cancel a ticket in the Vinhomes app, as a resident does: ``court-booker cancel <code>``.

From any screen: the history page (as :class:`~court_booker.tickets.TicketReader` opens it),
the ticket's card, its page, "Hủy tiện ích" at its top right, then "Xác nhận" in the dialog
that asks "Bạn chắc chắn muốn hủy tiện ích?". The app says "Huỷ tiện ích thành công" and shows
the history page again, its card still with the old status until the page is opened again
(field notes, "History page"). So a ticket counts as cancelled only once a page opened after
the tap shows it so; the history then takes its status, and the quota of its utility is read
again (a cancelled ticket counts no more).

It is a task of its own, like auto setup: no run in the history, its steps in the activity
log, the run lock of its machine held, refused in the scheduled run's quiet time.
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from court_booker import credentials
from court_booker.app_language import ENGLISH_SPORTS
from court_booker.config import SPORTS, Config, load_config
from court_booker.errors import (
    CourtBookerError,
    DeviceNotRespondingError,
    NavigationError,
    TicketNotCancelledError,
)
from court_booker.events import EventKind, LogSink, MultiSink, Reporter
from court_booker.flow import Booker
from court_booker.history import History, close_history, open_history
from court_booker.lock import RunLock, check_quiet_time
from court_booker.logging_setup import add_file_handler, configure_logging
from court_booker.paths import data_folder
from court_booker.quota import CANCEL, read_quota, settled_page
from court_booker.ready import AUTO_DRIVER, Supervisor
from court_booker.screen import Match, Node, Screen
from court_booker.tickets import CANCELLED, Ticket, TicketReader, cards, ticket_details

logger = logging.getLogger(__name__)

CANCEL_SECONDS = 60.0
"""Longest time from the history page to the ticket shown cancelled."""
PREPARE_SECONDS = 180.0
"""Longest time to bring MuMu, the driver and the app up, repairs included."""
_CARD_PAGES = 3
"""Swipes down the history page to find the card: a ticket still to be played was booked at
most two days before, so it is among the newest."""
_DIALOG_WAIT = 5.0
_GONE_WAIT = 10.0
"""How long the question may stay after "Xác nhận"."""
_CHECKS = 3
"""Times the history page is opened again to see the ticket cancelled."""
_CHECK_PAUSE = 1.0


def sport_of(utility: str) -> str | None:
    """Return the sport whose tile is ``utility``, in either language; ``None`` if none."""
    for names in (SPORTS, ENGLISH_SPORTS):
        for sport, name in names.items():
            if name.casefold() == utility.casefold():
                return sport
    return None


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


def machine_config(config: Config, index: int | None) -> Config:
    """Return the settings of MuMu instance ``index``: its ``[[instances]]`` entry's, if any.

    A machine switched off in the Setup still has its account and tickets, so it is driven
    with the first machine's settings then; a cancel needs no sport or court.
    """
    if index is None or index == config.mumu_index:
        return config
    from court_booker.cli import select_instance  # the command line imports this module

    if any(table.get("mumu_index") == index for table in config.instances):
        return select_instance(config, index)
    return replace(config, mumu_index=index, instances=[])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="court-booker cancel",
        description="Cancel a ticket in the Vinhomes app of a MuMu instance, then read its quota.",
    )
    parser.add_argument("code", help="the ticket's booking code (Mã đặt)")
    parser.add_argument(
        "--config", default="config.toml", help="config file (default: %(default)s)"
    )
    parser.add_argument(
        "--instance",
        type=int,
        metavar="N",
        help="the MuMu instance whose account holds the ticket (default: the config's first)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug output")
    return parser


def main(argv: list[str]) -> int:
    """Run ``court-booker cancel``; the exit codes are a run's (0 cancelled, 1 not)."""
    from court_booker import cli  # its helpers; it imports this module only when asked

    args = build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose)
    report = Reporter(LogSink())
    history: History | None = None
    frozen = False
    try:
        config = machine_config(load_config(args.config), args.instance)
        if config.log_dir:
            folder = Path(args.config).resolve().parent / config.log_dir
            suffix = "" if args.instance is None else f"-mumu{config.mumu_index}"
            logger.debug("Logging to %s", add_file_handler(folder, suffix=suffix))
        history = open_history(data_folder().database)
        if history is not None:
            report = Reporter(MultiSink(LogSink(), history))
        check_quiet_time(datetime.now(), config.wake_at, config.start_at, "cancel")
        code = _cancel(args, config, history, report)
    except KeyboardInterrupt:
        logger.warning("Interrupted")
        code = cli.EXIT_INTERRUPTED
    except CourtBookerError as exc:
        logger.error("%s", exc)
        report(EventKind.TICKET_NOT_CANCELLED, code=args.code, reason=str(exc))
        code = cli.exit_code(exc)
        frozen = isinstance(exc, DeviceNotRespondingError)
    except Exception as exc:  # the task must still log and report
        logger.exception("Unexpected error")
        report(EventKind.TICKET_NOT_CANCELLED, code=args.code, reason=repr(exc))
        code = cli.EXIT_ROUND_FAILED
    if history is not None:
        close_history(history)
    if frozen:  # a thread still waits on the device and could hold the exit
        cli.end_process(code)
    return code


def _cancel(
    args: argparse.Namespace, config: Config, history: History | None, report: Reporter
) -> int:
    """Take the machine's lock, bring the app up, cancel the ticket and read the quota."""
    from court_booker import cli

    folder = data_folder()
    path = folder.lock if args.instance is None else folder.instance_lock(config.mumu_index)
    lock = RunLock(path, report)
    lock.acquire("cancel")
    supervisor: Supervisor | None = None
    started_here = False
    try:
        if history is not None:
            cli.note_holder(history, config.mumu_index)
        supervisor = Supervisor(config, AUTO_DRIVER, report)
        started_here = _mumu_off(config)
        booker = Booker(
            supervisor.device,
            config,
            report,
            login_for=lambda: credentials.default_store().read(config.mumu_index),
            account_seen=lambda: (
                None if history is None else history.last_account(config.mumu_index)
            ),
        )
        supervisor.prepare(booker, datetime.now() + timedelta(seconds=PREPARE_SECONDS))
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
        holder = None if history is None else history.holder
        try:
            read_quota(
                booker,
                date.fromisoformat(ticket.play_date),
                CANCEL,
                report,
                utility=ticket.utility,
                sport=sport_of(ticket.utility),
                account_id=None if holder is None else holder.account_id,
            )
        except DeviceNotRespondingError:
            raise
        except Exception as exc:  # the ticket is cancelled: this only logs
            logger.warning("Quota not read after the cancel: %s", exc)
        return cli.EXIT_OK
    finally:
        hung = supervisor is not None and supervisor.device.hung
        if supervisor is not None and supervisor.device.connected and not hung:
            cli.close_device(supervisor.device)
        # MuMu goes back as it was; MuMuManager does not shut a frozen instance down.
        if started_here and not hung:
            cli.close_emulator(config)
        lock.release()


def _mumu_off(config: Config) -> bool:
    """Return whether the machine's MuMu is off, so this task closes it again once done."""
    if not config.mumu_manager:
        return False
    from court_booker.emulator import MuMu
    from court_booker.ready import find_manager

    try:
        return not MuMu(find_manager(config.mumu_manager), config.mumu_index).is_process_started()
    except CourtBookerError:
        return False
