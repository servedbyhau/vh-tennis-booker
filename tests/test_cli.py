"""CLI exit codes with the device layer replaced by fakes."""

import argparse
import json
import logging
import os
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import ClassVar

import pytest

import court_booker.cli as cli
from court_booker import device_setup, processes
from court_booker.cli import close_emulator
from court_booker.config import Config
from court_booker.credentials import Login
from court_booker.customers import CustomerBook
from court_booker.device_setup import Check, Status
from court_booker.engine import engine_command
from court_booker.errors import AppNotReadyError, DeviceNotRespondingError, EmulatorError
from court_booker.events import EventKind
from court_booker.history import History as HistoryStore
from court_booker.history import HistoryHandler, connect
from court_booker.lock import Holder
from court_booker.quota import Quota
from court_booker.ready import DeviceHandle
from court_booker.runner import RoundResult
from court_booker.tickets import Collected, Ticket


def fake_run(outcomes):
    def run_booking(device, config, *, results, supervisor=None, **kwargs):
        run_booking.config, run_booking.kwargs = config, kwargs
        if supervisor is not None:
            supervisor.start()  # as the run's preparation connects the device first
        for slot, ok in outcomes:
            if ok is KeyboardInterrupt:
                raise KeyboardInterrupt
            results.append(RoundResult(slot, ok, "detail", 1.0))
        return results

    return run_booking


class FakeDevice:
    """A device driven the way ``driver`` asks; ``closed`` counts ``close()`` calls."""

    def __init__(self, driver, error=None):
        self.driver = driver
        self.error = error
        self.closed = 0

    def close(self):
        self.closed += 1
        if self.error is not None:
            raise self.error


def fake_connect(config, driver="auto"):
    """Connect the device the way ``driver`` asks, as the supervisor does."""
    return FakeDevice("instrumentation" if driver == "auto" else driver)


def use_connect(monkeypatch, connect):
    """Make the run's supervisor connect its device with ``connect(config, driver)``.

    Returns the supervisors the run makes, as they are made.
    """
    made = []

    class FakeSupervisor:
        def __init__(self, config, driver="auto", report=None, now=None, launch_after=()):
            self.config, self.driver, self.report = config, driver, report
            self.launch_after = launch_after
            made.append(self)
            self.device = DeviceHandle()
            self.repairs = 0

        def start(self):
            self.device.replace(connect(self.config, self.driver))
            self.report(EventKind.DEVICE_READY, driver=self.device.driver)

        def prepare(self, booker, deadline):
            self.start()

    monkeypatch.setattr(cli, "Supervisor", FakeSupervisor)
    return made


def run_cli(monkeypatch, tmp_path, outcomes=(), connect=fake_connect, args=(), now=None):
    """Run the CLI with a fake device; the time is 05:40 unless ``now`` gives a class."""
    use_connect(monkeypatch, connect)
    monkeypatch.setattr(cli, "run_booking", fake_run(outcomes))
    monkeypatch.setattr(cli, "datetime", now or FixedDatetime)
    return cli.main(["--config", str(tmp_path / "missing.toml"), *args])


def test_all_rounds_ok_exits_0(monkeypatch, tmp_path):
    assert run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)]) == cli.EXIT_OK


def test_failed_round_exits_1(monkeypatch, tmp_path):
    outcomes = [("18:00 - 19:00", False), ("19:00 - 20:00", True)]
    assert run_cli(monkeypatch, tmp_path, outcomes) == cli.EXIT_ROUND_FAILED


def test_the_driver_flag_reaches_the_device_and_the_history(monkeypatch, tmp_path):
    asked = []

    def connect(config, driver):
        asked.append(driver)
        return fake_connect(config, driver)

    events = []
    monkeypatch.setattr(
        cli, "Reporter", lambda sink: lambda kind, **data: events.append((kind, data))
    )
    run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)], connect, ["--driver", "uiautomator2"])

    assert asked == ["uiautomator2"]
    assert ("device_ready", {"driver": "uiautomator2"}) in [(k.value, d) for k, d in events]


def test_bad_config_exits_2(monkeypatch, tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("unknown = 1\n", encoding="utf-8")
    use_connect(monkeypatch, fake_connect)
    assert cli.main(["--config", str(path)]) == cli.EXIT_BAD_REQUEST


def test_device_error_exits_3(monkeypatch, tmp_path):
    def connect(config, driver):
        raise EmulatorError("MuMu did not start")

    assert run_cli(monkeypatch, tmp_path, connect=connect) == cli.EXIT_DEVICE


def test_ctrl_c_prints_finished_rounds_and_exits_130(monkeypatch, tmp_path, capsys):
    outcomes = [("18:00 - 19:00", True), ("19:00 - 20:00", KeyboardInterrupt)]

    assert run_cli(monkeypatch, tmp_path, outcomes) == cli.EXIT_INTERRUPTED
    out = capsys.readouterr().out
    assert "Summary" in out
    assert "OK   18:00 - 19:00" in out


def test_passed_start_time_exits_2_before_connecting(monkeypatch, tmp_path):
    def connect(config, driver):
        raise AssertionError("must not connect")

    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    code = run_cli(monkeypatch, tmp_path, connect=connect, args=["--at", "05:00"])
    assert code == cli.EXIT_BAD_REQUEST


def test_scheduled_uses_config_start_and_clock_offset(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    monkeypatch.setattr(cli, "ntp_offset", lambda server: 0.25)
    run = fake_run([("18:00 - 19:00", True)])
    use_connect(monkeypatch, fake_connect)
    monkeypatch.setattr(cli, "run_booking", run)

    assert cli.main(["--config", str(tmp_path / "missing.toml"), "--scheduled"]) == 0
    assert run.kwargs["start"] == datetime(2026, 10, 8, 6, 0)
    assert run.kwargs["clock"].offset == 0.25  # anchored to the answer


@pytest.mark.parametrize(
    ("config_text", "answer", "asked"),
    [('ntp_server = ""\n', 0.25, []), ("", None, ["time.google.com"])],
)
def test_without_an_ntp_answer_the_run_waits_by_the_pc_clock(
    monkeypatch, tmp_path, config_text, answer, asked
):
    path = tmp_path / "config.toml"
    path.write_text(config_text, encoding="utf-8")
    servers = []
    monkeypatch.setattr(cli, "ntp_offset", lambda server: servers.append(server) or answer)
    run = fake_run([("18:00 - 19:00", True)])
    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    use_connect(monkeypatch, fake_connect)
    monkeypatch.setattr(cli, "run_booking", run)

    assert cli.main(["--config", str(path), "--scheduled"]) == 0
    assert servers == asked
    assert run.kwargs["clock"].offset is None


def test_an_untimed_run_does_not_ask_the_time_server(monkeypatch, tmp_path):
    def ntp_offset(server):
        raise AssertionError("must not ask")

    monkeypatch.setattr(cli, "ntp_offset", ntp_offset)

    assert run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)]) == cli.EXIT_OK


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 8, 5, 40)  # before the default wake time, 05:45


def test_summary_is_sent_to_telegram_even_on_device_error(monkeypatch, tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('telegram_token = "t"\ntelegram_chat_id = "42"\n', encoding="utf-8")
    sent = []
    monkeypatch.setattr(cli, "send_telegram", lambda token, chat, text: sent.append(text))

    def connect(config, driver):
        raise EmulatorError("MuMu did not start")

    use_connect(monkeypatch, connect)
    assert cli.main(["--config", str(path)]) == cli.EXIT_DEVICE
    assert sent == ["court-booker: 0/0 ok\nError: MuMu did not start"]


def test_every_run_ends_with_a_windows_notification(monkeypatch, tmp_path, windows_notifications):
    outcomes = [("18:00 - 19:00", True), ("19:00 - 20:00", False)]

    assert run_cli(monkeypatch, tmp_path, outcomes, args=["--dry-run"]) == cli.EXIT_ROUND_FAILED
    (title, body), *_ = windows_notifications
    # Booking day: 2026-10-08, the fake today, plus the default two days.
    assert title == "Đặt sân 10/10: 1/2 thành công (chạy thử)"
    assert body.splitlines() == ["✅ 18:00 - 19:00 · S10", "❌ 19:00 - 20:00 · Có lỗi, xem nhật ký"]


def test_the_notification_reports_a_config_that_did_not_load(tmp_path, windows_notifications):
    path = tmp_path / "config.toml"
    path.write_text("slot = 1\n", encoding="utf-8")

    assert cli.main(["--config", str(path)]) == cli.EXIT_BAD_REQUEST
    ((title, _body),) = windows_notifications
    assert title.endswith(": không đặt được")


def test_the_notification_follows_its_settings(monkeypatch, tmp_path, windows_notifications):
    path = tmp_path / "config.toml"
    path.write_text('notification_language = "en"\n', encoding="utf-8")
    use_connect(monkeypatch, fake_connect)
    monkeypatch.setattr(cli, "run_booking", fake_run([("18:00 - 19:00", True)]))
    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    cli.main(["--config", str(path)])
    assert windows_notifications[0][0] == "Courts for 10 Oct: 1/1 booked"

    path.write_text("windows_notification = false\n", encoding="utf-8")
    cli.main(["--config", str(path)])
    assert len(windows_notifications) == 1


def test_a_notification_that_fails_does_not_change_the_exit_code(monkeypatch, tmp_path):
    def send_windows(title, body):
        raise RuntimeError("no toast")

    monkeypatch.setattr(cli, "send_windows", send_windows)

    assert run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)]) == cli.EXIT_OK
    assert "Windows notification not shown" in read_log(tmp_path)


def test_log_names_the_python_and_code_folder(monkeypatch, tmp_path):
    run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)])

    text = next((tmp_path / "logs").glob("court-booker-*.log")).read_text(encoding="utf-8")
    assert f"Python {sys.executable}, code in " in text
    assert str(Path(cli.__file__).resolve().parent) in text


def read_log(tmp_path):
    return next((tmp_path / "logs").glob("court-booker-*.log")).read_text(encoding="utf-8")


def test_run_events_reach_the_log(monkeypatch, tmp_path):
    run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)], args=["--dry-run"])

    text = read_log(tmp_path)
    assert "Event run_started trigger='dry_run' dry_run=True" in text
    assert "Event device_ready" in text
    assert "Event run_finished status='ok' booked=1 total=1 error=None" in text


def test_run_finished_is_reported_on_a_device_error(monkeypatch, tmp_path):
    def connect(config, driver):
        raise EmulatorError("MuMu did not start")

    run_cli(monkeypatch, tmp_path, connect=connect)

    assert "Event run_finished status='failed' booked=0 total=0" in read_log(tmp_path)


def test_a_frozen_device_is_reported_then_ends_the_process(monkeypatch, tmp_path, data_home):
    ended = []
    monkeypatch.setattr(cli, "end_process", ended.append)
    error = "MuMu did not answer click within 60 s"

    def run_booking(device, config, *, results, **kwargs):
        raise DeviceNotRespondingError(error)

    use_connect(monkeypatch, fake_connect)
    monkeypatch.setattr(cli, "run_booking", run_booking)
    monkeypatch.setattr(cli, "datetime", FixedDatetime)

    code = cli.main(["--config", str(tmp_path / "missing.toml")])

    assert code == cli.EXIT_DEVICE
    assert ended == [cli.EXIT_DEVICE]
    assert f"run_finished status='failed' booked=0 total=0 error={error!r}" in read_log(tmp_path)
    assert not (data_home / "run.lock").exists()


def test_other_device_errors_end_the_process_normally(monkeypatch, tmp_path):
    ended = []
    monkeypatch.setattr(cli, "end_process", ended.append)

    def connect(config, driver):
        raise EmulatorError("MuMu did not start")

    assert run_cli(monkeypatch, tmp_path, connect=connect) == cli.EXIT_DEVICE
    assert ended == []


@pytest.mark.parametrize(
    "outcomes, args",
    [
        ([("18:00 - 19:00", True)], []),
        ([("18:00 - 19:00", False)], ["--dry-run"]),
        ([("18:00 - 19:00", KeyboardInterrupt)], []),
    ],
    ids=["real run", "dry run", "Ctrl+C"],
)
def test_the_driver_stops_after_every_run(monkeypatch, tmp_path, outcomes, args):
    devices = []

    def connect(config, driver):
        devices.append(fake_connect(config, driver))
        return devices[-1]

    run_cli(monkeypatch, tmp_path, outcomes, connect, args)

    # uiautomator2 and the other tools need UiAutomation, which the driver holds.
    assert [device.closed for device in devices] == [1]


def test_a_driver_that_does_not_stop_only_warns(monkeypatch, tmp_path):
    def connect(config, driver):
        return FakeDevice("instrumentation", OSError("adb is gone"))

    assert run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)], connect) == cli.EXIT_OK
    assert "Could not stop the driver" in read_log(tmp_path)


def test_a_frozen_device_is_not_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "end_process", lambda code: None)
    device = FakeDevice("instrumentation")

    def run_booking(device, config, *, results, **kwargs):
        raise DeviceNotRespondingError("MuMu did not answer click within 60 s")

    use_connect(monkeypatch, lambda config, driver: device)
    monkeypatch.setattr(cli, "run_booking", run_booking)
    monkeypatch.setattr(cli, "datetime", FixedDatetime)

    cli.main(["--config", str(tmp_path / "missing.toml")])

    # Each call would wait the watchdog's 60 s.
    assert device.closed == 0


def test_a_real_run_closes_mumu_after_its_rounds(monkeypatch, tmp_path, closed_mumu):
    outcomes = [("18:00 - 19:00", False), ("19:00 - 20:00", True)]

    assert run_cli(monkeypatch, tmp_path, outcomes) == cli.EXIT_ROUND_FAILED
    assert [config.mumu_index for config in closed_mumu] == [0]


@pytest.mark.parametrize(
    "outcomes, args",
    [
        ([("18:00 - 19:00", True)], ["--dry-run"]),
        ([("18:00 - 19:00", True), ("19:00 - 20:00", KeyboardInterrupt)], []),
        ([], []),
    ],
    ids=["dry run", "Ctrl+C", "no round"],
)
def test_mumu_stays_open(monkeypatch, tmp_path, closed_mumu, outcomes, args):
    run_cli(monkeypatch, tmp_path, outcomes, args=args)

    assert closed_mumu == []


def test_an_error_before_the_rounds_leaves_mumu_open(monkeypatch, tmp_path, closed_mumu):
    def run_booking(device, config, *, results, **kwargs):
        raise AppNotReadyError("The app is logged out")

    use_connect(monkeypatch, fake_connect)
    monkeypatch.setattr(cli, "run_booking", run_booking)
    monkeypatch.setattr(cli, "datetime", FixedDatetime)

    assert cli.main(["--config", str(tmp_path / "missing.toml")]) == cli.EXIT_APP_NOT_READY
    assert closed_mumu == []


def test_a_frozen_mumu_is_not_closed(monkeypatch, tmp_path, closed_mumu):
    monkeypatch.setattr(cli, "end_process", lambda code: None)

    def run_booking(device, config, *, results, **kwargs):
        results.append(RoundResult("18:00 - 19:00", False, "MuMu did not answer", 60.0))
        raise DeviceNotRespondingError("MuMu did not answer click within 60 s")

    use_connect(monkeypatch, fake_connect)
    monkeypatch.setattr(cli, "run_booking", run_booking)
    monkeypatch.setattr(cli, "datetime", FixedDatetime)

    assert cli.main(["--config", str(tmp_path / "missing.toml")]) == cli.EXIT_DEVICE
    assert closed_mumu == []


def test_without_mumu_manager_mumu_is_left_alone(monkeypatch, tmp_path, closed_mumu):
    path = tmp_path / "config.toml"
    path.write_text('mumu_manager = ""\n', encoding="utf-8")

    run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)], args=["--config", str(path)])

    assert closed_mumu == []


def test_close_emulator_shuts_the_configured_instance_down(monkeypatch):
    shut = []

    class FakeMuMu:
        def __init__(self, manager, index, attempts=1):
            self.manager, self.index, self.attempts = manager, index, attempts

        def shutdown(self):
            shut.append((self.manager, self.index, self.attempts))

    monkeypatch.setattr(cli, "MuMu", FakeMuMu)

    close_emulator(Config(mumu_manager="C:/MuMu/MuMuManager.exe", mumu_index=1))

    # Retried like a run's other MuMuManager commands: both instances close at once.
    assert shut == [(Path("C:/MuMu/MuMuManager.exe"), 1, 3)]


INSTANCES = """slots = ["18:00 - 19:00", "19:00 - 20:00"]

[[instances]]
mumu_index = 1
slots = ["20:00 - 21:00"]
court = "S9 - Sân tennis"
"""


class FakeProcess:
    """Stand in for ``subprocess.Popen``; ``started`` lists the commands and what was true."""

    started: ClassVar[list] = []

    def __init__(self, command, **kwargs):
        self.pid = 4242
        self.command, self.kwargs = command, kwargs
        FakeProcess.started.append(self)

    def wait(self):
        self.waited = True
        return 0


@pytest.fixture
def spawned(monkeypatch):
    FakeProcess.started = []
    monkeypatch.setattr(cli.subprocess, "Popen", FakeProcess)
    return FakeProcess.started


def test_another_instance_books_on_its_own(
    monkeypatch, tmp_path, data_home, spawned, windows_notifications
):
    path = tmp_path / "config.toml"
    path.write_text(INSTANCES, encoding="utf-8")
    cleaned = []
    monkeypatch.setattr(HistoryStore, "interrupt_stale_runs", lambda self: cleaned.append(self))
    locks = []
    run = fake_run([("20:00 - 21:00", True)])

    def run_booking(device, config, *, results, **kwargs):
        locks.extend(sorted(item.name for item in data_home.glob("*.lock")))
        return run(device, config, results=results, **kwargs)

    supervisors = use_connect(monkeypatch, fake_connect)
    monkeypatch.setattr(cli, "run_booking", run_booking)
    monkeypatch.setattr(cli, "datetime", FixedDatetime)

    assert cli.main(["--config", str(path), "--instance", "1"]) == cli.EXIT_OK

    assert (run.config.mumu_index, run.config.slots) == (1, ["20:00 - 21:00"])
    # Launched once the first machine has booted, the config's order.
    assert [supervisor.launch_after for supervisor in supervisors] == [[0]]
    assert run.config.court == "S9 - Sân tennis"
    assert locks == ["run-mumu1.lock"]  # beside the first instance's run.lock
    assert next((tmp_path / "logs").glob("court-booker-*-mumu1.log")).exists()
    assert windows_notifications[0][0].startswith("MuMu 1 · Đặt sân 10/10: 1/1")
    # The first instance's process clears stale runs and starts the others, never this one.
    assert cleaned == [] and spawned == []


def test_an_instance_missing_from_the_config_exits_2(monkeypatch, tmp_path, spawned):
    path = tmp_path / "config.toml"
    path.write_text(INSTANCES, encoding="utf-8")

    assert run_cli(monkeypatch, tmp_path, args=["--config", str(path), "--instance", "3"]) == 2


def test_a_run_starts_a_process_for_each_other_instance(
    monkeypatch, tmp_path, data_home, spawned, windows_notifications
):
    path = tmp_path / "config.toml"
    path.write_text(INSTANCES, encoding="utf-8")
    steps = []
    monkeypatch.setattr(HistoryStore, "interrupt_stale_runs", lambda self: steps.append("clean"))
    real_process = FakeProcess.__init__

    def start(self, command, **kwargs):
        steps.append(("start", (data_home / "run.lock").exists()))
        real_process(self, command, **kwargs)

    monkeypatch.setattr(FakeProcess, "__init__", start)
    args = ["--config", str(path), "--dry-run", "--at", "05:50", "--slots", "07:00 - 08:00"]

    assert run_cli(monkeypatch, tmp_path, [("07:00 - 08:00", True)], args=args) == cli.EXIT_OK

    (process,) = spawned
    assert process.command == [
        *engine_command(),
        *["--config", str(path.resolve()), "--instance", "1", "--driver", "auto"],
        *["--dry-run", "--at", "05:50"],  # its own slots, not the ones given here
    ]
    assert process.kwargs == {"stdout": subprocess.DEVNULL}
    assert process.waited
    assert steps == ["clean", ("start", True)]  # with the run lock held, after the cleanup
    assert windows_notifications[0][0].startswith("MuMu 0 · ")
    assert "MuMu instance 1 books in process 4242" in read_log(tmp_path)


@pytest.mark.parametrize(
    ("text", "args", "logged"),
    [
        (INSTANCES, ["--device", "127.0.0.1:16384"], 'need mumu_manager and device = "auto"'),
        ("[[instances]]\nmumu_index = 0\n", [], "Skipping the [[instances]] entry with mumu_index"),
    ],
)
def test_an_instance_that_cannot_book_side_by_side_is_skipped(
    monkeypatch, tmp_path, spawned, windows_notifications, text, args, logged
):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")

    run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)], args=["--config", str(path), *args])

    assert spawned == []
    assert logged in read_log(tmp_path)
    assert not windows_notifications[0][0].startswith("MuMu")  # one instance, as before


def test_a_failed_close_only_warns(monkeypatch, tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(f'mumu_manager = "{(tmp_path / "none.exe").as_posix()}"\n', encoding="utf-8")
    monkeypatch.setattr(cli, "close_emulator", close_emulator)

    code = run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)], args=["--config", str(path)])

    assert code == cli.EXIT_OK
    text = read_log(tmp_path)
    assert "Closing MuMu instance 0" in text
    assert "WARNING" in text
    assert "Could not close MuMu: MuMuManager not found at" in text


def test_a_run_is_recorded_in_the_history(monkeypatch, tmp_path, data_home):
    run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)], args=["--dry-run"])

    connection = sqlite3.connect(data_home / "booker.db")
    ((run_id, trigger, status),) = connection.execute("SELECT id, trigger, status FROM runs")
    kinds = [kind for (kind,) in connection.execute("SELECT kind FROM events ORDER BY id")]
    query = "SELECT message FROM log_lines WHERE run_id = ?"
    lines = [line for (line,) in connection.execute(query, (run_id,))]
    connection.close()
    assert (trigger, status) == ("dry_run", "ok")
    assert kinds == ["run_started", "device_ready", "run_finished"]
    assert f"court-booker {cli.__version__}" in lines
    assert "Summary" in lines


def test_the_rounds_write_the_history_once_they_are_over(monkeypatch, tmp_path, data_home):
    seen = []

    def run_booking(device, config, *, results, supervisor=None, on_race=None, **kwargs):
        supervisor.start()
        on_race()
        logging.getLogger("court_booker.runner").info("Round 1/1: 18:00 - 19:00")
        with sqlite3.connect(data_home / "booker.db") as db:
            seen.extend(message for (message,) in db.execute("SELECT message FROM log_lines"))
        results.append(RoundResult("18:00 - 19:00", True, "booked", 1.0))
        return results

    use_connect(monkeypatch, fake_connect)
    monkeypatch.setattr(cli, "run_booking", run_booking)
    monkeypatch.setattr(cli, "datetime", FixedDatetime)

    assert cli.main(["--config", str(tmp_path / "missing.toml"), "--dry-run"]) == cli.EXIT_OK

    connection = sqlite3.connect(data_home / "booker.db")
    lines = [line for (line,) in connection.execute("SELECT message FROM log_lines ORDER BY id")]
    connection.close()
    assert f"court-booker {cli.__version__}" in seen  # written before the race
    assert "Round 1/1: 18:00 - 19:00" not in seen
    assert lines.index("Round 1/1: 18:00 - 19:00") < lines.index("Summary")


def test_a_run_is_recorded_with_whose_account_it_books_with(
    monkeypatch, tmp_path, data_home, saved_logins
):
    db = connect(data_home / "booker.db")
    book = CustomerBook(db, saved_logins)
    account = book.add_account(book.add_customer("An").id, Login("0900000011", "x"), "Căn A")
    book.attach(account.id, 0)

    run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)])

    names = db.execute("SELECT account_id, customer, account FROM runs").fetchall()
    db.close()
    assert names == [(account.id, "An", "Căn A")]


def test_a_run_books_without_knowing_whose_account_it_is(
    monkeypatch, tmp_path, data_home, saved_logins
):
    def refuse(key):
        raise OSError("no vault")

    monkeypatch.setattr(saved_logins, "read", refuse)
    assert run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)]) == cli.EXIT_OK
    assert "Whose account MuMu 0 books with is not known" in read_log(tmp_path)


def test_the_history_stops_listening_after_the_run(monkeypatch, tmp_path):
    run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)])

    handlers = logging.getLogger("court_booker").handlers
    assert not any(isinstance(handler, HistoryHandler) for handler in handlers)


def test_a_run_books_without_the_history(monkeypatch, tmp_path, data_home):
    data_home.parent.mkdir(parents=True, exist_ok=True)
    data_home.write_text("not a folder", encoding="utf-8")

    assert run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)]) == cli.EXIT_OK
    assert "run not recorded" in read_log(tmp_path)


def test_a_run_waits_for_no_one_and_releases_the_lock(monkeypatch, tmp_path, data_home):
    run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)])

    assert "Run lock taken: manual run" in read_log(tmp_path)
    assert not (data_home / "run.lock").exists()


def test_a_run_is_refused_while_another_holds_the_lock(monkeypatch, tmp_path, data_home):
    pid, started = processes.current()  # a process that is surely running
    holder = Holder(pid, started, "dry_run", "2026-10-13T10:43:10")
    data_home.mkdir(parents=True)
    (data_home / "run.lock").write_text(json.dumps(vars(holder)), encoding="utf-8")

    def connect(config, driver):
        raise AssertionError("must not touch the device")

    code = run_cli(monkeypatch, tmp_path, connect=connect, args=["--dry-run"])

    assert code == cli.EXIT_BUSY
    assert f"Another run is in progress: dry_run run (pid {pid}) since 10:43:10" in read_log(
        tmp_path
    )
    assert (data_home / "run.lock").exists()


def test_a_run_stopped_midway_ends_up_interrupted(monkeypatch, tmp_path, data_home):
    run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)])
    connection = sqlite3.connect(data_home / "booker.db")
    with connection:
        connection.execute("UPDATE runs SET status = 'running'")  # as if the PC lost power

    run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)])

    statuses = [status for (status,) in connection.execute("SELECT status FROM runs ORDER BY id")]
    connection.close()
    assert statuses == ["interrupted", "ok"]


def test_the_scheduled_run_may_take_the_lock_over_before_the_start(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        cli.RunLock,
        "acquire_for_schedule",
        lambda self, trigger, take_over_at: calls.append((trigger, take_over_at)),
    )
    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    monkeypatch.setattr(cli, "ntp_offset", lambda server: 0.0)

    run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)], args=["--scheduled"])

    assert calls == [("scheduled", datetime(2026, 10, 8, 5, 58))]


def at(hour, minute):
    """Return a datetime class whose ``now`` is 2026-10-08 at ``hour:minute``."""

    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 8, hour, minute)

    return Fixed


def test_no_dry_run_while_the_scheduled_run_uses_the_emulator(monkeypatch, tmp_path, data_home):
    def connect(config, driver):
        raise AssertionError("must not touch the device")

    code = run_cli(monkeypatch, tmp_path, connect=connect, args=["--dry-run"], now=at(5, 55))

    assert code == cli.EXIT_BAD_REQUEST
    assert "No dry run from 05:45 to 06:05: the scheduled run uses the emulator" in read_log(
        tmp_path
    )
    assert not (data_home / "run.lock").exists()


def test_a_dry_run_may_start_once_the_scheduled_run_is_over(monkeypatch, tmp_path):
    outcomes = [("18:00 - 19:00", True)]

    assert run_cli(monkeypatch, tmp_path, outcomes, args=["--dry-run"], now=at(6, 5)) == 0


def test_a_manual_run_is_not_held_to_the_window(monkeypatch, tmp_path):
    outcomes = [("18:00 - 19:00", True)]

    assert run_cli(monkeypatch, tmp_path, outcomes, now=at(5, 55)) == cli.EXIT_OK


CHECKS = [
    Check("mumu_installed", Status.OK, "MuMu at C:/MuMu/MuMuManager.exe"),
    Check("app_installed", Status.USER, "com.vinhomes.resident is not installed in MuMu"),
]


def run_setup(monkeypatch, tmp_path, args=(), now=None, results=None):
    """Run ``court-booker setup`` with fake checks; returns the exit code and auto setup calls."""
    calls = []

    def fake_auto_setup(config, config_path, tools, *, restart_mumu=False, run=None):
        calls.append(restart_mumu)
        return results or [Check("wake_timers", Status.FIXED, "enabled")]

    monkeypatch.setattr(cli, "datetime", now or FixedDatetime)
    monkeypatch.setattr(cli, "find_tools", lambda config: None)
    monkeypatch.setattr(cli, "run_checks", lambda config, tools: CHECKS)
    monkeypatch.setattr(device_setup, "auto_setup", fake_auto_setup)
    code = cli.main(["setup", "--config", str(tmp_path / "missing.toml"), *args])
    return code, calls


def test_setup_prints_every_item(monkeypatch, tmp_path, capsys):
    code, calls = run_setup(monkeypatch, tmp_path)

    out = capsys.readouterr().out
    assert code == 1  # the app still has to be installed by the user
    assert "ok       mumu_installed  MuMu at C:/MuMu/MuMuManager.exe" in out
    assert "user     app_installed   com.vinhomes.resident is not installed" in out
    assert calls == []


def test_auto_setup_is_recorded_as_setup_steps(monkeypatch, tmp_path, data_home):
    code, calls = run_setup(monkeypatch, tmp_path, ["--auto", "--restart-mumu"])

    connection = sqlite3.connect(data_home / "booker.db")
    steps = connection.execute("SELECT run_id, category, kind FROM events ORDER BY id").fetchall()
    connection.close()
    assert code == cli.EXIT_OK
    assert calls == [True]
    assert steps == [
        (None, "setup", "setup_started"),
        (None, "setup", "setup_item"),
        (None, "setup", "setup_finished"),
    ]
    assert not (data_home / "run.lock").exists()


def test_auto_setup_waits_for_no_run(monkeypatch, tmp_path, data_home):
    pid, started = processes.current()
    data_home.mkdir(parents=True)
    holder = Holder(pid, started, "dry_run", "2026-10-13T10:43:10")
    (data_home / "run.lock").write_text(json.dumps(vars(holder)), encoding="utf-8")

    code, calls = run_setup(monkeypatch, tmp_path, ["--auto"])

    assert code == cli.EXIT_BUSY
    assert calls == []


def test_no_auto_setup_while_the_scheduled_run_uses_the_emulator(monkeypatch, tmp_path):
    code, calls = run_setup(monkeypatch, tmp_path, ["--auto"], now=at(5, 50))

    assert code == cli.EXIT_BAD_REQUEST
    assert calls == []


def test_serve_explains_a_missing_app_extra(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "court_booker.api.server", None)

    assert cli.main(["serve"]) == cli.EXIT_BAD_REQUEST
    assert "The backend needs the app extra" in capsys.readouterr().out


def test_a_run_does_not_load_the_backend():
    code = "import sys, court_booker.cli; print('fastapi' in sys.modules)"
    src = str(Path(cli.__file__).resolve().parents[1])
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": src},
        check=True,
    )

    assert result.stdout.strip() == "False"


def test_run_trigger():
    def args(scheduled=False, dry_run=False):
        return argparse.Namespace(scheduled=scheduled, dry_run=dry_run)

    assert cli.run_trigger(args(scheduled=True, dry_run=True)) == "scheduled"
    assert cli.run_trigger(args(dry_run=True)) == "dry_run"
    assert cli.run_trigger(args()) == "manual"


def test_run_status():
    ok = RoundResult("18:00 - 19:00", True, "booked", 7.0)
    failed = RoundResult("19:00 - 20:00", False, "Hết chỗ", 1.0)

    assert cli.run_status([ok, ok], None, interrupted=False) == "ok"
    assert cli.run_status([ok, failed], None, interrupted=False) == "partial"
    assert cli.run_status([ok], "adb lost", interrupted=False) == "partial"
    assert cli.run_status([failed], None, interrupted=False) == "failed"
    assert cli.run_status([], "MuMu did not start", interrupted=False) == "failed"
    assert cli.run_status([ok], "interrupted", interrupted=True) == "interrupted"


class FakeReader:
    """Reads one ticket and one picture, or fails as ``error`` says."""

    error: ClassVar = None
    made: ClassVar = []
    quotas: ClassVar = []

    def __init__(self, booker, folder, deadline):
        self.booker, self.folder = booker, folder
        self.collected = Collected()
        FakeReader.made.append(self)

    def read(self, wanted):
        self.wanted = wanted
        ticket = Ticket(
            "1234567", "Sân Tennis", "S6", "2026-10-10", "18:00 - 19:00", "Đã đăng ký", None
        )
        self.collected.tickets.append(ticket)
        self.collected.photos["1234567"] = "1234567.png"
        if FakeReader.error is not None:
            raise FakeReader.error
        return self.collected


@pytest.fixture
def reader(monkeypatch):
    """Read the tickets with :class:`FakeReader`, and record what the run did, in order."""
    monkeypatch.setattr(FakeReader, "error", None)
    monkeypatch.setattr(FakeReader, "made", [])
    monkeypatch.setattr(cli, "TicketReader", FakeReader)
    monkeypatch.setattr(FakeReader, "quotas", [])

    def read_quota(booker, play_date, moment, report, slots=None):
        FakeReader.quotas.append((play_date, moment))
        report(EventKind.QUOTA_READ, moment=moment)

    monkeypatch.setattr(cli, "read_quota", read_quota)
    return FakeReader


def run_with_booker(monkeypatch, tmp_path, outcomes, args=(), connect=fake_connect):
    """Run the CLI with rounds that hand a booker over, as the real ones do."""
    inner = fake_run(outcomes)

    def run_booking(device, config, *, on_booker=None, **kwargs):
        on_booker(argparse.Namespace(config=config, device=device))
        return inner(device, config, **kwargs)

    use_connect(monkeypatch, connect)
    monkeypatch.setattr(cli, "run_booking", run_booking)
    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    return cli.main(["--config", str(tmp_path / "missing.toml"), *args])


BOOKED = [("18:00 - 19:00", True), ("19:00 - 20:00", False)]


def test_a_real_run_reads_the_tickets_of_the_slots_it_booked(
    monkeypatch, tmp_path, reader, data_home, closed_mumu
):
    assert run_with_booker(monkeypatch, tmp_path, BOOKED) == cli.EXIT_ROUND_FAILED
    (made,) = reader.made
    assert made.folder == data_home / "tickets"
    (wanted,) = made.wanted
    assert (wanted.slot, wanted.court) == ("18:00 - 19:00", Config().court)
    with sqlite3.connect(data_home / "booker.db") as db:
        assert db.execute("SELECT code, device, photo FROM tickets").fetchall() == [
            ("1234567", 0, "1234567.png")
        ]
        kinds = [row[0] for row in db.execute("SELECT kind FROM events ORDER BY id")]
    # After the run's own result, never before it; the quota once the tickets are saved.
    assert kinds[-3:] == ["run_finished", "tickets_saved", "quota_read"]
    assert reader.quotas == [(date(2026, 10, 10), "after")]


def test_the_tickets_come_after_the_notification_and_before_the_driver_stops(
    monkeypatch, tmp_path, reader
):
    order = []
    devices = []

    def connect(config, driver):
        device = fake_connect(config, driver)
        device.close = lambda: order.append("close")
        devices.append(device)
        return device

    monkeypatch.setattr(cli, "send_windows", lambda title, body: order.append("notify"))
    read = FakeReader.read
    monkeypatch.setattr(
        FakeReader, "read", lambda self, wanted: order.append("tickets") or read(self, wanted)
    )
    monkeypatch.setattr(cli, "close_emulator", lambda config: order.append("mumu"))
    manager = tmp_path / "MuMuManager.exe"
    (tmp_path / "missing.toml").write_text(f"mumu_manager = '{manager}'", encoding="utf-8")
    run_with_booker(monkeypatch, tmp_path, BOOKED, connect=connect)
    assert order == ["notify", "tickets", "close", "mumu"]


@pytest.mark.parametrize(
    ("outcomes", "args"),
    [
        ([("18:00 - 19:00", False)], ()),
        (BOOKED, ("--dry-run",)),
        ([("18:00 - 19:00", True), ("19:00 - 20:00", KeyboardInterrupt)], ()),
    ],
    ids=["nothing booked", "dry run", "interrupted"],
)
def test_no_tickets_are_read(monkeypatch, tmp_path, reader, outcomes, args):
    run_with_booker(monkeypatch, tmp_path, outcomes, args)
    assert reader.made == []


@pytest.mark.parametrize("error", [RuntimeError("boom"), KeyboardInterrupt()])
def test_tickets_that_fail_do_not_change_the_result(
    monkeypatch, tmp_path, reader, closed_mumu, error
):
    monkeypatch.setattr(FakeReader, "error", error)
    (tmp_path / "missing.toml").write_text("mumu_manager = 'MuMuManager.exe'", encoding="utf-8")
    assert run_with_booker(monkeypatch, tmp_path, BOOKED[:1]) == cli.EXIT_OK
    assert len(closed_mumu) == 1


def test_an_emulator_frozen_at_the_tickets_keeps_the_result(
    monkeypatch, tmp_path, reader, closed_mumu, data_home
):
    monkeypatch.setattr(FakeReader, "error", DeviceNotRespondingError("screenshot hung"))
    (tmp_path / "missing.toml").write_text("mumu_manager = 'MuMuManager.exe'", encoding="utf-8")
    assert run_with_booker(monkeypatch, tmp_path, BOOKED[:1]) == cli.EXIT_OK
    assert closed_mumu == []  # MuMuManager does not shut a frozen instance down
    with sqlite3.connect(data_home / "booker.db") as db:
        assert db.execute("SELECT COUNT(*) FROM tickets").fetchone() == (1,)
        assert db.execute("SELECT status FROM runs").fetchall() == [("ok",)]


class StepClock:
    """A clock that moves one second with each look at it."""

    def __init__(self, at):
        self.at = at

    def now(self):
        self.at += timedelta(seconds=1)
        return self.at


class OtherRuns:
    """A history in which another machine books for the first ``looks`` looks."""

    def __init__(self, looks):
        self.looks = looks
        self.saved = []

    def other_runs_going(self):
        self.looks -= 1
        return self.looks >= 0

    def save_tickets(self, *args):
        self.saved.append(args)


def read_after(monkeypatch, looks):
    """Read the tickets of a 06:00 run while another machine books; return what was saved."""
    start = datetime(2026, 11, 22, 6, 0)
    waits = []
    monkeypatch.setattr(cli, "wait_until", lambda moment, now: waits.append(moment))
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: None)
    others = OtherRuns(looks)
    booker = argparse.Namespace(config=Config())
    results = [RoundResult("18:00 - 19:00", True, "booked", 5.0, "S6 - Sân tennis")]
    clock = StepClock(start + cli.TICKETS_AFTER)
    cli.read_tickets(booker, results, start.date(), start, clock, others, lambda kind, **data: None)
    assert waits == [start + timedelta(minutes=3)]
    return others, clock.at - start


def test_tickets_wait_for_the_other_machines_to_end_their_rounds(monkeypatch, reader):
    others, _ = read_after(monkeypatch, looks=5)
    assert others.looks < 0
    assert len(others.saved) == 1
    (wanted,) = reader.made[0].wanted
    assert wanted.court == "S6 - Sân tennis"


def test_tickets_are_read_all_the_same_after_a_run_that_was_killed(monkeypatch, reader, caplog):
    with caplog.at_level(logging.WARNING):
        others, after = read_after(monkeypatch, looks=10_000)
    assert len(others.saved) == 1
    assert after >= timedelta(minutes=3, seconds=30)
    # Before the quiet time of the start ends, with the time reading may take.
    assert after + timedelta(seconds=cli.TICKETS_SECONDS) <= timedelta(minutes=5, seconds=5)
    assert "still recorded as booking" in caplog.text


def test_a_run_by_hand_waits_for_the_other_machines_too(monkeypatch, reader):
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: None)
    others = OtherRuns(3)
    results = [RoundResult("18:00 - 19:00", True, "booked", 5.0)]
    clock = StepClock(datetime(2026, 11, 22, 10, 0))
    booker = argparse.Namespace(config=Config())
    day = datetime(2026, 11, 24).date()
    cli.read_tickets(booker, results, day, None, clock, others, lambda kind, **data: None)
    assert others.looks < 0
    assert len(others.saved) == 1


@pytest.mark.parametrize(
    ("args", "times"),
    [((), 1), (("--dry-run",), 0), (("--instance", "1"), 0)],
    ids=["real run", "dry run", "a run beside the first"],
)
def test_a_real_run_forgets_the_expired_tickets_once_all_is_done(
    monkeypatch, tmp_path, reader, data_home, closed_mumu, args, times
):
    (tmp_path / "missing.toml").write_text("[[instances]]\nmumu_index = 1\n", encoding="utf-8")
    monkeypatch.setattr(cli, "start_instances", lambda *args, **kwargs: [])
    order = []
    monkeypatch.setattr(cli, "wait_for_instances", lambda instances: order.append("all done"))
    monkeypatch.setattr(cli, "forget_expired", lambda data, today: order.append((data.root, today)))
    run_with_booker(monkeypatch, tmp_path, BOOKED[:1], args)
    assert order == ["all done"] + [(data_home, FixedDatetime.now().date())] * times


def short_quota(used):
    def read_quota(booker, play_date, moment, report, slots=None):
        return Quota("Sân Tennis", play_date.isoformat()[:7], used, play_date.isoformat(), 1)

    return read_quota


@pytest.mark.parametrize(("used", "warned"), [(7, True), (6, False)])
def test_a_quota_too_short_for_the_next_run_is_told(
    monkeypatch, tmp_path, reader, data_home, closed_mumu, windows_notifications, used, warned
):
    monkeypatch.setattr(cli, "read_quota", short_quota(used))

    run_with_booker(monkeypatch, tmp_path, BOOKED)

    titles = [title for title, _ in windows_notifications]
    assert ("Lần đặt tới thiếu hạn mức" in titles) is warned
    if warned:
        body = windows_notifications[-1][1]
        assert body.startswith("Sân Tennis còn 1/8 của tháng 10/2026, mà đã chọn 2 khung giờ")
