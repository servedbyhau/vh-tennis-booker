"""The account's tickets: read from the app's history page, with a picture of each new one.

Runs after the rounds of a real run are over, reported and notified (:mod:`court_booker.cli`),
so nothing here can delay or fail a booking. The history page ("Lịch sử tiện ích") opens
from the icon at the top right of the utilities list and lists the newest bookings first, one
clickable card each; a card opens its ticket, with the QR code.

A ticket's page has a cancel button at its top right, so only two things are ever tapped: that
icon, on a utilities list read twice the same, and a card, named by its whole label (which
holds its booking code). Everything else is Back. Both pages are recognised by their shape,
not by captions, so the app's language does not matter (read in Vietnamese on 2026-11-22).
"""

from __future__ import annotations

import logging
import re
import struct
import time
import unicodedata
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

from court_booker.errors import DeviceNotRespondingError, NavigationError
from court_booker.flow import Booker
from court_booker.geometry import is_inside
from court_booker.screen import Node, Screen

logger = logging.getLogger(__name__)

REGISTERED = "registered"
PROCESSING = "processing"
CANCELLED = "cancelled"
OTHER = "other"
"""A status the app showed in words not known here; its words are kept as well."""

PHOTOS_KEPT = 500
"""Pictures kept, about 70 KB each; they hold personal data and stay on this PC."""

_CODE = re.compile(r"[^:]+: *(\d{4,})")
_TIME = re.compile(r".*?(\d{2})/(\d{2})/(\d{4}) +(\d{2}:\d{2}) *- *(\d{2}:\d{2})")
_CREATED = re.compile(r".*?(\d{2})/(\d{2})/(\d{4}) *- *(\d{2}:\d{2})")
_QR = "qr code"
"""The QR code's label on a ticket; the QR widget names it, in English in any app language."""
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}
"""Values per pixel of a PNG by colour type, of the types a screenshot may have."""

_HEADER_HEIGHT = 0.1
_ICON_LEFT = 0.8
_ICON_WIDTH = 0.2
"""Where the history icon is, as shares of the screen: within the header, at its right end."""
_STEADY = 0.5
"""Seconds between the two reads that must agree before the history icon is tapped."""
_PAGE_TIMEOUT = 15.0
"""Seconds a page may take to show; the history showed within 4 s (2026-11-22)."""
_QR_WAIT = 5.0
_PICTURE_SETTLE = 0.5
"""Pause before a picture and before it is taken again."""
_PICTURE_TRIES = 6
"""Pictures taken of a ticket until its layout held still. A ticket moves its lower half
while its description loads: on 2026-11-22 the directions link moved up by 230 px between
a read 0.5 s after the ticket showed and the picture."""
_RELOAD_PAUSE = 5.0
"""Seconds before the history is read again for a ticket missing or still processing."""
REGISTER_WAIT = 45.0
"""How long the history is read again for tickets to show as registered; a picture is then
taken of them as they are."""
_MARGIN = 10
"""Pixels kept under the directions link, where the picture of a ticket ends."""


@dataclass(frozen=True)
class Ticket:
    """One booking as its card on the history page shows it."""

    code: str
    utility: str
    """The utility's name in the app's language, such as ``Sân Tennis``."""
    court: str
    play_date: str
    """ISO date of play."""
    slot: str
    """``19:00 - 20:00``, as the config writes a slot."""
    status_text: str
    """The status in the app's words."""
    created_at: str | None
    """When it was booked, ``YYYY-MM-DDTHH:MM``."""

    @property
    def status(self) -> str:
        """Return the status: registered, processing, cancelled or other."""
        return ticket_status(self.status_text)


@dataclass(frozen=True)
class Wanted:
    """A booking this run made, to find among the tickets and take a picture of."""

    play_date: str
    slot: str
    court: str

    def matches(self, ticket: Ticket) -> bool:
        """Return whether ``ticket`` is this booking; one cancelled before is not."""
        return (
            ticket.status != CANCELLED
            and ticket.play_date == self.play_date
            and ticket.slot == self.slot
            and ticket.court.casefold() == self.court.casefold()
        )


@dataclass
class Collected:
    """What the history page showed, and the pictures taken."""

    tickets: list[Ticket] = field(default_factory=list)
    photos: dict[str, str] = field(default_factory=dict)
    """Booking code to the picture's file name."""


def ticket_status(text: str) -> str:
    """Return what the app's status ``text`` means, in either language of the app."""
    words = unicodedata.normalize("NFC", text).casefold().strip()
    # The app writes both "huỷ" (read on 2026-11-22) and "hủy".
    if "huỷ" in words or "hủy" in words or "cancel" in words:
        return CANCELLED
    if words in ("đang xử lý", "processing"):
        return PROCESSING
    if words in ("đã đăng ký", "registered"):
        return REGISTERED
    return OTHER


def _iso_date(day: str, month: str, year: str) -> str | None:
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def parse_card(label: str) -> Ticket | None:
    """Return the booking a card of the history page names, or ``None`` for another element.

    A card reads, line by line: the utility, the code, the court, the time of play, the
    status' caption, the status, and when it was booked. Captions end with a colon and are
    not compared, as they differ with the app's language.
    """
    lines = [line.strip() for line in unicodedata.normalize("NFC", label).split("\n")]
    if len(lines) < 6:
        return None
    code = _CODE.fullmatch(lines[1])
    _, colon, court = lines[2].partition(":")
    played = _TIME.fullmatch(lines[3])
    if code is None or played is None or not colon or not court.strip():
        return None
    if not lines[4].endswith(":") or not lines[0] or not lines[5]:
        return None
    day = _iso_date(*played.group(1, 2, 3))
    if day is None:
        return None
    created_at = None
    created = _CREATED.fullmatch(lines[6]) if len(lines) > 6 else None
    if created is not None:
        booked_on = _iso_date(*created.group(1, 2, 3))
        created_at = None if booked_on is None else f"{booked_on}T{created[4]}"
    return Ticket(
        code=code[1],
        utility=lines[0],
        court=court.strip(),
        play_date=day,
        slot=f"{played[4]} - {played[5]}",
        status_text=lines[5],
        created_at=created_at,
    )


def cards(screen: Screen) -> list[tuple[Ticket, Node]]:
    """Return the bookings ``screen`` lists, newest first, each with its card."""
    found = []
    for node in screen.nodes:
        ticket = parse_card(node.desc) if node.clickable else None
        if ticket is not None:
            found.append((ticket, node))
    return found


def history_icon(screen: Screen) -> Node | None:
    """Return the history icon of the utilities list: the one unlabelled button at its right."""
    width, height = screen.size
    found = [
        node
        for node in screen.nodes
        if node.clickable
        and not node.desc
        and node.box[0] >= width * _ICON_LEFT
        and node.box[2] - node.box[0] <= width * _ICON_WIDTH
        and node.box[3] <= height * _HEADER_HEIGHT
    ]
    return found[0] if len(found) == 1 else None


def ticket_details(screen: Screen, code: str) -> Node | None:
    """Return the details of ticket ``code`` if ``screen`` is its page.

    They hold the code on a line of its own, which a card of the history page does not.
    """
    return next((node for node in screen.nodes if code in node.desc.split("\n")), None)


def picture_end(screen: Screen, code: str) -> int | None:
    """Return the row where the picture of ticket ``code`` ends, or ``None`` if not found.

    That is just under the directions link ("Chỉ đường"): the lowest button within the
    details that stays in the right half; the fees and the payment below it are left out.
    """
    details = ticket_details(screen, code)
    if details is None:
        return None
    middle = screen.size[0] / 2
    links = [
        node
        for node in screen.nodes
        if node.clickable
        and node.desc
        and node.box[0] >= middle
        and is_inside(node.box, details.box)
    ]
    return max((node.box[3] for node in links), default=None)


def crop_png(data: bytes, height: int) -> bytes:
    """Return the PNG ``data`` cut to its first ``height`` rows.

    Rows are stored from the top, each filtered by the one above at most, so the rows kept
    stay valid as they are: no image library is needed. Raises ``ValueError`` for a PNG that
    is interlaced, unknown or damaged.
    """
    if not data.startswith(_PNG_SIGNATURE):
        raise ValueError("Not a PNG")
    header = b""
    packed = bytearray()
    position = len(_PNG_SIGNATURE)
    while position + 8 <= len(data):
        size, kind = struct.unpack_from(">I4s", data, position)
        body = data[position + 8 : position + 8 + size]
        position += 12 + size
        if kind == b"IHDR":
            header = body
        elif kind == b"IDAT":
            packed += body
        elif kind == b"IEND":
            break
    if len(header) != 13:
        raise ValueError("A PNG without its header")
    width, rows, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", header)
    if depth != 8 or colour not in _PNG_CHANNELS or interlace:
        raise ValueError(f"A PNG of depth {depth}, colour type {colour}, interlace {interlace}")
    if not 0 < height < rows:
        return data
    try:
        raw = zlib.decompress(bytes(packed))
    except zlib.error as exc:
        raise ValueError(f"A damaged PNG: {exc}") from exc
    kept = height * (1 + width * _PNG_CHANNELS[colour])
    if len(raw) < kept:
        raise ValueError("A PNG with rows missing")
    return b"".join(
        (
            _PNG_SIGNATURE,
            _chunk(b"IHDR", struct.pack(">II", width, height) + header[8:]),
            _chunk(b"IDAT", zlib.compress(raw[:kept], 9)),
            _chunk(b"IEND", b""),
        )
    )


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def png_width(data: bytes) -> int:
    """Return the width of the PNG ``data``; raises ``ValueError`` if it is none."""
    if len(data) < 24 or not data.startswith(_PNG_SIGNATURE):
        raise ValueError("Not a PNG")
    return struct.unpack_from(">I", data, 16)[0]


class TicketReader:
    """Read the tickets with ``booker``'s device, before ``deadline`` on ``clock``."""

    def __init__(
        self,
        booker: Booker,
        folder: Path,
        deadline: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.booker = booker
        self.folder = folder
        self.deadline = deadline
        self._clock = clock
        self._sleep = sleep
        self.collected = Collected()

    def read(self, wanted: Sequence[Wanted]) -> Collected:
        """Read the history page and take a picture of each ticket ``wanted``.

        Starts from any screen a round leaves. The page is read again while a ticket wanted is
        missing or still processing, for :data:`REGISTER_WAIT` at most. A failure keeps what
        was read so far and is only logged; a frozen emulator is raised, as nothing more can
        be asked of it.
        """
        try:
            self._read(wanted)
        except DeviceNotRespondingError:
            raise
        except Exception:  # the bookings are made and reported: a ticket not read only logs
            logger.warning("Could not read the tickets", exc_info=True)
        return self.collected

    def _read(self, wanted: Sequence[Wanted]) -> None:
        screen = self._open_history()
        give_up = min(self._clock() + REGISTER_WAIT, self.deadline)
        while True:
            listed = [ticket for ticket, _ in cards(screen)]
            self.collected.tickets = listed
            found = [self._find(want, listed) for want in wanted]
            settled = all(t is not None and t.status != PROCESSING for t in found)
            if settled or self._clock() + _RELOAD_PAUSE >= give_up:
                break
            self._sleep(_RELOAD_PAUSE)
            screen = self._open_history()
        for want, ticket in zip(wanted, found):
            if ticket is None:
                logger.warning("No ticket for %s %s on the history page", want.play_date, want.slot)
            elif ticket.code not in self.collected.photos:
                self._take_picture(ticket)

    def _find(self, want: Wanted, listed: Sequence[Ticket]) -> Ticket | None:
        # Newest first: the one just booked comes before an older one of the same slot.
        return next((ticket for ticket in listed if want.matches(ticket)), None)

    def _open_history(self) -> Screen:
        """Open the history page from any screen and return it once it lists a booking."""
        booker = self.booker
        screen = booker.return_to_utilities()
        icon = self._steady_icon(screen)
        booker.tap(icon)
        found = booker.wait_for(lambda shown: cards(shown) or None, self._left(_PAGE_TIMEOUT))
        if found is None:
            raise NavigationError("The history page did not show")
        # The cards come in a frame or more; the count of the first reads may be short.
        self._sleep(_PICTURE_SETTLE)
        return booker.snapshot()

    def _steady_icon(self, screen: Screen) -> Node:
        """Return the history icon once two reads of the utilities list show it alike.

        An element without a label is tapped by its place, and a ticket's cancel button is
        about there, so the list must be the screen shown, not one on its way out.
        """
        until = self._clock() + self._left(_PAGE_TIMEOUT)
        while True:
            before = history_icon(screen)
            self._sleep(_STEADY)
            screen = self.booker.snapshot()
            listed = screen.find(self.booker.utility) is not None
            if before is not None and listed and history_icon(screen) == before:
                return before
            if self._clock() >= until:
                raise NavigationError("The utilities list shows no history icon")

    def _take_picture(self, ticket: Ticket) -> None:
        """Open ``ticket`` from the history page, save its picture and go back to the page."""
        booker = self.booker
        listed = {shown.code: node for shown, node in cards(booker.snapshot())}
        card = listed.get(ticket.code)
        if card is None:
            raise NavigationError(f"Ticket {ticket.code} is no longer on the history page")
        booker.tap(card)
        opened = booker.wait_for(
            lambda shown: ticket_details(shown, ticket.code), self._left(_PAGE_TIMEOUT)
        )
        if opened is None:
            raise NavigationError(f"Ticket {ticket.code} did not open")
        has_code = booker.wait_for(
            lambda shown: next((n for n in shown.nodes if n.desc == _QR), None),
            self._left(_QR_WAIT),
            opened[1],
        )
        if has_code is None:
            logger.warning("Ticket %s shows no QR code", ticket.code)
        self._sleep(_PICTURE_SETTLE)
        screen = booker.snapshot()
        if ticket_details(screen, ticket.code) is None:
            raise NavigationError(f"Ticket {ticket.code} closed by itself")
        try:
            self.collected.photos[ticket.code] = self._save_picture(screen, ticket.code)
        except (OSError, ValueError) as exc:
            logger.warning("Could not save the picture of ticket %s: %s", ticket.code, exc)
        booker.press_back()
        back = booker.wait_for(lambda shown: cards(shown) or None, self._left(_PAGE_TIMEOUT))
        if back is None:
            raise NavigationError("Back from a ticket did not show the history page")

    def _save_picture(self, screen: Screen, code: str) -> str:
        """Save the screen as ``<code>.png`` down to the directions link; return its name.

        The picture counts only if the link is at the same place before and after it;
        after :data:`_PICTURE_TRIES` it is kept whole.
        """
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f"{code}.png"
        part = self.folder / f"{code}.part.png"
        try:
            end = picture_end(screen, code)
            for _ in range(_PICTURE_TRIES):
                self.booker.device.screenshot(str(part))
                before, screen = end, self.booker.snapshot()
                end = picture_end(screen, code)
                if end is not None and end == before:
                    break
                self._sleep(_PICTURE_SETTLE)
            else:
                end = None
            data = part.read_bytes()
            if end is None or png_width(data) != screen.size[0]:
                logger.warning("Ticket %s: no steady directions link; picture kept whole", code)
            else:
                data = crop_png(data, end + _MARGIN)
            part.write_bytes(data)
            part.replace(path)
        finally:
            part.unlink(missing_ok=True)
        logger.info("Saved the picture of ticket %s", code)
        return path.name

    def _left(self, wait: float) -> float:
        """Return ``wait`` cut to the time left; raises once none is."""
        left = self.deadline - self._clock()
        if left <= 0:
            raise NavigationError("No time left to read the tickets")
        return min(wait, left)


def drop_old_photos(folder: Path, keep: int = PHOTOS_KEPT) -> None:
    """Delete the oldest pictures in ``folder`` beyond ``keep``; a failure only logs."""
    try:
        photos = sorted(folder.glob("*.png"), key=lambda path: path.stat().st_mtime)
        for old in photos[:-keep]:
            old.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete old ticket pictures", exc_info=True)
