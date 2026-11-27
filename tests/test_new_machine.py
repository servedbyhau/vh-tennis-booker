"""A new machine's MuMu instance, made with a fake MuMuManager; no emulator required."""

import json
import subprocess

import pytest

from court_booker import new_machine
from court_booker.errors import EmulatorError
from court_booker.new_machine import MACHINE_SETTINGS, NoRoomError, check_room, make_machine

GB = 1024**3


class FakeMuMu:
    """MuMuManager's instances: a copy answers -502 at once and grows its disk over the reads
    after, as MuMu Player 6.8 does; ``empty`` keeps the copy's disk at 0."""

    def __init__(self, running=False, empty=False, size=7 * GB):
        self.instances = {0: {"size": size, "running": running, "settings": {}}}
        self.empty = empty
        self.calls = []
        self.now = 0.0

    def run(self, argv):
        command, index = argv[1], argv[3]
        self.calls.append((command, *argv[3:]))
        if command == "info":
            if index == "all":
                data = {str(i): self._info(i) for i in self.instances}
            else:
                data = self._info(int(index))
            return self._answer(data)
        instance = self.instances[int(index)]
        if command == "control":
            instance["running"] = argv[4] == "launch"
            return self._answer({})
        if command == "clone":
            self.instances[max(self.instances) + 1] = {"size": 0, "running": False, "settings": {}}
            return subprocess.CompletedProcess(argv, -502, stdout='{"errmsg": "mainnx"}', stderr="")
        if command == "setting":
            pairs = argv[4:]
            if "-val" in pairs:
                for key, value in zip(pairs[1::4], pairs[3::4]):
                    instance["settings"][key] = value
                return self._answer({})
            return self._answer({key: instance["settings"].get(key) for key in pairs[1::2]})
        if command == "delete":
            del self.instances[int(index)]
            return self._answer({})
        raise AssertionError(argv)

    def _info(self, index):
        instance = self.instances[index]
        if index != 0 and not self.empty and instance["size"] < self.instances[0]["size"]:
            instance["size"] += self.instances[0]["size"] // 2  # copied over two reads
        return {
            "index": str(index),
            "disk_size_bytes": instance["size"],
            "is_process_started": instance["running"],
        }

    @staticmethod
    def _answer(data):
        return subprocess.CompletedProcess([], 0, stdout=json.dumps(data), stderr="")

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture
def manager(tmp_path):
    path = tmp_path / "MuMuManager.exe"
    path.write_bytes(b"")
    return path


def make(manager, fake):
    return make_machine(manager, 0, run=fake.run, sleep=fake.sleep, clock=lambda: fake.now)


def test_a_copy_of_the_first_instance_is_made_and_set_up_once_copied(manager):
    fake = FakeMuMu()

    index = make(manager, fake)

    assert index == 1
    assert fake.instances[1]["size"] == fake.instances[0]["size"]
    assert fake.instances[1]["settings"] == MACHINE_SETTINGS
    assert ("clone", "0") in fake.calls


def test_a_running_first_instance_is_shut_to_be_copied_and_started_again(manager):
    fake = FakeMuMu(running=True)

    make(manager, fake)

    controls = [call for call in fake.calls if call[0] == "control"]
    assert controls == [("control", "0", "shutdown"), ("control", "0", "launch")]
    assert fake.instances[0]["running"] is True


def test_an_empty_copy_fails_and_is_deleted(manager):
    fake = FakeMuMu(empty=True)

    with pytest.raises(EmulatorError, match="empty instance"):
        make(manager, fake)

    assert list(fake.instances) == [0]


@pytest.mark.parametrize(
    ("ram", "free", "why"),
    [(8, 50 * GB, "RAM"), (16, 5 * GB, "disk")],
)
def test_no_room_is_told_before_any_copy(manager, ram, free, why):
    fake = FakeMuMu()
    fake.instances[1] = {"size": 7 * GB, "running": False, "settings": {}}  # 3 with the new one

    with pytest.raises(NoRoomError, match=why) as refused:
        check_room(manager, 0, ram_gb=lambda: ram, free_disk=lambda path: free, run=fake.run)

    assert refused.value.reason == why.lower()

    assert not any(call[0] == "clone" for call in fake.calls)


def test_room_counts_the_new_instance(manager):
    fake = FakeMuMu()

    count = check_room(manager, 0, ram_gb=lambda: 8, free_disk=lambda path: 50 * GB, run=fake.run)

    assert count == 2  # 2 x 2 GB + 4 GB for Windows fit in 8 GB


def test_the_settings_are_the_ones_a_run_needs():
    assert new_machine.MACHINE_SETTINGS["resolution_width.custom"] == "540"
    assert new_machine.MACHINE_SETTINGS["performance_cpu.custom"] == "2"
