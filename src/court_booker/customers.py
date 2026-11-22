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
    mask_phone,
)
from court_booker.errors import CourtBookerError
from court_booker.history import Holder, connect

logger = logging.getLogger(__name__)


class PhoneTakenError(CourtBookerError):
    """Another account already has the phone number."""


class AccountAttachedError(CourtBookerError):
    """The account is attached to a machine, so it is not removed."""


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
    """A customer, a person or a group, with the accounts they gave, the first one first."""

    id: str
    name: str
    representative: str
    """Who speaks for them; may be empty."""
    contact: str
    """How to reach them, as the user wrote it; may be empty."""
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
            Customer(*row, accounts=tuple(accounts.get(row[0], ())))
            for row in self.db.execute(
                "SELECT id, name, representative, contact, note FROM customers"
                " ORDER BY created_at, rowid"
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

    def login(self, account_id: str) -> Login | None:
        """Return the account's saved login, ``None`` once gone; raises for an unknown account."""
        return self.store.read(self.account(account_id).id)

    def _devices(self) -> dict[str, int]:
        """Return the MuMu instance each phone number is attached to."""
        found: dict[str, int] = {}
        for index in range(MAX_INDEX + 1):
            login = self.store.read(index)
            if login is not None:
                found.setdefault(login.phone, index)
        return found

    # Customers ---------------------------------------------------------------

    def add_customer(
        self, name: str, note: str = "", representative: str = "", contact: str = ""
    ) -> Customer:
        """Add a customer without accounts."""
        customer_id = _new_id()
        with self.db:
            self.db.execute(
                "INSERT INTO customers (id, name, representative, contact, note, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (customer_id, name, representative, contact, note, _now()),
            )
        return Customer(customer_id, name, representative, contact, note, ())

    def change_customer(
        self, customer_id: str, name: str, note: str, representative: str = "", contact: str = ""
    ) -> Customer:
        """Change who the customer is; every fact is given."""
        self.customer(customer_id)
        with self.db:
            self.db.execute(
                "UPDATE customers SET name = ?, representative = ?, contact = ?, note = ?"
                " WHERE id = ?",
                (name, representative, contact, note, customer_id),
            )
        return self.customer(customer_id)

    def remove_customer(self, customer_id: str, detach: bool = False) -> None:
        """Remove the customer, their accounts and logins.

        Refused while an account is attached to a machine, unless ``detach`` takes it from there.
        """
        customer = self.customer(customer_id)
        for account in customer.accounts:
            self._free(account, detach)
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
        self._check_free(login.phone)
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

    def change_account(
        self,
        account_id: str,
        label: str,
        password: str | None = None,
        phone: str | None = None,
    ) -> Account:
        """Give the account another label and, if given, phone number and password.

        What is not given stays, and an attached account stays on its machine, which logs in
        with the new login. One whose saved login is gone needs both again.
        """
        account = self.account(account_id)
        if phone is not None:
            self._check_free(phone, account_id)
        if phone is not None or password is not None:
            saved = self.store.read(account_id)
            if saved is None and (phone is None or password is None):
                raise CredentialError("The account's saved login is gone: give both again")
            old = saved or Login("", "")
            login = Login(phone or old.phone, password or old.password)
            self.store.save(account_id, login)
            if account.device is not None:
                try:
                    self.store.save(account.device, login)
                except CredentialError:
                    # Its machine is the one with its phone number: the two stay the same.
                    self.store.save(account_id, old)
                    raise
        with self.db:
            self.db.execute("UPDATE accounts SET label = ? WHERE id = ?", (label, account_id))
        return self.account(account_id)

    def remove_account(self, account_id: str, detach: bool = False) -> None:
        """Remove the account and its login.

        Refused while it is attached to a machine, unless ``detach`` takes it from there.
        """
        self._free(self.account(account_id), detach)
        self.store.delete(account_id)
        with self.db:
            self.db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))

    def _check_free(self, phone: str, account_id: str | None = None) -> None:
        """Raise :class:`PhoneTakenError` if an account but ``account_id`` has the number."""
        for customer in self.customers():
            for account in customer.accounts:
                if account.phone == phone and account.id != account_id:
                    raise PhoneTakenError(f"{customer.name} already has the account")

    def _free(self, account: Account, detach: bool) -> None:
        if account.device is None:
            return
        if not detach:
            raise AccountAttachedError(f"The account is attached to MuMu {account.device}")
        self.store.delete(account.device)

    # Machines ----------------------------------------------------------------

    def attach(self, account_id: str, device: int) -> Account:
        """Let MuMu instance ``device`` book with the account, in place of the one it had.

        An account attached to another machine moves: that one is left without any.
        """
        account = self.account(account_id)
        login = self.store.read(account_id)
        if login is None:
            raise CredentialError("The account's saved login is gone: add the account again")
        # Saved there before it is taken from here: a vault that refuses changes nothing.
        self.store.save(device, login)
        if account.device not in (None, device):
            self.store.delete(account.device)
        return self.account(account_id)

    def detach(self, device: int) -> None:
        """Let MuMu instance ``device`` book with whichever account its app has logged in."""
        self.store.delete(device)

    def adopt(self, name: Callable[[int], str]) -> int:
        """Give each machine's login that belongs to no customer one of its own.

        That is a login saved before there were customers; ``name`` gets the customer's number
        in the list. Returns how many were adopted.
        """
        known = {account.phone for customer in self.customers() for account in customer.accounts}
        adopted = 0
        for index in range(MAX_INDEX + 1):
            login = self.store.read(index)
            if login is None or login.phone in known:
                continue
            number = len(self.customers()) + 1
            self.add_account(self.add_customer(name(number)).id, login)
            known.add(login.phone)
            adopted += 1
        return adopted


def holder_on(path: Path, store: CredentialStore, device: int) -> Holder | None:
    """Return whose account MuMu instance ``device`` books with, ``None`` without a chosen one.

    ``path`` is the database.
    """
    connection = connect(path)
    try:
        customers = CustomerBook(connection, store).customers()
    finally:
        connection.close()
    for customer in customers:
        for account in customer.accounts:
            if account.device == device and account.phone is not None:
                name = account.label or mask_phone(account.phone)
                return Holder(account.id, customer.name, name)
    return None


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


def _new_id() -> str:
    """Return an id no other data folder uses: they share the Windows vault."""
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now().isoformat(timespec="milliseconds")
