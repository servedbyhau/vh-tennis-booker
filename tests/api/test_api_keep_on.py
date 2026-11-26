"""Tests for the keep-on route, with a fake ``powercfg``."""

import functools
import subprocess

import pytest

from court_booker import keep_on

FRESH = {"sleep": 1800, "hibernate": 10800, "lid": 1, "screen": 600, "wifi": 0, "usb": 1}


@pytest.fixture
def plan(monkeypatch):
    values = dict(FRESH)
    names = {(s.subgroup, s.setting): s.name for s in keep_on.SETTINGS}

    def run(argv):
        if argv[1] == "/qh":
            ac = values[names[(argv[3], argv[4])]]
            output = f"Current AC Power Setting Index: 0x{ac:08x}\nCurrent DC: 0x00000000\n"
            return subprocess.CompletedProcess(argv, 0, stdout=output, stderr="")
        if argv[1] == "/setacvalueindex":
            values[names[(argv[3], argv[4])]] = int(argv[5])
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    for name in ("state", "switch_on", "switch_off"):
        real = getattr(keep_on, name)
        bound = functools.partial(real, run=run, modern_standby=lambda: False)
        monkeypatch.setattr(keep_on, name, bound)
    return values


def test_the_pc_is_not_kept_on_at_first(client, plan):
    assert client.get("/api/keep-on").json() == {"on": False, "modern_standby": False}


def test_on_then_off_gives_back_the_plan(client, plan, context):
    assert client.put("/api/keep-on", json={"on": True}).json()["on"] is True
    assert plan["sleep"] == 0
    assert context.data.power_plan.exists()

    assert client.put("/api/keep-on", json={"on": False}).json()["on"] is False
    assert plan == FRESH


def test_a_powercfg_failure_is_told(client, monkeypatch):
    def failing(*args, **kwargs):
        raise keep_on.PowerPlanError("powercfg could not run")

    monkeypatch.setattr(keep_on, "state", failing)

    response = client.get("/api/keep-on")

    assert response.status_code == 503
    assert response.json()["error"] == "power"
