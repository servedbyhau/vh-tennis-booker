"""MuMu control tests with a fake MuMuManager; no emulator required."""

import json
import subprocess

import pytest

from court_booker.emulator import CALL_ATTEMPTS, RETRY_DELAY, MuMu
from court_booker.errors import EmulatorError

RUNNING = {
    "index": "0",
    "is_android_started": True,
    "adb_host_ip": "127.0.0.1",
    "adb_port": 16384,
}
STOPPED = {"index": "0", "is_android_started": False}


class FakeManager:
    """Records calls; Android reports started after ``boot_polls`` info calls post-launch."""

    def __init__(self, started=False, boot_polls=2, keyed=False):
        self.calls = []
        self.started = started
        self.boot_polls = boot_polls
        self.keyed = keyed
        self.now = 0.0

    def run(self, argv):
        command = argv[1]
        self.calls.append(command)
        if command == "control":
            self.launched_at = len(self.calls)
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if not self.started and "control" in self.calls:
            polls_since_launch = len(self.calls) - self.launched_at
            self.started = polls_since_launch >= self.boot_polls
        state = RUNNING if self.started else STOPPED
        data = {"0": state} if self.keyed else state
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(data), stderr="")

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture
def manager_path(tmp_path):
    path = tmp_path / "MuMuManager.exe"
    path.write_bytes(b"")
    return path


def make(manager_path, fake):
    return MuMu(manager_path, 0, run=fake.run, clock=lambda: fake.now, sleep=fake.sleep)


def test_running_instance_is_not_launched(manager_path):
    fake = FakeManager(started=True)
    make(manager_path, fake).ensure_started(timeout=180)
    assert fake.calls == ["info"]


def test_stopped_instance_is_launched_and_awaited(manager_path):
    fake = FakeManager(boot_polls=3)
    make(manager_path, fake).ensure_started(timeout=180)
    assert fake.calls == ["info", "control", "info", "info", "info"]


def test_boot_timeout_raises(manager_path):
    fake = FakeManager(boot_polls=1000)
    with pytest.raises(EmulatorError, match="did not finish booting"):
        make(manager_path, fake).ensure_started(timeout=10)


def test_adb_serial_from_keyed_info(manager_path):
    fake = FakeManager(started=True, keyed=True)
    assert make(manager_path, fake).adb_serial() == "127.0.0.1:16384"


def test_missing_manager_explains_the_setting(tmp_path):
    mumu = MuMu(tmp_path / "missing.exe", run=FakeManager().run)
    with pytest.raises(EmulatorError, match="mumu_manager"):
        mumu.is_started()


class SettingManager:
    """Answers ``setting`` like MuMuManager: JSON of the asked keys; records every call."""

    def __init__(self, values):
        self.values = dict(values)
        self.calls = []

    def run(self, argv):
        self.calls.append(argv[1:])
        args = argv[4:]
        if "-val" in args:
            pairs = zip(args[1::4], args[3::4])
            self.values.update(pairs)
            output = ""
        else:
            output = json.dumps({key: self.values[key] for key in args[1::2]})
        return subprocess.CompletedProcess(argv, 0, stdout=output, stderr="")


def test_settings_are_read_by_key(manager_path):
    fake = SettingManager({"resolution_width": "540.000000", "resolution_dpi": "220.000000"})

    values = MuMu(manager_path, run=fake.run).settings("resolution_width", "resolution_dpi")

    assert values == {"resolution_width": "540.000000", "resolution_dpi": "220.000000"}
    assert fake.calls == [["setting", "-v", "0", "-k", "resolution_width", "-k", "resolution_dpi"]]


def test_settings_are_written_as_key_value_pairs(manager_path):
    fake = SettingManager({})

    MuMu(manager_path, run=fake.run).change_settings({"resolution_mode": "custom", "x": "1"})

    assert fake.calls == [
        ["setting", "-v", "0", "-k", "resolution_mode", "-val", "custom", "-k", "x", "-val", "1"]
    ]
    assert fake.values == {"resolution_mode": "custom", "x": "1"}


def test_unreadable_settings_raise(manager_path):
    def run(argv):
        return subprocess.CompletedProcess(argv, 0, stdout="no json", stderr="")

    with pytest.raises(EmulatorError, match="setting"):
        MuMu(manager_path, run=run).settings("resolution_dpi")


def test_restart_asks_mumu(manager_path):
    fake = FakeManager(started=True)

    make(manager_path, fake).restart()

    assert fake.calls == ["control"]


def test_shutdown_asks_mumu_to_shut_the_instance_down(manager_path):
    calls = []

    def run(argv):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    MuMu(manager_path, 1, run=run).shutdown()

    assert calls == [[str(manager_path), "control", "-v", "1", "shutdown"]]


def test_failed_command_raises(manager_path):
    calls = []

    def run(argv):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="no such player")

    with pytest.raises(EmulatorError, match="no such player"):
        MuMu(manager_path, run=run).is_started()
    assert len(calls) == 1  # the setup checks and the backend answer at once


NEMU_FAILED = '{\n  "errcode": -500,\n  "errmsg": "nemu-api init failed"\n}'
"""What ``control launch`` printed on 2026-11-19, exit code 4294966796."""


class FlakyManager(FakeManager):
    """Fails ``command`` (any, if empty) ``failures`` times, as MuMuManager did on 2026-11-19."""

    def __init__(self, failures, command="", **kwargs):
        super().__init__(**kwargs)
        self.failures = failures
        self.command = command
        self.sleeps = []

    def run(self, argv):
        if self.failures and self.command in ("", argv[1]):
            self.failures -= 1
            self.calls.append(f"{argv[1]} (failed)")
            return subprocess.CompletedProcess(argv, 4294966796, stdout=NEMU_FAILED, stderr="")
        return super().run(argv)

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        super().sleep(seconds)


def flaky(manager_path, fake):
    return MuMu(
        manager_path,
        run=fake.run,
        clock=lambda: fake.now,
        sleep=fake.sleep,
        attempts=CALL_ATTEMPTS,
    )


def test_a_failed_command_of_a_run_is_tried_again(manager_path, caplog):
    fake = FlakyManager(failures=1, started=True)

    assert flaky(manager_path, fake).is_started()
    assert fake.calls == ["info (failed)", "info"]
    assert fake.sleeps == [RETRY_DELAY]
    assert "nemu-api init failed" in caplog.text and "trying again in 2 s (2 of 3)" in caplog.text


def test_a_launch_that_fails_once_still_boots(manager_path):
    fake = FlakyManager(failures=1, command="control", boot_polls=1)

    flaky(manager_path, fake).ensure_started(timeout=180)

    assert fake.calls == ["info", "control (failed)", "control", "info"]


def test_a_command_failing_every_try_raises(manager_path):
    fake = FlakyManager(failures=10, started=True)

    with pytest.raises(EmulatorError, match="nemu-api init failed"):
        flaky(manager_path, fake).is_started()
    assert fake.calls == ["info (failed)"] * 3
    assert fake.sleeps == [RETRY_DELAY] * 2


class StuckBootManager(FakeManager):
    """Android never boots after the launch; after a ``control restart`` it boots at once."""

    def run(self, argv):
        if argv[1] == "control" and argv[-1] == "restart":
            self.boot_polls = 1
        return super().run(argv)


def test_an_instance_that_does_not_boot_is_restarted(manager_path, caplog):
    fake = StuckBootManager(boot_polls=1000)

    make(manager_path, fake).ensure_started(timeout=10, restarts=1)

    # Five polls 2 s apart fill the 10 s, then the restart and the poll that sees Android.
    assert fake.calls == ["info", "control"] + ["info"] * 5 + ["control", "info"]
    assert "did not finish booting in 10 s; restarting it (1 of 1)" in caplog.text


def test_an_instance_that_does_not_boot_after_its_restarts_raises(manager_path):
    fake = FakeManager(boot_polls=1000)

    with pytest.raises(EmulatorError, match="did not finish booting"):
        make(manager_path, fake).ensure_started(timeout=10, restarts=1)
    assert fake.calls.count("control") == 2  # the launch and one restart
