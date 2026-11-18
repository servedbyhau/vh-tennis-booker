"""The Vinhomes login a run types in when the app logged out, kept in Windows' vault.

The app logs an account out when it logs in on another device. With a login saved for a
MuMu instance, the run logs in again by itself (:meth:`court_booker.flow.Booker.log_in`).
Each login lives in Windows Credential Manager as a generic credential, encrypted for the
signed-in Windows user, who also runs the daily task. It is never written to
``config.toml``, a log, the history or an answer of the backend; the backend only tells
whether one is saved, with the phone number masked.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from dataclasses import dataclass, field
from typing import Protocol

from court_booker.errors import CourtBookerError

logger = logging.getLogger(__name__)

TARGET = "CourtBooker/vinhomes/mumu-{index}"
"""The vault's name of the login of MuMu instance ``index``."""
MAX_PASSWORD = 128
"""Longest password kept; the vault holds up to 2560 bytes."""


class CredentialError(CourtBookerError):
    """The vault could not keep or remove a login."""


@dataclass(frozen=True)
class Login:
    """A phone number and password of the Vinhomes app; the password never shows in a repr."""

    phone: str
    password: str = field(repr=False)

    @property
    def masked_phone(self) -> str:
        """Return the phone number with all but its first two and last two digits hidden."""
        return mask_phone(self.phone)


def mask_phone(phone: str) -> str:
    """Return ``phone`` as ``09••••••79``: enough to recognise it, not to read it."""
    if len(phone) <= 4:
        return "•" * len(phone)
    return phone[:2] + "•" * (len(phone) - 4) + phone[-2:]


class CredentialStore(Protocol):
    """Where the logins live: the Windows vault, or a test double."""

    def read(self, index: int) -> Login | None: ...

    def save(self, index: int, login: Login) -> None: ...

    def delete(self, index: int) -> None: ...


class MemoryStore:
    """Logins in memory: for tests, and where Windows' vault is missing."""

    def __init__(self) -> None:
        self.logins: dict[int, Login] = {}

    def read(self, index: int) -> Login | None:
        return self.logins.get(index)

    def save(self, index: int, login: Login) -> None:
        self.logins[index] = login

    def delete(self, index: int) -> None:
        self.logins.pop(index, None)


_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
"""Kept on this PC for this Windows user, across sign-ins; not roamed to other PCs."""
_ERROR_NOT_FOUND = 1168


if sys.platform == "win32":
    from ctypes import wintypes

    class _FILETIME(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    class _CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", _FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]


class WindowsVault:
    """Logins in Windows Credential Manager, through ``advapi32`` (no extra package)."""

    def __init__(self) -> None:
        self._api = ctypes.WinDLL("advapi32", use_last_error=True)  # type: ignore[attr-defined]
        self._api.CredReadW.restype = ctypes.c_bool
        self._api.CredWriteW.restype = ctypes.c_bool
        self._api.CredDeleteW.restype = ctypes.c_bool

    def read(self, index: int) -> Login | None:
        found = ctypes.POINTER(_CREDENTIAL)()
        target = TARGET.format(index=index)
        if not self._api.CredReadW(target, _CRED_TYPE_GENERIC, 0, ctypes.byref(found)):
            error = ctypes.get_last_error()  # type: ignore[attr-defined]
            if error != _ERROR_NOT_FOUND:
                logger.warning("Could not read the saved login of MuMu %d (error %d)", index, error)
            return None
        try:
            credential = found.contents
            blob = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            return Login(credential.UserName or "", blob.decode("utf-8"))
        finally:
            self._api.CredFree(found)

    def save(self, index: int, login: Login) -> None:
        secret = login.password.encode("utf-8")
        blob = (ctypes.c_ubyte * len(secret)).from_buffer_copy(secret)
        credential = _CREDENTIAL(
            Type=_CRED_TYPE_GENERIC,
            TargetName=TARGET.format(index=index),
            Comment="Court Booker: the Vinhomes login typed in when the app logged out",
            CredentialBlobSize=len(secret),
            CredentialBlob=ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte)),
            Persist=_CRED_PERSIST_LOCAL_MACHINE,
            UserName=login.phone,
        )
        if not self._api.CredWriteW(ctypes.byref(credential), 0):
            error = ctypes.get_last_error()  # type: ignore[attr-defined]
            raise CredentialError(f"Windows could not keep the login (error {error})")

    def delete(self, index: int) -> None:
        if not self._api.CredDeleteW(TARGET.format(index=index), _CRED_TYPE_GENERIC, 0):
            error = ctypes.get_last_error()  # type: ignore[attr-defined]
            if error != _ERROR_NOT_FOUND:
                raise CredentialError(f"Windows could not remove the login (error {error})")


def default_store() -> CredentialStore:
    """Return the Windows vault; elsewhere (CI runs Linux) an empty store in memory."""
    return WindowsVault() if sys.platform == "win32" else MemoryStore()
