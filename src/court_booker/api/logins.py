"""Login routes: the Vinhomes login a run types in when the app logged out.

The app logs an account out when it logs in on another device. A login saved here, one per
MuMu instance, lives in Windows Credential Manager (:mod:`court_booker.credentials`). The
routes take a password but never answer one: they tell whether a login is saved, with the
phone number masked. Saving or removing one is not recorded in the history.
"""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time.
from typing import Annotated, Optional

from fastapi import APIRouter, Path, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from court_booker import credentials

router = APIRouter(prefix="/api", tags=["logins"])

MumuIndex = Annotated[int, Path(ge=0, le=63, description="The MuMu instance")]
PHONE_PATTERN = r"^0\d{9}$"
"""A Vietnamese mobile number, as the app's phone field takes it (10 digits)."""


class SavedLogin(BaseModel):
    """Whether a login is saved for a MuMu instance; never its password."""

    mumu_index: int
    saved: bool
    phone: Optional[str] = None
    """The phone number with its middle hidden, such as ``09••••••79``."""


class NewLogin(BaseModel):
    """The phone number and password of the Vinhomes app, to save for a MuMu instance."""

    model_config = ConfigDict(extra="forbid")

    phone: str = Field(pattern=PHONE_PATTERN)
    password: SecretStr = Field(min_length=1, max_length=credentials.MAX_PASSWORD)


def saved_login(index: int) -> SavedLogin:
    login = credentials.default_store().read(index)
    if login is None:
        return SavedLogin(mumu_index=index, saved=False)
    return SavedLogin(mumu_index=index, saved=True, phone=login.masked_phone)


@router.get("/logins/{mumu_index}", response_model=SavedLogin)
def read_login(mumu_index: MumuIndex) -> SavedLogin:
    """Tell whether a login is saved for the instance, with its phone number masked."""
    return saved_login(mumu_index)


@router.put("/logins/{mumu_index}", response_model=SavedLogin)
def save_login(mumu_index: MumuIndex, login: NewLogin) -> SavedLogin:
    """Save the login a run of the instance types in once the app logged out.

    It replaces the one saved before. The app does not check it here: a wrong one shows at
    the next logout, as a run that stops after one try (the app locks an account after 5
    wrong passwords). Windows refusing to keep it answers 503 ``credentials``.
    """
    store = credentials.default_store()
    store.save(mumu_index, credentials.Login(login.phone, login.password.get_secret_value()))
    return saved_login(mumu_index)


@router.delete("/logins/{mumu_index}", status_code=204, response_class=Response)
def delete_login(mumu_index: MumuIndex) -> Response:
    """Remove the saved login of the instance; a run then stops when the app logged out."""
    credentials.default_store().delete(mumu_index)
    return Response(status_code=204)
