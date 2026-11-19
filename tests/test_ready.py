"""Supervisor tests: MuMu, adb, the driver and the app replaced by scripted fakes."""

import logging
import threading
from datetime import datetime
from pathlib import Path

import pytest

import court_booker.ready as ready
from court_booker.config import Config
from court_booker.errors import (
    AdbNotFoundError,
    AppMissingError,
    AppNotReadyError,
    DeviceConnectionError,
    DeviceNotRespondingError,
    DriverError,
    DriverUnavailableError,
    EmulatorError,
    LoggedOutError,
    LoginFailedError,
    MuMuNotFoundError,
    NavigationError,
)
from court_booker.events import EventKind, MemorySink, Reporter
from court_booker.ready import DeviceHandle, QuickTap, Supervisor, setup_deadline
from court_booker.screen import Screen
from court_booker.watchdog import GuardedDevice, Watchdog

SERIAL = "127.0.0.1:16384"
NOW = datetime(2026, 11, 20, 5, 45)
DEADLINE = datetime(2026, 11, 20, 5, 58)


class Script:
    """Record each step; a step with errors queued raises the next one (``None`` passes)."""

    def __init__(self):
        self.calls = []
        self.errors = {}

    def fail(self, step, *errors):
        self.errors.setdefault(step, []).extend(errors)

    def step(self, name):
        self.calls.append(name)
        queue = self.errors.get(name)
        if queue:
            error = queue.pop(0)
            if error is not None:
                raise error


class FakeMuMu:
    def __init__(self, script, index, stops):
        self.script = script
        self.index = index
        self.manager = Path("C:/MuMu/nx_main/MuMuManager.exe")
        self.boot_waits = []
        self.stops = stops
        """Whether each shutdown stops it, in turn; it stops once the list is empty."""

    def ensure_started(self, timeout):
        self.boot_waits.append(timeout)
        self.script.step("boot")

    def shutdown(self):
        self.script.step("shutdown")

    def wait_stopped(self, timeout):
        self.script.calls.append("stopped?")
        return self.stops.pop(0) if self.stops else True

    def adb_serial(self):
        return SERIAL


class FakeAdb:
    def __init__(self, script):
        self.script = script
        self.online = False
        self.shells = []

    def devices(self):
        return [SERIAL] if self.online else []

    def connect_until(self, serial, timeout):
        self.script.step("connect")
        self.online = True
        return serial

    def disconnect(self, serial):
        self.script.step("disconnect")
        self.online = False

    def ping(self, serial):
        self.script.step("ping")

    def shell(self, serial, *args):
        self.shells.append(" ".join(args))
        return ""


class FakeDevice:
    """A connected driver: ``app_current`` is the probe, ``close`` stops it."""

    def __init__(self, script, driver="instrumentation"):
        self.script = script
        self.driver = driver
        self.hung = False

    def app_current(self):
        self.script.step("probe")
        return {"package": "com.vinhomes.resident"}

    def close(self):
        self.script.step("stop")


class FakeBooker:
    def __init__(self, script):
        self.script = script
        self.restarts = []
        self.last_screen = Screen([])

    def prepare(self, restart=False):
        self.restarts.append(restart)
        self.script.step("prepare")


class World:
    """The supervisor's collaborators as fakes sharing one ``script``."""

    def __init__(self, monkeypatch):
        self.script = Script()
        self.mumu = None
        self.adb = FakeAdb(self.script)
        self.sink = MemorySink()
        self.booker = FakeBooker(self.script)
        self.clock = [NOW]
        self.stops = []

        def make_mumu(manager, index, attempts=1):
            assert attempts == ready.CALL_ATTEMPTS  # each command of a run is tried again
            self.mumu = FakeMuMu(self.script, index, self.stops)
            return self.mumu

        def connect_driver(adb, serial):
            self.script.step("driver")
            return FakeDevice(self.script)

        def connect_uiautomator2(serial, watchdog):
            self.script.step("uiautomator2")
            return FakeDevice(self.script, "uiautomator2")

        monkeypatch.setattr(ready, "MuMu", make_mumu)
        monkeypatch.setattr(ready, "find_manager", lambda configured: Path(configured))
        screen = self.script.calls.append
        monkeypatch.setattr(ready, "prepare_screen", lambda mumu: screen("screen"))
        monkeypatch.setattr(ready, "find_adb", lambda path, folders: Path("adb.exe"))
        monkeypatch.setattr(ready, "Adb", lambda path: self.adb)
        monkeypatch.setattr(
            ready, "resolve_device", lambda adb, device, preferred, timeout: preferred or SERIAL
        )
        monkeypatch.setattr(ready, "connect_driver", connect_driver)
        monkeypatch.setattr(ready, "connect_uiautomator2", connect_uiautomator2)
        # QuickTap wraps the uiautomator2 device; the fake stands for both.
        monkeypatch.setattr(ready, "QuickTap", lambda device: device)

    def supervisor(self, driver="auto", config=None):
        return Supervisor(
            config or Config(),
            driver,
            Reporter(self.sink),
            now=lambda: self.clock[0],
        )

    def prepare(self, supervisor=None, deadline=DEADLINE):
        supervisor = supervisor or self.supervisor()
        supervisor.prepare(self.booker, deadline)
        return supervisor

    def repaired(self):
        return [e.data["action"] for e in self.sink.events if e.kind is EventKind.REPAIRED]


@pytest.fixture
def world(monkeypatch):
    return World(monkeypatch)


UP = ["screen", "boot", "connect", "ping", "driver", "probe", "prepare"]
"""A run that finds MuMu off: every layer brought up once, bottom up."""


def test_every_layer_is_brought_up_bottom_up(world):
    supervisor = world.prepare()

    assert world.script.calls == UP
    assert supervisor.repairs == 0
    assert supervisor.device.driver == "instrumentation"
    assert world.mumu.boot_waits == [180.0]  # the first boot waits boot_timeout
    assert world.booker.restarts == [False]  # restart_app restarts it anyway


def test_a_boot_that_fails_restarts_mumu(world, caplog):
    world.script.fail("boot", EmulatorError("MuMu instance 0 did not finish booting in 180 s"))

    supervisor = world.prepare()

    restart = ["shutdown", "stopped?", "boot"]
    assert world.script.calls == ["screen", "boot", *restart, *UP[2:]]
    assert world.mumu.boot_waits == [180.0, ready.BOOT_RETRY_WAIT]
    assert world.repaired() == ["restart_mumu"]
    assert supervisor.repairs == 1
    assert "MuMu failed (MuMu instance 0 did not finish booting in 180 s); restarting MuMu" in (
        caplog.text
    )


def test_a_mumu_that_does_not_shut_down_is_restarted_again(world):
    world.script.fail("boot", EmulatorError("did not finish booting"))
    world.stops.append(False)

    world.prepare()

    assert world.script.calls.count("shutdown") == 2
    assert world.repaired() == ["restart_mumu", "restart_mumu"]


def test_a_serial_that_does_not_connect_is_disconnected_and_connected_again(world):
    world.script.fail("connect", DeviceConnectionError("Could not connect to 127.0.0.1:16384"))

    world.prepare()

    # The second pass drops that serial alone, never the adb server the other instances use.
    first, second = ["screen", "boot", "connect"], ["boot", "disconnect", "connect", "ping"]
    assert world.script.calls[:7] == first + second
    assert world.repaired() == ["reconnect_adb"]


def test_adb_failing_in_a_row_restarts_mumu(world):
    error = DeviceConnectionError("adb shell on 127.0.0.1:16384 failed: device offline")
    world.script.fail("ping", error, error, error)

    world.prepare()

    assert world.repaired() == ["reconnect_adb", "reconnect_adb", "restart_mumu"]
    assert world.script.calls.count("shutdown") == 1


def test_android_that_gives_no_answer_restarts_mumu_at_once(world, caplog):
    world.script.fail("ping", DeviceNotRespondingError("Android did not answer adb within 10 s"))

    world.prepare()

    assert world.repaired() == ["restart_mumu"]  # a frozen MuMu: nothing above it can help
    assert world.script.calls.count("shutdown") == 1


def test_a_driver_that_does_not_start_is_started_again(world):
    world.script.fail("driver", DriverUnavailableError("The driver did not answer"))

    supervisor = world.prepare()

    assert world.script.calls.count("driver") == 2
    assert supervisor.device.driver == "instrumentation"
    assert world.adb.shells == ["am force-stop dev.courtbooker.driver"]  # frees UiAutomation
    assert world.repaired() == ["restart_driver"]


def test_a_driver_that_never_starts_leaves_the_device_to_uiautomator2(world, caplog):
    error = DriverUnavailableError("The driver did not answer")
    world.script.fail("driver", error, error)

    supervisor = world.prepare()

    assert world.script.calls.count("driver") == ready.DRIVER_STARTS
    assert supervisor.device.driver == "uiautomator2"
    assert "using uiautomator2" in caplog.text


def test_asking_for_the_driver_never_falls_back(world):
    error = DriverUnavailableError("The driver did not answer")
    world.script.fail("driver", error, error)

    supervisor = world.prepare(world.supervisor(driver="instrumentation"))

    assert "uiautomator2" not in world.script.calls
    assert supervisor.device.driver == "instrumentation"


def test_asking_for_uiautomator2_leaves_the_driver_alone(world):
    supervisor = world.prepare(world.supervisor(driver="uiautomator2"))

    assert "driver" not in world.script.calls
    assert supervisor.device.driver == "uiautomator2"


def test_a_driver_lost_while_the_app_gets_ready_is_started_again(world):
    world.script.fail("prepare", DriverError("The driver closed the connection during dump"))

    world.prepare()

    calls = world.script.calls
    assert calls.count("driver") == 2
    assert calls.index("stop") < calls.index("driver", calls.index("prepare"))  # old one stopped
    assert world.booker.restarts == [False, True]
    assert world.repaired() == ["restart_driver"]


def test_a_device_that_hung_is_given_up_without_a_call(world):
    supervisor = world.prepare()
    supervisor.device._device._watchdog.hung = "dump"  # a call on it did not end in time
    world.script.calls.clear()

    supervisor._ensure_driver()

    assert "stop" not in world.script.calls  # its worker thread may still wait on it
    assert supervisor.device.ever_hung


def test_an_app_not_ready_is_restarted_with_growing_pauses(world, repair_pauses):
    world.script.fail("prepare", *[AppNotReadyError("The app did not show 'Tiện ích'")] * 4)

    world.prepare()

    assert world.booker.restarts == [False, True, True, True, True]
    assert repair_pauses == [5.0, 10.0, 20.0]  # the first restart goes at once
    # Three failures in a row restart the driver under the app too.
    assert world.repaired() == ["restart_app", "restart_app", "restart_driver", "restart_app"]


@pytest.mark.parametrize(
    ("step", "error"),
    [
        ("prepare", LoggedOutError("The app is logged out")),
        ("prepare", LoginFailedError("The app refused the saved login")),
        ("prepare", AppMissingError("com.vinhomes.resident is not installed")),
        ("boot", MuMuNotFoundError("MuMuManager not found")),
    ],
)
def test_a_failure_no_repair_can_change_ends_at_once(world, step, error):
    world.script.fail(step, error)
    supervisor = world.supervisor()

    with pytest.raises(type(error)):
        world.prepare(supervisor)
    assert supervisor.repairs == 0


def test_adb_missing_ends_at_once(world, monkeypatch):
    def no_adb(path, folders):
        raise AdbNotFoundError("adb not found")

    monkeypatch.setattr(ready, "find_adb", no_adb)

    with pytest.raises(AdbNotFoundError):
        world.prepare()


def test_the_deadline_ends_the_repairs(world, caplog):
    error = AppNotReadyError("The app did not show 'Tiện ích'")
    world.script.fail("prepare", error, error)
    supervisor = world.supervisor()
    original = world.booker.prepare

    def prepare(restart=False):
        world.clock[0] = DEADLINE  # the first try ran into the deadline
        original(restart)

    world.booker.prepare = prepare

    with pytest.raises(AppNotReadyError):
        world.prepare(supervisor)
    assert supervisor.repairs == 0
    assert "Not ready by 05:58:00.000 after 0 repair(s)" in caplog.text


def test_restarts_of_mumu_are_limited(world, caplog):
    world.script.fail("boot", *[EmulatorError("did not finish booting")] * 10)

    with pytest.raises(EmulatorError):
        world.prepare()
    assert world.script.calls.count("shutdown") == ready.MUMU_RESTARTS
    assert "giving up" in caplog.text


def test_repairs_are_limited(world):
    world.script.fail("prepare", *[NavigationError("Could not return to the home screen")] * 50)
    supervisor = world.supervisor()

    with pytest.raises(NavigationError):
        world.prepare(supervisor)
    assert supervisor.repairs == ready.REPAIRS_MAX


def test_a_device_the_run_does_not_manage_has_only_its_app_repaired(world):
    device = FakeDevice(world.script)
    supervisor = Supervisor(Config(), device=device, now=lambda: NOW)
    world.script.fail("prepare", AppNotReadyError("no home"))

    supervisor.prepare(world.booker, DEADLINE)

    assert world.script.calls == ["prepare", "prepare"]
    assert supervisor.repairs == 1


def test_a_device_failure_of_a_device_the_run_does_not_manage_ends_the_run(world):
    supervisor = Supervisor(Config(), device=FakeDevice(world.script), now=lambda: NOW)
    world.script.fail("prepare", DeviceNotRespondingError("MuMu did not answer dump within 60 s"))

    with pytest.raises(DeviceNotRespondingError):
        supervisor.prepare(world.booker, DEADLINE)
    assert supervisor.repairs == 0


def test_without_mumu_manager_mumu_is_left_alone(world):
    world.prepare(world.supervisor(config=Config(mumu_manager="")))

    assert world.script.calls == ["connect", "ping", "driver", "probe", "prepare"]


def test_each_repair_is_reported(world):
    world.script.fail("prepare", AppNotReadyError("no home"))
    world.prepare()

    (event,) = [e for e in world.sink.events if e.kind is EventKind.REPAIRED]
    assert event.data == {
        "layer": "app",
        "action": "restart_app",
        "error": "no home",
        "repair": 1,
    }


@pytest.mark.parametrize(
    ("start", "now", "deadline"),
    [
        (datetime(2026, 11, 20, 6), datetime(2026, 11, 20, 5, 45), datetime(2026, 11, 20, 5, 58)),
        # Woken late: two minutes for repairs all the same.
        (datetime(2026, 11, 20, 6), datetime(2026, 11, 20, 5, 59), datetime(2026, 11, 20, 6, 1)),
        (None, datetime(2026, 11, 20, 10), datetime(2026, 11, 20, 10, 5)),
    ],
    ids=["timed", "late", "untimed"],
)
def test_the_deadline_is_a_minute_before_the_warm_up(start, now, deadline):
    assert setup_deadline(start, 60.0, now) == deadline


def test_a_handle_without_a_device_raises_a_device_error():
    with pytest.raises(DeviceConnectionError, match="No device is connected"):
        DeviceHandle().dump_hierarchy()


def test_a_handle_stops_the_device_it_replaces():
    script = Script()
    handle = DeviceHandle(FakeDevice(script))

    handle.replace(FakeDevice(script, "uiautomator2"))

    assert script.calls == ["stop"]
    assert handle.driver == "uiautomator2"


def test_a_handle_never_calls_a_device_that_hung():
    script = Script()
    hung = FakeDevice(script)
    hung.hung = True
    handle = DeviceHandle(hung)

    handle.close()
    handle.drop()

    assert script.calls == []
    assert handle.ever_hung and not handle.connected


# uiautomator2's taps and MuMu's path -----------------------------------------


class TouchDevice:
    """Record taps the way uiautomator2 takes them: ``touch.down(x, y).up(x, y)``."""

    serial = SERIAL

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

    def press(self, key):
        self.events.append(("press", key))
        return True


def test_quick_tap_touches_down_then_up_at_the_point():
    device = TouchDevice()

    QuickTap(device).click(270, 1537)

    assert device.events == [("down", 270, 1537), ("up", 270, 1537)]


def test_quick_tap_passes_everything_else_to_the_device():
    device = TouchDevice()
    quick = QuickTap(device)

    assert quick.press("back") is True
    assert quick.serial == SERIAL
    assert device.events == [("press", "back")]


def test_a_quick_tap_is_one_time_limited_call():
    release = threading.Event()
    device = GuardedDevice(QuickTap(TouchDevice(release)), Watchdog(timeout=0.05))
    try:
        with pytest.raises(DeviceNotRespondingError, match="did not answer click within"):
            device.click(270, 1537)
    finally:
        release.set()


def test_closing_uiautomator2_leaves_its_server_running():
    device = TouchDevice()

    QuickTap(device).close()  # TouchDevice has no close(): nothing reaches it

    assert device.events == []


def test_a_wrong_mumu_path_is_found_again(tmp_path, monkeypatch, caplog):
    found = tmp_path / "nx_main" / "MuMuManager.exe"
    monkeypatch.setattr(ready, "find_mumu_manager", lambda configured: found)
    caplog.set_level(logging.INFO)

    assert ready.find_manager("C:/old/MuMuManager.exe") == found
    assert "MuMu found at" in caplog.text


def test_a_missing_mumu_keeps_the_configured_path(monkeypatch):
    monkeypatch.setattr(ready, "find_mumu_manager", lambda configured: None)

    assert str(ready.find_manager("C:/old/MuMuManager.exe")) == str(Path("C:/old/MuMuManager.exe"))
