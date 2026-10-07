"""Send the run summary to a phone via a Telegram bot."""

from __future__ import annotations

import logging
import urllib.parse
import urllib.request
from collections.abc import Sequence
from typing import Callable

from court_booker.runner import RoundResult

logger = logging.getLogger(__name__)

Post = Callable[[str, bytes], None]

_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
_TIMEOUT = 10.0


def format_summary(
    results: Sequence[RoundResult], error: str | None = None, dry_run: bool = False
) -> str:
    """Return a short plain-text summary of the run."""
    booked = sum(result.ok for result in results)
    title = f"court-booker: {booked}/{len(results)} ok"
    if dry_run:
        title += " (dry run)"
    lines = [title]
    for result in results:
        lines.append(f"{'OK' if result.ok else 'FAIL'} {result.slot}: {result.detail}")
    if error:
        lines.append(f"Error: {error}")
    return "\n".join(lines)


def http_post(url: str, data: bytes) -> None:
    """POST form data to ``url``."""
    with urllib.request.urlopen(url, data=data, timeout=_TIMEOUT) as response:
        response.read()


def send_telegram(token: str, chat_id: str, text: str, post: Post = http_post) -> bool:
    """Send ``text`` to ``chat_id``; log and return ``False`` on failure, never raise."""
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        post(_API_URL.format(token=token), data)
    except (OSError, ValueError) as exc:  # URLError and HTTPError are OSErrors
        # The URL holds the bot token, so only the error itself is logged.
        logger.warning("Telegram message not sent: %s", exc)
        return False
    logger.info("Telegram summary sent")
    return True
