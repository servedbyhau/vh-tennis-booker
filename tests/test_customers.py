"""The customers, their accounts' logins and machines, on a scratch database and vault."""

import logging
import sqlite3

import pytest

from court_booker import credentials
from court_booker.credentials import CredentialError, Login, MemoryStore
from court_booker.customers import (
    AccountAttachedError,
    CustomerBook,
    PhoneTakenError,
    UnknownRecordError,
    adopt_saved_logins,
    holder_on,
)
from court_booker.history import Holder, connect

FIRST = Login("0900000011", "mat-khau-1")
SECOND = Login("0900000022", "mat-khau-2")


@pytest.fixture
def db(tmp_path):
    connection = connect(tmp_path / "booker.db")
    yield connection
    connection.close()


@pytest.fixture
def book(db):
    return CustomerBook(db, MemoryStore())


def test_customers_are_listed_as_added_with_their_accounts(book):
    an = book.add_customer("An", "gọi trước")
    book.add_customer("Bình")
    book.add_account(an.id, FIRST, "Căn A")
    book.add_account(an.id, SECOND)

    listed = book.customers()

    assert [(c.name, c.note) for c in listed] == [("An", "gọi trước"), ("Bình", "")]
    accounts = [(a.label, a.phone, a.device) for a in listed[0].accounts]
    assert accounts == [("Căn A", FIRST.phone, None), ("", SECOND.phone, None)]
    assert listed[1].accounts == ()


def test_the_database_holds_no_phone_number_and_no_password(book, db):
    account = book.add_account(book.add_customer("An").id, FIRST, "Căn A")
    book.attach(account.id, 2)

    everything = "".join(str(tuple(row)) for row in db.iterdump())
    assert FIRST.phone not in everything
    assert FIRST.password not in everything


def test_a_customer_takes_another_name_and_note(book):
    an = book.add_customer("An")
    book.change_customer(an.id, "Nhóm An", "mới", "Anh An", "Zalo 0900")
    changed = book.customer(an.id)
    assert (changed.name, changed.note) == ("Nhóm An", "mới")
    assert (changed.representative, changed.contact) == ("Anh An", "Zalo 0900")


def test_a_phone_number_belongs_to_one_account_only(book):
    book.add_account(book.add_customer("An").id, FIRST)
    binh = book.add_customer("Bình")
    with pytest.raises(PhoneTakenError, match="An already has"):
        book.add_account(binh.id, Login(FIRST.phone, "khác"))
    assert book.customer(binh.id).accounts == ()


def test_attaching_saves_the_login_the_machine_s_runs_type_in(book):
    account = book.add_account(book.add_customer("An").id, FIRST)

    assert book.attach(account.id, 1).device == 1

    assert book.store.read(1) == FIRST
    assert book.attach(account.id, 1).device == 1  # again: no change


def test_attaching_another_account_replaces_the_one_before(book):
    an = book.add_customer("An")
    first, second = book.add_account(an.id, FIRST), book.add_account(an.id, SECOND)
    book.attach(first.id, 1)
    book.attach(second.id, 1)
    assert [a.device for a in book.customer(an.id).accounts] == [None, 1]
    assert book.store.read(1) == SECOND
    assert book.store.read(first.id) == FIRST  # kept for the next time


def test_an_account_moves_to_the_machine_it_is_attached_to(book):
    account = book.add_account(book.add_customer("An").id, FIRST)
    book.attach(account.id, 1)
    assert book.attach(account.id, 2).device == 2
    assert book.store.read(1) is None  # one account, one machine
    assert book.store.read(2) == FIRST


def test_a_move_the_vault_refuses_changes_nothing(book, monkeypatch):
    account = book.add_account(book.add_customer("An").id, FIRST)
    book.attach(account.id, 1)

    def refuse(key, login):
        raise CredentialError("Windows could not keep the login (error 5)")

    monkeypatch.setattr(book.store, "save", refuse)
    with pytest.raises(CredentialError):
        book.attach(account.id, 2)
    assert book.account(account.id).device == 1


def test_a_new_password_reaches_the_machine_too(book):
    account = book.add_account(book.add_customer("An").id, FIRST, "Căn A")
    book.attach(account.id, 0)

    changed = book.change_account(account.id, "Căn B", "mat-khau-moi")

    assert changed.label == "Căn B"
    assert book.store.read(0) == book.store.read(account.id) == Login(FIRST.phone, "mat-khau-moi")
    book.change_account(account.id, "Căn C")  # the label alone
    assert book.store.read(0).password == "mat-khau-moi"


def test_a_new_phone_number_keeps_the_password_and_the_machine(book):
    account = book.add_account(book.add_customer("An").id, FIRST)
    book.attach(account.id, 1)

    changed = book.change_account(account.id, "", phone=SECOND.phone)

    assert (changed.phone, changed.device) == (SECOND.phone, 1)
    assert book.store.read(1) == book.store.read(account.id)
    assert book.store.read(1) == Login(SECOND.phone, FIRST.password)
    both = book.change_account(account.id, "", "mat-khau-moi", FIRST.phone)
    assert both.device == 1
    assert book.store.read(1) == Login(FIRST.phone, "mat-khau-moi")


def test_a_new_phone_number_is_no_other_accounts(book):
    an = book.add_customer("An")
    first = book.add_account(an.id, FIRST)
    second = book.add_account(book.add_customer("Bình").id, SECOND)
    with pytest.raises(PhoneTakenError, match="An already has"):
        book.change_account(second.id, "", phone=FIRST.phone)
    assert book.store.read(second.id) == SECOND
    assert book.change_account(first.id, "Căn A", phone=FIRST.phone).label == "Căn A"  # its own


def test_a_phone_number_the_machine_refuses_changes_nothing(book, monkeypatch):
    account = book.add_account(book.add_customer("An").id, FIRST)
    book.attach(account.id, 1)
    save = book.store.save

    def refuse(key, login):
        if key == 1:
            raise CredentialError("Windows could not keep the login (error 5)")
        save(key, login)

    monkeypatch.setattr(book.store, "save", refuse)
    with pytest.raises(CredentialError):
        book.change_account(account.id, "", phone=SECOND.phone)
    assert book.account(account.id).phone == FIRST.phone
    assert book.account(account.id).device == 1


def test_what_is_attached_is_not_removed(book):
    an = book.add_customer("An")
    account = book.add_account(an.id, FIRST)
    book.attach(account.id, 0)
    with pytest.raises(AccountAttachedError):
        book.remove_account(account.id)
    with pytest.raises(AccountAttachedError):
        book.remove_customer(an.id)
    assert book.store.read(account.id) == FIRST

    book.detach(0)
    book.remove_customer(an.id)
    assert book.customers() == []
    assert book.store.logins == {}


def test_what_is_attached_is_taken_from_its_machine_when_asked(book):
    an = book.add_customer("An")
    first, second = book.add_account(an.id, FIRST), book.add_account(an.id, SECOND)
    book.attach(first.id, 0)
    book.attach(second.id, 2)

    book.remove_account(first.id, detach=True)
    assert book.store.read(0) is None
    assert book.store.read(2) == SECOND  # the other machine keeps its account

    book.remove_customer(an.id, detach=True)
    assert book.customers() == []
    assert book.store.logins == {}


def test_a_removed_account_leaves_the_others(book):
    an = book.add_customer("An")
    first, second = book.add_account(an.id, FIRST), book.add_account(an.id, SECOND)
    book.remove_account(first.id)
    assert [a.id for a in book.customer(an.id).accounts] == [second.id]
    assert book.store.read(first.id) is None


def test_an_account_whose_login_is_gone_is_shown_and_needs_it_whole_again(book):
    an = book.add_customer("An")
    account = book.add_account(an.id, FIRST)
    book.store.delete(account.id)
    assert book.account(account.id).phone is None
    with pytest.raises(CredentialError):
        book.attach(account.id, 0)
    with pytest.raises(CredentialError):
        book.change_account(account.id, "", "mới")
    with pytest.raises(CredentialError):
        book.change_account(account.id, "", phone=SECOND.phone)
    both = book.change_account(account.id, "", SECOND.password, SECOND.phone)
    assert both.phone == SECOND.phone
    book.remove_account(account.id)


def test_an_unknown_id_is_told(book):
    for call in (
        lambda: book.customer("x"),
        lambda: book.change_customer("x", "An", ""),
        lambda: book.remove_customer("x"),
        lambda: book.add_account("x", FIRST),
        lambda: book.change_account("x", ""),
        lambda: book.remove_account("x"),
        lambda: book.attach("x", 0),
    ):
        with pytest.raises(UnknownRecordError):
            call()
    assert book.store.logins == {}


def test_a_login_the_vault_refuses_leaves_no_account(book, monkeypatch):
    an = book.add_customer("An")

    def refuse(key, login):
        raise CredentialError("Windows could not keep the login (error 5)")

    monkeypatch.setattr(book.store, "save", refuse)
    with pytest.raises(CredentialError):
        book.add_account(an.id, FIRST)
    assert book.customer(an.id).accounts == ()


def test_an_account_the_database_refuses_leaves_no_login(book, db):
    an = book.add_customer("An")
    db.execute("CREATE TRIGGER full BEFORE INSERT ON accounts BEGIN SELECT RAISE(ABORT, 'x'); END")
    with pytest.raises(sqlite3.Error):
        book.add_account(an.id, FIRST)
    assert book.store.logins == {}


def test_logins_saved_before_customers_get_one_each_once(tmp_path):
    store = MemoryStore()
    store.save(0, FIRST)
    store.save(2, SECOND)
    path = tmp_path / "booker.db"

    for _ in range(2):  # every start of the backend
        adopt_saved_logins(path, store, "Khách hàng {}".format)

    connection = connect(path)
    listed = CustomerBook(connection, store).customers()
    connection.close()
    assert [c.name for c in listed] == ["Khách hàng 1", "Khách hàng 2"]
    assert [a.device for c in listed for a in c.accounts] == [0, 2]
    assert store.read(0) == FIRST  # as it was


def test_a_database_that_fails_costs_the_adoption_only(tmp_path, caplog):
    path = tmp_path / "booker.db"
    path.write_bytes(b"no database at all" * 100)
    with caplog.at_level(logging.WARNING):
        adopt_saved_logins(path, MemoryStore(), str)
    assert "Could not give the saved logins customers" in caplog.text


def test_a_data_folder_set_by_hand_has_logins_of_its_own(monkeypatch):
    monkeypatch.delenv("COURT_BOOKER_HOME", raising=False)
    assert credentials.target(1) == "CourtBooker/vinhomes/mumu-1"  # as saved since 1.1.0
    assert credentials.target("ab") == "CourtBooker/vinhomes/account-ab"
    monkeypatch.setenv("COURT_BOOKER_HOME", "C:/scratch")
    assert credentials.target(1) != "CourtBooker/vinhomes/mumu-1"
    assert credentials.target(1).endswith("/vinhomes/mumu-1")


def test_whose_account_a_machine_books_with_is_told(tmp_path):
    path = tmp_path / "booker.db"
    store = MemoryStore()
    db = connect(path)
    book = CustomerBook(db, store)
    an = book.add_customer("An")
    named, plain = book.add_account(an.id, FIRST, "Căn A"), book.add_account(an.id, SECOND)
    book.attach(named.id, 0)
    book.attach(plain.id, 2)
    db.close()

    assert holder_on(path, store, 0) == Holder(named.id, "An", "Căn A")
    assert holder_on(path, store, 2) == Holder(plain.id, "An", "09••••••22")
    assert holder_on(path, store, 1) is None  # no account chosen
