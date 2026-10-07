"""Flow tests against a fake device; no emulator required."""

import pytest

import court_booker.flow as flow
from court_booker.config import Config
from court_booker.errors import AppNotReadyError
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
