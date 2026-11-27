"""Tests for starting a dry run or a booking now, with the process launch replaced."""

import json
import subprocess
from datetime import datetime

import pytest

from court_booker import processes
from court_booker.api import runs
from court_booker.engine import engine_command
from court_booker.lock import Holder


class At(datetime):
    moment = datetime(2026, 10, 13, 14, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.moment


class FakeProcess:
    """A dry run process that runs until ``finish`` is called."""

    pid = 4321

    def __init__(self):
        self.code = None

    def poll(self):
        return self.code

    def finish(self):
        self.code = 0


launched_argv = []
"""The arguments of each run launched, beside ``launched``'s config paths."""


@pytest.fixture
def launched(monkeypatch):
    """Record dry run launches instead of starting processes; the time is 14:00."""
    calls = []

    def launch(path, argv):
        calls.append(path)
        launched_argv.append(argv)
        return FakeProcess()

    launched_argv.clear()

    monkeypatch.setattr(runs, "launch", launch)
    monkeypatch.setattr(runs, "datetime", At)
    return calls


def test_a_dry_run_starts_in_its_own_process(client, context, launched):
    response = client.post("/api/runs/dry-run")

    assert response.status_code == 202
    assert response.json() == {"pid": 4321, "started_at": "2026-10-13T14:00:00"}
    assert launched == [context.config_path.resolve()]


def test_a_second_dry_run_waits_for_the_first_to_end(app, client, launched):
    client.post("/api/runs/dry-run")

    while_running = client.post("/api/runs/dry-run")
    app.state.dry_run.finish()
    after = client.post("/api/runs/dry-run")

    assert while_running.status_code == 409
    assert while_running.json()["detail"].endswith("dry_run (pid 4321)")
    assert after.status_code == 202
    assert len(launched) == 2


def test_no_dry_run_while_a_run_holds_the_lock(client, context, launched):
    context.data.ensure()
    pid, started = processes.current()
    holder = Holder(pid, started, "scheduled", "2026-10-13T13:59:00")
    context.data.lock.write_text(json.dumps(vars(holder)), encoding="utf-8")

    response = client.post("/api/runs/dry-run")

    assert response.status_code == 409
    assert "scheduled run" in response.json()["detail"]
    assert launched == []


def test_no_dry_run_while_a_ticket_is_cancelled(app, client, launched):
    from court_booker.api.tasks import Task

    app.state.cancel = Task("cancel", 1, "2026-10-13T13:59:00", FakeProcess(), "1234567")

    response = client.post("/api/runs/dry-run")

    assert (response.status_code, response.json()["detail"]) == (
        409,
        "Another task is in progress: cancel on MuMu 1",
    )
    assert launched == []


def test_no_dry_run_around_the_scheduled_run(client, launched, monkeypatch):
    monkeypatch.setattr(At, "moment", datetime(2026, 10, 14, 5, 50))

    response = client.post("/api/runs/dry-run")

    assert response.status_code == 400
    assert launched == []


def test_launch_starts_the_dry_run_command(monkeypatch, tmp_path):
    started = []

    def popen(argv, **options):
        started.append((argv, options))
        return FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", popen)

    runs.launch(tmp_path / "config.toml", ["--dry-run"])

    ((argv, options),) = started
    assert argv == [
        *engine_command(),
        "--dry-run",
        "--config",
        str(tmp_path / "config.toml"),
    ]
    assert options["cwd"] == tmp_path
    assert options["stdout"] is subprocess.DEVNULL


def test_a_dry_run_is_launched_as_one(client, launched):
    client.post("/api/runs/dry-run")

    assert launched_argv == [["--dry-run"]]


@pytest.mark.parametrize(
    ("moment", "argv"),
    [
        (datetime(2026, 10, 14, 5, 52), ["--at", "06:00"]),  # the scheduled run did not start
        (datetime(2026, 10, 14, 14, 0), []),
    ],
)
def test_a_booking_now_waits_for_the_start_time_or_books_at_once(
    client, launched, monkeypatch, moment, argv
):
    monkeypatch.setattr(At, "moment", moment)

    response = client.post("/api/runs/now")

    assert response.status_code == 202
    assert launched_argv == [argv]


@pytest.mark.parametrize("moment", [datetime(2026, 10, 14, 5, 30), datetime(2026, 10, 14, 21, 0)])
def test_no_booking_now_while_the_app_is_closed(client, launched, monkeypatch, moment):
    monkeypatch.setattr(At, "moment", moment)

    response = client.post("/api/runs/now")

    assert response.status_code == 400
    assert launched == []


def test_a_booking_now_shows_as_a_run_by_hand_and_blocks_a_dry_run(app, client, context, launched):
    from court_booker.api import status

    client.post("/api/runs/now")

    shown = status.running(context, booking=app.state.booking)
    dry_run = client.post("/api/runs/dry-run")

    assert shown is not None and shown.trigger == "manual"
    assert dry_run.status_code == 409
    assert dry_run.json()["detail"].endswith("booking (pid 4321)")


@pytest.mark.parametrize("moment", [datetime(2026, 10, 14, 3, 0), datetime(2026, 10, 14, 21, 0)])
def test_no_dry_run_while_the_app_is_closed(client, launched, monkeypatch, moment):
    monkeypatch.setattr(At, "moment", moment)

    response = client.post("/api/runs/dry-run")

    assert response.status_code == 400
    assert "the app is closed" in response.json()["detail"]
    assert launched == []
