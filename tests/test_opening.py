"""The log of the opening: the clocks and the first round's calendar."""

from datetime import datetime, timedelta

from court_booker.events import EventKind, MemorySink, Reporter
from court_booker.opening import DeviceClock, Opening, OpeningWatch, read_device_clock

START = datetime(2026, 11, 25, 6, 0, 0, 100000)


def ticking(*moments):
    times = iter(moments)
    return lambda: next(times)


def test_android_s_clock_is_told_against_the_middle_of_its_read():
    before = datetime(2026, 11, 25, 5, 59, 0)
    after = before + timedelta(milliseconds=60)
    android = (before + timedelta(milliseconds=30) - timedelta(milliseconds=150)).timestamp()

    read = read_device_clock(lambda: android, ticking(before, after), reads=1)

    assert read == DeviceClock(-0.15, 0.03)


def test_the_read_of_the_shortest_round_trip_is_kept():
    at = datetime(2026, 11, 25, 5, 59, 0)
    times = [at, at + timedelta(milliseconds=140), at, at + timedelta(milliseconds=40)]
    times += [at, at + timedelta(milliseconds=90)]
    android = iter([at.timestamp() + 0.2, at.timestamp() + 0.02, at.timestamp() + 0.1])

    read = read_device_clock(lambda: next(android), ticking(*times))

    assert read == DeviceClock(0.0, 0.02)


def test_a_clock_that_cannot_be_read_tells_nothing():
    def fail():
        raise OSError("adb gone")

    assert read_device_clock(fail, datetime.now) is None  # none of the three succeeded


def test_the_watch_notes_the_first_calendar_and_passes_every_event_on():
    sink = MemorySink()
    opened = START + timedelta(milliseconds=900)
    watch = OpeningWatch(Reporter(sink), ticking(opened, opened + timedelta(seconds=9)))

    watch(EventKind.SLOT_STARTED, slot="18:00 - 19:00", round=1, rounds=2)
    watch(EventKind.CALENDAR_OPENED, attempt=3)
    watch(EventKind.CALENDAR_OPENED, attempt=1)  # a later one is not the opening

    assert (watch.opened, watch.attempt) == (opened, 3)
    assert [event.kind for event in sink.events] == [
        EventKind.SLOT_STARTED,
        EventKind.CALENDAR_OPENED,
        EventKind.CALENDAR_OPENED,
    ]


def opening(**fields):
    values = {
        "start": START,
        "pc_offset": 0.152,
        "before": DeviceClock(-0.137, 0.025),
        "after": DeviceClock(-0.140, 0.020),
        "first_tap": START + timedelta(milliseconds=5),
        "opened": START + timedelta(milliseconds=905),
        "attempt": 2,
    }
    return Opening(**{**values, **fields})


def test_the_opening_is_told_in_one_line():
    assert opening().describe() == (
        "Opening: PC clock -0.152 s from NTP, Android -0.137 s (±0.025) at the warm-up and"
        " -0.140 s (±0.020) after the rounds; first tap at 06:00:00.105 NTP"
        " (05:59:59.968 on Android), calendar at 06:00:01.005 NTP after 0.9 s, attempt 2"
    )


def test_the_event_holds_every_fact():
    assert opening().event_data() == {
        "start": "2026-11-25T06:00:00.100",
        "pc_offset": 0.152,
        "device_before": {"offset": -0.137, "spread": 0.025},
        "device_after": {"offset": -0.14, "spread": 0.02},
        "first_tap": "2026-11-25T06:00:00.105",
        "device_first_tap": "2026-11-25T05:59:59.968",
        "calendar_opened": "2026-11-25T06:00:01.005",
        "seconds_to_calendar": 0.9,
        "attempt": 2,
    }


def test_what_was_not_read_is_told_so():
    told = opening(pc_offset=None, before=None, after=None, opened=None, attempt=None)

    assert told.describe() == (
        "Opening: PC clock not known from NTP, Android not read at the warm-up and not read"
        " after the rounds; first tap at 06:00:00.105 NTP (- on Android), calendar at - NTP"
        " after None s, attempt None"
    )
    assert told.event_data()["device_first_tap"] is None
