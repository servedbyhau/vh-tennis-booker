"""Tests for the Zalo Bot client, with the network replaced."""

import json
import logging

import pytest

from court_booker import credentials, zalo
from court_booker.zalo import (
    Bot,
    Chat,
    Link,
    NoMessageError,
    ZaloError,
    ZaloTokenError,
    forget_link,
    read_link,
    save_link,
    send_report,
    send_tickets,
)

TOKEN = "1234:secret-token"
LINK = Link(TOKEN, Chat("chat-1", "Hậu"))


class FakeZalo:
    """The Bot API: answers in turn, and the requests it got as ``(method, body, type)``."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.asked = []

    def __call__(self, url, body, content_type, timeout):
        assert url.startswith(f"https://bot-api.zaloplatforms.com/bot{TOKEN}/")
        self.asked.append((url.rsplit("/", 1)[1], body, content_type))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        status, data = answer
        return status, json.dumps(data).encode()

    def json(self, index=-1):
        return json.loads(self.asked[index][1])


def ok(result=None):
    return 200, {"ok": True, "result": result or {}}


def message(chat_id="chat-1", name="Hậu", is_bot=False):
    return {
        "event_name": "message.text.received",
        "message": {
            "from": {"id": chat_id, "display_name": name, "is_bot": is_bot},
            "chat": {"id": chat_id, "chat_type": "PRIVATE"},
            "text": "hi",
        },
    }


def test_the_token_is_checked_by_the_bot_s_name():
    api = FakeZalo(ok({"id": "1", "account_name": "bot.Court", "account_type": "BASIC"}))

    assert Bot(TOKEN, api).check() == "bot.Court"
    assert api.asked[0][0] == "getMe"


@pytest.mark.parametrize("status", [401, 404])
def test_a_token_zalo_does_not_know_is_told_apart(status):
    with pytest.raises(ZaloTokenError) as raised:
        Bot(TOKEN, FakeZalo((status, {"ok": False, "description": "Unauthorized"}))).check()
    assert TOKEN not in str(raised.value)


def test_the_chat_is_whoever_wrote_to_the_bot():
    api = FakeZalo(ok(message()))

    assert Bot(TOKEN, api).next_chat(10) == Chat("chat-1", "Hậu")
    assert api.asked[0][0] == "getUpdates"
    assert api.json() == {"timeout": "10"}


def test_of_several_messages_the_last_person_s_is_taken():
    api = FakeZalo(ok([message("a", "An"), message("b", "Bình"), message("c", "Bot", True)]))

    assert Bot(TOKEN, api).next_chat(5) == Chat("b", "Bình")


@pytest.mark.parametrize("answer", [(408, {"ok": False}), ok({}), ok({"event_name": "x"})])
def test_no_message_is_told_apart(answer):
    with pytest.raises(NoMessageError):
        Bot(TOKEN, FakeZalo(answer)).next_chat(5)


def test_a_message_is_sent_as_json_and_cut_to_what_zalo_takes():
    api = FakeZalo(ok())

    Bot(TOKEN, api).send_text("chat-1", "x" * 2500)

    name, _, content_type = api.asked[0]
    assert (name, content_type) == ("sendMessage", "application/json")
    sent = api.json()
    assert sent["chat_id"] == "chat-1"
    assert len(sent["text"]) == zalo.LONGEST_TEXT


def test_a_picture_is_sent_as_a_file(tmp_path):
    picture = tmp_path / "1234567.png"
    picture.write_bytes(b"\x89PNG picture")
    api = FakeZalo(ok())

    Bot(TOKEN, api).send_photo("chat-1", picture, "S6 · 30/11")

    name, body, content_type = api.asked[0]
    assert name == "sendPhoto"
    assert content_type.startswith("multipart/form-data; boundary=")
    assert b'name="chat_id"\r\n\r\nchat-1\r\n' in body
    assert 'name="caption"\r\n\r\nS6 · 30/11\r\n'.encode() in body
    assert b'filename="1234567.png"\r\nContent-Type: image/png\r\n\r\n\x89PNG picture' in body


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        ((422, {"ok": False, "description": "not allowed"}), 422),
        ((200, {"ok": False, "error_code": 429, "description": "Quota exceeded"}), 429),
        ((500, None), 500),
    ],
)
def test_a_refusal_keeps_zalo_s_code(answer, code):
    with pytest.raises(ZaloError) as raised:
        Bot(TOKEN, FakeZalo(answer)).send_text("chat-1", "hi")
    assert raised.value.code == code
    assert not isinstance(raised.value, ZaloTokenError)


def test_no_network_never_shows_the_token():
    error = OSError(f"cannot reach https://bot-api.zaloplatforms.com/bot{TOKEN}/sendMessage")

    with pytest.raises(ZaloError) as raised:
        Bot(TOKEN, FakeZalo(error)).send_text("chat-1", "hi")
    assert TOKEN not in str(raised.value)
    assert raised.value.code is None


def test_the_link_is_kept_in_the_vault_and_forgotten():
    store = credentials.MemoryStore()
    assert read_link(store) is None

    save_link(store, LINK)
    assert read_link(store) == LINK
    assert store.logins[credentials.ZALO].phone == "chat-1"
    assert TOKEN not in repr(read_link(store))

    forget_link(store)
    assert read_link(store) is None


def test_an_unreadable_link_reads_as_none(caplog):
    store = credentials.MemoryStore()
    store.save(credentials.ZALO, credentials.Login("chat-1", "not json"))

    assert read_link(store) is None
    assert "Zalo link could not be read" in caplog.text


def test_the_link_has_a_vault_name_of_its_own(monkeypatch):
    monkeypatch.delenv(credentials.HOME_ENV, raising=False)

    assert credentials.target(credentials.ZALO) == "CourtBooker/zalo"


def test_a_report_that_fails_only_logs(caplog):
    api = FakeZalo((422, {"ok": False, "description": "not allowed"}))

    with caplog.at_level(logging.WARNING):
        assert send_report(LINK, "Đặt sân 30/11: 2/2 thành công", api) is False
    assert "Zalo message not sent" in caplog.text
    assert TOKEN not in caplog.text


def test_a_report_is_sent(caplog):
    api = FakeZalo(ok())

    assert send_report(LINK, "Đặt sân", api) is True
    assert api.json()["text"] == "Đặt sân"


def test_a_picture_that_fails_costs_no_other(tmp_path):
    pictures = [(tmp_path / f"{code}.png", f"Mã vé {code}") for code in ("1", "2", "3")]
    for picture, _ in pictures:
        picture.write_bytes(b"png")
    pictures[1][0].unlink()  # gone from the folder
    api = FakeZalo(ok(), (422, {"ok": False}))

    assert send_tickets(LINK, pictures, api) == 1
    assert [name for name, _, _ in api.asked] == ["sendPhoto", "sendPhoto"]
