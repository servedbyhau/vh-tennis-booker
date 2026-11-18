"""Tests for the saved logins: never shown, kept per MuMu instance."""

import pytest

from court_booker import credentials
from court_booker.credentials import Login, MemoryStore, mask_phone


def test_a_login_never_shows_its_password():
    login = Login("0900000079", "mat-khau-bi-mat")

    assert "mat-khau-bi-mat" not in repr(login)
    assert "mat-khau-bi-mat" not in str(login)


@pytest.mark.parametrize(
    ("phone", "masked"), [("0900000079", "09••••••79"), ("0912", "••••"), ("", "")]
)
def test_a_phone_number_shows_its_ends_only(phone, masked):
    assert mask_phone(phone) == masked


def test_each_instance_keeps_its_own_login():
    store = MemoryStore()

    store.save(0, Login("0900000001", "one"))
    store.save(1, Login("0900000002", "two"))
    store.delete(0)
    store.delete(5)  # nothing saved: no error

    assert store.read(0) is None
    assert store.read(1) == Login("0900000002", "two")


def test_the_suite_never_reaches_the_windows_vault():
    assert isinstance(credentials.default_store(), MemoryStore)  # tests/conftest.py
