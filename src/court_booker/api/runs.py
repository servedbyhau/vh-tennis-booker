"""Run routes: start a dry run, or a booking now, from the app."""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time.
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from court_booker.api.context import AppContext, Context
from court_booker.api.tasks import running_task
from court_booker.clock import parse_time
from court_booker.engine import engine_command
from court_booker.errors import LockHeldError
from court_booker.lock import RunLock, check_booking_hours, check_quiet_time

router = APIRouter(prefix="/api", tags=["runs"])

# Keep a console window from opening for the run.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_starting = threading.Lock()
"""Two requests at once must not both find no run and both start one."""


def launch(config_path: Path, argv: list[str]) -> "subprocess.Popen[bytes]":
    """Start ``court-booker`` with ``argv`` in its own process, as the scheduled task starts a
    run.

    The run then takes the exact code path of the 06:00 run, writes its own history and log
    file, and a crash in it cannot take the backend down.
    """
    return subprocess.Popen(
        [*engine_command(), *argv, "--config", str(config_path)],
        cwd=config_path.parent,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_NO_WINDOW,
    )


RUNS = ("dry_run", "booking")
"""Where the backend keeps the process of the run of each kind it started last."""


class DryRunStarted(BaseModel):
    """A run has started (a dry run, or a booking now); its steps show in the history as it
    goes."""

    pid: int
    started_at: str


@router.post("/runs/dry-run", status_code=202, response_model=DryRunStarted)
def start_dry_run(context: Context, request: Request) -> DryRunStarted:
    """Start a dry run of the saved settings; it stops before "Xác nhận".

    Refused (400 ``bad_request``) from the wake time to 5 minutes after the start time and
    (409 ``lock_held``) while a run holds the lock, or while the dry run or a task on a machine
    started last is still running (they may not hold the lock yet, or hold another machine's).
    The dry run checks again itself.
    """
    config = context.config()
    now = datetime.now()
    check_quiet_time(now, config.wake_at, config.start_at, "dry run")
    return start(context, request, "dry_run", ["--dry-run"], now)


@router.post("/runs/now", status_code=202, response_model=DryRunStarted)
def start_booking(context: Context, request: Request) -> DryRunStarted:
    """Book for real now, as by hand (``manual``): before the start time the run gets ready
    and books at it (``--at``), as the scheduled run would; from it, at once.

    For a morning the scheduled run missed (the PC did not wake) or one booked by hand. Refused
    (400 ``bad_request``) before the wake time and from 21:00, when the app is closed, and (409
    ``lock_held``) while a run holds the lock, or while a run or a task started last from the
    app is still running. Every machine books, whatever its days.
    """
    config = context.config()
    now = datetime.now()
    check_booking_hours(now, config.wake_at, "booking")
    start_at = datetime.combine(now.date(), parse_time(config.start_at, "start time"))
    argv = ["--at", config.start_at] if now < start_at else []
    return start(context, request, "booking", argv, now)


def started_run(request: Request) -> Optional[tuple[str, Any]]:
    """Return the kind and the process of the run started from the app still running."""
    for kind in RUNS:
        process = getattr(request.app.state, kind, None)
        if process is not None and process.poll() is None:
            return kind, process
    return None


def start(
    context: AppContext, request: Request, kind: str, argv: list[str], now: datetime
) -> DryRunStarted:
    """Start the run ``kind`` with ``argv`` once nothing else runs."""
    with _starting:
        last = started_run(request)
        if last is not None:
            raise LockHeldError(f"Another run is in progress: {last[0]} (pid {last[1].pid})")
        task = running_task(request)
        if task is not None:
            raise LockHeldError(f"Another task is in progress: {task.kind} on MuMu {task.machine}")
        holder = RunLock(context.data.lock).running_holder()
        if holder is not None:
            raise LockHeldError(f"Another run is in progress: {holder.describe()}")
        process = launch(context.config_path.resolve(), argv)
        setattr(request.app.state, kind, process)
    return DryRunStarted(pid=process.pid, started_at=now.isoformat(timespec="seconds"))
