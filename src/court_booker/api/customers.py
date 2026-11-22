"""Customer routes: the customers, their Vinhomes accounts, and the machine of each account.

They take passwords but never answer one, and answer a phone number with its middle hidden.
Nothing of them is recorded in the history.
"""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time.
import threading
from collections.abc import Iterator
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Path, Response
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

_changing = threading.Lock()
"""One change at a time: each one checks the others' phone numbers and machines first."""


class CustomerAccount(BaseModel):
    """A customer's Vinhomes account; never its password."""

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
    note: str
    accounts: list[CustomerAccount]


class CustomerFields(BaseModel):
    """What is known of a customer."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    note: Note = ""


class NewAccount(BaseModel):
    """The login of an account of the Vinhomes app, and what tells it from the others."""

    model_config = ConfigDict(extra="forbid")

    phone: str = Field(pattern=PHONE_PATTERN)
    password: Password
    label: Label = ""


class AccountChange(BaseModel):
    """Another label and, if given, password; the phone number stays."""

    model_config = ConfigDict(extra="forbid")

    label: Label
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
        return shown(book.add_customer(fields.name, fields.note))


@router.put("/customers/{customer_id}", response_model=CustomerRecord)
def change_customer(book: Book, customer_id: RecordId, fields: CustomerFields) -> CustomerRecord:
    """Change a customer's name and note."""
    with _changing:
        return shown(book.change_customer(customer_id, fields.name, fields.note))


@router.delete("/customers/{customer_id}", status_code=204, response_class=Response)
def remove_customer(book: Book, customer_id: RecordId) -> Response:
    """Remove a customer with their accounts and saved logins.

    Refused (409 ``account_attached``) while one of the accounts is attached to a machine.
    """
    with _changing:
        book.remove_customer(customer_id)
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


@router.put("/customer-accounts/{account_id}", response_model=CustomerRecord)
def change_account(
    context: Context, book: Book, account_id: RecordId, change: AccountChange
) -> CustomerRecord:
    """Change an account's label and, if given, password; answers the customer.

    A new password of an attached account is the one its machine logs in with, so it is
    refused (409 ``lock_held``) while a run goes on.
    """
    password = None if change.password is None else change.password.get_secret_value()
    with _changing:
        if password is not None:
            check_no_run(context)
        book.change_account(account_id, change.label, password)
        return shown(book.owner(account_id))


@router.delete("/customer-accounts/{account_id}", status_code=204, response_class=Response)
def remove_account(book: Book, account_id: RecordId) -> Response:
    """Remove an account with its saved login.

    Refused (409 ``account_attached``) while it is attached to a machine.
    """
    with _changing:
        book.remove_account(account_id)
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
