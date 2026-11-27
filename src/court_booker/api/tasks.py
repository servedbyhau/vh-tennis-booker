"""Tasks the app starts on one machine: a ticket's cancel and a quota read, each in its own
process (``court-booker cancel``, ``court-booker quota``), a new machine's MuMu instance
(``court-booker new-machine``), the Vinhomes app installed from a file on every instance
(``court-booker install-app``), and opening a machine's MuMu.

One task at a time, and none while a run or a dry run goes on: each drives a machine's app, and
the run lock of the machine it uses may not be held yet when it starts.
"""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time, where Python 3.9 has no `X | None`, so `Optional` is used instead.
import logging
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from court_booker.api.context import AppContext, Context
from court_booker.api.customers import Book, MumuIndex
from court_booker.api.errors import NoMachineError
from court_booker.app_install import MAX_FILE_BYTES
from court_booker.device_setup import find_mumu_manager
from court_booker.emulator import MuMu
from court_booker.engine import engine_command
from court_booker.errors import EmulatorError, LockHeldError, MuMuNotFoundError, RequestError
from court_booker.lock import RunLock, check_quiet_time
from court_booker.new_machine import NoRoomError, check_room

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["tasks"])

KINDS = ("cancel", "quota", "machine", "app")
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
    for kind in ("dry_run", "booking"):  # the runs the app starts (api/runs.py)
        process = getattr(request.app.state, kind, None)
        if process is not None and process.poll() is None:
            raise LockHeldError(f"Another run is in progress: {kind} (pid {process.pid})")
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


@router.post("/machines/{mumu_index}/open", status_code=204, response_class=Response)
def open_machine(context: Context, request: Request, mumu_index: MumuIndex) -> Response:
    """Launch the MuMu instance of machine ``mumu_index``, or show its window if it runs.

    Refused as :func:`start` refuses (a run starts and shuts MuMu itself), and (503 ``device``)
    when MuMuManager is not found or fails.
    """
    config = context.config()
    check_quiet_time(datetime.now(), config.wake_at, config.start_at, "MuMu opening")
    with starting:
        check_free(request, context, mumu_index)
        manager = find_mumu_manager(config.mumu_manager)
        if manager is None:
            raise MuMuNotFoundError("MuMuManager not found")
        mumu = MuMu(manager, mumu_index)
        try:
            if mumu.is_process_started():
                mumu.show_window()
            else:
                mumu.launch()
        except EmulatorError:
            logger.warning("MuMu %d not opened", mumu_index, exc_info=True)
            raise
    return Response(status_code=204)


class Room(BaseModel):
    """Whether this PC has the RAM and the disk for one more MuMu instance."""

    room: bool
    reason: Optional[str] = None
    """Why not: ``ram`` or ``disk``."""


@router.get("/machines/room", response_model=Room)
def read_room(context: Context) -> Room:
    """Tell whether a new machine's MuMu instance would fit, as making one checks first
    (2 GB of RAM an instance besides 4 GB for Windows, the disk of a copy); room is assumed
    where MuMu cannot be asked, as making one would tell then."""
    config = context.config()
    manager = find_mumu_manager(config.mumu_manager)
    if manager is None:
        return Room(room=True)
    try:
        check_room(manager, config.mumu_index)
    except NoRoomError as exc:
        return Room(room=False, reason=exc.reason)
    except EmulatorError:
        return Room(room=True)
    return Room(room=True)


@router.get("/machines/new", response_model=TaskState)
def read_new_machine(request: Request) -> TaskState:
    """Show the machine's MuMu instance made last from the app: going on, or how it ended
    (0 made, 1 not, 2 refused, 3 MuMu failed, 5 a run went on)."""
    return state_of(last(request, "machine"))


@router.post("/machines/new", status_code=202, response_model=TaskState)
def start_new_machine(context: Context, request: Request) -> TaskState:
    """Make another machine's MuMu instance, a copy of the first machine's set up to book
    (``court-booker new-machine``, a minute or a few).

    Refused (409 ``no_room``) when the PC lacks the RAM or the disk for it, (503 ``device``)
    without MuMuManager, and as :func:`start` refuses; the first machine is the one it uses.
    """
    config = context.config()
    check_quiet_time(datetime.now(), config.wake_at, config.start_at, "new machine")
    manager = find_mumu_manager(config.mumu_manager)
    if manager is None:
        raise MuMuNotFoundError("MuMuManager not found")
    check_room(manager, config.mumu_index)
    return start(request, context, "machine", config.mumu_index, ["new-machine"])


UPLOAD_NAME = "app-upload"
"""Where the app's file waits in the data folder; the install deletes it once done."""
APP_FILE = {
    "required": True,
    "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
}


@router.get("/app/install", response_model=TaskState)
def read_app_install(request: Request) -> TaskState:
    """Show the Vinhomes app install started last from the app: going on, or how it ended
    (0 installed everywhere, 1 not on some instance, 2 not the Vinhomes app or refused,
    3 MuMu or adb failed, 5 a run went on)."""
    return state_of(last(request, "app"))


@router.post(
    "/app/install",
    status_code=202,
    response_model=TaskState,
    openapi_extra={"requestBody": APP_FILE},
)
async def start_app_install(context: Context, request: Request) -> TaskState:
    """Install the Vinhomes app from the file sent (an .apk, .xapk or .apks, as it is) on every
    MuMu instance, once its signature is the app's (``court-booker install-app``, a minute a
    machine or so).

    Refused (400 ``bad_request``) for an empty file or one past 1 GB, and as :func:`start`
    refuses, before the file is read; a file not signed by the app ends the task with 2.
    """
    config = context.config()
    check_quiet_time(datetime.now(), config.wake_at, config.start_at, "app install")
    check_free(request, context, config.mumu_index)
    upload = context.data.root / UPLOAD_NAME
    upload.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with upload.open("wb") as file:
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                break
            file.write(chunk)
    if not 0 < size <= MAX_FILE_BYTES:
        upload.unlink(missing_ok=True)
        raise RequestError(f"The app's file is empty or past 1 GB ({size} bytes)")
    argv = ["install-app", str(upload), "--remove-file"]
    return start(request, context, "app", config.mumu_index, argv)
