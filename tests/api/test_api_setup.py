"""Tests for the device setup route, with MuMu, adb and powercfg replaced."""

from datetime import datetime
from pathlib import Path

import pytest

from court_booker import device_setup
from court_booker.api import setup
from court_booker.device_setup import Check, MachineChecks, Status

MANAGER = Path("C:/MuMu/nx_main/MuMuManager.exe")


class At(datetime):
    moment = datetime(2026, 10, 2, 14, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.moment


@pytest.fixture
def pc(monkeypatch):
    """A PC with MuMu instances 0 and 1; instance 1 lacks the app, wake timers are off."""
    asked = []

    def check_machine(mumu, adb, package, seen):
        asked.append((mumu.index, seen.name))
        app = Status.USER if mumu.index == 1 else Status.OK
        return MachineChecks(mumu.index, Status.OK, Status.FIXABLE, app)

    monkeypatch.setattr(setup, "datetime", At)
    monkeypatch.setattr(device_setup, "find_mumu_manager", lambda configured: MANAGER)
    monkeypatch.setattr(setup, "instance_indexes", lambda manager: [0, 1])
    monkeypatch.setattr(setup, "find_adb", lambda configured, folders: Path("adb.exe"))
    monkeypatch.setattr(device_setup, "check_machine", check_machine)
    monkeypatch.setattr(
        device_setup,
        "check_wake_timers",
        lambda: Check("wake_timers", Status.FIXABLE, "Wake timers disabled"),
    )
    return asked


def test_setup_tells_each_machine(client, pc):
    response = client.get("/api/setup")

    assert response.status_code == 200
    assert response.json() == {
        "mumu": "fixable",  # found; the test config names no path
        "wake_timers": "fixable",
        "machines": [
            {"mumu_index": 0, "screen": "ok", "performance": "fixable", "app": "ok"},
            {"mumu_index": 1, "screen": "ok", "performance": "fixable", "app": "user"},
        ],
    }
    assert pc == [(0, "apps-seen.json"), (1, "apps-seen.json")]


def test_setup_without_mumu_has_no_machine(client, pc, monkeypatch):
    monkeypatch.setattr(device_setup, "find_mumu_manager", lambda configured: None)

    report = client.get("/api/setup").json()

    assert (report["mumu"], report["machines"]) == ("user", [])
    assert pc == []


def test_setup_waits_around_the_scheduled_run(client, pc, monkeypatch):
    monkeypatch.setattr(At, "moment", datetime(2026, 10, 2, 5, 50))

    response = client.get("/api/setup")

    assert (response.status_code, response.json()["error"]) == (409, "lock_held")
    assert pc == []


def test_setup_waits_for_a_run(client, pc, context):
    from court_booker.lock import RunLock

    lock = RunLock(context.data.lock)
    lock.acquire("dry_run")
    try:
        response = client.get("/api/setup")
    finally:
        lock.release()

    assert (response.status_code, response.json()["error"]) == (409, "lock_held")
    assert pc == []
