"""Telegram tests with a fake HTTP post; no network required."""

import urllib.error
import urllib.parse

from court_booker.notify import format_summary, send_telegram
from court_booker.runner import RoundResult

RESULTS = [
    RoundResult("18:00 - 19:00", True, "booked", 4.2),
    RoundResult("19:00 - 20:00", False, "Slot 19:00 - 20:00 is fully booked", 2.1),
]


def test_format_summary():
    text = format_summary(RESULTS)
    assert text.splitlines() == [
        "court-booker: 1/2 ok",
        "OK 18:00 - 19:00: booked",
        "FAIL 19:00 - 20:00: Slot 19:00 - 20:00 is fully booked",
    ]


def test_format_summary_with_run_error():
    text = format_summary([], error="MuMu did not start", dry_run=True)
    assert text.splitlines() == ["court-booker: 0/0 ok (dry run)", "Error: MuMu did not start"]


def test_send_telegram_posts_chat_and_text():
    sent = []
    assert send_telegram("123:abc", "42", "hello", post=lambda url, data: sent.append((url, data)))
    url, data = sent[0]
    assert url == "https://api.telegram.org/bot123:abc/sendMessage"
    assert urllib.parse.parse_qs(data.decode()) == {"chat_id": ["42"], "text": ["hello"]}


def test_send_telegram_failure_is_logged_not_raised(caplog):
    def post(url, data):
        raise urllib.error.URLError("no network")

    assert send_telegram("123:secret", "42", "hello", post=post) is False
    assert "no network" in caplog.text
    assert "secret" not in caplog.text
