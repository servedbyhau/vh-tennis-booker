"""The customers, the Vinhomes accounts each one gave, and the machine an account books on.

The database keeps the names and notes only. An account's phone number and password live in
Windows Credential Manager under the account's id (:mod:`court_booker.credentials`), and
attaching an account to a MuMu instance saves its login as that instance's, the one a run
types in. So a run needs nothing from here, and an instance's account is the one with the
instance's phone number; nothing else has to agree with it.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from court_booker.credentials import (
    MAX_INDEX,
    CredentialError,
    CredentialStore,
    Login,
)
from court_booker.errors import CourtBookerError
from court_booker.history import connect

logger = logging.getLogger(__name__)


class PhoneTakenError(CourtBookerError):
    """Another account already has the phone number."""


class AccountAttachedError(CourtBookerError):
    """The account is attached to a machine: it is neither removed nor attached to another."""


class UnknownRecordError(CourtBookerError):
    """No customer or account has the id."""


@dataclass(frozen=True)
class Account:
    """A customer's Vinhomes account; its password is never part of it."""

    id: str
    label: str
    """What tells it from the customer's others, such as ``Căn A``; may be empty."""
    phone: str | None
    """The whole phone number, ``None`` once its saved login is gone; mask it to show it."""
    device: int | None
    """The MuMu instance it is attached to."""


@dataclass(frozen=True)
class Customer:
    """A customer with the accounts they gave, the first one first."""

    id: str
    name: str
    note: str
    accounts: tuple[Account, ...]


class CustomerBook:
    """Read and change the customers in ``db``, with their logins in ``store``."""

    def __init__(self, db: sqlite3.Connection, store: CredentialStore) -> None:
        self.db = db
        self.store = store

    # Reading -----------------------------------------------------------------

    def customers(self) -> list[Customer]:
        """Return every customer in the order they were added."""
        devices = self._devices()
        accounts: dict[str, list[Account]] = {}
        for account_id, customer_id, label in self.db.execute(
            "SELECT id, customer_id, label FROM accounts ORDER BY created_at, rowid"
        ):
            login = self.store.read(account_id)
            phone = None if login is None else login.phone
            device = None if phone is None else devices.get(phone)
            accounts.setdefault(customer_id, []).append(Account(account_id, label, phone, device))
        return [
            Customer(customer_id, name, note, tuple(accounts.get(customer_id, ())))
            for customer_id, name, note in self.db.execute(
                "SELECT id, name, note FROM customers ORDER BY created_at, rowid"
            )
        ]

    def customer(self, customer_id: str) -> Customer:
        """Return the customer; raises :class:`UnknownRecordError`."""
        for customer in self.customers():
            if customer.id == customer_id:
                return customer
        raise UnknownRecordError(f"No customer {customer_id}")

    def owner(self, account_id: str) -> Customer:
        """Return the customer the account belongs to; raises :class:`UnknownRecordError`."""
        for customer in self.customers():
            if any(account.id == account_id for account in customer.accounts):
                return customer
        raise UnknownRecordError(f"No account {account_id}")

    def account(self, account_id: str) -> Account:
        """Return the account; raises :class:`UnknownRecordError`."""
        accounts = self.owner(account_id).accounts
        return next(account for account in accounts if account.id == account_id)

    def _devices(self) -> dict[str, int]:
        """Return the MuMu instance each phone number is attached to."""
        found: dict[str, int] = {}
        for index in range(MAX_INDEX + 1):
            login = self.store.read(index)
            if login is not None:
                found.setdefault(login.phone, index)
        return found

    # Customers ---------------------------------------------------------------

    def add_customer(self, name: str, note: str = "") -> Customer:
        """Add a customer without accounts."""
        customer_id = _new_id()
        with self.db:
            self.db.execute(
                "INSERT INTO customers (id, name, note, created_at) VALUES (?, ?, ?, ?)",
                (customer_id, name, note, _now()),
            )
        return Customer(customer_id, name, note, ())

    def change_customer(self, customer_id: str, name: str, note: str) -> Customer:
        """Give the customer another name and note."""
        self.customer(customer_id)
        with self.db:
            self.db.execute(
                "UPDATE customers SET name = ?, note = ? WHERE id = ?", (name, note, customer_id)
            )
        return self.customer(customer_id)

    def remove_customer(self, customer_id: str) -> None:
        """Remove the customer, their accounts and logins; refused while one is attached."""
        customer = self.customer(customer_id)
        for account in customer.accounts:
            _refuse_attached(account)
        # The logins first: a vault that refuses leaves the customer to remove again.
        for account in customer.accounts:
            self.store.delete(account.id)
        with self.db:
            self.db.execute("DELETE FROM accounts WHERE customer_id = ?", (customer_id,))
            self.db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))

    # Accounts ----------------------------------------------------------------

    def add_account(self, customer_id: str, login: Login, label: str = "") -> Account:
        """Add an account to the customer; its phone number must be no other account's."""
        self.customer(customer_id)
        for customer in self.customers():
            if any(account.phone == login.phone for account in customer.accounts):
                raise PhoneTakenError(f"{customer.name} already has the account")
        account_id = _new_id()
        # The login first: an account in the list always had one.
        self.store.save(account_id, login)
        try:
            with self.db:
                self.db.execute(
                    "INSERT INTO accounts (id, customer_id, label, created_at) VALUES (?, ?, ?, ?)",
                    (account_id, customer_id, label, _now()),
                )
        except sqlite3.Error:
            self.store.delete(account_id)
            raise
        return self.account(account_id)

    def change_account(self, account_id: str, label: str, password: str | None = None) -> Account:
        """Give the account another label and, if given, password, also on its machine."""
        account = self.account(account_id)
        if password is not None:
            if account.phone is None:
                raise CredentialError("The account's saved login is gone: add the account again")
            login = Login(account.phone, password)
            self.store.save(account_id, login)
            if account.device is not None:
                self.store.save(account.device, login)
        with self.db:
            self.db.execute("UPDATE accounts SET label = ? WHERE id = ?", (label, account_id))
        return self.account(account_id)

    def remove_account(self, account_id: str) -> None:
        """Remove the account and its login; refused while it is attached to a machine."""
        _refuse_attached(self.account(account_id))
        self.store.delete(account_id)
        with self.db:
            self.db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))

    # Machines ----------------------------------------------------------------

    def attach(self, account_id: str, device: int) -> Account:
        """Let MuMu instance ``device`` book with the account, in place of the one it had."""
        account = self.account(account_id)
        login = self.store.read(account_id)
        if login is None:
            raise CredentialError("The account's saved login is gone: add the account again")
        if account.device not in (None, device):
            raise AccountAttachedError(f"The account is attached to MuMu {account.device}")
        self.store.save(device, login)
        return self.account(account_id)

    def detach(self, device: int) -> None:
        """Let MuMu instance ``device`` book with whichever account its app has logged in."""
        self.store.delete(device)

    def adopt(self, name: Callable[[int], str]) -> int:
        """Give each machine's login that belongs to no customer one of its own.

        That is a login saved before there were customers. Returns how many were adopted.
        """
        known = {account.phone for customer in self.customers() for account in customer.accounts}
        adopted = 0
        for index in range(MAX_INDEX + 1):
            login = self.store.read(index)
            if login is None or login.phone in known:
                continue
            self.add_account(self.add_customer(name(index)).id, login)
            known.add(login.phone)
            adopted += 1
        return adopted


def adopt_saved_logins(path: Path, store: CredentialStore, name: Callable[[int], str]) -> None:
    """Run :meth:`CustomerBook.adopt` on the database at ``path``; a failure only logs."""
    try:
        connection = connect(path)
        try:
            adopted = CustomerBook(connection, store).adopt(name)
        finally:
            connection.close()
        if adopted:
            logger.info("Gave %d saved login(s) a customer", adopted)
    except (sqlite3.Error, CourtBookerError):
        logger.warning("Could not give the saved logins customers", exc_info=True)


def _refuse_attached(account: Account) -> None:
    if account.device is not None:
        raise AccountAttachedError(f"The account is attached to MuMu {account.device}")


def _new_id() -> str:
    """Return an id no other data folder uses: they share the Windows vault."""
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now().isoformat(timespec="milliseconds")
