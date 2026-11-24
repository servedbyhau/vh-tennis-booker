"""The quota read of a machine, started from the app, with the process launch replaced."""

from datetime import datetime
from typing import ClassVar

import pytest

from court_booker.api import tasks


class At(datetime):
    moment = datetime(2026, 10, 2, 14, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.moment


class FakeProcess:
    pid = 4321

    def __init__(self):
        self.code = None

    def poll(self):
        return self.code

    def finish(self, code=0):
        self.code = code


@pytest.fixture
def launched(monkeypatch):
    calls = []

    def launch(path, argv):
        calls.append(argv)
        return FakeProcess()

    monkeypatch.setattr(tasks, "launcher", launch)
    monkeypatch.setattr(tasks, "datetime", At)
    return calls


def attach_account(client, index):
    customer = client.post("/api/customers", json={"name": "An"}).json()
    account = {"phone": "0900000079", "password": "x", "label": "Căn A"}
    added = client.post(f"/api/customers/{customer['id']}/accounts", json=account).json()
    account_id = added["accounts"][0]["id"]
    assert client.put(f"/api/machines/{index}/account", json={"account_id": account_id}).is_success


def test_a_machine_reads_its_account_s_quota_again(app, client, launched):
    attach_account(client, 2)
    assert client.get("/api/machines/quota").json()["machine"] is None

    answer = client.post("/api/machines/2/quota")
    app.state.quota.process.finish()
    state = client.get("/api/machines/quota").json()

    assert answer.status_code == 202
    assert answer.json()["running"] is True
    assert launched == [["quota", "--instance", "2"]]
    assert (state["machine"], state["running"], state["exit_code"]) == (2, False, 0)


def test_the_first_machine_reads_it_without_an_instance(client, launched):
    attach_account(client, 0)

    assert client.post("/api/machines/0/quota").status_code == 202
    assert launched == [["quota"]]


def test_a_machine_without_an_account_reads_nothing(client, launched):
    answer = client.post("/api/machines/1/quota")

    assert (answer.status_code, answer.json()["error"]) == (409, "no_machine")
    assert launched == []


def test_one_task_at_a_time_across_kinds(app, client, launched):
    attach_account(client, 2)
    client.post("/api/machines/2/quota")

    second = client.post("/api/machines/2/quota")

    assert (second.status_code, second.json()["error"]) == (409, "lock_held")
    assert second.json()["detail"] == "Another task is in progress: quota on MuMu 2"


def test_no_quota_read_around_the_scheduled_run(client, launched, monkeypatch):
    attach_account(client, 2)
    monkeypatch.setattr(At, "moment", datetime(2026, 10, 2, 5, 50))

    assert client.post("/api/machines/2/quota").status_code == 400
    assert launched == []


class FakeMuMu:
    """MuMu as MuMuManager tells it: ``running`` instances, and what was asked."""

    running: ClassVar[set] = set()
    asked: ClassVar[list] = []

    def __init__(self, manager, index):
        self.index = index

    def is_process_started(self):
        return self.index in FakeMuMu.running

    def launch(self):
        FakeMuMu.asked.append(("launch", self.index))

    def show_window(self):
        FakeMuMu.asked.append(("show", self.index))


@pytest.fixture
def mumu(monkeypatch, tmp_path):
    FakeMuMu.running, FakeMuMu.asked = set(), []
    monkeypatch.setattr(tasks, "find_mumu_manager", lambda configured: tmp_path / "MuMu.exe")
    monkeypatch.setattr(tasks, "MuMu", FakeMuMu)
    monkeypatch.setattr(tasks, "datetime", At)
    return FakeMuMu


def test_a_machine_off_is_launched(client, mumu):
    assert client.post("/api/machines/2/open").status_code == 204
    assert mumu.asked == [("launch", 2)]


def test_a_machine_on_shows_its_window(client, mumu):
    mumu.running = {0}

    assert client.post("/api/machines/0/open").status_code == 204
    assert mumu.asked == [("show", 0)]


def test_no_machine_opens_while_a_task_uses_it(app, client, mumu, launched):
    attach_account(client, 2)
    client.post("/api/machines/2/quota")

    answer = client.post("/api/machines/1/open")

    assert (answer.status_code, answer.json()["error"]) == (409, "lock_held")
    assert mumu.asked == []


def test_no_machine_opens_around_the_scheduled_run(client, mumu, monkeypatch):
    monkeypatch.setattr(At, "moment", datetime(2026, 10, 2, 5, 50))

    assert client.post("/api/machines/0/open").status_code == 400
    assert mumu.asked == []


def test_without_mumumanager_nothing_opens(client, mumu, monkeypatch):
    monkeypatch.setattr(tasks, "find_mumu_manager", lambda configured: None)

    answer = client.post("/api/machines/0/open")

    assert (answer.status_code, answer.json()["error"]) == (503, "device")
