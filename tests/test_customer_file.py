"""The customers' Excel file: written out, read back, and what reading it changes."""

import io

import pytest
from openpyxl import Workbook, load_workbook

from court_booker import customer_file
from court_booker.credentials import Login, MemoryStore
from court_booker.customer_file import HEADERS, apply_import, plan_import, read_rows
from court_booker.customers import CustomerBook
from court_booker.errors import RequestError
from court_booker.history import connect


@pytest.fixture
def book(tmp_path):
    connection = connect(tmp_path / "booker.db")
    yield CustomerBook(connection, MemoryStore())
    connection.close()


def workbook(*rows, header=HEADERS):
    """Return an .xlsx file of ``rows`` under ``header``, as Excel saves one."""
    sheet_book = Workbook()
    sheet = sheet_book.active
    sheet.append(list(header))
    for row in rows:
        sheet.append(list(row))
    out = io.BytesIO()
    sheet_book.save(out)
    return out.getvalue()


def cells(data):
    sheet = load_workbook(io.BytesIO(data)).active
    return [[cell.value for cell in row] for row in sheet.iter_rows()]


def test_the_customers_are_written_a_row_an_account_with_passwords_only_if_asked(book):
    an = book.add_customer("Anh An", "gọi trước", representative="An", contact="Zalo An")
    book.add_account(an.id, Login("0900000011", "mk-1"), "Căn A")
    book.add_customer("Chị Bình")

    plain = cells(customer_file.write_customers(book.customers()))
    whole = cells(
        customer_file.write_customers(book.customers(), lambda i: book.store.read(i).password)
    )

    assert plain[0] == list(HEADERS)
    assert plain[1] == ["Anh An", "An", "Zalo An", "gọi trước", "Căn A", "0900000011", None]
    assert plain[2] == ["Chị Bình", None, None, None, None, None, None]
    assert whole[1][-1] == "mk-1"


def test_a_file_read_back_gives_its_rows_the_0_excel_dropped_put_back(book):
    data = workbook(
        ["Anh An", "", "", "", "Căn A", 900000011, "mk-1"],  # a number: Excel drops the 0
        [None] * 7,  # an empty row is skipped
        ["Anh An", "", "", "", "Căn B", "0900.000.022", 12345],
    )

    rows = read_rows(data)

    assert [(row.line, row.label, customer_file.phone_of(row.phone)) for row in rows] == [
        (2, "Căn A", "0900000011"),
        (4, "Căn B", "0900000022"),
    ]
    assert rows[1].password == "12345"


@pytest.mark.parametrize(
    "data", [b"not a workbook", workbook(["x"], header=("Khách", "Số điện thoại"))]
)
def test_a_file_that_is_not_ours_is_refused(data):
    with pytest.raises(RequestError):
        read_rows(data)


def test_the_plan_adds_updates_and_tells_the_rows_left_out(book):
    an = book.add_customer("Anh An")
    book.add_account(an.id, Login("0900000011", "cu"), "Căn A")
    bình = book.add_customer("Chị Bình")
    book.add_account(bình.id, Login("0900000099", "x"))
    rows = read_rows(
        workbook(
            ["anh an", "", "Zalo An", "", "Căn A", "0900000011", "moi"],  # known: a new password
            ["Anh An", "", "", "", "Căn B", "0900000022", "mk-2"],  # a new account
            ["Anh Cường", "", "", "", "", "", ""],  # a new customer without accounts
            ["Anh Dũng", "", "", "", "", "0900000033", ""],  # a new account without a password
            ["Anh An", "", "", "", "", "0900000099", "y"],  # Chị Bình's number
            ["", "", "", "", "", "0900000044", "z"],  # nobody's
            ["Anh An", "", "", "", "", "123", "z"],  # not a phone number
            ["Anh An", "", "", "", "Căn B2", "0900000022", "mk-2"],  # twice in the file
        )
    )

    plan = plan_import(book, rows)

    assert plan.new_customers == ["Anh Cường"]
    assert plan.changed_customers == ["Anh An"]  # as the app has it
    assert plan.new_accounts == ["0900000022"]
    assert plan.changed_accounts == ["0900000011"]
    assert [(problem.line, problem.code) for problem in plan.problems] == [
        (5, "no_password"),
        (6, "taken"),
        (7, "no_name"),
        (8, "bad_phone"),
        (9, "twice"),
    ]
    assert plan.problems[1].owner == "Chị Bình"


def test_applying_the_plan_makes_its_changes_once(book):
    an = book.add_customer("Anh An", "ghi chú")
    book.add_account(an.id, Login("0900000011", "cu"), "Căn A")
    rows = read_rows(
        workbook(
            ["Anh An", "", "Zalo An", "", "", "0900000011", "moi"],
            ["Anh An", "", "", "", "Căn B", "0900000022", "mk-2"],
            ["Anh Cường", "Cường", "", "", "", "", ""],
        )
    )

    apply_import(book, plan_import(book, rows))
    apply_import(book, plan_import(book, rows))  # again: nothing more
    again = plan_import(book, rows)
    assert (again.new_accounts, again.changed_accounts, again.changed_customers) == ([], [], [])

    customers = {customer.name: customer for customer in book.customers()}
    assert list(customers) == ["Anh An", "Anh Cường"]
    an_now = customers["Anh An"]
    assert (an_now.contact, an_now.note) == ("Zalo An", "ghi chú")  # empty cells keep facts
    assert [(a.label, a.phone) for a in an_now.accounts] == [
        ("Căn A", "0900000011"),  # its name kept: the file left it empty
        ("Căn B", "0900000022"),
    ]
    assert book.login(an_now.accounts[0].id) == Login("0900000011", "moi")
    assert customers["Anh Cường"].representative == "Cường"


def test_the_template_has_the_columns_alone():
    assert cells(customer_file.template()) == [list(HEADERS)]
