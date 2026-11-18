"""Refuse requests that a web page of another site makes the browser send to the backend.

The backend listens on 127.0.0.1 and has no login, so only this PC reaches it, but a page of
any site open in a browser on this PC can still make the browser send it requests. A
``POST`` without a body needs no permission from the backend (a dry run would start), and a
site whose name is pointed at 127.0.0.1 after the page loaded (DNS rebinding) could read and
change everything. Every request and WebSocket must therefore name this PC as its host, and
one that comes from a page must come from a page of this PC: the app's own window and the
development server both are.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit

LOCAL_NAMES = frozenset({"127.0.0.1", "localhost"})
"""The names this PC is reached by: the backend listens on 127.0.0.1 only."""

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]
App = Callable[[Scope, Receive, Send], Awaitable[None]]


def host_name(host: str) -> str:
    """Return the name in a ``Host`` header, without its port."""
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def is_local_host(host: str) -> bool:
    """Return whether a ``Host`` header names this PC; the desktop window sends no port."""
    return host_name(host.strip().lower()) in LOCAL_NAMES


def is_local_origin(origin: str) -> bool:
    """Return whether an ``Origin`` header is a page of this PC, on any port.

    The packaged window loads its page from the backend; in development Vite serves it on
    another port and forwards ``/api``. ``null`` (a file or a sandboxed page) is not local.
    """
    try:
        parts = urlsplit(origin.strip().lower())
    except ValueError:
        return False
    return parts.scheme == "http" and parts.hostname in LOCAL_NAMES


def refusal(scope: Scope) -> str | None:
    """Return why the request in ``scope`` is refused, or ``None`` if it may go on.

    A request without an ``Origin``, such as one from a command line, comes from no page.
    """
    headers = {name.lower(): value for name, value in scope.get("headers", [])}
    host = headers.get(b"host", b"").decode("latin-1")
    if not is_local_host(host):
        return f"Host {host!r} is not this PC"
    origin = headers.get(b"origin")
    if origin is not None and not is_local_origin(origin.decode("latin-1")):
        return f"A page of {origin.decode('latin-1')!r} may not use the backend"
    return None


class LocalOnly:
    """ASGI middleware that answers a refused request with 403, before any route runs."""

    def __init__(self, app: App) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        reason = refusal(scope) if scope["type"] in ("http", "websocket") else None
        if reason is None:
            await self.app(scope, receive, send)
        elif scope["type"] == "websocket":
            await receive()  # websocket.connect; closing now refuses the handshake with 403
            await send({"type": "websocket.close", "code": 1008})
        else:
            body = json.dumps({"error": "forbidden", "detail": reason}).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode("ascii")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
