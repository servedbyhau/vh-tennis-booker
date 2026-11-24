"""The money: charges made from the tickets saved, priced by the price list, paid."""

from datetime import datetime

import pytest

from court_booker import history, money
from court_booker.tickets import Ticket

SEEN = datetime(2026, 11, 24, 6, 3)
ACCOUNT = "a" * 32
CUSTOMER = "c" * 32


def ticket(code, play_date="2026-11-26", slot="18:00 - 19:00", status="Đã đăng ký"):
    return Ticket(code, "Sân Pickleball", "S9 - Sân Pickleball", play_date, slot, status, None)


@pytest.fixture
def db(tmp_path):
    connection = history.connect(tmp_path / "booker.db")
    connection.execute(
        "INSERT INTO customers (id, name, note, created_at) VALUES (?, 'Anh An', '', 'x')",
        (CUSTOMER,),
    )
    connection.execute(
        "INSERT INTO accounts (id, customer_id, label, created_at) VALUES (?, ?, 'Căn A', 'x')",
        (ACCOUNT, CUSTOMER),
    )
    connection.commit()
    yield connection
    connection.close()


def save(db, *tickets, holder=True, seen=SEEN):
    store = history.History(db)
    if holder:
        store.holder = history.Holder(ACCOUNT, "Anh An", "Căn A")
    store.save_tickets(1, tickets, {}, seen)


def prices(db, normal=100_000, golden=150_000):
    money.save_prices(
        db, money.PriceList("17:00", "21:00", [money.Price("pickleball", normal, golden)])
    )


def test_a_ticket_to_play_of_a_chosen_account_becomes_a_charge(db):
    save(db, ticket("1"), ticket("2", play_date="2026-11-20"))  # one played already
    save(db, ticket("3"), holder=False)  # a machine without a chosen account

    assert [charge["code"] for charge in money.list_charges(db)] == ["1"]


def test_a_charge_is_priced_golden_or_not_by_its_slot(db):
    prices(db)
    save(db, ticket("1", slot="18:00 - 19:00"), ticket("2", slot="07:00 - 08:00"))

    charges = {charge["code"]: charge for charge in money.list_charges(db)}

    assert (charges["1"]["golden"], charges["1"]["amount"]) == (True, 150_000)
    assert (charges["2"]["golden"], charges["2"]["amount"]) == (False, 100_000)
    assert charges["1"]["customer"] == "Anh An"
    assert charges["1"]["sport"] == "pickleball"


def test_without_a_price_the_amount_is_not_known(db):
    save(db, ticket("1"))

    assert money.list_charges(db)[0]["amount"] is None


def test_a_cancelled_ticket_owes_nothing_and_stays_once_the_ticket_is_gone(db):
    prices(db)
    save(db, ticket("1"))
    save(db, ticket("1", status="Đã huỷ"))
    db.execute("DELETE FROM tickets")  # the day of play is over
    db.commit()

    (charge,) = money.list_charges(db)

    assert (charge["cancelled"], charge["amount"]) == (True, 0)


def test_an_amount_set_by_hand_wins_until_reset(db):
    prices(db)
    save(db, ticket("1"))

    money.set_amount(db, "1", 120_000)
    set_by_hand = money.list_charges(db)[0]
    money.set_amount(db, "1", None)

    assert (set_by_hand["amount"], set_by_hand["set_by_hand"]) == (120_000, True)
    assert money.list_charges(db)[0]["amount"] == 150_000


def test_a_customer_booked_for_free_owes_nothing(db):
    prices(db)
    save(db, ticket("1"))

    assert money.set_free(db, CUSTOMER, True)
    assert money.free_customers(db) == [CUSTOMER]
    assert money.list_charges(db)[0]["amount"] == 0
    assert not money.set_free(db, "d" * 32, True)


def test_charges_are_paid_and_listed_by_month(db):
    save(db, ticket("1"), ticket("2", play_date="2026-12-01"))

    assert money.mark_paid(db, ["1"], True, SEEN) == 1
    november = money.list_charges(db, "2026-11")

    assert [charge["code"] for charge in november] == ["1"]
    assert november[0]["paid_at"] == "2026-11-24T06:03:00"
    assert money.charge_months(db) == ["2026-12", "2026-11"]
    money.mark_paid(db, ["1"], False, SEEN)
    assert money.list_charges(db, "2026-11")[0]["paid_at"] is None


def test_the_price_list_keeps_its_golden_hours(db):
    assert money.read_prices(db) == money.PriceList("17:00", "21:00", [])

    money.save_prices(db, money.PriceList("16:00", "20:00", [money.Price("tennis", 1, 2)]))

    assert money.read_prices(db) == money.PriceList("16:00", "20:00", [money.Price("tennis", 1, 2)])
