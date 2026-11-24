"""A task on one machine's app, outside any run: ``court-booker cancel`` and ``court-booker quota``.

Each is a task of its own, like auto setup: no run in the history, its steps in the activity
log, refused in the scheduled run's quiet time, the machine's run lock held while it drives the
app. It brings MuMu, the driver and the app up as a run does (repairs included), checks the
account, does its work, then puts MuMu back as it was: shut again if the task started it.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from court_booker import credentials
from court_booker.config import Config, load_config
from court_booker.errors import CourtBookerError, DeviceNotRespondingError
from court_booker.events import EventKind, LogSink, MultiSink, Reporter
from court_booker.flow import Booker
from court_booker.history import History, close_history, open_history
from court_booker.lock import RunLock, check_quiet_time
from court_booker.logging_setup import add_file_handler, configure_logging
from court_booker.paths import data_folder
from court_booker.ready import AUTO_DRIVER, Supervisor

logger = logging.getLogger(__name__)

PREPARE_SECONDS = 180.0
"""Longest time to bring MuMu, the driver and the app up, repairs included."""

Work = Callable[[Booker, Config, "History | None", Reporter], int]
"""What a task does once the app is ready; returns the exit code."""


def machine_config(config: Config, index: int | None) -> Config:
    """Return the settings of MuMu instance ``index``: its ``[[instances]]`` entry's, if any.

    A machine switched off in the Setup still has its account and tickets, so it is driven
    with the first machine's settings then; a task on the app needs no court.
    """
    if index is None or index == config.mumu_index:
        return config
    from court_booker.cli import select_instance  # the command line imports this module

    if any(table.get("mumu_index") == index for table in config.instances):
        return select_instance(config, index)
    return replace(config, mumu_index=index, instances=[])


def task_parser(prog: str, description: str) -> argparse.ArgumentParser:
    """Return the parser of a task, with ``--config``, ``--instance`` and ``--verbose``."""
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument(
        "--config", default="config.toml", help="config file (default: %(default)s)"
    )
    parser.add_argument(
        "--instance",
        type=int,
        metavar="N",
        help="the MuMu instance whose app it uses (default: the config's first)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug output")
    return parser


def run_task(
    args: argparse.Namespace,
    task: str,
    work: Work,
    failed: EventKind,
    fields: dict[str, Any] | None = None,
) -> int:
    """Run ``work`` as ``task`` on the machine of ``args``; return the exit code.

    A failure is logged and reported as ``failed`` with ``fields`` and its reason; the exit
    codes are a run's (0 done, 1 not, 2 refused, 3 device, 4 app, 5 busy).
    """
    from court_booker import cli  # its helpers; it imports this module only when asked

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
        check_quiet_time(datetime.now(), config.wake_at, config.start_at, task)
        code = on_machine(args, config, history, report, task, work)
    except KeyboardInterrupt:
        logger.warning("Interrupted")
        code = cli.EXIT_INTERRUPTED
    except CourtBookerError as exc:
        logger.error("%s", exc)
        report(failed, **(fields or {}), reason=str(exc))
        code = cli.exit_code(exc)
        frozen = isinstance(exc, DeviceNotRespondingError)
    except Exception as exc:  # the task must still log and report
        logger.exception("Unexpected error")
        report(failed, **(fields or {}), reason=repr(exc))
        code = cli.EXIT_ROUND_FAILED
    if history is not None:
        close_history(history)
    if frozen:  # a thread still waits on the device and could hold the exit
        cli.end_process(code)
    return code


def on_machine(
    args: argparse.Namespace,
    config: Config,
    history: History | None,
    report: Reporter,
    task: str,
    work: Work,
) -> int:
    """Take the machine's lock, bring its app up, run ``work``, and put MuMu back as it was."""
    from court_booker import cli

    folder = data_folder()
    path = folder.lock if args.instance is None else folder.instance_lock(config.mumu_index)
    lock = RunLock(path, report)
    lock.acquire(task)
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
        return work(booker, config, history, report)
    finally:
        hung = supervisor is not None and supervisor.device.hung
        if supervisor is not None and supervisor.device.connected and not hung:
            cli.close_device(supervisor.device)
        # MuMu goes back as it was; MuMuManager does not shut a frozen instance down.
        if started_here and not hung:
            cli.close_emulator(config)
        lock.release()


def account_of(history: History | None) -> str | None:
    """Return the id of the account the task's machine books with, if one is chosen."""
    holder = None if history is None else history.holder
    return None if holder is None else holder.account_id


def _mumu_off(config: Config) -> bool:
    """Return whether the machine's MuMu is off, so the task closes it again once done."""
    if not config.mumu_manager:
        return False
    from court_booker.emulator import MuMu
    from court_booker.ready import find_manager

    try:
        return not MuMu(find_manager(config.mumu_manager), config.mumu_index).is_process_started()
    except CourtBookerError:
        return False
