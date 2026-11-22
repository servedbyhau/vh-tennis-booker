"""Customer routes: the customers, their Vinhomes accounts, and the machine of each account.

They answer a phone number with its middle hidden and no password, but for the one route the
form of an account is filled from. Nothing of them is recorded in the history.
"""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time.
import threading
from collections.abc import Iterator
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints

from court_booker import credentials
from court_booker.api.context import Context
from court_booker.credentials import Login, mask_phone
from court_booker.customers import Account, Customer, CustomerBook
from court_booker.errors import LockHeldError
from court_booker.history import connect
from court_booker.lock import RunLock

router = APIRouter(prefix="/api", tags=["customers"])

PHONE_PATTERN = r"^0\d{9}$"
"""A Vietnamese mobile number, as the app's phone field takes it (10 digits)."""
RecordId = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]
MumuIndex = Annotated[int, Path(ge=0, le=credentials.MAX_INDEX, description="The MuMu instance")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Password = Annotated[SecretStr, Field(min_length=1, max_length=credentials.MAX_PASSWORD)]

Detach = Annotated[
    bool, Query(description="Whether an account attached to a machine is taken from it")
]

_changing = threading.Lock()
"""One change at a time: each one checks the others' phone numbers and machines first."""


class CustomerAccount(BaseModel):
    """A customer's Vinhomes account, without its password."""

    id: str
    label: str
    phone: Optional[str]
    """The phone number with its middle hidden, ``None`` once its saved login is gone."""
    device: Optional[int]
    """The MuMu instance it is attached to."""


class CustomerRecord(BaseModel):
    """A customer with the accounts they gave."""

    id: str
    name: str
    representative: str
    contact: str
    note: str
    accounts: list[CustomerAccount]


class CustomerFields(BaseModel):
    """What is known of a customer."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    representative: Label = ""
    contact: Label = ""
    note: Note = ""


class AccountLogin(BaseModel):
    """The saved login of an account as it is, ``None`` once it is gone."""

    phone: Optional[str]
    password: Optional[str]


class NewAccount(BaseModel):
    """The login of an account of the Vinhomes app, and what tells it from the others."""

    model_config = ConfigDict(extra="forbid")

    phone: str = Field(pattern=PHONE_PATTERN)
    password: Password
    label: Label = ""


class AccountChange(BaseModel):
    """Another label and, if given, phone number and password; what is not given stays."""

    model_config = ConfigDict(extra="forbid")

    label: Label
    phone: Optional[str] = Field(default=None, pattern=PHONE_PATTERN)
    password: Optional[Password] = None


class AttachedAccount(BaseModel):
    """The account a machine books with from its next run on."""

    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(pattern=r"^[0-9a-f]{32}$")


def customer_book(context: Context) -> Iterator[CustomerBook]:
    """Open the customers for one request."""
    connection = connect(context.data.database)
    try:
        yield CustomerBook(connection, credentials.default_store())
    finally:
        connection.close()


Book = Annotated[CustomerBook, Depends(customer_book)]


def check_no_run(context: Context) -> None:
    """Raise :class:`LockHeldError` while a run goes on, which may be about to log in."""
    holder = RunLock(context.data.lock).running_holder()
    if holder is not None:
        raise LockHeldError(f"Another run is in progress: {holder.describe()}")


def shown_account(account: Account) -> CustomerAccount:
    phone = None if account.phone is None else mask_phone(account.phone)
    return CustomerAccount(id=account.id, label=account.label, phone=phone, device=account.device)


def shown(customer: Customer) -> CustomerRecord:
    return CustomerRecord(
        id=customer.id,
        name=customer.name,
        representative=customer.representative,
        contact=customer.contact,
        note=customer.note,
        accounts=[shown_account(account) for account in customer.accounts],
    )


@router.get("/customers", response_model=list[CustomerRecord])
def list_customers(book: Book) -> list[CustomerRecord]:
    """List the customers in the order they were added, each with their accounts."""
    return [shown(customer) for customer in book.customers()]


@router.post("/customers", status_code=201, response_model=CustomerRecord)
def add_customer(book: Book, fields: CustomerFields) -> CustomerRecord:
    """Add a customer without accounts."""
    with _changing:
        return shown(book.add_customer(**fields.model_dump()))


@router.put("/customers/{customer_id}", response_model=CustomerRecord)
def change_customer(book: Book, customer_id: RecordId, fields: CustomerFields) -> CustomerRecord:
    """Change who a customer is; every fact not given is emptied."""
    with _changing:
        return shown(book.change_customer(customer_id, **fields.model_dump()))


@router.delete("/customers/{customer_id}", status_code=204, response_class=Response)
def remove_customer(
    context: Context, book: Book, customer_id: RecordId, detach: Detach = False
) -> Response:
    """Remove a customer with their accounts and saved logins.

    Refused (409 ``account_attached``) while one of the accounts is attached to a machine, unless
    ``detach`` takes it from there; not while a run goes on (409 ``lock_held``).
    """
    with _changing:
        if detach:
            check_no_run(context)
        book.remove_customer(customer_id, detach)
    return Response(status_code=204)


@router.post("/customers/{customer_id}/accounts", status_code=201, response_model=CustomerRecord)
def add_account(book: Book, customer_id: RecordId, account: NewAccount) -> CustomerRecord:
    """Add an account to a customer and save its login; answers the customer.

    The app does not check the login here: a wrong one shows when a run logs in with it. A
    phone number another account has is refused (409 ``phone_taken``), and Windows refusing
    to keep the login answers 503 ``credentials``.
    """
    login = Login(account.phone, account.password.get_secret_value())
    with _changing:
        book.add_account(customer_id, login, account.label)
        return shown(book.customer(customer_id))


@router.get("/customer-accounts/{account_id}/login", response_model=AccountLogin)
def read_login(book: Book, account_id: RecordId, response: Response) -> AccountLogin:
    """The account's saved login, whole, to fill the form that changes it.

    The user asked to see it there (2026-11-22). Only this PC reaches the backend
    (``local_only.py``), and no cache keeps the answer.
    """
    login = book.login(account_id)
    response.headers["Cache-Control"] = "no-store"
    if login is None:
        return AccountLogin(phone=None, password=None)
    return AccountLogin(phone=login.phone, password=login.password)


@router.put("/customer-accounts/{account_id}", response_model=CustomerRecord)
def change_account(
    context: Context, book: Book, account_id: RecordId, change: AccountChange
) -> CustomerRecord:
    """Change an account's label and, if given, phone number and password; answers the customer.

    A new login of an attached account is the one its machine logs in with, so it is refused
    (409 ``lock_held``) while a run goes on. A phone number belongs to one account only
    (409 ``phone_taken``).
    """
    password = None if change.password is None else change.password.get_secret_value()
    with _changing:
        if password is not None or change.phone is not None:
            check_no_run(context)
        book.change_account(account_id, change.label, password, change.phone)
        return shown(book.owner(account_id))


@router.delete("/customer-accounts/{account_id}", status_code=204, response_class=Response)
def remove_account(
    context: Context, book: Book, account_id: RecordId, detach: Detach = False
) -> Response:
    """Remove an account with its saved login.

    Refused (409 ``account_attached``) while it is attached to a machine, unless ``detach`` takes
    it from there; not while a run goes on (409 ``lock_held``).
    """
    with _changing:
        if detach:
            check_no_run(context)
        book.remove_account(account_id, detach)
    return Response(status_code=204)


@router.put("/machines/{mumu_index}/account", response_model=CustomerRecord)
def attach_account(
    context: Context, book: Book, mumu_index: MumuIndex, attached: AttachedAccount
) -> CustomerRecord:
    """Let a machine book with an account from its next run on; answers the customer.

    The run logs the machine's Vinhomes app in with it. An account on another machine moves.
    Refused while a run goes on (409 ``lock_held``).
    """
    with _changing:
        check_no_run(context)
        book.attach(attached.account_id, mumu_index)
        return shown(book.owner(attached.account_id))


@router.delete("/machines/{mumu_index}/account", status_code=204, response_class=Response)
def detach_account(context: Context, book: Book, mumu_index: MumuIndex) -> Response:
    """Let a machine book with whichever account its app has logged in.

    A run then stops when the app logged out. Refused while a run goes on (409 ``lock_held``).
    """
    with _changing:
        check_no_run(context)
        book.detach(mumu_index)
    return Response(status_code=204)
