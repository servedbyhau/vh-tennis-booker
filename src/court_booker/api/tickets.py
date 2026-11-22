"""Ticket routes: the accounts' tickets as the runs last read them, and their pictures."""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time, where Python 3.9 has no `X | None`, so `Optional` is used instead.
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Query
from fastapi import Path as PathParameter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from court_booker import history_read
from court_booker.api.context import Context
from court_booker.api.errors import NotFoundError
from court_booker.api.history import HistoryDb

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


def photo_path(folder: Path, name: Optional[str]) -> Optional[Path]:
    """Return the picture ``name`` in ``folder`` if it is there; old ones are deleted."""
    path = None if name is None else folder / Path(name).name
    return path if path is not None and path.is_file() else None


@router.get("/tickets", response_model=list[Ticket])
def list_tickets(
    context: Context,
    db: HistoryDb,
    since: Annotated[Optional[str], Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_TICKETS)] = history_read.DEFAULT_TICKETS,
) -> list[dict[str, Any]]:
    """List every machine's tickets, the latest day of play first, by slot within a day.

    ``since`` keeps the tickets played that day or later.
    """
    folder = context.data.tickets
    return [
        {**row, "has_photo": photo_path(folder, row["photo"]) is not None}
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
    code: Annotated[str, PathParameter(pattern=r"^\d{1,20}$")],
) -> FileResponse:
    """Answer with the picture of a ticket, down to its directions link."""
    path = photo_path(context.data.tickets, history_read.ticket_photo(db, code))
    if path is None:
        raise NotFoundError(f"No picture of ticket {code}")
    # Checked each time: a later run may have taken it again.
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-cache"})
