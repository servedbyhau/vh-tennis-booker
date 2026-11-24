"""The request routes: what each customer asks to book."""

import pytest


@pytest.fixture
def customer(client):
    return client.post("/api/customers", json={"name": "An"}).json()["id"]


def asked(customer, **fields):
    return {
        "customer_id": customer,
        "subdivision": "origami",
        "sport": "pickleball",
        "court": "S9 - Sân Pickleball",
        "slots": ["18:00 - 19:00"],
        "days": [0, 2, 4],
        "machine": 1,
        **fields,
    }


def test_a_request_is_added_listed_changed_and_removed(client, customer):
    added = client.post("/api/requests", json=asked(customer))
    request_id = added.json()["id"]
    changed = client.put(f"/api/requests/{request_id}", json=asked(customer, active=False))
    listed = client.get("/api/requests").json()
    removed = client.delete(f"/api/requests/{request_id}")

    assert added.status_code == 201
    assert {key: added.json()[key] for key in ("days", "machine", "active", "note")} == {
        "days": [0, 2, 4],
        "machine": 1,
        "active": True,
        "note": "",
    }
    assert changed.json()["active"] is False
    assert [item["id"] for item in listed] == [request_id]
    assert removed.status_code == 204
    assert client.get("/api/requests").json() == []


def test_the_days_are_kept_once_each_in_order(client, customer):
    added = client.post("/api/requests", json=asked(customer, days=[4, 0, 4]))

    assert added.json()["days"] == [0, 4]


def test_a_request_of_an_unknown_customer_is_refused(client):
    answer = client.post("/api/requests", json=asked("f" * 32))

    assert (answer.status_code, answer.json()["error"]) == (404, "not_found")


@pytest.mark.parametrize(
    "fields",
    [{"slots": []}, {"slots": ["6h"]}, {"days": [7]}, {"slots": ["06:00 - 07:00"] * 3}],
)
def test_a_request_out_of_bounds_is_refused(client, customer, fields):
    assert client.post("/api/requests", json=asked(customer, **fields)).status_code == 422


def test_an_unknown_request_is_not_changed(client, customer):
    answer = client.put(f"/api/requests/{'e' * 32}", json=asked(customer))

    assert (answer.status_code, answer.json()["error"]) == (404, "not_found")
