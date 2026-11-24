"""What each customer asks to book: a court, its slots, the days of the week, a machine.

A request is the customer's wish as the user took it down; it books nothing by itself. The app
applies it to its machine's settings (the court, the slots and the days that machine books),
which the daily task then books with that machine's account.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from court_booker.customers import UnknownRecordError


@dataclass
class Request:
    customer_id: str
    subdivision: str
    sport: str
    court: str
    slots: list[str]
    days: list[int] = field(default_factory=list)
    """0 Monday to 6 Sunday; empty: every day."""
    machine: int | None = None
    active: bool = True
    note: str = ""
    id: str = ""
    created_at: str = ""


def _row(row: sqlite3.Row | tuple[Any, ...], names: list[str]) -> Request:
    item = dict(zip(names, row))
    return Request(
        customer_id=item["customer_id"],
        subdivision=item["subdivision"],
        sport=item["sport"],
        court=item["court"],
        slots=json.loads(item["slots"]),
        days=json.loads(item["days"]),
        machine=item["machine"],
        active=bool(item["active"]),
        note=item["note"],
        id=item["id"],
        created_at=item["created_at"],
    )


def list_requests(db: sqlite3.Connection) -> list[Request]:
    """Return every request, by customer, the newest last."""
    cursor = db.execute("SELECT * FROM requests ORDER BY customer_id, created_at")
    names = [column[0] for column in cursor.description]
    return [_row(row, names) for row in cursor.fetchall()]


def get_request(db: sqlite3.Connection, request_id: str) -> Request:
    """Return a request; raises :class:`UnknownRecordError`."""
    cursor = db.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
    row = cursor.fetchone()
    if row is None:
        raise UnknownRecordError(f"No request {request_id}")
    return _row(row, [column[0] for column in cursor.description])


def _values(request: Request) -> tuple[Any, ...]:
    return (
        request.customer_id,
        request.subdivision,
        request.sport,
        request.court,
        json.dumps(request.slots, ensure_ascii=False),
        json.dumps(sorted(set(request.days))),
        request.machine,
        int(request.active),
        request.note,
    )


def add_request(db: sqlite3.Connection, request: Request, now: datetime) -> Request:
    """Record a new request; raises :class:`UnknownRecordError` for an unknown customer."""
    if (
        db.execute("SELECT 1 FROM customers WHERE id = ?", (request.customer_id,)).fetchone()
        is None
    ):
        raise UnknownRecordError(f"No customer {request.customer_id}")
    request_id = uuid.uuid4().hex
    with db:
        db.execute(
            "INSERT INTO requests (customer_id, subdivision, sport, court, slots, days, machine,"
            " active, note, id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*_values(request), request_id, now.isoformat(timespec="seconds")),
        )
    return get_request(db, request_id)


def change_request(db: sqlite3.Connection, request_id: str, request: Request) -> Request:
    """Replace what a request asks; raises :class:`UnknownRecordError`."""
    get_request(db, request_id)
    with db:
        db.execute(
            "UPDATE requests SET customer_id = ?, subdivision = ?, sport = ?, court = ?,"
            " slots = ?, days = ?, machine = ?, active = ?, note = ? WHERE id = ?",
            (*_values(request), request_id),
        )
    return get_request(db, request_id)


def remove_request(db: sqlite3.Connection, request_id: str) -> None:
    """Remove a request; raises :class:`UnknownRecordError`."""
    with db:
        if db.execute("DELETE FROM requests WHERE id = ?", (request_id,)).rowcount == 0:
            raise UnknownRecordError(f"No request {request_id}")


def as_dict(request: Request) -> dict[str, Any]:
    return asdict(request)
