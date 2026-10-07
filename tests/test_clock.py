"""Start-time tests with fake clocks; no network required."""

import struct
from datetime import datetime, timedelta

import pytest

from court_booker.clock import offset_from_reply, resolve_start, wait_until
from court_booker.errors import RequestError

NOW = datetime(2026, 10, 8, 5, 45, 0)


def test_resolve_start_later_today():
    assert resolve_start("06:00", NOW) == datetime(2026, 10, 8, 6, 0, 0)
    assert resolve_start("06:00:30", NOW) == datetime(2026, 10, 8, 6, 0, 30)


def test_resolve_start_slightly_late_still_runs():
    assert resolve_start("05:40", NOW) == datetime(2026, 10, 8, 5, 40)


def test_resolve_start_long_passed_is_rejected():
    with pytest.raises(RequestError, match="already passed"):
        resolve_start("05:00", NOW)


@pytest.mark.parametrize("text", ["6h", "25:00", "06:00 AM", ""])
def test_resolve_start_rejects_bad_format(text):
    with pytest.raises(RequestError, match="Invalid start time"):
        resolve_start(text, NOW)


class FakeClock:
    def __init__(self, start):
        self.now_value = start
        self.sleeps = []

    def now(self):
        return self.now_value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now_value += timedelta(seconds=seconds)


def test_wait_until_ends_on_time_with_fine_steps_at_the_end():
    clock = FakeClock(NOW)
    target = datetime(2026, 10, 8, 6, 0)

    wait_until(target, now=clock.now, sleep=clock.sleep)

    assert clock.now_value >= target
    assert clock.now_value - target < timedelta(milliseconds=2)
    assert max(clock.sleeps) <= 30
    assert clock.sleeps[-1] <= 0.001


def test_wait_until_applies_offset():
    clock = FakeClock(NOW)
    # The PC is 2 s slow, so the true 06:00:00 is local 05:59:58.
    wait_until(datetime(2026, 10, 8, 6, 0), offset=2.0, now=clock.now, sleep=clock.sleep)
    assert abs((clock.now_value - datetime(2026, 10, 8, 5, 59, 58)).total_seconds()) < 0.002


def test_wait_until_past_target_returns_at_once():
    clock = FakeClock(NOW)
    wait_until(NOW - timedelta(minutes=1), now=clock.now, sleep=clock.sleep)
    assert clock.sleeps == []


def ntp_reply(server_seconds):
    seconds = int(server_seconds) + 2_208_988_800
    fraction = int((server_seconds % 1) * 2**32)
    timestamp = struct.pack("!II", seconds, fraction)
    return bytes(32) + timestamp + timestamp


def test_offset_from_reply():
    # Sent at 1000.0, received at 1000.2; the server stamped 1001.6 in the middle.
    offset = offset_from_reply(ntp_reply(1001.6), sent=1000.0, received=1000.2)
    assert offset == pytest.approx(1.5, abs=1e-6)


def test_offset_from_short_reply_is_none():
    assert offset_from_reply(b"\x00" * 10, 0.0, 0.0) is None
