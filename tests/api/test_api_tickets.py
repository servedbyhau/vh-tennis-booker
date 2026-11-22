from datetime import datetime

import pytest

from court_booker import history
from court_booker.tickets import Ticket

PNG = b"\x89PNG\r\n\x1a\nmade up"


@pytest.fixture
def save(context):
    """Return a function that records tickets of a MuMu instance, as a run does."""

    def record(device, *tickets, photos=None):
        store = history.History(history.connect(context.data.database))
        store.save_tickets(device, tickets, photos or {}, datetime(2026, 10, 1, 6, 1, 12))
        store.close()

    return record


def ticket(code="1234567", play_date="2026-10-03", slot="08:00 - 09:00", status="Đã đăng ký"):
    return Ticket(
        code, "Sân Tennis", "S6 - Sân tennis", play_date, slot, status, "2026-10-01T06:00"
    )


def add_photo(context, name, data=PNG):
    context.data.tickets.mkdir(parents=True, exist_ok=True)
    (context.data.tickets / name).write_bytes(data)


def test_no_tickets_yet(client):
    assert client.get("/api/tickets").json() == []


def test_a_ticket_comes_with_what_the_app_showed(client, context, save):
    save(1, ticket(), photos={"1234567": "1234567.png"})
    add_photo(context, "1234567.png")
    assert client.get("/api/tickets").json() == [
        {
            "code": "1234567",
            "device": 1,
            "court": "S6 - Sân tennis",
            "play_date": "2026-10-03",
            "slot": "08:00 - 09:00",
            "status": "registered",
            "status_text": "Đã đăng ký",
            "created_at": "2026-10-01T06:00",
            "seen_at": "2026-10-01T06:01:12.000",
            "has_photo": True,
        }
    ]


def test_every_machine_s_tickets_come_together(client, save):
    save(1, ticket("11"), ticket("22", "2026-10-02"))
    save(2, ticket("33", slot="07:00 - 08:00"), ticket("44", status="Đã huỷ"))
    listed = client.get("/api/tickets").json()
    assert [(item["code"], item["device"]) for item in listed] == [
        ("33", 2),
        ("11", 1),
        ("44", 2),
        ("22", 1),
    ]
    assert [item["status"] for item in listed if item["code"] == "44"] == ["cancelled"]
    later = client.get("/api/tickets", params={"since": "2026-10-03", "limit": 2}).json()
    assert [item["code"] for item in later] == ["33", "11"]


@pytest.mark.parametrize("params", [{"since": "3/10"}, {"limit": 0}, {"limit": 99999}])
def test_a_query_out_of_bounds_is_refused(client, params):
    answer = client.get("/api/tickets", params=params)
    assert (answer.status_code, answer.json()["error"]) == (422, "invalid_request")


def test_a_picture_is_served(client, context, save):
    save(1, ticket(), photos={"1234567": "1234567.png"})
    add_photo(context, "1234567.png")
    answer = client.get("/api/tickets/1234567/photo")
    assert answer.status_code == 200
    assert answer.content == PNG
    assert answer.headers["content-type"] == "image/png"
    assert answer.headers["cache-control"] == "no-cache"


def test_a_picture_deleted_since_is_not_found(client, save):
    save(1, ticket(), photos={"1234567": "1234567.png"})
    assert [item["has_photo"] for item in client.get("/api/tickets").json()] == [False]
    answer = client.get("/api/tickets/1234567/photo")
    assert (answer.status_code, answer.json()["error"]) == (404, "not_found")


def test_a_ticket_without_a_picture_is_not_found(client, save):
    save(1, ticket())
    assert client.get("/api/tickets/1234567/photo").status_code == 404
    assert client.get("/api/tickets/99/photo").status_code == 404


@pytest.mark.parametrize("code", ["..%5Cbooker", "abc", "1" * 21])
def test_only_a_code_names_a_picture(client, code):
    assert client.get(f"/api/tickets/{code}/photo").status_code in (404, 422)


def test_a_picture_is_served_from_its_folder_only(client, context, save):
    """Whatever the database holds, no other file of the PC is answered."""
    secret = context.data.root / "config.toml"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text("secret", encoding="utf-8")
    save(1, ticket(), photos={"1234567": "../config.toml"})
    assert client.get("/api/tickets/1234567/photo").status_code == 404
