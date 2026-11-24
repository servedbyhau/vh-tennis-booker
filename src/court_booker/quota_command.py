"""Read an account's quota when asked: ``court-booker quota [--instance N]``.

The machine's app reads its history page once, back to the month of the next day it books
(today + 2), and each utility the account plays that month is reported, as a run reads it
(:func:`court_booker.quota.read_quotas`). It is a task on the machine's app
(:mod:`court_booker.machine_task`), as a cancel is: refused around the scheduled run and while
a run uses the machine.
"""

from __future__ import annotations

from datetime import date, timedelta

from court_booker.config import DAYS_AHEAD, Config
from court_booker.errors import NavigationError
from court_booker.events import EventKind, Reporter
from court_booker.flow import Booker
from court_booker.history import History
from court_booker.machine_task import account_of, run_task, task_parser
from court_booker.quota import ASKED, read_quotas


def main(argv: list[str]) -> int:
    """Run ``court-booker quota``; the exit codes are a run's (0 read, 1 not)."""
    args = task_parser(
        "court-booker quota",
        "Read what is left of the quota of a MuMu instance's account, in the Vinhomes app.",
    ).parse_args(argv)

    def work(booker: Booker, config: Config, history: History | None, report: Reporter) -> int:
        play_date = date.today() + timedelta(days=DAYS_AHEAD)
        read = read_quotas(booker, play_date, ASKED, report, account_of(history))
        if read is None:
            raise NavigationError("The history page was not read back far enough")
        return 0

    return run_task(args, "quota", work, EventKind.QUOTA_NOT_READ)
