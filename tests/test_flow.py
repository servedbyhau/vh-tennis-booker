"""Flow tests against a fake device; no emulator required."""

from datetime import date

import pytest

import court_booker.flow as flow
from court_booker.config import Config
from court_booker.errors import (
    AppNotReadyError,
    BookingNotOpenError,
    ElementNotFoundError,
    SlotUnavailableError,
)
from court_booker.flow import Booker

CONTINUE_BOUNDS = {"left": 20, "top": 890, "right": 520, "bottom": 945}
# Slot bounds after 0, 1 and 2 swipes: off-screen, hidden by the bottom button, fully visible.
SLOT_BOUNDS_AFTER_SWIPES = {0: None, 1: (870, 905), 2: (700, 735)}


class FakeElement:
    def __init__(self, device, selector):
        self.device = device
        self.selector = selector

    def _is_continue_button(self):
        return self.selector.get("description") == "Tiếp tục"

    def exists(self, timeout=0):
        if self._is_continue_button() or "descriptionMatches" in self.selector:
            return True
        return self.device.slot_bounds() is not None

    @property
    def info(self):
        if self._is_continue_button():
            return {"bounds": CONTINUE_BOUNDS}
        top, bottom = self.device.slot_bounds()
        return {
            "contentDescription": "14:00 - 15:00",
            "bounds": {"left": 200, "top": top, "right": 330, "bottom": bottom},
        }

    def click(self):
        self.device.tapped = self.device.slot_bounds()


class FakeDevice:
    """Device whose time slot moves into view as the screen is scrolled."""

    def __init__(self):
        self.swipes = 0
        self.tapped = None

    def slot_bounds(self):
        return SLOT_BOUNDS_AFTER_SWIPES[min(self.swipes, 2)]

    def __call__(self, **selector):
        return FakeElement(self, selector)

    def window_size(self):
        return 540, 960

    def swipe(self, *args):
        self.swipes += 1


def test_select_slot_scrolls_until_fully_visible(monkeypatch):
    monkeypatch.setattr(flow.time, "sleep", lambda seconds: None)
    device = FakeDevice()

    Booker(device, Config()).select_slot("14:00 - 15:00")

    assert device.swipes == 2
    assert device.tapped == (700, 735)


class ScreenElement:
    def __init__(self, device, selector):
        self.device = device
        self.selector = selector

    def exists(self, timeout=0):
        return self.selector.get("description") in self.device.visible()

    def wait(self, timeout=0):
        return self.exists()

    def click(self):
        self.device.taps.append(self.selector.get("description"))
        if self.selector.get("description") == "Tiện ích":
            self.device.screen = "utilities"


APP_SCREENS = {"home": {"Tiện ích"}, "utilities": {"Sân Tennis"}, "loading": set()}


class AppDevice:
    """Device whose app reaches its home screen once started, unless logged out."""

    def __init__(self, logged_in=True, current="other.app"):
        self.screen = "loading"
        self.logged_in = logged_in
        self.current = current
        self.calls = []
        self.taps = []

    def visible(self):
        if self.screen == "loading" and self.logged_in and "app_start" in self.calls:
            self.screen = "home"
        return APP_SCREENS[self.screen]

    def __call__(self, **selector):
        return ScreenElement(self, selector)

    def app_stop(self, package):
        self.calls.append("app_stop")

    def app_start(self, package):
        self.calls.append("app_start")

    def app_current(self):
        return {"package": self.current}


def test_prepare_restarts_app_and_stops_on_utilities(monkeypatch):
    monkeypatch.setattr(flow.time, "sleep", lambda seconds: None)
    device = AppDevice()

    Booker(device, Config()).prepare()

    assert device.calls == ["app_stop", "app_start"]
    assert device.taps == ["Tiện ích"]
    assert device.screen == "utilities"


def test_prepare_keeps_running_app_without_restart(monkeypatch):
    monkeypatch.setattr(flow.time, "sleep", lambda seconds: None)
    device = AppDevice(current="com.vinhomes.resident")
    device.screen = "utilities"

    Booker(device, Config(restart_app=False)).prepare()

    assert device.calls == []
    assert device.taps == []


def test_prepare_reports_logged_out_app(monkeypatch):
    clock = iter(range(0, 10_000, 5))
    monkeypatch.setattr(flow.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(flow.time, "monotonic", lambda: next(clock))

    with pytest.raises(AppNotReadyError, match="logged in"):
        Booker(AppDevice(logged_in=False), Config()).prepare()


class OpeningBooker(Booker):
    """Booker whose screens are scripted: the slot opens on attempt ``opens_on``."""

    def __init__(self, opens_on, fully_booked=False):
        super().__init__(device=None, config=Config(open_retry_seconds=60))
        self.opens_on = opens_on
        self.fully_booked = fully_booked
        self.entries = 0
        self.backs = 0

    def tap_and_advance(self, target, name, next_screen):
        self.entries += 1

    def select_date(self, target):
        if self.entries < self.opens_on:
            raise ElementNotFoundError(f"Date {target.isoformat()} is not bookable")

    def select_slot(self, slot):
        if self.fully_booked:
            raise SlotUnavailableError(f"Slot {slot} is fully booked")

    def return_to_utilities(self):
        self.backs += 1


def fake_monotonic(monkeypatch, step):
    clock = iter(range(0, 100_000, step))
    monkeypatch.setattr(flow.time, "monotonic", lambda: next(clock))


def test_open_slot_reloads_until_open(monkeypatch):
    fake_monotonic(monkeypatch, step=1)
    booker = OpeningBooker(opens_on=3)

    booker.open_slot("18:00 - 19:00", date(2026, 10, 10))

    assert booker.entries == 3
    assert booker.backs == 2


def test_open_slot_gives_up_after_retry_window(monkeypatch):
    fake_monotonic(monkeypatch, step=20)
    booker = OpeningBooker(opens_on=1000)

    with pytest.raises(BookingNotOpenError, match="not open after 3 attempt"):
        booker.open_slot("18:00 - 19:00", date(2026, 10, 10))


def test_open_slot_does_not_retry_fully_booked(monkeypatch):
    fake_monotonic(monkeypatch, step=1)
    booker = OpeningBooker(opens_on=1, fully_booked=True)

    with pytest.raises(SlotUnavailableError):
        booker.open_slot("18:00 - 19:00", date(2026, 10, 10))
    assert booker.entries == 1
