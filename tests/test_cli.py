"""CLI exit codes with the device layer replaced by fakes."""

import court_booker.cli as cli
from court_booker.errors import EmulatorError
from court_booker.runner import RoundResult


def fake_run(outcomes):
    def run_booking(device, config, *, dry_run=False, results=None):
        for slot, ok in outcomes:
            if ok is KeyboardInterrupt:
                raise KeyboardInterrupt
            results.append(RoundResult(slot, ok, "detail", 1.0))
        return results

    return run_booking


def run_cli(monkeypatch, tmp_path, outcomes=(), connect=lambda config: object()):
    monkeypatch.setattr(cli, "connect_device", connect)
    monkeypatch.setattr(cli, "run_booking", fake_run(outcomes))
    return cli.main(["--config", str(tmp_path / "missing.toml")])


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
