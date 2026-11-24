"""Runner tests with a fake booker; no device required."""

import contextlib
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import court_booker.runner as runner
from court_booker.clock import NtpClock
from court_booker.config import Config
from court_booker.errors import (
    AppNotReadyError,
    DeviceNotRespondingError,
    NavigationError,
    QuotaFullError,
    SlotUnavailableError,
)
from court_booker.events import EventKind, MemorySink, Reporter
from court_booker.flow import Booked
from court_booker.screen import Node, Screen

FULL_SLOT = Node("18:00 - 19:00\nHết chỗ", (38, 1178, 263, 1262), True)


@pytest.fixture(autouse=True)
def quota(monkeypatch):
    """Note each read of the quota in the booker's events instead of reading the app."""
    failure = []

    def read_quota(booker, play_date, moment, report, slots=None):
        booker.events.append(("quota", play_date, moment, slots))
        if failure:
            raise failure[0]

    monkeypatch.setattr(runner, "read_quota", read_quota)
    return failure


class FakeBooker:
    def __init__(self, device, config, report=None, login_for=None, account_seen=None):
        self.login_for = login_for
        self.booked = []
        self.events = []
        self.commands = 0
        self.last_screen = Screen([FULL_SLOT])

    def prepare(self, restart=False):
        self.events.append("prepare")

    def locate_entry(self):
        self.events.append("locate")

    def check_home(self):
        self.events.append("check")

    def book(self, slot, target, dry_run=False):
        if slot == "18:00 - 19:00":
            raise SlotUnavailableError("Slot 18:00 - 19:00 is fully booked")
        self.booked.append(slot)
        return Booked(shown_court="S9 - Sân tennis")


class FakeDevice:
    def app_current(self):
        return {"package": "com.vinhomes.resident"}


def test_failed_round_does_not_stop_later_rounds(monkeypatch):
    monkeypatch.setattr(runner, "Booker", FakeBooker)
    config = Config(slots=["18:00 - 19:00", "19:00 - 20:00"])
    results = []

    returned = runner.run_booking(FakeDevice(), config, dry_run=True, results=results)

    assert returned is results
    assert [(r.slot, r.ok) for r in results] == [("18:00 - 19:00", False), ("19:00 - 20:00", True)]
    assert results[1].detail == "dry run passed"
    assert [r.court for r in results] == [None, "S9 - Sân tennis"]  # as the app showed it


class FakeClock:
    """Note each check of the time server in ``events``."""

    def __init__(self, events):
        self.events = events

    def now(self):
        return datetime(2026, 10, 10, 5, 45)  # the tests replace wait_until

    def measure(self):
        self.events.append("measure")

    def reading(self):
        return "06:00:00.100 (NTP), PC clock 05:59:59.343"


def test_entry_is_located_just_before_the_start_time(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="court_booker")
    events = []

    def make_booker(device, config, report=None, login_for=None, account_seen=None):
        booker = FakeBooker(device, config, report)
        booker.events = events
        return booker

    monkeypatch.setattr(runner, "Booker", make_booker)
    monkeypatch.setattr(runner, "wait_until", lambda target, now: events.append(target))
    start = datetime(2026, 10, 10, 6, 0)

    config = Config(slots=["19:00 - 20:00"], warm_up_seconds=60)
    runner.run_booking(
        FakeDevice(),
        config,
        start=start,
        clock=FakeClock(events),
        on_race=lambda: events.append("race"),
    )

    # Checked every minute from 05:46 until the deadline, 05:58, while waiting on the home screen.
    checks = [datetime(2026, 10, 10, 5, 46) + timedelta(minutes=minute) for minute in range(12)]
    assert events == [
        "prepare",
        ("quota", date(2026, 10, 12), "before", 1),  # what the app checks at 06:00
        "check",  # back on the home screen
        *[step for tick in checks for step in (tick, "check")],
        "race",  # the history waits in memory from the warm-up to the end of the rounds
        start - timedelta(seconds=60),
        "measure",  # once more, as Windows may have set the PC clock since the first check
        "locate",
        start - runner.LOCATE_AHEAD,
        "locate",
        start + timedelta(seconds=0.1),  # a tap before 06:00 by the app's clock is refused
    ]
    assert "Start reached at 06:00:00.100 (NTP), PC clock 05:59:59.343" in caplog.text


@pytest.mark.parametrize(
    ("answer", "offset", "logged"),
    [
        (0.012, 0.012, "Clock offset +0.012 s (-0.745 s since 05:50:03.000"),
        (None, 0.757, "Keeping the clock offset +0.757 s from 05:50:03.000"),
    ],
)
def test_the_clock_is_checked_again_at_the_warm_up(monkeypatch, caplog, answer, offset, logged):
    caplog.set_level(logging.INFO, logger="court_booker")
    monkeypatch.setattr(runner, "Booker", FakeBooker)
    monkeypatch.setattr(runner, "wait_until", lambda target, now: None)
    answers = iter([0.757, answer])
    clock = NtpClock(
        "time.google.com",
        lambda server: next(answers),
        lambda: datetime(2026, 10, 10, 5, 50, 3),
        lambda: 1000.0,
    )
    clock.measure()  # as the run does at 05:50, before connecting to the device

    runner.run_booking(
        FakeDevice(), Config(slots=["19:00 - 20:00"]), start=datetime(2026, 10, 10, 6), clock=clock
    )

    assert clock.offset == offset
    assert logged in caplog.text


def test_failed_warm_up_is_retried_just_before_the_start(monkeypatch, caplog):
    class SlowListBooker(FakeBooker):
        def locate_entry(self):
            self.events.append("locate")
            if self.events.count("locate") == 1:
                raise NavigationError("Tapped 'Tiện ích' but the next screen did not appear")

    bookers = []

    def make_booker(device, config, report=None, login_for=None, account_seen=None):
        bookers.append(SlowListBooker(device, config, report))
        return bookers[-1]

    monkeypatch.setattr(runner, "Booker", make_booker)
    monkeypatch.setattr(runner, "wait_until", lambda target, now: None)

    results = runner.run_booking(
        FakeDevice(),
        Config(slots=["19:00 - 20:00"]),
        start=datetime(2026, 10, 10, 6, 0),
        clock=FakeClock([]),  # 05:45: time to repair before the start
    )

    # The app made ready again, then the list opened at once, and read just before the start.
    steps = ["prepare", "locate", "prepare", "locate", "locate"]
    assert [e for e in bookers[0].events if e != "check" and e[0] != "quota"] == steps
    assert results[0].ok
    assert "The run was no longer ready: Tapped 'Tiện ích' but the next screen" in caplog.text


def test_failed_round_logs_the_last_screen(monkeypatch, caplog):
    monkeypatch.setattr(runner, "Booker", FakeBooker)
    caplog.set_level(logging.DEBUG, logger="court_booker")
    config = Config(slots=["18:00 - 19:00", "19:00 - 20:00"])

    runner.run_booking(FakeDevice(), config, dry_run=True)

    messages = [record.getMessage() for record in caplog.records]
    error = messages.index("Slot 18:00 - 19:00 is fully booked")
    last_screen = (
        "Last screen read (1 elements):\n  [38,1178][263,1262] clickable '18:00 - 19:00\\nHết chỗ'"
    )
    assert messages[error + 1] == last_screen
    assert messages.count(last_screen) == 1


def test_failed_preparation_logs_the_last_screen(monkeypatch, caplog):
    class LoggedOutBooker(FakeBooker):
        def prepare(self, restart=False):
            raise AppNotReadyError("The app did not show 'Tiện ích'")

    monkeypatch.setattr(runner, "Booker", LoggedOutBooker)
    caplog.set_level(logging.DEBUG, logger="court_booker")

    with pytest.raises(AppNotReadyError):
        runner.run_booking(FakeDevice(), Config(slots=["19:00 - 20:00"]))

    assert "Last screen read (1 elements):" in caplog.text


class ShotDevice(FakeDevice):
    """A device that saves a fake screenshot; ``shots`` names each one."""

    def __init__(self):
        self.shots = []

    def screenshot(self, filename):
        Path(filename).write_bytes(b"\x89PNG fake")
        self.shots.append(Path(filename).name)


class StuckBooker(FakeBooker):
    """Fails every slot on a screen it did not know, as the popup of 2026-11-17 did."""

    def book(self, slot, target, dry_run=False):
        raise NavigationError("Could not return to the utilities list")


def shots_of(monkeypatch, tmp_path, booker, slots, dry_run=False):
    """Run ``booker`` on ``slots`` and return the screenshots saved and the steps."""
    monkeypatch.setattr(runner, "Booker", booker)
    device, sink = ShotDevice(), MemorySink()
    with contextlib.suppress(AppNotReadyError):  # the preparation's failure ends the run
        runner.run_booking(
            device, Config(slots=slots), dry_run=dry_run, report=Reporter(sink), screens=tmp_path
        )
    return device.shots, [event for event in sink.events if event.kind is EventKind.SCREEN_SAVED]


def test_a_run_that_books_takes_no_screenshot(monkeypatch, tmp_path):
    shots, steps = shots_of(monkeypatch, tmp_path, FakeBooker, ["19:00 - 20:00"])

    assert shots == [] and steps == []


def test_a_failure_the_app_explained_takes_no_screenshot(monkeypatch, tmp_path):
    shots, _ = shots_of(monkeypatch, tmp_path, FakeBooker, ["19:00 - 20:00", "18:00 - 19:00"])

    assert shots == []  # "fully booked" is in the log word for word


def test_an_unexplained_failure_of_the_last_round_saves_the_screen(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="court_booker")

    shots, steps = shots_of(monkeypatch, tmp_path, StuckBooker, ["18:00 - 19:00", "19:00 - 20:00"])

    assert len(shots) == 1 and shots[0].endswith("-mumu0.png")
    assert steps[0].data == {"path": str(tmp_path / shots[0])}
    assert "Screen not saved: the next round goes first" in caplog.text  # the first round's
    assert f"Saved the screen at the failure: {tmp_path / shots[0]}" in caplog.text


def test_an_app_not_made_ready_saves_the_screen(monkeypatch, tmp_path):
    class LoggedOutBooker(FakeBooker):
        def prepare(self, restart=False):
            raise AppNotReadyError("The app is logged out")

    shots, steps = shots_of(monkeypatch, tmp_path, LoggedOutBooker, ["19:00 - 20:00"])

    assert len(shots) == 1 and len(steps) == 1


def test_a_dry_run_takes_no_screenshot(monkeypatch, tmp_path):
    shots, _ = shots_of(monkeypatch, tmp_path, StuckBooker, ["19:00 - 20:00"], dry_run=True)

    assert shots == []


def test_a_screenshot_that_fails_never_costs_the_run(monkeypatch, tmp_path, caplog):
    class BrokenDevice(ShotDevice):
        def screenshot(self, filename):
            raise RuntimeError("adb screencap gave no PNG")

    monkeypatch.setattr(runner, "Booker", StuckBooker)
    results = runner.run_booking(BrokenDevice(), Config(slots=["19:00 - 20:00"]), screens=tmp_path)

    assert [r.ok for r in results] == [False]
    assert "Could not save the screen" in caplog.text


def test_only_the_newest_screenshots_are_kept(monkeypatch, tmp_path):
    for day in range(1, runner.SCREENS_KEPT + 5):
        (tmp_path / f"2026-10-{day:02d}-060000-mumu0.png").write_bytes(b"old")

    shots, _ = shots_of(monkeypatch, tmp_path, StuckBooker, ["19:00 - 20:00"])

    kept = sorted(path.name for path in tmp_path.glob("*.png"))
    assert len(kept) == runner.SCREENS_KEPT
    assert shots[0] in kept and "2026-10-01-060000-mumu0.png" not in kept


def test_events_follow_the_run(monkeypatch):
    monkeypatch.setattr(runner, "Booker", FakeBooker)
    sink = MemorySink()
    config = Config(slots=["18:00 - 19:00", "19:00 - 20:00"])

    runner.run_booking(FakeDevice(), config, dry_run=True, report=Reporter(sink))

    assert sink.kinds == [
        EventKind.APP_READY,
        EventKind.BOOKING_STARTED,
        EventKind.SLOT_STARTED,
        EventKind.SLOT_FAILED,
        EventKind.SLOT_STARTED,
        EventKind.SLOT_BOOKED,
    ]
    started, failed, booked = sink.events[1], sink.events[3], sink.events[5]
    assert started.data["court"] == config.court
    assert started.data["slots"] == ["18:00 - 19:00", "19:00 - 20:00"]
    assert started.data["dry_run"] is True
    assert sink.events[2].data == {"slot": "18:00 - 19:00", "round": 1, "rounds": 2}
    assert failed.data["reason"] == "Slot 18:00 - 19:00 is fully booked"
    assert booked.data["slot"] == "19:00 - 20:00"
    assert booked.data["commands"] == 0
    assert booked.data["shown_court"] == "S9 - Sân tennis"
    assert "ticket" not in booked.data  # details not found are left out


def test_timed_run_reports_the_wait(monkeypatch):
    monkeypatch.setattr(runner, "Booker", FakeBooker)
    monkeypatch.setattr(runner, "wait_until", lambda target, now: None)
    sink = MemorySink()
    start = datetime(2026, 10, 13, 6, 0)

    runner.run_booking(
        FakeDevice(), Config(slots=["19:00 - 20:00"]), start=start, report=Reporter(sink)
    )

    assert sink.kinds[:3] == [EventKind.APP_READY, EventKind.WAITING, EventKind.BOOKING_STARTED]
    assert sink.events[1].data == {"until": "2026-10-13T06:00:00"}
    assert sink.events[2].data["date"] == "2026-10-15"


def test_a_frozen_device_ends_the_run_after_its_round(monkeypatch):
    class FrozenBooker(FakeBooker):
        def book(self, slot, target, dry_run=False):
            raise DeviceNotRespondingError("MuMu did not answer dump_hierarchy within 60 s")

    monkeypatch.setattr(runner, "Booker", FrozenBooker)
    sink = MemorySink()
    results = []
    config = Config(slots=["18:00 - 19:00", "19:00 - 20:00"])

    with pytest.raises(DeviceNotRespondingError):
        runner.run_booking(FakeDevice(), config, results=results, report=Reporter(sink))

    assert [(r.slot, r.ok) for r in results] == [("18:00 - 19:00", False)]
    assert sink.kinds[-1] is EventKind.SLOT_FAILED
    assert sink.events[-1].data["reason"] == "MuMu did not answer dump_hierarchy within 60 s"


QUOTA = "Booking quota used up: Căn hộ đã hết hạn mức đăng ký tiện ích cho phép."


@pytest.mark.parametrize("failing", [0, 1])
def test_the_quota_notice_skips_the_rounds_left(monkeypatch, caplog, failing):
    slots = ["16:00 - 17:00", "17:00 - 18:00", "18:00 - 19:00"]
    tried = []

    class QuotaBooker(FakeBooker):
        def book(self, slot, target, dry_run=False):
            tried.append(slot)
            if slot == slots[failing]:
                raise QuotaFullError(QUOTA)
            return super().book(slot, target, dry_run)

    monkeypatch.setattr(runner, "Booker", QuotaBooker)
    sink = MemorySink()
    results = []

    runner.run_booking(FakeDevice(), Config(slots=slots), results=results, report=Reporter(sink))

    assert tried == slots[: failing + 1]  # the rounds left never reach the device
    assert [(r.slot, r.ok, r.detail) for r in results[failing:]] == [
        (slots[failing], False, QUOTA),
        *[(slot, False, runner.QUOTA_SKIPPED) for slot in slots[failing + 1 :]],
    ]
    assert sink.events[-1].data == {
        "slot": slots[2],
        "reason": "Skipped: the booking quota is used up",
        "seconds": 0.0,
        "commands": 0,
    }
    assert sink.kinds.count(EventKind.SLOT_STARTED) == failing + 1
    assert f"Booking quota used up; skipping {', '.join(slots[failing + 1 :])}" in caplog.text


@pytest.mark.parametrize(
    ("ahead", "hurry"), [(timedelta(minutes=15), False), (timedelta(seconds=90), True)]
)
def test_a_run_begun_near_its_start_hurries(monkeypatch, ahead, hurry):
    made = []

    def make_booker(device, config, report=None, login_for=None, account_seen=None):
        made.append(FakeBooker(device, config, report, login_for, account_seen))
        return made[-1]

    monkeypatch.setattr(runner, "Booker", make_booker)
    monkeypatch.setattr(runner, "wait_until", lambda moment, now: None)
    clock = FakeClock([])
    runner.run_booking(FakeDevice(), Config(slots=["a"]), start=clock.now() + ahead, clock=clock)
    assert made[0].hurry is hurry


def test_a_run_without_a_start_never_holds_the_history(monkeypatch):
    monkeypatch.setattr(runner, "Booker", FakeBooker)
    raced = []

    results = runner.run_booking(
        FakeDevice(), Config(slots=["19:00 - 20:00"]), dry_run=True, on_race=lambda: raced.append(1)
    )

    assert raced == []  # its steps show as they happen
    assert [result.ok for result in results] == [True]


def test_the_booker_is_handed_over_before_anything_runs(monkeypatch):
    monkeypatch.setattr(runner, "Booker", FakeBooker)
    handed = []

    def on_booker(booker):
        handed.append((booker, list(booker.events)))

    runner.run_booking(
        FakeDevice(), Config(slots=["19:00 - 20:00"]), dry_run=True, on_booker=on_booker
    )

    (booker, events), *others = handed
    assert isinstance(booker, FakeBooker)
    assert events == []
    assert others == []


class LateClock(FakeClock):
    def now(self):
        return datetime(2026, 10, 10, 5, 56)


@pytest.mark.parametrize(("clock", "read"), [(FakeClock, True), (LateClock, False)])
def test_the_quota_is_read_unless_the_start_is_near(monkeypatch, clock, read):
    events = []

    def make_booker(device, config, report=None, login_for=None, account_seen=None):
        booker = FakeBooker(device, config, report)
        booker.events = events
        return booker

    monkeypatch.setattr(runner, "Booker", make_booker)
    monkeypatch.setattr(runner, "wait_until", lambda target, now: None)
    config = Config(slots=["18:00 - 19:00", "19:00 - 20:00"])

    runner.run_booking(FakeDevice(), config, start=datetime(2026, 10, 10, 6), clock=clock([]))

    quota = [event for event in events if event[0] == "quota"]
    assert quota == ([("quota", date(2026, 10, 12), "before", 2)] if read else [])


def test_a_quota_not_read_still_books(monkeypatch, caplog, quota):
    events = []

    def make_booker(device, config, report=None, login_for=None, account_seen=None):
        booker = FakeBooker(device, config, report)
        booker.events = events
        return booker

    quota.append(NavigationError("The history page did not show"))
    monkeypatch.setattr(runner, "Booker", make_booker)
    config = Config(slots=["19:00 - 20:00"])

    results = runner.run_booking(FakeDevice(), config, dry_run=True)

    assert events[1:3] == [("quota", events[1][1], "before", 1), "check"]
    assert [result.ok for result in results] == [True]
    assert "Quota not read: The history page did not show" in caplog.text
