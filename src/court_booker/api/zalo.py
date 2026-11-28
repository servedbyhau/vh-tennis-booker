"""Zalo routes: the user's bot linked to their chat, switched on or off, tried and unlinked.

The token comes in once, when linking, and is never answered back: the routes only tell
whether a link is saved and the name of the chat it sends to.
"""

# No `from __future__ import annotations`: FastAPI and Pydantic read the annotations at run
# time.
from dataclasses import replace
from typing import Optional

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

from court_booker import credentials, notify, zalo
from court_booker.api.activity import record
from court_booker.api.context import AppContext, Context
from court_booker.api.errors import ZaloUnlinkedError
from court_booker.config import save_config
from court_booker.events import EventKind

router = APIRouter(prefix="/api", tags=["zalo"])

WAIT_FOR_MESSAGE = 10.0
"""Seconds linking waits for a message to the bot, for one written just after the press."""


class ZaloState(BaseModel):
    """Whether a run's outcome and tickets go to Zalo, and to whom."""

    linked: bool
    """A bot and the chat it sends to are saved."""
    name: Optional[str] = None
    """The name Zalo shows for the chat, once linked."""
    enabled: bool
    """Sending is on; it sends only once linked too."""


class ZaloLinkRequest(BaseModel):
    """The token of the user's bot, as the Zalo Bot Creator gave it."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=8, max_length=300)


class ZaloSwitch(BaseModel):
    """Sending to Zalo on or off."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool


def zalo_state(context: AppContext) -> ZaloState:
    """Return what is saved: the link in Windows' vault, the switch in the config."""
    link = zalo.read_link(credentials.default_store())
    return ZaloState(
        linked=link is not None,
        name=None if link is None else link.chat.name,
        enabled=context.config().zalo_notification,
    )


def switch(context: AppContext, enabled: bool) -> None:
    """Save the switch when it changes, and record so."""
    old = context.config()
    if old.zalo_notification != enabled:
        save_config(replace(old, zalo_notification=enabled), context.config_path)
        record(context, EventKind.SETTINGS_SAVED, changed=["zalo_notification"])


@router.get("/zalo", response_model=ZaloState)
def read_zalo(context: Context) -> ZaloState:
    """Read whether runs send to Zalo, and to whom."""
    return zalo_state(context)


@router.post("/zalo/link", response_model=ZaloState)
def link_zalo(context: Context, request: ZaloLinkRequest) -> ZaloState:
    """Link the bot of ``token`` to whoever wrote to it last, and switch sending on.

    Waits up to :data:`WAIT_FOR_MESSAGE` for a message to the bot, then sends one back in the
    saved language; only a link that sent it is saved. A token Zalo does not know answers
    400 ``zalo_token``, no message 409 ``zalo_no_message``, any other failure 503 ``zalo``.
    """
    bot = zalo.Bot(request.token)
    bot.check()
    chat = bot.next_chat(WAIT_FOR_MESSAGE)
    bot.send_text(chat.id, notify.format_zalo_test(context.config().notification_language))
    zalo.save_link(credentials.default_store(), zalo.Link(request.token.strip(), chat))
    record(context, EventKind.SETTINGS_SAVED, changed=["zalo_link"])
    switch(context, True)
    return zalo_state(context)


@router.put("/zalo", response_model=ZaloState)
def switch_zalo(context: Context, request: ZaloSwitch) -> ZaloState:
    """Switch sending to Zalo on or off; it applies from the next run."""
    switch(context, request.enabled)
    return zalo_state(context)


@router.delete("/zalo", status_code=204, response_class=Response)
def unlink_zalo(context: Context) -> Response:
    """Forget the bot and the chat; nothing is sent to Zalo until linked again."""
    zalo.forget_link(credentials.default_store())
    record(context, EventKind.SETTINGS_SAVED, changed=["zalo_link"])
    return Response(status_code=204)


@router.post("/zalo/test", status_code=204, response_class=Response)
def test_zalo(context: Context) -> Response:
    """Send a sample message to the linked chat, whether sending is on or not.

    Without a link 409 ``zalo_unlinked``; a message Zalo did not take 503 ``zalo``.
    """
    link = zalo.read_link(credentials.default_store())
    if link is None:
        raise ZaloUnlinkedError("No Zalo bot is linked")
    language = context.config().notification_language
    zalo.Bot(link.token).send_text(link.chat.id, notify.format_zalo_test(language))
    return Response(status_code=204)
