"""The customers as an Excel file: written out to keep or move, read back to add many at once.

One row an account: its customer's name and facts, then the account's name, phone number and
password (left empty unless asked for). A customer without accounts has a row of their own.
Reading a file plans what it changes first (:func:`plan_import`), so the user sees it before
:func:`apply_import` does it: a customer is found by name, an account by phone number; a known
number gets the file's name and password, none is ever added twice. ``openpyxl`` is imported
only here, by the backend.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Callable

from court_booker.credentials import Login
from court_booker.customers import Account, Customer, CustomerBook
from court_booker.errors import RequestError

HEADERS = (
    "Khách",
    "Người đại diện",
    "Liên hệ",
    "Ghi chú",
    "Tên tài khoản",
    "Số điện thoại",
    "Mật khẩu",
)
"""The columns, in Vietnamese as the user reads them; a file is read by these names."""
SHEET = "Khách hàng"
MAX_ROWS = 2000
"""More rows than any PC's customers: a bigger file is not one of ours."""
_PHONE = re.compile(r"^0\d{9}$")
_COLUMN_WIDTHS = (24, 20, 22, 24, 20, 16, 18)


@dataclass(frozen=True)
class FileRow:
    """One row read from a file, its cells stripped; ``line`` is its row number in Excel."""

    line: int
    customer: str
    representative: str
    contact: str
    note: str
    label: str
    phone: str
    password: str


@dataclass(frozen=True)
class Problem:
    """Why a row of a file is left out: ``code`` for the UI to word, with the phone number
    and the customer it is about, when there are."""

    line: int
    code: str
    """``no_name``, ``bad_phone``, ``twice``, ``taken`` (another customer's number) or
    ``no_password`` (a new account without one)."""
    phone: str = ""
    owner: str = ""


@dataclass
class ImportPlan:
    """What a file changes, and the rows it cannot use with why."""

    new_customers: list[str] = field(default_factory=list)
    changed_customers: list[str] = field(default_factory=list)
    new_accounts: list[str] = field(default_factory=list)
    """The phone numbers added."""
    changed_accounts: list[str] = field(default_factory=list)
    """The known phone numbers given another name or password."""
    problems: list[Problem] = field(default_factory=list)
    """Each row left out, with why."""
    rows: list[FileRow] = field(default_factory=list)
    """The rows that are used, in the file's order."""


def write_customers(
    customers: list[Customer], password_of: Callable[[str], str | None] | None = None
) -> bytes:
    """Return ``customers`` as an .xlsx file, with each account's password if ``password_of``
    gives it (by account id); without it the password column stays empty."""
    rows = []
    for customer in customers:
        facts = [customer.name, customer.representative, customer.contact, customer.note]
        for account in customer.accounts:
            password = None if password_of is None else password_of(account.id)
            rows.append([*facts, account.label, account.phone or "", password or ""])
        if not customer.accounts:
            rows.append([*facts, "", "", ""])
    return _workbook(rows)


def template() -> bytes:
    """Return an .xlsx file with the columns alone, to fill."""
    return _workbook([])


def _workbook(rows: list[list[str]]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    book = Workbook()
    sheet = book.active
    sheet.title = SHEET
    sheet.append(list(HEADERS))
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(row)
    for index, width in enumerate(_COLUMN_WIDTHS, start=1):
        letter = sheet.cell(row=1, column=index).column_letter
        sheet.column_dimensions[letter].width = width
        # Text, so Excel keeps the 0 a phone number starts with and a password as typed.
        for cell in sheet[letter][1:]:
            cell.number_format = "@"
    # The empty rows to fill are text too.
    for letter in ("F", "G"):
        sheet.column_dimensions[letter].number_format = "@"
    sheet.freeze_panes = "A2"
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def read_rows(data: bytes) -> list[FileRow]:
    """Return the filled rows of an .xlsx file written from :func:`template` or an export.

    Raises :class:`RequestError` for a file that is not a workbook or lacks the columns.
    """
    from openpyxl import load_workbook

    try:
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # a zip, an XML or a format error, all alike to the user
        raise RequestError("The file is not an Excel workbook (.xlsx)") from exc
    try:
        sheet = book.active
        lines = sheet.iter_rows(values_only=True)
        header = [_text(cell) for cell in next(lines, ())]
        missing = [name for name in HEADERS if name not in header]
        if missing:
            raise RequestError(f"The file lacks the columns: {', '.join(missing)}")
        where = [header.index(name) for name in HEADERS]
        rows = []
        for line, values in enumerate(lines, start=2):
            if line > MAX_ROWS + 1:
                raise RequestError(f"The file has more than {MAX_ROWS} rows")
            cells = [_text(values[i]) if i < len(values) else "" for i in where]
            if any(cells):
                rows.append(FileRow(line, *cells))
        return rows
    finally:
        book.close()


def _text(value: object) -> str:
    """Return a cell as text: a whole number without ``.0``, nothing as empty."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def phone_of(text: str) -> str:
    """Return the digits of a phone number, with the 0 Excel drops from a number put back."""
    digits = re.sub(r"\D", "", text)
    return "0" + digits if len(digits) == 9 and not digits.startswith("0") else digits


def plan_import(book: CustomerBook, rows: list[FileRow]) -> ImportPlan:
    """Return what ``rows`` change in ``book``, without changing it."""
    plan = ImportPlan()
    customers = {customer.name.casefold(): customer for customer in book.customers()}
    owners = {
        account.phone: customer
        for customer in customers.values()
        for account in customer.accounts
        if account.phone is not None
    }
    accounts = {
        account.phone: account
        for customer in customers.values()
        for account in customer.accounts
        if account.phone is not None
    }
    seen_phones: set[str] = set()
    named: dict[str, str] = {}  # the customers met in the file, by name, as first written
    for row in rows:
        name = row.customer
        if not name:
            plan.problems.append(Problem(row.line, "no_name"))
            continue
        phone = phone_of(row.phone) if row.phone else ""
        if row.phone and not _PHONE.match(phone):
            plan.problems.append(Problem(row.line, "bad_phone", row.phone))
            continue
        if phone and phone in seen_phones:
            plan.problems.append(Problem(row.line, "twice", phone))
            continue
        known = customers.get(name.casefold())
        owner = owners.get(phone) if phone else None
        if owner is not None and owner.name.casefold() != name.casefold():
            plan.problems.append(Problem(row.line, "taken", phone, owner.name))
            continue
        if phone and owner is None and not row.password:
            plan.problems.append(Problem(row.line, "no_password", phone))
            continue
        key = name.casefold()
        if key not in named:
            named[key] = name
            if known is None:
                plan.new_customers.append(name)
            elif _facts_change(known, row):
                plan.changed_customers.append(known.name)
        if phone:
            seen_phones.add(phone)
            if owner is None:
                plan.new_accounts.append(phone)
            elif _account_changes(book, accounts[phone], row):
                plan.changed_accounts.append(phone)
        shown = name if known is None else known.name  # as the app has it
        plan.rows.append(FileRow(row.line, shown, *_rest(row, phone)))
    return plan


def _rest(row: FileRow, phone: str) -> tuple[str, str, str, str, str, str]:
    return (row.representative, row.contact, row.note, row.label, phone, row.password)


def _account_changes(book: CustomerBook, account: Account, row: FileRow) -> bool:
    """Return whether a row gives a known account another name or password than it has."""
    if row.label and row.label != account.label:
        return True
    saved = book.login(account.id) if row.password else None
    return bool(row.password) and (saved is None or saved.password != row.password)


def _facts_change(customer: Customer, row: FileRow) -> bool:
    """Return whether a row gives a known customer a fact they do not have as written."""
    given = (
        (row.representative, customer.representative),
        (row.contact, customer.contact),
        (row.note, customer.note),
    )
    return any(new and new != old for new, old in given)


def apply_import(book: CustomerBook, plan: ImportPlan) -> None:
    """Make the changes of ``plan``: customers added or given the file's facts, accounts added
    or given the file's name and password. A fact or a name left empty in the file stays."""
    by_name = {customer.name.casefold(): customer for customer in book.customers()}
    for row in plan.rows:
        key = row.customer.casefold()
        customer = by_name.get(key)
        if customer is None:
            customer = book.add_customer(
                row.customer, row.note, representative=row.representative, contact=row.contact
            )
            by_name[key] = customer
        elif _facts_change(customer, row):
            customer = book.change_customer(
                customer.id,
                customer.name,
                row.note or customer.note,
                representative=row.representative or customer.representative,
                contact=row.contact or customer.contact,
            )
            by_name[key] = customer
        if not row.phone:
            continue
        account = next(
            (
                account
                for known in book.customers()
                for account in known.accounts
                if account.phone == row.phone
            ),
            None,
        )
        if account is None:
            book.add_account(customer.id, Login(row.phone, row.password), row.label)
        elif _account_changes(book, account, row):
            book.change_account(
                account.id, row.label or account.label, password=row.password or None
            )
