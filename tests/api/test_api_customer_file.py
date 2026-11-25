"""The customers' file routes: the file written, its template, and a file read back."""

import io
import os

from openpyxl import Workbook, load_workbook

from court_booker.customer_file import HEADERS
from court_booker.lock import RunLock

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def workbook(*rows):
    book = Workbook()
    book.active.append(list(HEADERS))
    for row in rows:
        book.active.append(list(row))
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def add(client, name="An", phone="0900000011", password="mk-1"):
    customer = client.post("/api/customers", json={"name": name}).json()
    client.post(
        f"/api/customers/{customer['id']}/accounts",
        json={"phone": phone, "password": password, "label": "Căn A"},
    )


def rows_of(answer):
    sheet = load_workbook(io.BytesIO(answer.content)).active
    return [[cell.value for cell in row] for row in sheet]


def test_the_file_is_an_excel_workbook_with_passwords_only_when_asked(client, saved_logins):
    add(client)

    plain = client.get("/api/customers/file")
    whole = client.get("/api/customers/file", params={"passwords": True})

    assert plain.headers["content-type"] == XLSX
    assert plain.headers["cache-control"] == "no-store"
    assert "attachment" in plain.headers["content-disposition"]
    assert rows_of(plain)[1] == ["An", None, None, None, "Căn A", "0900000011", None]
    assert rows_of(whole)[1][-1] == "mk-1"


def test_the_template_is_the_columns(client):
    assert rows_of(client.get("/api/customers/file/template")) == [list(HEADERS)]


def test_a_file_is_told_first_then_applied(client, saved_logins):
    add(client)
    data = workbook(
        ["An", "", "", "", "", "0900000011", "moi"],
        ["Bình", "", "", "", "Căn B", "0900000022", "mk-2"],
        ["Bình", "", "", "", "", "12", ""],
    )

    told = client.post("/api/customers/file", content=data, headers={"content-type": XLSX})
    before = client.get("/api/customers").json()
    done = client.post(
        "/api/customers/file", params={"apply": True}, content=data, headers={"content-type": XLSX}
    )

    assert told.json() == {
        "new_customers": ["Bình"],
        "changed_customers": [],
        "new_accounts": ["0900000022"],
        "changed_accounts": ["0900000011"],
        "problems": [{"line": 4, "code": "bad_phone", "phone": "12", "owner": ""}],
        "applied": False,
    }
    assert [customer["name"] for customer in before] == ["An"]
    assert done.json()["applied"] is True
    assert [customer["name"] for customer in client.get("/api/customers").json()] == ["An", "Bình"]


def test_a_file_that_is_not_a_workbook_is_refused(client):
    answer = client.post("/api/customers/file", content=b"x", headers={"content-type": XLSX})

    assert (answer.status_code, answer.json()["error"]) == (400, "bad_request")


def test_applying_waits_for_a_run(client, saved_logins, context, monkeypatch):
    holder = type("Holder", (), {"describe": lambda self: f"scheduled (pid {os.getpid()})"})()
    monkeypatch.setattr(RunLock, "running_holder", lambda self: holder)
    data = workbook(["Bình", "", "", "", "", "0900000022", "mk-2"])

    answer = client.post(
        "/api/customers/file", params={"apply": True}, content=data, headers={"content-type": XLSX}
    )

    assert (answer.status_code, answer.json()["error"]) == (409, "lock_held")
    assert client.get("/api/customers").json() == []
