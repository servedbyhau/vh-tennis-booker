"""Ticket routes: the accounts' tickets as the runs last read them, their pictures, and the
cancel of one in the app (``court-booker cancel``, in its own process)."""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time, where Python 3.9 has no `X | None`, so `Optional` is used instead.
import subprocess
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Query, Request
from fastapi import Path as PathParameter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from court_booker import history_read
from court_booker.api.context import Context
from court_booker.api.customers import Book
from court_booker.api.errors import NoMachineError, NotFoundError, TicketCancelledError
from court_booker.api.history import HistoryDb
from court_booker.customers import CustomerBook
from court_booker.engine import engine_command
from court_booker.errors import LockHeldError
from court_booker.lock import RunLock, check_quiet_time

router = APIRouter(prefix="/api", tags=["tickets"])

MAX_TICKETS = 2000
"""The most tickets one request may ask for."""


class Ticket(BaseModel):
    """One ticket of an account, as the app's history page last showed it."""

    code: str
    """The app's booking code."""
    device: int
    """The MuMu instance whose account holds it."""
    customer: Optional[str]
    """Whose account holds it; empty if no run that read it had a chosen one."""
    account: Optional[str]
    """The account's name, else its phone number with the middle hidden."""
    court: str
    play_date: str
    slot: str
    status: Literal["registered", "processing", "cancelled", "other"]
    status_text: str
    """The status in the app's own words, for one not known here (``other``)."""
    created_at: Optional[str]
    """When it was booked, to the minute."""
    seen_at: str
    """When a run last read it: a status changed in the app since is not known."""
    has_photo: bool
    machine: Optional[int]
    """The MuMu instance that can cancel it now: the one its account is attached to, or the
    one that read it when no chosen account did; empty when its account is on no machine."""


Code = Annotated[str, PathParameter(pattern=r"^\d{1,20}$")]

# Keep a console window from opening for the cancel.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_starting = threading.Lock()
"""Two requests at once must not both find no cancel going on and both start one."""


def attached(book: CustomerBook) -> dict[str, int]:
    """Return the machine each account is attached to, by the account's id."""
    return {
        account.id: account.device
        for customer in book.customers()
        for account in customer.accounts
        if account.device is not None
    }


def machine_of(row: Mapping[str, Any], machines: Mapping[str, int]) -> Optional[int]:
    """Return the machine that can cancel the ticket of ``row`` (see :attr:`Ticket.machine`)."""
    account = row.get("account_id")
    return row["device"] if account is None else machines.get(account)


def photo_path(folder: Path, name: Optional[str]) -> Optional[Path]:
    """Return the picture ``name`` in ``folder`` if it is there; old ones are deleted."""
    path = None if name is None else folder / Path(name).name
    return path if path is not None and path.is_file() else None


@router.get("/tickets", response_model=list[Ticket])
def list_tickets(
    context: Context,
    db: HistoryDb,
    book: Book,
    since: Annotated[Optional[str], Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_TICKETS)] = history_read.DEFAULT_TICKETS,
) -> list[dict[str, Any]]:
    """List every machine's tickets, the latest day of play first, by slot within a day.

    ``since`` keeps the tickets played that day or later.
    """
    folder = context.data.tickets
    machines = attached(book)
    return [
        {
            **row,
            "has_photo": photo_path(folder, row["photo"]) is not None,
            "machine": machine_of(row, machines),
        }
        for row in history_read.list_tickets(db, since=since, limit=limit)
    ]


@router.get(
    "/tickets/{code}/photo",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}, "description": "The ticket's picture"}},
)
def ticket_photo(
    context: Context,
    db: HistoryDb,
    code: Code,
) -> FileResponse:
    """Answer with the picture of a ticket, down to its directions link."""
    path = photo_path(context.data.tickets, history_read.ticket_photo(db, code))
    if path is None:
        raise NotFoundError(f"No picture of ticket {code}")
    # Checked each time: a later run may have taken it again.
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-cache"})


@dataclass
class Cancelling:
    """The cancel the backend started last."""

    code: str
    machine: int
    started_at: str
    process: "subprocess.Popen[bytes]"


class CancelState(BaseModel):
    """The cancel started last from the app, going on or over; all empty before any."""

    code: Optional[str] = None
    machine: Optional[int] = None
    started_at: Optional[str] = None
    running: bool = False
    exit_code: Optional[int] = None
    """``court-booker cancel``'s: 0 cancelled, 1 not, 2 around the scheduled run, 3 or 4 the
    machine or its app not ready, 5 a run on the machine."""


def launch_cancel(
    config_path: Path, code: str, instance: Optional[int]
) -> "subprocess.Popen[bytes]":
    """Start ``court-booker cancel`` in its own process, as the dry run is started."""
    argv = [*engine_command(), "cancel", code, "--config", str(config_path)]
    if instance is not None:
        argv += ["--instance", str(instance)]
    return subprocess.Popen(
        argv,
        cwd=config_path.parent,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_NO_WINDOW,
    )


def cancel_state(last: Optional[Cancelling]) -> CancelState:
    """Return what ``last`` tells of the cancel started last."""
    if last is None:
        return CancelState()
    code = last.process.poll()
    return CancelState(
        code=last.code,
        machine=last.machine,
        started_at=last.started_at,
        running=code is None,
        exit_code=code,
    )


def cancel_running(request: Request) -> bool:
    """Tell whether the cancel the backend started last still runs."""
    return cancel_state(getattr(request.app.state, "cancel", None)).running


@router.get("/tickets/cancel", response_model=CancelState)
def read_cancel(request: Request) -> CancelState:
    """Show the cancel started last: which ticket, on which machine, and how it ended."""
    return cancel_state(getattr(request.app.state, "cancel", None))


@router.post("/tickets/{code}/cancel", status_code=202, response_model=CancelState)
def start_cancel(
    context: Context, db: HistoryDb, book: Book, request: Request, code: Code
) -> CancelState:
    """Cancel the ticket in the app of the machine its account is on; it takes about a minute.

    Refused when the ticket is not recorded (404 ``not_found``) or cancelled already (409
    ``ticket_cancelled``), when its account is on no machine (409 ``no_machine``), from the wake
    time to 5 minutes after the start (400 ``bad_request``), and while a run, a dry run or
    another cancel goes on (409 ``lock_held``). The cancel checks again itself.
    """
    row = history_read.get_ticket(db, code)
    if row is None:
        raise NotFoundError(f"No ticket {code}")
    if row["status"] == "cancelled":
        raise TicketCancelledError(f"Ticket {code} is cancelled already")
    machine = machine_of(row, attached(book))
    if machine is None:
        raise NoMachineError(f"The account of ticket {code} is on no machine")
    config = context.config()
    now = datetime.now()
    check_quiet_time(now, config.wake_at, config.start_at, "cancel")
    with _starting:
        if cancel_running(request):
            raise LockHeldError("Another ticket is being cancelled")
        dry_run = getattr(request.app.state, "dry_run", None)
        if dry_run is not None and dry_run.poll() is None:
            raise LockHeldError(f"Another run is in progress: dry run (pid {dry_run.pid})")
        for path in (context.data.lock, context.data.instance_lock(machine)):
            holder = RunLock(path).running_holder()
            if holder is not None:
                raise LockHeldError(f"Another run is in progress: {holder.describe()}")
        instance = None if machine == config.mumu_index else machine
        process = launch_cancel(context.config_path.resolve(), code, instance)
        request.app.state.cancel = Cancelling(
            code, machine, now.isoformat(timespec="seconds"), process
        )
    return cancel_state(request.app.state.cancel)
