"""Tests for the Zalo routes, with the Bot API replaced: no request leaves the PC."""

import json

import pytest

from court_booker import credentials, history_read, zalo
from court_booker.api import zalo as zalo_routes
from court_booker.config import Config, load_config, save_config
from court_booker.zalo import Chat, Link, read_link, save_link

TOKEN = "1234:secret-token"


class FakeZalo:
    """The Bot API by method: each answers ``(status, data)``; the calls as ``(method, body)``."""

    def __init__(self):
        self.answers = {
            "getMe": (200, {"ok": True, "result": {"account_name": "bot.Court"}}),
            "getUpdates": (
                200,
                {
                    "ok": True,
                    "result": {
                        "message": {
                            "from": {"id": "chat-1", "display_name": "Hậu", "is_bot": False},
                            "chat": {"id": "chat-1", "chat_type": "PRIVATE"},
                            "text": "hi",
                        }
                    },
                },
            ),
            "sendMessage": (200, {"ok": True, "result": {"message_id": "1"}}),
        }
        self.calls = []

    def __call__(self, url, body, content_type, timeout):
        method = url.rsplit("/", 1)[1]
        self.calls.append((method, json.loads(body)))
        status, data = self.answers[method]
        return status, json.dumps(data).encode()


@pytest.fixture
def api(monkeypatch):
    fake = FakeZalo()
    monkeypatch.setattr(zalo, "http_post", fake)
    monkeypatch.setattr(zalo_routes, "WAIT_FOR_MESSAGE", 1.0)
    return fake


def steps(context):
    connection = history_read.open_read_only(context.data.database)
    found = history_read.list_events(connection)
    connection.close()
    return [step["data"]["changed"] for step in found]


def test_nothing_is_linked_at_first(client, context):
    assert client.get("/api/zalo").json() == {"linked": False, "name": None, "enabled": True}
    assert not context.config_path.exists()


def test_linking_finds_who_wrote_to_the_bot_and_writes_back(client, context, api, saved_logins):
    save_config(Config(zalo_notification=False), context.config_path)

    response = client.post("/api/zalo/link", json={"token": f" {TOKEN} "})

    assert response.json() == {"linked": True, "name": "Hậu", "enabled": True}
    assert TOKEN not in response.text
    assert [method for method, _ in api.calls] == ["getMe", "getUpdates", "sendMessage"]
    assert api.calls[2][1]["chat_id"] == "chat-1"
    assert api.calls[2][1]["text"].startswith("Court Booker đã kết nối.")
    assert read_link(saved_logins) == Link(TOKEN, Chat("chat-1", "Hậu"))
    assert load_config(context.config_path).zalo_notification is True
    assert steps(context) == [["zalo_notification"], ["zalo_link"]]  # newest first


@pytest.mark.parametrize(
    ("method", "answer", "status", "error"),
    [
        ("getMe", (401, {"ok": False, "description": "Unauthorized"}), 400, "zalo_token"),
        ("getUpdates", (408, {"ok": False}), 409, "zalo_no_message"),
        ("sendMessage", (422, {"ok": False, "description": "not allowed"}), 503, "zalo"),
    ],
)
def test_a_link_that_failed_saves_nothing(
    client, context, api, saved_logins, method, answer, status, error
):
    api.answers[method] = answer

    response = client.post("/api/zalo/link", json={"token": TOKEN})

    assert (response.status_code, response.json()["error"]) == (status, error)
    assert TOKEN not in response.text
    assert read_link(saved_logins) is None
    assert not context.config_path.exists()


def test_no_network_answers_503(client, monkeypatch):
    def offline(url, body, content_type, timeout):
        raise OSError("no network")

    monkeypatch.setattr(zalo, "http_post", offline)

    response = client.post("/api/zalo/link", json={"token": TOKEN})

    assert (response.status_code, response.json()["error"]) == (503, "zalo")


def test_the_switch_reaches_the_file(client, context, saved_logins):
    save_link(saved_logins, Link(TOKEN, Chat("chat-1", "Hậu")))

    response = client.put("/api/zalo", json={"enabled": False})

    assert response.json() == {"linked": True, "name": "Hậu", "enabled": False}
    assert load_config(context.config_path).zalo_notification is False
    assert steps(context) == [["zalo_notification"]]


def test_unlinking_forgets_the_bot(client, context, saved_logins):
    save_link(saved_logins, Link(TOKEN, Chat("chat-1", "Hậu")))

    assert client.delete("/api/zalo").status_code == 204

    assert saved_logins.read(credentials.ZALO) is None
    assert client.get("/api/zalo").json()["linked"] is False


def test_a_test_message_goes_to_the_linked_chat(client, context, api, saved_logins):
    save_link(saved_logins, Link(TOKEN, Chat("chat-1", "Hậu")))
    save_config(Config(notification_language="en"), context.config_path)

    assert client.post("/api/zalo/test").status_code == 204

    ((method, body),) = api.calls
    assert method == "sendMessage"
    assert body["text"].startswith("Court Booker is linked.")


def test_a_test_message_needs_a_link(client):
    response = client.post("/api/zalo/test")

    assert (response.status_code, response.json()["error"]) == (409, "zalo_unlinked")


def test_a_short_token_is_refused(client):
    response = client.post("/api/zalo/link", json={"token": "x"})

    assert (response.status_code, response.json()["error"]) == (422, "invalid_request")
