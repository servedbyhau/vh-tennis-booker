"""``court-booker quota`` with a fake device: what it reads and reports."""

import json
import sqlite3
from datetime import date, datetime, timedelta

import pytest

from court_booker import cli, machine_task, quota_command
from court_booker.errors import LockHeldError
from court_booker.quota import Quota


class At(datetime):
    """The time of day the command runs at, 10:00 unless set."""

    moment = datetime(2026, 11, 24, 10, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.moment


class FakeDevice:
    connected = True
    hung = False

    def close(self):
        pass


class FakeSupervisor:
    def __init__(self, config, driver, report):
        self.config = config
        self.device = FakeDevice()
        made.append(self)

    def prepare(self, booker, deadline):
        pass


made = []


@pytest.fixture
def command(monkeypatch, tmp_path):
    """Run ``court-booker quota`` with a fake device; return its exit code."""
    made.clear()
    monkeypatch.setattr(machine_task, "datetime", At)
    monkeypatch.setattr(machine_task, "Supervisor", FakeSupervisor)
    monkeypatch.setattr(machine_task, "_mumu_off", lambda config: False)
    reads = []

    def read_quotas(booker, play_date, moment, report, account_id=None):
        reads.append((play_date, moment, account_id))
        return run.found

    monkeypatch.setattr(quota_command, "read_quotas", read_quotas)

    def run(*argv):
        return cli.main(["quota", "--config", str(tmp_path / "missing.toml"), *argv])

    run.reads = reads
    run.found = [Quota("Sân Tennis", "2026-11", 3, "2026-11-26", 0)]
    return run


def events(data_home):
    with sqlite3.connect(data_home / "booker.db") as db:
        rows = db.execute("SELECT kind, data FROM events").fetchall()
    return [(kind, json.loads(data)) for kind, data in rows]


def test_the_quota_is_read_for_the_next_day_booked(command, data_home):
    assert command("--instance", "0") == cli.EXIT_OK

    ((day, moment, account),) = command.reads
    assert (day, moment, account) == (date.today() + timedelta(days=2), "asked", None)
    assert made[0].config.mumu_index == 0


def test_a_page_not_read_far_enough_fails_the_command(command, data_home):
    command.found = None

    assert command() == cli.EXIT_ROUND_FAILED

    (failed,) = [data for kind, data in events(data_home) if kind == "quota_not_read"]
    assert "not read back far enough" in failed["reason"]


def test_no_quota_read_in_the_quiet_time(command, data_home, monkeypatch):
    monkeypatch.setattr(At, "moment", datetime(2026, 11, 24, 5, 50))

    assert command() == cli.EXIT_BAD_REQUEST
    assert made == []
    ((kind, data),) = events(data_home)
    assert kind == "quota_not_read"
    assert "No quota from 05:45" in data["reason"]


def test_a_machine_busy_with_a_run_reads_nothing(command, monkeypatch):
    def busy(self, trigger):
        raise LockHeldError("Another run is in progress")

    monkeypatch.setattr(machine_task.RunLock, "acquire", busy)

    assert command() == cli.EXIT_BUSY
    assert command.reads == []
