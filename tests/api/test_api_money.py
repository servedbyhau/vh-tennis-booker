"""The money routes: prices, the charges of a month, what was paid."""

from datetime import datetime

from court_booker import history
from court_booker.tickets import Ticket

PRICES = {
    "golden_from": "17:00",
    "golden_to": "21:00",
    "prices": [{"sport": "pickleball", "normal": 100000, "golden": 150000}],
}


def add_charge(client, context, code="1234567", play_date="2026-11-26"):
    """Add a customer with an account, and a ticket of it as a run saves it."""
    customer = client.post("/api/customers", json={"name": "An"}).json()
    account = {"phone": "0900000079", "password": "x", "label": "Căn A"}
    added = client.post(f"/api/customers/{customer['id']}/accounts", json=account).json()
    account_id = added["accounts"][0]["id"]
    store = history.History(history.connect(context.data.database))
    store.holder = history.Holder(account_id, "An", "Căn A")
    ticket = Ticket(
        code,
        "Sân Pickleball",
        "S9 - Sân Pickleball",
        play_date,
        "18:00 - 19:00",
        "Đã đăng ký",
        None,
    )
    store.save_tickets(1, [ticket], {}, datetime(2026, 11, 24, 6, 3))
    store.close()
    return customer["id"]


def test_prices_are_saved_and_read(client):
    assert client.get("/api/money/prices").json() == {
        "golden_from": "17:00",
        "golden_to": "21:00",
        "prices": [],
    }

    assert client.put("/api/money/prices", json=PRICES).json() == PRICES
    assert client.get("/api/money/prices").json() == PRICES


def test_a_price_out_of_bounds_is_refused(client):
    bad = {**PRICES, "golden_from": "25:00"}

    assert client.put("/api/money/prices", json=bad).status_code == 422


def test_the_charges_of_a_month_are_priced_and_paid(client, context):
    client.put("/api/money/prices", json=PRICES)
    customer = add_charge(client, context)

    listed = client.get("/api/money/charges", params={"month": "2026-11"}).json()
    paid = client.put("/api/money/paid", json={"codes": ["1234567"], "paid": True})
    after = client.get("/api/money/charges").json()["charges"][0]

    (charge,) = listed["charges"]
    assert listed["months"] == ["2026-11"]
    assert (charge["customer_id"], charge["customer"], charge["amount"]) == (customer, "An", 150000)
    assert paid.status_code == 204
    assert after["paid_at"] is not None


def test_a_charge_takes_an_amount_by_hand_and_is_unpaid_again(client, context):
    add_charge(client, context)

    set_by_hand = client.put("/api/money/charges/1234567", json={"amount": 90000, "paid": True})
    charge = client.get("/api/money/charges").json()["charges"][0]
    client.put("/api/money/charges/1234567", json={"reset_amount": True, "paid": False})
    reset = client.get("/api/money/charges").json()["charges"][0]

    assert set_by_hand.status_code == 204
    assert (charge["amount"], charge["set_by_hand"]) == (90000, True)
    assert (reset["amount"], reset["set_by_hand"], reset["paid_at"]) == (None, False, None)


def test_an_unknown_charge_is_refused(client):
    answer = client.put("/api/money/charges/7654321", json={"paid": True})

    assert (answer.status_code, answer.json()["error"]) == (404, "not_found")


def test_a_customer_is_booked_for_free(client, context):
    client.put("/api/money/prices", json=PRICES)
    customer = add_charge(client, context)

    marked = client.put(f"/api/money/customers/{customer}/free", json={"free": True})
    listed = client.get("/api/money/charges").json()

    assert marked.status_code == 204
    assert listed["free_customers"] == [customer]
    assert listed["charges"][0]["amount"] == 0
