"""The money of the bookings made for customers: their charges, the prices, what was paid.

A ticket a customer's account booked becomes a charge when a run saves it (``charges`` in the
history database, :meth:`court_booker.history.History.save_tickets`), and stays once the ticket
is gone. Its amount is the price of its sport (``prices``), the golden one for a slot that starts
in the golden hours, unless one was set by hand; a cancelled ticket and a customer booked for
free (the user's own account, say) owe nothing. A charge is paid once marked so.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from court_booker.quota import sport_of

GOLDEN_FROM = "17:00"
"""Start of the golden hours, when not set: the evening slots everyone wants."""
GOLDEN_TO = "21:00"


@dataclass(frozen=True)
class Price:
    """What a slot of a sport costs, in VND: a normal slot and one in the golden hours."""

    sport: str
    normal: int
    golden: int


@dataclass(frozen=True)
class PriceList:
    golden_from: str
    golden_to: str
    prices: list[Price]

    def golden(self, slot: str) -> bool:
        """Tell whether ``slot`` ("18:00 - 19:00") starts in the golden hours."""
        start = slot.split("-", 1)[0].strip().zfill(5)
        return self.golden_from <= start < self.golden_to

    def amount(self, sport: str | None, slot: str) -> int | None:
        """Return what ``slot`` of ``sport`` costs, ``None`` without a price for it."""
        price = next((price for price in self.prices if price.sport == sport), None)
        if price is None:
            return None
        return price.golden if self.golden(slot) else price.normal


def read_prices(db: sqlite3.Connection) -> PriceList:
    """Return the price list, the default golden hours when none were set."""
    settings = dict(db.execute("SELECT key, value FROM money_settings").fetchall())
    prices = [
        Price(sport, normal, golden)
        for sport, normal, golden in db.execute(
            "SELECT sport, normal, golden FROM prices ORDER BY sport"
        )
    ]
    return PriceList(
        settings.get("golden_from", GOLDEN_FROM), settings.get("golden_to", GOLDEN_TO), prices
    )


def save_prices(db: sqlite3.Connection, prices: PriceList) -> None:
    """Replace the price list."""
    with db:
        db.execute("DELETE FROM prices")
        db.executemany(
            "INSERT INTO prices (sport, normal, golden) VALUES (?, ?, ?)",
            [(price.sport, price.normal, price.golden) for price in prices.prices],
        )
        db.executemany(
            "INSERT INTO money_settings (key, value) VALUES (?, ?)"
            " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            [("golden_from", prices.golden_from), ("golden_to", prices.golden_to)],
        )


def charge_saved_tickets(db: sqlite3.Connection, today: str) -> None:
    """Make the charges of the tickets of a chosen account still to play that have none yet,
    and cancel those of the tickets read cancelled.

    A run makes them as it saves the tickets; this catches the ones saved before there was
    money (schema 8), each once.
    """
    with db:
        db.execute(
            "INSERT INTO charges (code, account_id, customer, account, utility, court,"
            " play_date, slot, created_at)"
            " SELECT code, account_id, customer, account, utility, court, play_date, slot, seen_at"
            " FROM tickets WHERE account_id IS NOT NULL AND status != 'cancelled'"
            " AND play_date >= ? ON CONFLICT (code) DO NOTHING",
            (today,),
        )
        db.execute(
            "UPDATE charges SET cancelled = 1"
            " WHERE code IN (SELECT code FROM tickets WHERE status = 'cancelled')"
        )


def list_charges(db: sqlite3.Connection, month: str | None = None) -> list[dict[str, Any]]:
    """Return the charges of ``month`` (``YYYY-MM`` of the day of play), or all, priced.

    Each holds whose it is by today's names (those of then once removed), its sport, whether
    its slot is golden, its amount (the one set by hand, else the price list's, ``None``
    without a price; 0 for a cancelled ticket or a customer booked for free) and when it was
    paid.
    """
    prices = read_prices(db)
    rows = db.execute(
        "SELECT charges.code, charges.account_id, charges.utility, charges.court,"
        " charges.play_date, charges.slot, charges.cancelled, charges.amount AS set_amount,"
        " charges.paid_at, accounts.customer_id,"
        " COALESCE(customers.name, charges.customer) AS customer,"
        " COALESCE(NULLIF(accounts.label, ''), charges.account) AS account,"
        " COALESCE(customers.free, 0) AS free"
        " FROM charges LEFT JOIN accounts ON accounts.id = charges.account_id"
        " LEFT JOIN customers ON customers.id = accounts.customer_id"
        " WHERE (? IS NULL OR substr(charges.play_date, 1, 7) = ?)"
        " ORDER BY charges.play_date, charges.slot, charges.code",
        (month, month),
    )
    found = []
    for row in rows:
        item = dict(zip([column[0] for column in rows.description], row))
        sport = sport_of(item["utility"])
        owed = not item["cancelled"] and not item["free"]
        listed = prices.amount(sport, item["slot"])
        if not owed:
            amount = 0
        elif item["set_amount"] is not None:
            amount = item["set_amount"]
        else:
            amount = listed
        found.append(
            {
                "code": item["code"],
                "customer_id": item["customer_id"],
                "customer": item["customer"],
                "account": item["account"],
                "sport": sport,
                "court": item["court"],
                "play_date": item["play_date"],
                "slot": item["slot"],
                "golden": prices.golden(item["slot"]),
                "amount": amount,
                "set_by_hand": item["set_amount"] is not None,
                "cancelled": bool(item["cancelled"]),
                "free": bool(item["free"]),
                "paid_at": item["paid_at"],
            }
        )
    return found


def charge_months(db: sqlite3.Connection) -> list[str]:
    """Return the months of play that have charges, the newest first."""
    rows = db.execute(
        "SELECT DISTINCT substr(play_date, 1, 7) FROM charges ORDER BY 1 DESC"
    ).fetchall()
    return [month for (month,) in rows]


def mark_paid(db: sqlite3.Connection, codes: list[str], paid: bool, now: datetime) -> int:
    """Mark the charges ``codes`` paid now, or not paid; return how many there were."""
    at = now.isoformat(timespec="seconds") if paid else None
    with db:
        cursor = db.executemany(
            "UPDATE charges SET paid_at = ? WHERE code = ?", [(at, code) for code in codes]
        )
    return cursor.rowcount


def set_amount(db: sqlite3.Connection, code: str, amount: int | None) -> bool:
    """Set a charge's amount by hand, or back to the price list's with ``None``."""
    with db:
        cursor = db.execute("UPDATE charges SET amount = ? WHERE code = ?", (amount, code))
    return cursor.rowcount > 0


def set_free(db: sqlite3.Connection, customer_id: str, free: bool) -> bool:
    """Book for customer ``customer_id`` for free, or not; return whether it exists."""
    with db:
        cursor = db.execute("UPDATE customers SET free = ? WHERE id = ?", (int(free), customer_id))
    return cursor.rowcount > 0


def free_customers(db: sqlite3.Connection) -> list[str]:
    """Return the ids of the customers booked for free."""
    return [row[0] for row in db.execute("SELECT id FROM customers WHERE free = 1")]
