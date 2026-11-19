"""Runner tests with a fake booker; no device required."""

import contextlib
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import court_booker.runner as runner
from court_booker.clock import NtpClock
from court_booker.config import Config
from court_booker.errors import (
    AdbNotFoundError,
    AppNotReadyError,
    CourtBookerError,
    DeviceConnectionError,
    DeviceNotRespondingError,
    DriverError,
    DriverUnavailableError,
    LoggedOutError,
    LoginFailedError,
    NavigationError,
    QuotaFullError,
    SlotUnavailableError,
)
from court_booker.events import EventKind, MemorySink, Reporter
from court_booker.flow import Booked
from court_booker.screen import Node, Screen
from court_booker.watchdog import GuardedDevice, Watchdog

FULL_SLOT = Node("18:00 - 19:00\nHết chỗ", (38, 1178, 263, 1262), True)


class FakeBooker:
    def __init__(self, device, config, report=None, login_for=None):
        self.login_for = login_for
        self.booked = []
        self.events = []
        self.commands = 0
        self.last_screen = Screen([FULL_SLOT])

    def prepare(self, restart=False):
        self.events.append("prepare")

    def locate_entry(self):
        self.events.append("locate")

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
        raise AssertionError("the tests replace wait_until")

    def measure(self):
        self.events.append("measure")

    def reading(self):
        return "06:00:00.100 (NTP), PC clock 05:59:59.343"


def test_entry_is_located_just_before_the_start_time(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="court_booker")
    events = []

    def make_booker(device, config, report=None, login_for=None):
        booker = FakeBooker(device, config, report)
        booker.events = events
        return booker

    monkeypatch.setattr(runner, "Booker", make_booker)
    monkeypatch.setattr(runner, "wait_until", lambda target, now: events.append(target))
    start = datetime(2026, 10, 10, 6, 0)

    config = Config(slots=["19:00 - 20:00"], warm_up_seconds=60)
    runner.run_booking(FakeDevice(), config, start=start, clock=FakeClock(events))

    assert events == [
        "prepare",
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

    def make_booker(device, config, report=None, login_for=None):
        bookers.append(SlowListBooker(device, config, report))
        return bookers[-1]

    monkeypatch.setattr(runner, "Booker", make_booker)
    monkeypatch.setattr(runner, "wait_until", lambda target, now: None)

    results = runner.run_booking(
        FakeDevice(), Config(slots=["19:00 - 20:00"]), start=datetime(2026, 10, 10, 6, 0)
    )

    assert bookers[0].events == ["prepare", "locate", "locate"]
    assert results[0].ok
    assert "Could not open the utilities list yet" in caplog.text


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


class FailingPrepareBooker(FakeBooker):
    """Fails ``prepare`` with the next of ``errors`` while any is left; records each try."""

    def __init__(self, device, config, report=None, login_for=None):
        super().__init__(device, config, report, login_for)
        self.errors = []

    def prepare(self, restart=False):
        self.events.append(f"prepare restart={restart}")
        if self.errors:
            raise self.errors.pop(0)


def prepare_tries(monkeypatch, errors, start=None, now=None):
    """Run with ``prepare`` failing with ``errors``; return the tries and the results."""
    events = []

    def make_booker(device, config, report=None, login_for=None):
        booker = FailingPrepareBooker(device, config, report)
        booker.errors = list(errors)
        booker.events = events
        return booker

    class Clock(FakeClock):
        def now(self):
            return now

    monkeypatch.setattr(runner, "Booker", make_booker)
    monkeypatch.setattr(runner, "wait_until", lambda target, now: None)
    config = Config(slots=["19:00 - 20:00"], warm_up_seconds=60)
    results = []
    try:
        runner.run_booking(
            FakeDevice(), config, start=start, clock=Clock([]), results=results, dry_run=True
        )
    except CourtBookerError as exc:
        return [e for e in events if e.startswith("prepare")], exc
    return [e for e in events if e.startswith("prepare")], results


def test_an_app_not_ready_is_restarted_and_prepared_again(monkeypatch, caplog):
    tries, results = prepare_tries(
        monkeypatch, [AppNotReadyError("Could not return to the home screen")]
    )

    assert tries == ["prepare restart=False", "prepare restart=True"]
    assert [r.ok for r in results] == [True]
    assert "The app is not ready (Could not return to the home screen); restarting it" in (
        caplog.text
    )


def test_an_app_never_ready_ends_the_run_after_its_tries(monkeypatch):
    errors = [NavigationError("Could not return to the home screen")] * 5
    tries, error = prepare_tries(monkeypatch, [AppNotReadyError("no home"), *errors])

    assert len(tries) == runner.PREPARE_ATTEMPTS
    assert str(error) == "Could not return to the home screen"


@pytest.mark.parametrize(
    "error",
    [
        LoggedOutError("The app is logged out"),
        LoginFailedError("The app refused the saved login"),  # the app locks after 5
    ],
)
def test_a_logout_is_not_tried_again(monkeypatch, error):
    tries, raised = prepare_tries(monkeypatch, [error])

    assert tries == ["prepare restart=False"]
    assert raised is error


def test_a_timed_run_does_not_try_again_after_its_warm_up(monkeypatch):
    start = datetime(2026, 11, 19, 6, 0)
    late = start - timedelta(seconds=30)  # inside the 60 s warm-up

    tries, _ = prepare_tries(monkeypatch, [AppNotReadyError("no home")], start, late)

    assert tries == ["prepare restart=False"]


def test_a_timed_run_tries_again_before_its_warm_up(monkeypatch):
    start = datetime(2026, 11, 19, 6, 0)

    tries, results = prepare_tries(
        monkeypatch, [AppNotReadyError("no home")], start, datetime(2026, 11, 19, 5, 46)
    )

    assert tries == ["prepare restart=False", "prepare restart=True"]
    assert [r.ok for r in results] == [True]


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


class TouchDevice:
    """Record taps the way uiautomator2 takes them: ``touch.down(x, y).up(x, y)``."""

    serial = "127.0.0.1:16384"

    def __init__(self, release=None):
        self.events = []
        self.touch = self
        self.release = release
        """An event ``up`` waits for, to stand for a frozen emulator."""

    def down(self, x, y):
        self.events.append(("down", x, y))
        return self

    def up(self, x, y):
        if self.release is not None:
            self.release.wait()
        self.events.append(("up", x, y))
        return self

    def click(self, x, y):
        self.events.append(("click", x, y))

    def press(self, key):
        self.events.append(("press", key))
        return True


def test_quick_tap_touches_down_then_up_at_the_point():
    device = TouchDevice()

    runner.QuickTap(device).click(270, 1537)

    assert device.events == [("down", 270, 1537), ("up", 270, 1537)]


def test_quick_tap_passes_everything_else_to_the_device():
    device = TouchDevice()
    quick = runner.QuickTap(device)

    assert quick.press("back") is True
    assert quick.serial == "127.0.0.1:16384"
    assert device.events == [("press", "back")]


def test_a_quick_tap_is_one_time_limited_call():
    release = threading.Event()
    device = GuardedDevice(runner.QuickTap(TouchDevice(release)), Watchdog(timeout=0.05))
    try:
        with pytest.raises(DeviceNotRespondingError, match="did not answer click within"):
            device.click(270, 1537)
    finally:
        release.set()


class FakeDriver:
    driver = "instrumentation"


class FakeAdb:
    def __init__(self, path):
        self.shells = []

    def shell(self, serial, *args):
        self.shells.append(" ".join(args))
        return ""


@pytest.fixture
def drivers(monkeypatch):
    """Connect without MuMu or adb; the driver starts unless ``drivers.driver`` is an error."""
    state = type("Drivers", (), {"driver": FakeDriver(), "tried": [], "adb": None})()

    def make_adb(path):
        state.adb = FakeAdb(path)
        return state.adb

    def connect_driver(adb, serial):
        state.tried.append("instrumentation")
        if isinstance(state.driver, BaseException):
            raise state.driver
        return state.driver

    def connect_uiautomator2(serial, watchdog):
        state.tried.append("uiautomator2")
        return TouchDevice()

    monkeypatch.setattr(runner, "Adb", make_adb)
    monkeypatch.setattr(runner, "find_adb", lambda path, dirs: "adb")
    monkeypatch.setattr(runner, "resolve_device", lambda adb, device, preferred: "serial")
    monkeypatch.setattr(runner, "connect_driver", connect_driver)
    monkeypatch.setattr(runner, "connect_uiautomator2", connect_uiautomator2)
    return state


def test_the_driver_drives_the_device_when_it_starts(drivers):
    device = runner.connect_device(Config(mumu_manager=""))

    assert device.driver == "instrumentation"
    assert drivers.tried == ["instrumentation"]


@pytest.mark.parametrize(
    "error",
    [
        DriverUnavailableError("The driver did not answer 10 s after being started"),
        DriverError("The driver refused hello: boom"),
        KeyError("version"),
    ],
)
def test_without_the_driver_uiautomator2_drives_the_device(drivers, caplog, error):
    drivers.driver = error

    device = runner.connect_device(Config(mumu_manager=""))

    assert device.driver == "uiautomator2"
    assert drivers.tried == ["instrumentation", "uiautomator2"]
    assert f"Driver unavailable ({error}); using uiautomator2" in caplog.text
    # A driver left running would hold UiAutomation, which uiautomator2 needs.
    assert drivers.adb.shells == ["am force-stop dev.courtbooker.driver"]


def test_a_frozen_emulator_is_not_handed_to_uiautomator2(drivers):
    drivers.driver = DeviceNotRespondingError("MuMu did not answer connect within 60 s")

    with pytest.raises(DeviceNotRespondingError):
        runner.connect_device(Config(mumu_manager=""))

    assert drivers.tried == ["instrumentation"]


def test_asking_for_the_driver_fails_the_run_without_it(drivers):
    drivers.driver = DriverUnavailableError("The driver APK is missing")

    with pytest.raises(DriverUnavailableError):
        runner.connect_device(Config(mumu_manager=""), runner.INSTRUMENTATION)

    assert drivers.tried == ["instrumentation"]


def test_asking_for_uiautomator2_leaves_the_driver_alone(drivers):
    device = runner.connect_device(Config(mumu_manager=""), runner.UIAUTOMATOR2)

    assert device.driver == "uiautomator2"
    assert drivers.tried == ["uiautomator2"]


def test_closing_uiautomator2_leaves_its_server_running():
    device = TouchDevice()

    runner.QuickTap(device).close()  # TouchDevice has no close(): nothing reaches it

    assert device.events == []


def test_a_wrong_mumu_path_is_found_again(tmp_path, monkeypatch, caplog):
    found = tmp_path / "nx_main" / "MuMuManager.exe"
    monkeypatch.setattr(runner, "find_mumu_manager", lambda configured: found)
    caplog.set_level(logging.INFO)

    assert runner.find_manager("C:/old/MuMuManager.exe") == found
    assert "MuMu found at" in caplog.text


def test_a_missing_mumu_keeps_the_configured_path(monkeypatch):
    monkeypatch.setattr(runner, "find_mumu_manager", lambda configured: None)

    assert str(runner.find_manager("C:/old/MuMuManager.exe")) == str(Path("C:/old/MuMuManager.exe"))


class ReconnectAdb:
    def __init__(self):
        self.disconnected = []

    def disconnect(self, serial):
        self.disconnected.append(serial)


def failing_once(error):
    """A ``resolve_device`` that raises ``error`` the first time, then returns its serial."""
    calls = []

    def resolve(adb, device, preferred):
        calls.append((device, preferred))
        if len(calls) == 1:
            raise error
        return preferred or device

    return resolve, calls


def test_a_serial_that_does_not_connect_is_connected_again(monkeypatch, caplog):
    resolve, calls = failing_once(
        DeviceConnectionError("Could not connect to 127.0.0.1:16384 in 30 s")
    )
    monkeypatch.setattr(runner, "resolve_device", resolve)
    adb = ReconnectAdb()

    assert runner.connect_serial(adb, "auto", "127.0.0.1:16384") == "127.0.0.1:16384"
    assert adb.disconnected == ["127.0.0.1:16384"]  # that serial alone, not the adb server
    assert len(calls) == 2
    assert "disconnecting it and connecting again" in caplog.text


def test_a_serial_that_never_connects_ends_the_run(monkeypatch):
    def resolve(adb, device, preferred):
        raise DeviceConnectionError("Could not connect to 127.0.0.1:16384 in 30 s")

    monkeypatch.setattr(runner, "resolve_device", resolve)
    adb = ReconnectAdb()

    with pytest.raises(DeviceConnectionError):
        runner.connect_serial(adb, "auto", "127.0.0.1:16384")
    assert adb.disconnected == ["127.0.0.1:16384"]


def test_without_a_known_serial_nothing_is_disconnected(monkeypatch):
    resolve, _ = failing_once(DeviceConnectionError("Could not connect"))
    monkeypatch.setattr(runner, "resolve_device", resolve)
    adb = ReconnectAdb()

    with pytest.raises(DeviceConnectionError):
        runner.connect_serial(adb, "auto", None)
    assert adb.disconnected == []


def test_mumu_commands_of_a_run_are_tried_again(tmp_path, monkeypatch):
    made = []

    class FakeMuMu:
        def __init__(self, manager, index, attempts=1):
            self.manager = manager
            made.append(attempts)

        def ensure_started(self, timeout, restarts=0):
            made.append(restarts)

        def adb_serial(self):
            return "127.0.0.1:16384"

    def no_adb(path, folders):
        raise AdbNotFoundError("stop here")

    monkeypatch.setattr(runner, "find_mumu_manager", lambda configured: tmp_path / "m.exe")
    monkeypatch.setattr(runner, "MuMu", FakeMuMu)
    monkeypatch.setattr(runner, "prepare_screen", lambda mumu: None)
    monkeypatch.setattr(runner, "find_adb", no_adb)

    with pytest.raises(AdbNotFoundError):
        runner.connect_device(Config(mumu_manager="C:/MuMu/MuMuManager.exe"))
    assert made == [3, 1]  # each command tried 3 times; a boot that stalls, restarted once


def test_the_screen_is_set_before_mumu_starts(tmp_path, monkeypatch):
    calls = []

    class FakeMuMu:
        def __init__(self, manager, index, attempts=1):
            self.manager = manager

        def ensure_started(self, timeout, restarts=0):
            calls.append("start")

        def adb_serial(self):
            return "127.0.0.1:16384"

    def no_adb(path, folders):
        raise AdbNotFoundError("stop here")

    monkeypatch.setattr(runner, "find_mumu_manager", lambda configured: tmp_path / "m.exe")
    monkeypatch.setattr(runner, "MuMu", FakeMuMu)
    monkeypatch.setattr(runner, "prepare_screen", lambda mumu: calls.append("screen"))
    monkeypatch.setattr(runner, "find_adb", no_adb)

    with pytest.raises(AdbNotFoundError):
        runner.connect_device(Config(mumu_manager="C:/old/MuMuManager.exe"))
    assert calls == ["screen", "start"]
