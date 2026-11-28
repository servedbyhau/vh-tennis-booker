"""Send the outcome of a run and its tickets to the user's Zalo, through their own Zalo Bot.

The user creates a bot in Zalo (the "Zalo Bot Creator" mini app), which gives a token, then
sends the bot any message from their own Zalo: that message tells the chat to send to
(:meth:`Bot.next_chat`). Zalo lets a bot write only to someone who wrote to it, never to a
phone number. The token and the chat are kept together in Windows' vault (:func:`save_link`),
never in ``config.toml``, a log or an answer of the backend; the token is part of every
address of the Bot API, so no address is ever logged either.

Sending never costs a booking: :func:`send_report` and :func:`send_tickets` log a failure
and go on. Docs: https://bot.zapps.me/docs/ (2026-11-28).
"""

from __future__ import annotations

import json
import logging
import mimetypes
import urllib.error
import urllib.request
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from court_booker.credentials import ZALO, CredentialStore, Login
from court_booker.errors import CourtBookerError

logger = logging.getLogger(__name__)

API_URL = "https://bot-api.zaloplatforms.com/bot{token}/{method}"
TIMEOUT = 20.0
"""Seconds a request may take; a picture is about 100 KB."""
LONGEST_TEXT = 2000
"""Characters of a message or a caption the Bot API takes."""
NO_UPDATE = 408
"""What ``getUpdates`` answers when nobody wrote within its wait."""
_BAD_TOKEN = (401, 404)
"""A token Zalo does not know: 401, or 404 for a malformed one (no such address)."""

Post = Callable[[str, bytes, str, float], "tuple[int, bytes]"]
"""Send a POST (address, body, content type, timeout); return the HTTP status and the body."""


class ZaloError(CourtBookerError):
    """Zalo did not take the request: no network, or the Bot API refused it (``code``)."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class ZaloTokenError(ZaloError):
    """Zalo knows no bot by this token: mistyped, or reset since."""


class NoMessageError(ZaloError):
    """Nobody wrote to the bot within the wait, so there is no chat to send to."""


@dataclass(frozen=True)
class Chat:
    """Someone who wrote to the bot: where to send, and the name Zalo shows."""

    id: str
    name: str


@dataclass(frozen=True)
class Link:
    """The user's bot and their chat with it; the token never shows in a repr."""

    token: str = field(repr=False)
    chat: Chat


def http_post(url: str, body: bytes, content_type: str, timeout: float) -> tuple[int, bytes]:
    """POST ``body`` to ``url``; an HTTP error answers its status, only no network raises."""
    request = urllib.request.Request(url, data=body, headers={"Content-Type": content_type})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        with error:
            return error.code, error.read()


class Bot:
    """The Bot API of one bot, by its token."""

    def __init__(self, token: str, post: Post | None = None) -> None:
        self._token = token.strip()
        self._post = post or http_post

    def __repr__(self) -> str:
        return "Bot(token=…)"

    def check(self) -> str:
        """Return the bot's account name; raise :class:`ZaloTokenError` for an unknown token."""
        result = self._call("getMe", {})
        return str(result.get("account_name") or "") if isinstance(result, dict) else ""

    def next_chat(self, wait: float) -> Chat:
        """Return who wrote to the bot last, waiting up to ``wait`` seconds for a message.

        Raises :class:`NoMessageError` when nobody did.
        """
        try:
            result = self._call("getUpdates", {"timeout": str(round(wait))}, wait + TIMEOUT)
        except ZaloError as error:
            if error.code == NO_UPDATE:
                raise NoMessageError("Nobody wrote to the bot", NO_UPDATE) from None
            raise
        updates = result if isinstance(result, list) else [result]
        for update in reversed(updates):
            message = update.get("message") if isinstance(update, dict) else None
            if not isinstance(message, dict):
                continue
            chat = message.get("chat") or {}
            sender = message.get("from") or {}
            if chat.get("id") and not sender.get("is_bot"):
                return Chat(str(chat["id"]), str(sender.get("display_name") or ""))
        raise NoMessageError("Nobody wrote to the bot", NO_UPDATE)

    def send_text(self, chat_id: str, text: str) -> None:
        """Send ``text`` to ``chat_id``, cut to what the Bot API takes."""
        self._call("sendMessage", {"chat_id": chat_id, "text": _cut(text)})

    def send_photo(self, chat_id: str, photo: Path, caption: str) -> None:
        """Send the picture ``photo`` (PNG or JPEG) to ``chat_id`` with ``caption``."""
        boundary = uuid.uuid4().hex
        kind = mimetypes.guess_type(photo.name)[0] or "image/png"
        parts = [
            _form_field(boundary, "chat_id", chat_id),
            _form_field(boundary, "caption", _cut(caption)),
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; '
                f'filename="{photo.name}"\r\nContent-Type: {kind}\r\n\r\n'
            ).encode()
            + photo.read_bytes()
            + b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
        self._send("sendPhoto", b"".join(parts), f"multipart/form-data; boundary={boundary}")

    def _call(self, method: str, fields: dict[str, str], timeout: float = TIMEOUT) -> object:
        """Call ``method`` with ``fields`` as JSON; return its ``result``."""
        body = json.dumps(fields, ensure_ascii=False).encode("utf-8")
        return self._send(method, body, "application/json", timeout)

    def _send(
        self, method: str, body: bytes, content_type: str, timeout: float = TIMEOUT
    ) -> object:
        """POST to ``method``; return the answer's ``result`` or raise :class:`ZaloError`."""
        url = API_URL.format(token=self._token, method=method)
        try:
            status, answer = self._post(url, body, content_type, timeout)
        except OSError as error:  # no network, or no answer in time; the address holds the token
            raise ZaloError(f"Zalo did not answer {method}: {type(error).__name__}") from None
        try:
            data = json.loads(answer.decode("utf-8")) if answer else {}
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        code = data.get("error_code")
        if status == 200 and data.get("ok", True) is not False and code in (None, 0):
            return data.get("result", {})
        code = code if isinstance(code, int) and code else status
        detail = str(data.get("description") or f"HTTP {status}")[:200]
        if code in _BAD_TOKEN:
            raise ZaloTokenError(f"Zalo knows no bot by this token ({code})", code)
        raise ZaloError(f"Zalo refused {method} ({code}): {detail}", code)


def _cut(text: str) -> str:
    """Return ``text`` cut to :data:`LONGEST_TEXT` characters."""
    return text if len(text) <= LONGEST_TEXT else text[: LONGEST_TEXT - 1] + "…"


def _form_field(boundary: str, name: str, value: str) -> bytes:
    """Return one text field of a multipart form."""
    return (
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
    ).encode()


def read_link(store: CredentialStore) -> Link | None:
    """Return the bot and chat saved in ``store``; ``None`` when none is, or it is unreadable."""
    saved = store.read(ZALO)
    if saved is None:
        return None
    try:
        data = json.loads(saved.password)
        return Link(str(data["token"]), Chat(saved.phone, str(data.get("name") or "")))
    except (ValueError, KeyError, TypeError):
        logger.warning("The saved Zalo link could not be read")
        return None


def save_link(store: CredentialStore, link: Link) -> None:
    """Keep ``link`` in ``store``: the chat as the user name, the token and name as the secret."""
    secret = json.dumps({"token": link.token, "name": link.chat.name}, ensure_ascii=False)
    store.save(ZALO, Login(link.chat.id, secret))


def forget_link(store: CredentialStore) -> None:
    """Remove the saved link; nothing is sent to Zalo from then on."""
    store.delete(ZALO)


def send_report(link: Link, text: str, post: Post | None = None) -> bool:
    """Send a run's ``text`` to the user's chat; log and return ``False`` on failure."""
    try:
        Bot(link.token, post).send_text(link.chat.id, text)
    except ZaloError as error:
        logger.warning("Zalo message not sent: %s", error)
        return False
    except Exception:  # reporting never costs anything
        logger.warning("Zalo message not sent", exc_info=True)
        return False
    logger.info("Zalo message sent")
    return True


def send_tickets(link: Link, pictures: Sequence[tuple[Path, str]], post: Post | None = None) -> int:
    """Send each ``(picture, caption)``; return how many went. A failure skips that one only."""
    bot = Bot(link.token, post)
    sent = 0
    for picture, caption in pictures:
        try:
            bot.send_photo(link.chat.id, picture, caption)
        except (ZaloError, OSError) as error:
            logger.warning("Zalo picture %s not sent: %s", picture.name, error)
            continue
        except Exception:  # reporting never costs anything
            logger.warning("Zalo picture %s not sent", picture.name, exc_info=True)
            continue
        sent += 1
    if pictures:
        logger.info("Zalo pictures sent: %d of %d", sent, len(pictures))
    return sent
