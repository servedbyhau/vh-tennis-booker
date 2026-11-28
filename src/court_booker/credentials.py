"""The Vinhomes logins: each machine's and each customer account's, kept in Windows' vault.

The app logs an account out when it logs in on another device. With a login saved for a
MuMu instance, the run logs in again by itself (:meth:`court_booker.flow.Booker.log_in`).
A customer's account (:mod:`court_booker.customers`) keeps its login under its id, and is
attached to a machine by saving it as that instance's. Each login lives in Windows
Credential Manager as a generic credential, encrypted for the signed-in Windows user, who
also runs the daily task. It is never written to ``config.toml``, a log, the history or an
answer of the backend; the backend only tells whether one is saved, with the phone number
masked. The link to the user's Zalo bot (:mod:`court_booker.zalo`) is kept there too, under
:data:`ZALO`.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import zlib
from dataclasses import dataclass, field
from typing import Protocol, Union

from court_booker.errors import CourtBookerError
from court_booker.paths import HOME_ENV

logger = logging.getLogger(__name__)

TARGET = "{app}/vinhomes/{owner}"
"""The vault's name of a login."""
APP = "CourtBooker"
MAX_INDEX = 63
"""The highest MuMu instance a login is kept for."""
Key = Union[int, str]
"""Whose login: a MuMu instance, by its index, or a customer's account, by its id."""
ZALO = "zalo"
"""The key of the Zalo link: the chat as the user name, the bot's token in the secret."""
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


def target(key: Key) -> str:
    """Return the vault's name of the login of ``key``.

    Every data folder of the PC shares one vault, so one set by hand (a scratch backend) has
    names of its own and never changes the installed app's logins.
    """
    home = os.environ.get(HOME_ENV)
    app = APP if not home else f"{APP}-{zlib.crc32(home.encode('utf-8')):08x}"
    if key == ZALO:
        return f"{app}/{ZALO}"
    owner = f"mumu-{key}" if isinstance(key, int) else f"account-{key}"
    return TARGET.format(app=app, owner=owner)


class CredentialStore(Protocol):
    """Where the logins live: the Windows vault, or a test double."""

    def read(self, key: Key) -> Login | None: ...

    def save(self, key: Key, login: Login) -> None: ...

    def delete(self, key: Key) -> None: ...


class MemoryStore:
    """Logins in memory: for tests, and where Windows' vault is missing."""

    def __init__(self) -> None:
        self.logins: dict[Key, Login] = {}

    def read(self, key: Key) -> Login | None:
        return self.logins.get(key)

    def save(self, key: Key, login: Login) -> None:
        self.logins[key] = login

    def delete(self, key: Key) -> None:
        self.logins.pop(key, None)


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

    def read(self, key: Key) -> Login | None:
        found = ctypes.POINTER(_CREDENTIAL)()
        name = target(key)
        if not self._api.CredReadW(name, _CRED_TYPE_GENERIC, 0, ctypes.byref(found)):
            error = ctypes.get_last_error()  # type: ignore[attr-defined]
            if error != _ERROR_NOT_FOUND:
                logger.warning("Could not read a saved login (error %d)", error)
            return None
        try:
            credential = found.contents
            blob = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            return Login(credential.UserName or "", blob.decode("utf-8"))
        finally:
            self._api.CredFree(found)

    def save(self, key: Key, login: Login) -> None:
        secret = login.password.encode("utf-8")
        blob = (ctypes.c_ubyte * len(secret)).from_buffer_copy(secret)
        credential = _CREDENTIAL(
            Type=_CRED_TYPE_GENERIC,
            TargetName=target(key),
            Comment="Court Booker: a login of the Vinhomes app, or the Zalo bot",
            CredentialBlobSize=len(secret),
            CredentialBlob=ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte)),
            Persist=_CRED_PERSIST_LOCAL_MACHINE,
            UserName=login.phone,
        )
        if not self._api.CredWriteW(ctypes.byref(credential), 0):
            error = ctypes.get_last_error()  # type: ignore[attr-defined]
            raise CredentialError(f"Windows could not keep the login (error {error})")

    def delete(self, key: Key) -> None:
        if not self._api.CredDeleteW(target(key), _CRED_TYPE_GENERIC, 0):
            error = ctypes.get_last_error()  # type: ignore[attr-defined]
            if error != _ERROR_NOT_FOUND:
                raise CredentialError(f"Windows could not remove the login (error {error})")


def default_store() -> CredentialStore:
    """Return the Windows vault; elsewhere (CI runs Linux) an empty store in memory."""
    return WindowsVault() if sys.platform == "win32" else MemoryStore()
