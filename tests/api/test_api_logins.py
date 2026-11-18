"""The login routes save a login for a MuMu instance and never answer its password."""

import pytest

from court_booker.credentials import CredentialError, Login

NEW = {"phone": "0900000079", "password": "mat-khau-bi-mat"}


def test_no_login_is_saved_at_first(client):
    assert client.get("/api/logins/0").json() == {"mumu_index": 0, "saved": False, "phone": None}


def test_a_saved_login_answers_its_masked_phone_only(client, saved_logins):
    reply = client.put("/api/logins/1", json=NEW)

    assert reply.status_code == 200
    assert reply.json() == {"mumu_index": 1, "saved": True, "phone": "09••••••79"}
    assert "mat-khau-bi-mat" not in reply.text
    assert "mat-khau-bi-mat" not in client.get("/api/logins/1").text
    assert saved_logins.read(1) == Login("0900000079", "mat-khau-bi-mat")
    assert saved_logins.read(0) is None  # each machine its own


def test_a_removed_login_is_gone(client, saved_logins):
    saved_logins.save(0, Login("0900000079", "x"))

    assert client.delete("/api/logins/0").status_code == 204
    assert client.delete("/api/logins/0").status_code == 204  # nothing left: no error
    assert saved_logins.read(0) is None


@pytest.mark.parametrize(
    "login",
    [
        {"phone": "090000007", "password": "x"},  # 9 digits
        {"phone": "9000000079", "password": "x"},
        {"phone": "0900000079", "password": ""},
        {"phone": "0900000079"},
        {**NEW, "extra": True},
    ],
)
def test_an_invalid_login_is_refused_without_echoing_it(client, saved_logins, login):
    reply = client.put("/api/logins/0", json=login)

    assert reply.status_code == 422
    assert reply.json()["error"] == "invalid_request"
    assert saved_logins.read(0) is None
    if login.get("password"):
        assert login["password"] not in reply.text


def test_a_vault_that_refuses_answers_credentials(client, saved_logins, monkeypatch):
    def refuse(index, login):
        raise CredentialError("Windows could not keep the login (error 1312)")

    monkeypatch.setattr(saved_logins, "save", refuse)

    reply = client.put("/api/logins/0", json=NEW)

    assert reply.status_code == 503
    assert reply.json()["error"] == "credentials"
    assert "mat-khau-bi-mat" not in reply.text
