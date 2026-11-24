import json
import subprocess
from datetime import datetime

import pytest

from court_booker import history, processes
from court_booker.api import tasks
from court_booker.engine import engine_command
from court_booker.lock import Holder
from court_booker.tickets import Ticket

PNG = b"\x89PNG\r\n\x1a\nmade up"


@pytest.fixture
def save(context):
    """Return a function that records tickets of a MuMu instance, as a run does."""

    def record(device, *tickets, photos=None, holder=None):
        store = history.History(history.connect(context.data.database))
        if holder is not None:
            store.set_holder(holder)
        store.save_tickets(device, tickets, photos or {}, datetime(2026, 10, 1, 6, 1, 12))
        store.close()

    return record


def ticket(code="1234567", play_date="2026-10-03", slot="08:00 - 09:00", status="Đã đăng ký"):
    return Ticket(
        code, "Sân Tennis", "S6 - Sân tennis", play_date, slot, status, "2026-10-01T06:00"
    )


def add_photo(context, name, data=PNG):
    context.data.tickets.mkdir(parents=True, exist_ok=True)
    (context.data.tickets / name).write_bytes(data)


def test_no_tickets_yet(client):
    assert client.get("/api/tickets").json() == []


def test_a_ticket_comes_with_what_the_app_showed(client, context, save):
    save(1, ticket(), photos={"1234567": "1234567.png"})
    add_photo(context, "1234567.png")
    assert client.get("/api/tickets").json() == [
        {
            "code": "1234567",
            "device": 1,
            "customer": None,
            "account": None,
            "court": "S6 - Sân tennis",
            "play_date": "2026-10-03",
            "slot": "08:00 - 09:00",
            "status": "registered",
            "status_text": "Đã đăng ký",
            "created_at": "2026-10-01T06:00",
            "seen_at": "2026-10-01T06:01:12.000",
            "has_photo": True,
            "machine": 1,
        }
    ]


def test_every_machine_s_tickets_come_together(client, save):
    save(1, ticket("11"), ticket("22", "2026-10-02"))
    save(2, ticket("33", slot="07:00 - 08:00"), ticket("44", status="Đã huỷ"))
    listed = client.get("/api/tickets").json()
    assert [(item["code"], item["device"]) for item in listed] == [
        ("33", 2),
        ("11", 1),
        ("44", 2),
        ("22", 1),
    ]
    assert [item["status"] for item in listed if item["code"] == "44"] == ["cancelled"]
    later = client.get("/api/tickets", params={"since": "2026-10-03", "limit": 2}).json()
    assert [item["code"] for item in later] == ["33", "11"]


@pytest.mark.parametrize("params", [{"since": "3/10"}, {"limit": 0}, {"limit": 99999}])
def test_a_query_out_of_bounds_is_refused(client, params):
    answer = client.get("/api/tickets", params=params)
    assert (answer.status_code, answer.json()["error"]) == (422, "invalid_request")


def test_a_picture_is_served(client, context, save):
    save(1, ticket(), photos={"1234567": "1234567.png"})
    add_photo(context, "1234567.png")
    answer = client.get("/api/tickets/1234567/photo")
    assert answer.status_code == 200
    assert answer.content == PNG
    assert answer.headers["content-type"] == "image/png"
    assert answer.headers["cache-control"] == "no-cache"


def test_a_picture_deleted_since_is_not_found(client, save):
    save(1, ticket(), photos={"1234567": "1234567.png"})
    assert [item["has_photo"] for item in client.get("/api/tickets").json()] == [False]
    answer = client.get("/api/tickets/1234567/photo")
    assert (answer.status_code, answer.json()["error"]) == (404, "not_found")


def test_a_ticket_without_a_picture_is_not_found(client, save):
    save(1, ticket())
    assert client.get("/api/tickets/1234567/photo").status_code == 404
    assert client.get("/api/tickets/99/photo").status_code == 404


@pytest.mark.parametrize("code", ["..%5Cbooker", "abc", "1" * 21])
def test_only_a_code_names_a_picture(client, code):
    assert client.get(f"/api/tickets/{code}/photo").status_code in (404, 422)


def test_a_picture_is_served_from_its_folder_only(client, context, save):
    """Whatever the database holds, no other file of the PC is answered."""
    secret = context.data.root / "config.toml"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text("secret", encoding="utf-8")
    save(1, ticket(), photos={"1234567": "../config.toml"})
    assert client.get("/api/tickets/1234567/photo").status_code == 404


class At(datetime):
    moment = datetime(2026, 10, 2, 14, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.moment


class FakeProcess:
    """A cancel that runs until ``finish`` is called."""

    pid = 4321

    def __init__(self):
        self.code = None

    def poll(self):
        return self.code

    def finish(self, code=0):
        self.code = code


@pytest.fixture
def launched(monkeypatch):
    """Record the cancels started instead of starting processes; the time is 14:00."""
    calls = []

    def launch(path, argv):
        calls.append((path, argv))
        return FakeProcess()

    monkeypatch.setattr(tasks, "launcher", launch)
    monkeypatch.setattr(tasks, "datetime", At)
    return calls


def attach_account(client, index):
    """Add a customer's account and attach it to MuMu instance ``index``; return its id."""
    customer = client.post("/api/customers", json={"name": "An"}).json()
    account = {"phone": "0900000079", "password": "x", "label": "Căn A"}
    added = client.post(f"/api/customers/{customer['id']}/accounts", json=account).json()
    account_id = added["accounts"][0]["id"]
    if index is not None:
        assert client.put(
            f"/api/machines/{index}/account", json={"account_id": account_id}
        ).is_success
    return account_id


def test_a_ticket_is_cancelled_by_the_machine_its_account_is_on(client, context, save, launched):
    account_id = attach_account(client, 2)
    save(1, ticket(), holder=history.Holder(account_id, "An", "Căn A"))

    (listed,) = client.get("/api/tickets").json()
    answer = client.post("/api/tickets/1234567/cancel")

    assert listed["machine"] == 2  # moved since machine 1 read it
    assert answer.status_code == 202
    assert answer.json() == {
        "code": "1234567",
        "machine": 2,
        "started_at": "2026-10-02T14:00:00",
        "running": True,
        "exit_code": None,
    }
    assert launched == [(context.config_path.resolve(), ["cancel", "1234567", "--instance", "2"])]


def test_a_ticket_of_the_first_machine_needs_no_instance(client, save, launched):
    save(0, ticket())  # read without a chosen account: its own machine cancels it

    assert client.post("/api/tickets/1234567/cancel").status_code == 202
    assert launched[0][1] == ["cancel", "1234567"]


def test_the_cancel_started_last_tells_how_it_ended(app, client, save, launched):
    assert client.get("/api/tickets/cancel").json()["code"] is None
    save(1, ticket())
    client.post("/api/tickets/1234567/cancel")

    app.state.cancel.process.finish(1)
    state = client.get("/api/tickets/cancel").json()

    assert (state["code"], state["running"], state["exit_code"]) == ("1234567", False, 1)


def test_a_ticket_whose_account_is_on_no_machine_is_not_cancelled(client, save, launched):
    account_id = attach_account(client, None)
    save(1, ticket(), holder=history.Holder(account_id, "An", "Căn A"))

    (listed,) = client.get("/api/tickets").json()
    answer = client.post("/api/tickets/1234567/cancel")

    assert listed["machine"] is None
    assert (answer.status_code, answer.json()["error"]) == (409, "no_machine")
    assert launched == []


@pytest.mark.parametrize(
    ("code", "status", "error"),
    [("1234567", 409, "ticket_cancelled"), ("7654321", 404, "not_found")],
)
def test_a_ticket_cancelled_or_unknown_is_refused(client, save, launched, code, status, error):
    save(1, ticket(status="Đã huỷ"))

    answer = client.post(f"/api/tickets/{code}/cancel")

    assert (answer.status_code, answer.json()["error"]) == (status, error)
    assert launched == []


def test_no_cancel_around_the_scheduled_run(client, save, launched, monkeypatch):
    monkeypatch.setattr(At, "moment", datetime(2026, 10, 2, 5, 50))
    save(1, ticket())

    assert client.post("/api/tickets/1234567/cancel").status_code == 400
    assert launched == []


@pytest.mark.parametrize("lock", ["run.lock", "run-mumu1.lock"])
def test_no_cancel_while_a_run_uses_the_machine(client, context, save, launched, lock):
    save(1, ticket())
    context.data.ensure()
    pid, started = processes.current()
    holder = Holder(pid, started, "scheduled", "2026-10-02T13:59:00")
    (context.data.root / lock).write_text(json.dumps(vars(holder)), encoding="utf-8")

    answer = client.post("/api/tickets/1234567/cancel")

    assert (answer.status_code, answer.json()["error"]) == (409, "lock_held")
    assert launched == []


def test_one_cancel_at_a_time(app, client, save, launched):
    save(1, ticket("11"), ticket("22"))
    client.post("/api/tickets/11/cancel")

    second = client.post("/api/tickets/22/cancel")
    app.state.cancel.process.finish()
    after = client.post("/api/tickets/22/cancel")

    assert (second.status_code, after.status_code) == (409, 202)


def test_launch_starts_the_task_command(monkeypatch, tmp_path):
    started = []
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **options: started.append(argv))

    tasks.launch(tmp_path / "config.toml", ["cancel", "1234567", "--instance", "2"])

    path = str(tmp_path / "config.toml")
    assert started == [
        [*engine_command(), "cancel", "1234567", "--instance", "2", "--config", path],
    ]
