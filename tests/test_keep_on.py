"""Keeping the PC on while plugged in, with a fake ``powercfg``; nothing reaches Windows."""

import json
import subprocess

import pytest

from court_booker import device_setup, keep_on
from court_booker.keep_on import SETTINGS, PowerPlanError

OUTPUT = """Power Scheme GUID: bfe96730-c015-4cfa-b549-ec3c64ca0e05  (Ultimate Performance)
  Subgroup GUID: 238c9fa8-0aad-41ed-83f4-97be242c8f20  (Sleep)
      Maximum Possible Setting: 0xffffffff
      Possible Settings increment: 0x00000001
    Current AC Power Setting Index: 0x{ac:08x}
    Current DC Power Setting Index: 0x{dc:08x}
"""
FRESH = {"sleep": 1800, "hibernate": 10800, "lid": 1, "screen": 600, "wifi": 0, "usb": 1}


class FakePlan:
    """The active plan's plugged-in values by setting name; a name left out is not on the PC.
    Records every change; ``failing`` answers every change with an error."""

    def __init__(self, values=None, failing=False):
        self.values = dict(FRESH if values is None else values)
        self.failing = failing
        self.changes = []
        self.names = {(s.subgroup, s.setting): s.name for s in SETTINGS}

    def run(self, argv):
        command = argv[1]
        if command == "/qh":
            name = self.names[(argv[3], argv[4])]
            if name not in self.values:
                return subprocess.CompletedProcess(argv, 0, stdout=OUTPUT.split("\n")[0], stderr="")
            output = OUTPUT.format(ac=self.values[name], dc=7)
            return subprocess.CompletedProcess(argv, 0, stdout=output, stderr="")
        if self.failing:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="Access denied")
        if command == "/setacvalueindex":
            name = self.names[(argv[3], argv[4])]
            self.values[name] = int(argv[5])
            self.changes.append((name, int(argv[5])))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")


@pytest.fixture(autouse=True)
def wake_timers(monkeypatch):
    calls = []
    monkeypatch.setattr(device_setup, "ensure_wake_timers", lambda run=None: calls.append(run))
    return calls


def no_standby():
    return False


def test_a_fresh_plan_is_not_kept_on():
    assert keep_on.state(FakePlan().run, no_standby).on is False


def test_on_keeps_the_pc_on_plugged_in_and_allows_wake_timers(tmp_path, wake_timers):
    plan = FakePlan()

    found = keep_on.switch_on(tmp_path / "plan.json", plan.run, no_standby)

    assert found.on is True
    assert plan.values == {
        "sleep": 0,
        "hibernate": 0,
        "lid": 0,
        "screen": 300,
        "wifi": 0,
        "usb": 0,
    }
    assert len(wake_timers) == 1


def test_off_gives_back_the_values_the_pc_had(tmp_path):
    plan = FakePlan({**FRESH, "sleep": 900, "screen": 120})
    saved = tmp_path / "plan.json"
    keep_on.switch_on(saved, plan.run, no_standby)

    found = keep_on.switch_off(saved, plan.run, no_standby)

    assert found.on is False
    assert plan.values == {**FRESH, "sleep": 900, "screen": 120}
    assert not saved.exists()


def test_on_twice_keeps_the_first_values(tmp_path):
    plan = FakePlan({**FRESH, "sleep": 900})
    saved = tmp_path / "plan.json"
    keep_on.switch_on(saved, plan.run, no_standby)
    keep_on.switch_on(saved, plan.run, no_standby)

    keep_on.switch_off(saved, plan.run, no_standby)

    assert plan.values["sleep"] == 900


def test_off_without_saved_values_gives_windows_defaults(tmp_path):
    plan = FakePlan({name: 0 for name in FRESH})

    keep_on.switch_off(tmp_path / "plan.json", plan.run, no_standby)

    assert plan.values == FRESH


def test_a_setting_the_pc_lacks_is_left_out(tmp_path):
    plan = FakePlan({name: value for name, value in FRESH.items() if name != "lid"})

    assert keep_on.switch_on(tmp_path / "plan.json", plan.run, no_standby).on is True
    assert "lid" not in plan.values
    assert json.loads((tmp_path / "plan.json").read_text()).keys() == plan.values.keys()


def test_a_value_changed_by_hand_shows_off(tmp_path):
    plan = FakePlan()
    keep_on.switch_on(tmp_path / "plan.json", plan.run, no_standby)
    plan.values["sleep"] = 600

    assert keep_on.state(plan.run, no_standby).on is False


def test_with_modern_standby_the_screen_stays_on(tmp_path):
    plan = FakePlan()

    found = keep_on.switch_on(tmp_path / "plan.json", plan.run, lambda: True)

    assert found.modern_standby is True
    assert found.on is True
    assert plan.values["screen"] == 0


def test_a_refused_change_is_an_error(tmp_path):
    with pytest.raises(PowerPlanError, match="Access denied"):
        keep_on.switch_on(tmp_path / "plan.json", FakePlan(failing=True).run, no_standby)
