"""Money routes: the prices, the charges of a month, what was paid (court_booker.money)."""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time, where Python 3.9 has no `X | None`, so `Optional` is used instead.
import sqlite3
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query, Response
from fastapi import Path as PathParameter
from pydantic import BaseModel, ConfigDict, Field

from court_booker import money
from court_booker.api.context import Context
from court_booker.api.errors import NotFoundError
from court_booker.history import connect

router = APIRouter(prefix="/api/money", tags=["money"])

Month = Annotated[Optional[str], Query(pattern=r"^\d{4}-\d{2}$")]
Code = Annotated[str, PathParameter(pattern=r"^\d{1,20}$")]
Time = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
Amount = Annotated[int, Field(ge=0, le=100_000_000)]


def money_db(context: Context) -> Iterator[sqlite3.Connection]:
    """Open the history database for one request."""
    connection = connect(context.data.database)
    try:
        yield connection
    finally:
        connection.close()


MoneyDb = Annotated[sqlite3.Connection, Depends(money_db)]


class Price(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sport: str = Field(min_length=1, max_length=40)
    normal: Amount
    """VND for a slot outside the golden hours."""
    golden: Amount
    """VND for a slot that starts in the golden hours."""


class Prices(BaseModel):
    """The price list: the golden hours and a price per sport."""

    model_config = ConfigDict(extra="forbid")

    golden_from: Time
    golden_to: Time
    prices: list[Price]


class Charge(BaseModel):
    """What a ticket a customer's account booked costs, and whether it was paid."""

    code: str
    customer_id: Optional[str]
    """Its customer, empty once the account is removed."""
    customer: Optional[str]
    account: Optional[str]
    sport: Optional[str]
    court: str
    play_date: str
    slot: str
    golden: bool
    amount: Optional[int]
    """VND: set by hand, else the price list's; empty without a price; 0 when cancelled or free."""
    set_by_hand: bool
    cancelled: bool
    free: bool
    paid_at: Optional[str]


class Charges(BaseModel):
    month: Optional[str]
    months: list[str]
    """The months with charges, the newest first."""
    charges: list[Charge]
    free_customers: list[str]


class ChargeChange(BaseModel):
    """Mark a charge paid or not, and set its amount by hand (``null`` takes the price list's)."""

    model_config = ConfigDict(extra="forbid")

    paid: Optional[bool] = None
    amount: Optional[Amount] = None
    reset_amount: bool = False


class PaidMark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codes: list[Annotated[str, Field(pattern=r"^\d{1,20}$")]]
    paid: bool


class FreeMark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    free: bool


def prices_of(price_list: money.PriceList) -> Prices:
    return Prices(
        golden_from=price_list.golden_from,
        golden_to=price_list.golden_to,
        prices=[Price(sport=p.sport, normal=p.normal, golden=p.golden) for p in price_list.prices],
    )


@router.get("/prices", response_model=Prices)
def read_prices(db: MoneyDb) -> Prices:
    """Show the price list."""
    return prices_of(money.read_prices(db))


@router.put("/prices", response_model=Prices)
def save_prices(db: MoneyDb, prices: Prices) -> Prices:
    """Replace the price list; the charges not set by hand follow it."""
    money.save_prices(
        db,
        money.PriceList(
            prices.golden_from,
            prices.golden_to,
            [money.Price(p.sport, p.normal, p.golden) for p in prices.prices],
        ),
    )
    return prices_of(money.read_prices(db))


@router.get("/charges", response_model=Charges)
def list_charges(db: MoneyDb, month: Month = None) -> dict[str, Any]:
    """List the charges of a month of play (every month when not given), priced; the tickets
    saved before the money was there are charged first."""
    money.charge_saved_tickets(db, datetime.now().date().isoformat())
    return {
        "month": month,
        "months": money.charge_months(db),
        "charges": money.list_charges(db, month),
        "free_customers": money.free_customers(db),
    }


@router.put("/charges/{code}", status_code=204, response_class=Response)
def change_charge(db: MoneyDb, code: Code, change: ChargeChange) -> Response:
    """Mark a charge paid or not, or set its amount; 404 for one not recorded."""
    if change.paid is not None and not money.mark_paid(db, [code], change.paid, datetime.now()):
        raise NotFoundError(f"No charge {code}")
    changes_amount = change.amount is not None or change.reset_amount
    amount = None if change.reset_amount else change.amount
    if changes_amount and not money.set_amount(db, code, amount):
        raise NotFoundError(f"No charge {code}")
    return Response(status_code=204)


@router.put("/paid", status_code=204, response_class=Response)
def mark_paid(db: MoneyDb, mark: PaidMark) -> Response:
    """Mark several charges paid at once, or not paid (a customer's month, say)."""
    money.mark_paid(db, mark.codes, mark.paid, datetime.now())
    return Response(status_code=204)


@router.put("/customers/{customer_id}/free", status_code=204, response_class=Response)
def mark_free(
    db: MoneyDb,
    customer_id: Annotated[str, PathParameter(pattern=r"^[0-9a-f]{32}$")],
    mark: FreeMark,
) -> Response:
    """Book for a customer for free (their charges owe nothing), or not."""
    if not money.set_free(db, customer_id, mark.free):
        raise NotFoundError(f"No customer {customer_id}")
    return Response(status_code=204)
