"""Tasks the app starts on one machine: a ticket's cancel and a quota read, each in its own
process (``court-booker cancel``, ``court-booker quota``).

One task at a time, and none while a run or a dry run goes on: each drives a machine's app, and
the run lock of the machine it uses may not be held yet when it starts.
"""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time, where Python 3.9 has no `X | None`, so `Optional` is used instead.
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from court_booker.api.context import AppContext, Context
from court_booker.api.customers import Book, MumuIndex
from court_booker.api.errors import NoMachineError
from court_booker.engine import engine_command
from court_booker.errors import LockHeldError
from court_booker.lock import RunLock, check_quiet_time

router = APIRouter(prefix="/api", tags=["tasks"])

KINDS = ("cancel", "quota")
"""The tasks that run in a process of their own, each kept in ``app.state`` under its kind."""

# Keep a console window from opening for the task.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
starting = threading.Lock()
"""Two requests at once must not both find the machines free and both start a task."""


@dataclass
class Task:
    """A task the backend started last, of one kind."""

    kind: str
    machine: int
    started_at: str
    process: "subprocess.Popen[bytes]"
    code: Optional[str] = None
    """The ticket a cancel is of."""


class TaskState(BaseModel):
    """The task of one kind started last from the app, going on or over; all empty before any."""

    code: Optional[str] = None
    """The ticket a cancel is of."""
    machine: Optional[int] = None
    started_at: Optional[str] = None
    running: bool = False
    exit_code: Optional[int] = None
    """The command's: 0 done, 1 not, 2 around the scheduled run, 3 or 4 the machine or its app
    not ready, 5 a run on the machine."""


def state_of(task: Optional[Task]) -> TaskState:
    """Return what ``task`` tells of itself."""
    if task is None:
        return TaskState()
    code = task.process.poll()
    return TaskState(
        code=task.code,
        machine=task.machine,
        started_at=task.started_at,
        running=code is None,
        exit_code=code,
    )


def last(request: Request, kind: str) -> Optional[Task]:
    """Return the task of ``kind`` started last."""
    return getattr(request.app.state, kind, None)


def running_task(request: Request) -> Optional[Task]:
    """Return the task still running, if one is."""
    for kind in KINDS:
        task = last(request, kind)
        if task is not None and task.process.poll() is None:
            return task
    return None


def check_free(request: Request, context: AppContext, machine: int) -> None:
    """Raise :class:`LockHeldError` while a run, a dry run or a task may use ``machine``."""
    task = running_task(request)
    if task is not None:
        raise LockHeldError(f"Another task is in progress: {task.kind} on MuMu {task.machine}")
    dry_run = getattr(request.app.state, "dry_run", None)
    if dry_run is not None and dry_run.poll() is None:
        raise LockHeldError(f"Another run is in progress: dry run (pid {dry_run.pid})")
    for path in (context.data.lock, context.data.instance_lock(machine)):
        holder = RunLock(path).running_holder()
        if holder is not None:
            raise LockHeldError(f"Another run is in progress: {holder.describe()}")


def launch(config_path: Path, argv: list[str]) -> "subprocess.Popen[bytes]":
    """Start the engine with ``argv`` in its own process, as the dry run is started."""
    return subprocess.Popen(
        [*engine_command(), *argv, "--config", str(config_path)],
        cwd=config_path.parent,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_NO_WINDOW,
    )


launcher = launch
"""Starts a task's process; tests replace it."""


def instance_argv(context: AppContext, machine: int) -> list[str]:
    """Return ``--instance N`` for a machine past the first, nothing for the first."""
    return [] if machine == context.config().mumu_index else ["--instance", str(machine)]


def start(
    request: Request,
    context: AppContext,
    kind: str,
    machine: int,
    argv: list[str],
    code: Optional[str] = None,
) -> TaskState:
    """Start the engine's ``argv`` as the task ``kind`` on ``machine``, once nothing uses it.

    Refused (400 ``bad_request``) from the wake time to 5 minutes after the start, and (409
    ``lock_held``) while a run, a dry run or another task goes on. The task checks again itself.
    """
    config = context.config()
    now = datetime.now()
    check_quiet_time(now, config.wake_at, config.start_at, kind)
    with starting:
        check_free(request, context, machine)
        process = launcher(context.config_path.resolve(), [*argv, *instance_argv(context, machine)])
        task = Task(kind, machine, now.isoformat(timespec="seconds"), process, code)
        setattr(request.app.state, kind, task)
    return state_of(task)


def machine_has_account(book: Book, machine: int) -> bool:
    """Tell whether one of the customers' accounts is attached to ``machine``."""
    return any(
        account.device == machine for customer in book.customers() for account in customer.accounts
    )


@router.get("/machines/quota", response_model=TaskState)
def read_quota_task(request: Request) -> TaskState:
    """Show the quota read started last: on which machine, and how it ended."""
    return state_of(last(request, "quota"))


@router.post("/machines/{mumu_index}/quota", status_code=202, response_model=TaskState)
def start_quota(context: Context, book: Book, request: Request, mumu_index: MumuIndex) -> TaskState:
    """Read the quota of the account on machine ``mumu_index`` again, in its app (about a minute).

    Refused for a machine without a chosen account (409 ``no_machine``), as the reading would be
    of no customer, and as :func:`start` refuses.
    """
    if not machine_has_account(book, mumu_index):
        raise NoMachineError(f"MuMu {mumu_index} books with no chosen account")
    return start(request, context, "quota", mumu_index, ["quota"])
