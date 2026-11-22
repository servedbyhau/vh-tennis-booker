"""The customer routes: what they change, refuse, and never answer."""

import os

import pytest

from court_booker.credentials import CredentialError, Login
from court_booker.lock import RunLock

ACCOUNT = {"phone": "0900000079", "password": "mat-khau-bi-mat", "label": "Căn A"}


@pytest.fixture
def customer(client):
    return client.post("/api/customers", json={"name": "An"}).json()


@pytest.fixture
def account(client, customer):
    url = f"/api/customers/{customer['id']}/accounts"
    return client.post(url, json=ACCOUNT).json()["accounts"][0]


@pytest.fixture
def running(context, monkeypatch):
    """Let a run hold the lock."""
    lock = RunLock(context.data.lock)
    holder = type("Holder", (), {"describe": lambda self: f"scheduled (pid {os.getpid()})"})()
    monkeypatch.setattr(RunLock, "running_holder", lambda self: holder)
    return lock


def attach(client, account, index):
    return client.put(f"/api/machines/{index}/account", json={"account_id": account["id"]})


def test_there_are_no_customers_at_first(client):
    assert client.get("/api/customers").json() == []


def test_a_customer_and_their_account_answer_no_password_and_a_masked_phone(
    client, customer, saved_logins
):
    reply = client.post(f"/api/customers/{customer['id']}/accounts", json=ACCOUNT)

    assert reply.status_code == 201
    (shown,) = reply.json()["accounts"]
    assert (shown["phone"], shown["label"], shown["device"]) == ("09••••••79", "Căn A", None)
    listed = client.get("/api/customers")
    assert listed.json() == [reply.json()]
    for text in (reply.text, listed.text):
        assert ACCOUNT["password"] not in text
        assert ACCOUNT["phone"] not in text
    assert saved_logins.read(shown["id"]) == Login("0900000079", "mat-khau-bi-mat")


def test_a_customer_is_changed_and_removed(client, customer, account):
    url = f"/api/customers/{customer['id']}"
    fields = {"representative": "An", "contact": "Zalo An", "note": "ghi chú"}
    reply = client.put(url, json={"name": "  Nhóm An ", **fields})
    shown = reply.json()
    assert shown["name"] == "Nhóm An"
    assert {key: shown[key] for key in fields} == fields
    assert len(reply.json()["accounts"]) == 1
    assert client.delete(url).status_code == 204
    assert client.get("/api/customers").json() == []
    assert client.delete(url).json()["error"] == "not_found"


def test_an_account_takes_a_label_and_a_password(client, account, saved_logins):
    attach(client, account, 2)
    url = f"/api/customer-accounts/{account['id']}"
    reply = client.put(url, json={"label": "Căn B", "password": "moi"})
    assert reply.json()["accounts"][0]["label"] == "Căn B"
    assert "moi" not in reply.text
    assert saved_logins.read(2).password == "moi"


def test_an_account_takes_another_phone_number(client, customer, account, saved_logins):
    attach(client, account, 2)
    url = f"/api/customer-accounts/{account['id']}"
    reply = client.put(url, json={"label": "Căn A", "phone": "0900000080"})
    (shown,) = reply.json()["accounts"]
    assert (shown["phone"], shown["device"]) == ("09••••••80", 2)
    assert "0900000080" not in reply.text
    assert saved_logins.read(2) == Login("0900000080", ACCOUNT["password"])

    other = client.post(f"/api/customers/{customer['id']}/accounts", json=ACCOUNT)
    taken = client.put(
        f"/api/customer-accounts/{other.json()['accounts'][1]['id']}",
        json={"label": "", "phone": "0900000080"},
    )
    assert (taken.status_code, taken.json()["error"]) == (409, "phone_taken")
    assert client.put(url, json={"label": "", "phone": "090000008"}).status_code == 422


def test_an_account_is_attached_and_detached(client, account, saved_logins):
    reply = attach(client, account, 1)
    assert reply.status_code == 200
    assert reply.json()["accounts"][0]["device"] == 1
    assert saved_logins.read(1).phone == ACCOUNT["phone"]
    assert client.delete("/api/machines/1/account").status_code == 204
    assert client.get("/api/customers").json()[0]["accounts"][0]["device"] is None
    assert saved_logins.read(1) is None


def test_an_attached_account_moves_but_is_not_removed(client, customer, account):
    attach(client, account, 1)
    assert attach(client, account, 2).json()["accounts"][0]["device"] == 2
    refused = [
        client.delete(f"/api/customer-accounts/{account['id']}"),
        client.delete(f"/api/customers/{customer['id']}"),
    ]
    assert {(reply.status_code, reply.json()["error"]) for reply in refused} == {
        (409, "account_attached")
    }


def test_what_is_attached_is_removed_when_asked(client, customer, account, saved_logins):
    attach(client, account, 1)
    url = f"/api/customer-accounts/{account['id']}"
    assert client.delete(url, params={"detach": True}).status_code == 204
    assert saved_logins.read(1) is None

    client.post(f"/api/customers/{customer['id']}/accounts", json=ACCOUNT)
    other = client.get("/api/customers").json()[0]["accounts"][0]
    attach(client, other, 2)
    reply = client.delete(f"/api/customers/{customer['id']}", params={"detach": True})
    assert reply.status_code == 204
    assert saved_logins.logins == {}


def test_a_phone_number_is_taken_once(client, account):
    other = client.post("/api/customers", json={"name": "Bình"}).json()
    reply = client.post(f"/api/customers/{other['id']}/accounts", json=ACCOUNT)
    assert (reply.status_code, reply.json()["error"]) == (409, "phone_taken")
    assert ACCOUNT["phone"] not in reply.text


def test_nothing_of_a_machine_changes_while_a_run_goes_on(client, account, saved_logins, running):
    url = f"/api/customer-accounts/{account['id']}"
    refused = [
        attach(client, account, 1),
        client.delete("/api/machines/1/account"),
        client.put(url, json={"label": "", "password": "moi"}),
        client.put(url, json={"label": "", "phone": "0900000080"}),
        client.delete(url, params={"detach": True}),
    ]
    assert {(reply.status_code, reply.json()["error"]) for reply in refused} == {(409, "lock_held")}
    assert saved_logins.read(1) is None
    assert client.put(url, json={"label": "Căn B"}).status_code == 200  # no login in it


@pytest.mark.parametrize(
    "body",
    [
        {"phone": "090000007", "password": "x"},
        {"phone": "9000000079", "password": "x"},
        {"phone": "0900000079", "password": ""},
        {"phone": "0900000079"},
        {**ACCOUNT, "extra": True},
        {**ACCOUNT, "label": "x" * 61},
    ],
)
def test_an_invalid_account_is_refused_without_echoing_it(client, customer, body):
    reply = client.post(f"/api/customers/{customer['id']}/accounts", json=body)
    assert reply.status_code == 422
    assert reply.json()["error"] == "invalid_request"
    if body.get("password"):
        assert body["password"] not in reply.text or body["password"] == "x"


@pytest.mark.parametrize("name", ["", "   ", "x" * 61])
def test_a_customer_needs_a_name(client, name):
    assert client.post("/api/customers", json={"name": name}).status_code == 422


def test_an_unknown_id_answers_not_found(client):
    unknown = "0" * 32
    assert client.put(f"/api/customers/{unknown}", json={"name": "An"}).status_code == 404
    assert client.delete(f"/api/customer-accounts/{unknown}").status_code == 404
    assert attach(client, {"id": unknown}, 0).status_code == 404
    assert client.delete("/api/customer-accounts/1").status_code == 422


def test_a_vault_that_refuses_answers_credentials(client, customer, saved_logins, monkeypatch):
    def refuse(key, login):
        raise CredentialError("Windows could not keep the login (error 5)")

    monkeypatch.setattr(saved_logins, "save", refuse)
    reply = client.post(f"/api/customers/{customer['id']}/accounts", json=ACCOUNT)
    assert (reply.status_code, reply.json()["error"]) == (503, "credentials")
