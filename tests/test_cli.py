"""CLI exit codes with the device layer replaced by fakes."""

from datetime import datetime

import court_booker.cli as cli
from court_booker.errors import EmulatorError
from court_booker.runner import RoundResult


def fake_run(outcomes):
    def run_booking(device, config, *, results, **kwargs):
        run_booking.kwargs = kwargs
        for slot, ok in outcomes:
            if ok is KeyboardInterrupt:
                raise KeyboardInterrupt
            results.append(RoundResult(slot, ok, "detail", 1.0))
        return results

    return run_booking


def run_cli(monkeypatch, tmp_path, outcomes=(), connect=lambda config: object(), args=()):
    monkeypatch.setattr(cli, "connect_device", connect)
    monkeypatch.setattr(cli, "run_booking", fake_run(outcomes))
    return cli.main(["--config", str(tmp_path / "missing.toml"), *args])


def test_all_rounds_ok_exits_0(monkeypatch, tmp_path):
    assert run_cli(monkeypatch, tmp_path, [("18:00 - 19:00", True)]) == cli.EXIT_OK


def test_failed_round_exits_1(monkeypatch, tmp_path):
    outcomes = [("18:00 - 19:00", False), ("19:00 - 20:00", True)]
    assert run_cli(monkeypatch, tmp_path, outcomes) == cli.EXIT_ROUND_FAILED


def test_bad_config_exits_2(monkeypatch, tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("unknown = 1\n", encoding="utf-8")
    monkeypatch.setattr(cli, "connect_device", lambda config: object())
    assert cli.main(["--config", str(path)]) == cli.EXIT_BAD_REQUEST


def test_device_error_exits_3(monkeypatch, tmp_path):
    def connect(config):
        raise EmulatorError("MuMu did not start")

    assert run_cli(monkeypatch, tmp_path, connect=connect) == cli.EXIT_DEVICE


def test_ctrl_c_prints_finished_rounds_and_exits_130(monkeypatch, tmp_path, capsys):
    outcomes = [("18:00 - 19:00", True), ("19:00 - 20:00", KeyboardInterrupt)]

    assert run_cli(monkeypatch, tmp_path, outcomes) == cli.EXIT_INTERRUPTED
    out = capsys.readouterr().out
    assert "Summary" in out
    assert "OK   18:00 - 19:00" in out


def test_passed_start_time_exits_2_before_connecting(monkeypatch, tmp_path):
    def connect(config):
        raise AssertionError("must not connect")

    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    code = run_cli(monkeypatch, tmp_path, connect=connect, args=["--at", "05:00"])
    assert code == cli.EXIT_BAD_REQUEST


def test_scheduled_uses_config_start_and_clock_offset(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    monkeypatch.setattr(cli, "ntp_offset", lambda server: 0.25)
    run = fake_run([("18:00 - 19:00", True)])
    monkeypatch.setattr(cli, "connect_device", lambda config: object())
    monkeypatch.setattr(cli, "run_booking", run)

    assert cli.main(["--config", str(tmp_path / "missing.toml"), "--scheduled"]) == 0
    assert run.kwargs["start"] == datetime(2026, 10, 8, 6, 0)
    assert run.kwargs["offset"] == 0.25


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 8, 5, 45)
