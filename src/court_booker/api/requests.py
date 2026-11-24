"""Request routes: what each customer asks to book (court_booker.requests)."""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time, where Python 3.9 has no `X | None`, so `Optional` is used instead.
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Response
from fastapi import Path as PathParameter
from pydantic import BaseModel, ConfigDict, Field

from court_booker import requests
from court_booker.api.money import MoneyDb

router = APIRouter(prefix="/api", tags=["requests"])

RecordId = Annotated[str, PathParameter(pattern=r"^[0-9a-f]{32}$")]
Slot = Annotated[str, Field(pattern=r"^\d{2}:\d{2} - \d{2}:\d{2}$")]
Day = Annotated[int, Field(ge=0, le=6)]


class RequestFields(BaseModel):
    """What a customer asks to book."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    subdivision: str = Field(max_length=40)
    sport: str = Field(min_length=1, max_length=40)
    court: str = Field(min_length=1, max_length=80)
    slots: list[Slot] = Field(min_length=1, max_length=2)
    days: list[Day] = Field(default_factory=list, max_length=7)
    """0 Monday to 6 Sunday; empty: every day."""
    machine: Optional[int] = Field(default=None, ge=0, le=31)
    """The MuMu instance that books it; empty while none was chosen."""
    active: bool = True
    note: str = Field(default="", max_length=500)


class BookingRequest(RequestFields):
    id: str
    created_at: str


def fields_of(fields: RequestFields) -> requests.Request:
    return requests.Request(**fields.model_dump())


@router.get("/requests", response_model=list[BookingRequest])
def list_requests(db: MoneyDb) -> list[dict[str, Any]]:
    """List every request, by customer."""
    return [requests.as_dict(item) for item in requests.list_requests(db)]


@router.post("/requests", status_code=201, response_model=BookingRequest)
def add_request(db: MoneyDb, fields: RequestFields) -> dict[str, Any]:
    """Record a customer's request; 404 for an unknown customer."""
    return requests.as_dict(requests.add_request(db, fields_of(fields), datetime.now()))


@router.put("/requests/{request_id}", response_model=BookingRequest)
def change_request(db: MoneyDb, request_id: RecordId, fields: RequestFields) -> dict[str, Any]:
    """Replace what a request asks."""
    return requests.as_dict(requests.change_request(db, request_id, fields_of(fields)))


@router.delete("/requests/{request_id}", status_code=204, response_class=Response)
def remove_request(db: MoneyDb, request_id: RecordId) -> Response:
    """Remove a request."""
    requests.remove_request(db, request_id)
    return Response(status_code=204)
