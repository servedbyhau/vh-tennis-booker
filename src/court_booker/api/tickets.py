"""Ticket routes: the accounts' tickets as the runs last read them, their pictures, and the
cancel of one in the app (``court-booker cancel``, in its own process)."""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time, where Python 3.9 has no `X | None`, so `Optional` is used instead.
import contextlib
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Query, Request, Response
from fastapi import Path as PathParameter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from court_booker import history_read
from court_booker.api.context import Context
from court_booker.api.customers import Book
from court_booker.api.errors import NoMachineError, NotFoundError, TicketCancelledError
from court_booker.api.history import HistoryDb
from court_booker.api.tasks import TaskState, last, start, state_of
from court_booker.customers import CustomerBook
from court_booker.history import connect
from court_booker.quota import sport_of

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
    sport: Optional[str]
    """The sport of its utility (``tennis``, ``pickleball``...), empty for one not known here."""
    sent_at: Optional[str]
    """When its picture was marked sent to its customer; empty while not."""
    machine: Optional[int]
    """The MuMu instance that can cancel it now: the one its account is attached to, or the
    one that read it when no chosen account did; empty when its account is on no machine."""


Code = Annotated[str, PathParameter(pattern=r"^\d{1,20}$")]


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
            "sport": sport_of(row["utility"]),
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


@router.get("/tickets/cancel", response_model=TaskState)
def read_cancel(request: Request) -> TaskState:
    """Show the cancel started last: which ticket, on which machine, and how it ended."""
    return state_of(last(request, "cancel"))


@router.post("/tickets/{code}/cancel", status_code=202, response_model=TaskState)
def start_cancel(
    context: Context, db: HistoryDb, book: Book, request: Request, code: Code
) -> TaskState:
    """Cancel the ticket in the app of the machine its account is on; it takes about a minute.

    Refused when the ticket is not recorded (404 ``not_found``) or cancelled already (409
    ``ticket_cancelled``), when its account is on no machine (409 ``no_machine``), and as
    :func:`court_booker.api.tasks.start` refuses (around the scheduled run, or another run or
    task going on). The cancel checks again itself.
    """
    row = history_read.get_ticket(db, code)
    if row is None:
        raise NotFoundError(f"No ticket {code}")
    if row["status"] == "cancelled":
        raise TicketCancelledError(f"Ticket {code} is cancelled already")
    machine = machine_of(row, attached(book))
    if machine is None:
        raise NoMachineError(f"The account of ticket {code} is on no machine")
    return start(request, context, "cancel", machine, ["cancel", code], code)


class SentMark(BaseModel):
    """Whether a ticket's picture was sent to its customer."""

    sent: bool


@router.put("/tickets/{code}/sent", status_code=204, response_class=Response)
def mark_ticket_sent(context: Context, code: Code, mark: SentMark) -> Response:
    """Mark the ticket sent to its customer now, or not sent; 404 for a ticket not recorded."""
    at = datetime.now().isoformat(timespec="seconds") if mark.sent else None
    with contextlib.closing(connect(context.data.database)) as db:
        if not history_read.mark_sent(db, code, at):
            raise NotFoundError(f"No ticket {code}")
    return Response(status_code=204)
