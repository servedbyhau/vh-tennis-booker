"""MuMu control tests with a fake MuMuManager; no emulator required."""

import json
import subprocess

import pytest

from court_booker.emulator import CALL_ATTEMPTS, RETRY_DELAY, MuMu, instance_indexes
from court_booker.errors import EmulatorError, MuMuNotFoundError

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


def test_show_window_brings_the_instance_to_the_front(manager_path):
    calls = []

    def run(argv):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    MuMu(manager_path, 2, run=run).show_window()

    assert calls == [[str(manager_path), "control", "-v", "2", "show_window"]]


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


def test_a_stopped_instance_is_seen_stopped(manager_path):
    fake = FakeManager(started=False)

    assert make(manager_path, fake).wait_stopped(timeout=5)


def test_an_instance_that_keeps_running_is_not_seen_stopped(manager_path):
    def run(argv):
        state = {"index": "0", "is_process_started": True, "is_android_started": True}
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(state), stderr="")

    clock = [0.0]

    def sleep(seconds):
        clock[0] += seconds

    mumu = MuMu(manager_path, run=run, clock=lambda: clock[0], sleep=sleep)

    assert not mumu.wait_stopped(timeout=5)
    assert clock[0] >= 5


def test_an_unreadable_state_counts_as_still_running(manager_path):
    def run(argv):  # a frozen instance makes info hang until its time limit
        raise subprocess.TimeoutExpired(argv, 20)

    clock = [0.0]

    def sleep(seconds):
        clock[0] += seconds

    mumu = MuMu(manager_path, run=run, clock=lambda: clock[0], sleep=sleep)

    assert not mumu.wait_stopped(timeout=2)


def test_a_missing_manager_is_a_failure_no_repair_can_change(tmp_path):
    with pytest.raises(MuMuNotFoundError):
        MuMu(tmp_path / "missing.exe", run=FakeManager().run).is_started()


_DEVICE_EXE = r'"C:\Program Files\Netease\MuMuPlayer\nx_device\15.0\shell\MuMuNxDevice.exe"'
DEVICES = [
    (9232, f"{_DEVICE_EXE} --vm MuMuPlayerGlobal-15.0-0"),
    (13168, f"{_DEVICE_EXE} --vm MuMuPlayerGlobal-15.0-1"),
]
"""The two instances' processes as Windows lists them (2026-11-19)."""


@pytest.mark.parametrize(("index", "ended"), [(0, [9232]), (1, [13168])])
def test_kill_ends_the_process_of_its_instance_alone(manager_path, index, ended):
    stopped = []

    found = MuMu(manager_path, index).kill(find=lambda name: DEVICES, stop=stopped.append)

    assert found and stopped == ended


def test_kill_without_a_process_ends_nothing(manager_path):
    stopped = []

    assert not MuMu(manager_path, 2).kill(find=lambda name: DEVICES, stop=stopped.append)
    assert stopped == []


def test_a_process_that_cannot_be_ended_is_logged(manager_path, caplog):
    def stop(pid):
        raise PermissionError("access denied")

    assert MuMu(manager_path, 0).kill(find=lambda name: DEVICES, stop=stop)
    assert "Could not end process 9232: access denied" in caplog.text


def test_a_sibling_asks_the_same_manager_about_another_instance(manager_path):
    fake = FakeManager(started=True)
    argvs = []

    def run(argv):
        argvs.append(argv)
        return fake.run(argv)

    mumu = MuMu(manager_path, 0, run=run, clock=lambda: fake.now, sleep=fake.sleep, attempts=3)
    sibling = mumu.sibling(4)

    assert sibling.is_started()
    assert (sibling.manager, sibling.index, sibling.attempts) == (manager_path, 4, 1)
    assert "4" in argvs[-1]


@pytest.mark.parametrize(
    ("answer", "indexes"),
    [
        ({"0": STOPPED, "2": STOPPED, "1": RUNNING}, [0, 1, 2]),
        (STOPPED, [0]),  # one instance answers as itself
    ],
)
def test_the_instances_are_listed_lowest_first(manager_path, answer, indexes):
    def run(argv):
        assert argv[1:] == ["info", "-v", "all"]
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(answer), stderr="")

    assert instance_indexes(manager_path, run) == indexes


def test_a_listing_that_fails_raises(manager_path, tmp_path):
    def run(argv):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="nemu-api init failed")

    with pytest.raises(EmulatorError):
        instance_indexes(manager_path, run)
    with pytest.raises(MuMuNotFoundError):
        instance_indexes(tmp_path / "missing.exe", run)
