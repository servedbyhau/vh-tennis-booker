"""Reading the tickets on a scripted app; no device required."""

import logging
import struct
import zlib
from xml.sax.saxutils import quoteattr

import pytest

from court_booker import tickets
from court_booker.config import Config
from court_booker.errors import DeviceNotRespondingError
from court_booker.flow import Booker
from court_booker.screen import Node, Screen
from court_booker.tickets import Ticket, TicketReader, Wanted, crop_png, parse_card, png_width

WIDTH, HEIGHT = 540, 1600
CANCEL = "Hủy tiện ích"
ICON = (472, 42, 528, 100)
LIST = [
    ("", (6, 38, 72, 104), True),
    ("Danh sách tiện ích", (141, 52, 399, 89), False),
    ("", ICON, True),
    ("Sân Tennis", (388, 240, 505, 425), True),
    ("Sân Pickleball", (270, 425, 388, 609), True),
]


def card(code, slot="19:00 - 20:00", status="Đã đăng ký", court="S6 - Sân tennis"):
    """Return a card's label as the app's history page read on 2026-11-22."""
    return (
        f"Sân Tennis\nMã đặt: {code}\nVị trí: {court}\nThời gian: 03/10/2026 {slot}\n"
        f"Trạng thái:\n{status}\nThời gian tạo: 01/10/2026 - 06:00"
    )


def history_page(*labels):
    page = [
        ("", (6, 38, 72, 104), True),
        ("Lịch sử tiện ích", (164, 52, 376, 89), False),
        ("", (472, 43, 528, 99), True),  # the filter, in the place of the history icon
    ]
    for row, label in enumerate(labels):
        top = 132 + row * 381
        page.append((label, (23, top, 517, min(top + 359, HEIGHT)), True))
    return page


def ticket_page(code, link=True):
    page = [
        ("", (6, 38, 72, 104), True),
        ("Chi tiết đặt lịch", (99, 52, 311, 89), False),
        (CANCEL, (376, 38, 528, 104), True),
        ("qr code", (133, 165, 408, 440), False),
        (
            f"Sân Tennis\nMã đặt lịch\n{code}\nMã giao dịch\n7654321\nThời gian đặt lịch\n"
            "03/10/2026 19:00 - 20:00\nVị trí/dịch vụ\nS6 - Sân tennis",
            (0, 642, 540, 1463),
            False,
        ),
        ("Xem thêm", (36, 720, 504, 885), True),
        ("Phí đặt chỗ\n0 VND\nSố lượng cư dân\n4", (36, 1165, 504, 1274), False),
        ("Đặt lịch khác", (35, 1490, 505, 1584), True),
    ]
    if link:
        page.append(("Chỉ đường", (379, 1091, 504, 1140), True))
    return page


def png(width=4, height=6, channels=4, interlace=0):
    """Return a PNG whose row ``n`` holds the value ``n`` (modulo 256) in every pixel."""
    colour = {1: 0, 3: 2, 4: 6}[channels]
    raw = b"".join(b"\x00" + bytes([row % 256]) * (width * channels) for row in range(height))

    def chunk(kind, body):
        crc = struct.pack(">I", zlib.crc32(kind + body))
        return struct.pack(">I", len(body)) + kind + body + crc

    header = struct.pack(">IIBBBBB", width, height, 8, colour, 0, 0, interlace)
    packed = zlib.compress(raw)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", packed[:5])
        + chunk(b"IDAT", packed[5:])
        + chunk(b"IEND", b"")
    )


def rows(data):
    """Return the size and raw rows of a PNG."""
    width, height = struct.unpack_from(">II", data, 16)
    start = data.index(b"IDAT")
    size = struct.unpack_from(">I", data, start - 4)[0]
    return width, height, zlib.decompress(data[start + 4 : start + 4 + size])


def size(data):
    """Return the width and height of a PNG."""
    return struct.unpack_from(">II", data, 16)


class HistoryApp:
    """The app from a ticket left by a round: Back to the list, its icon, cards and tickets.

    ``pages`` are the cards of the history page, one list per time it is opened (the last one
    stays). A tap must name a labelled element by its label, as the driver needs it.
    """

    def __init__(self, *pages, link=True, screenshot=None):
        self.pages = list(pages)
        self.link = link
        self.screen = "left"  # the ticket the last round ended on
        self.opened = 0
        self.taps = []
        self.take = screenshot or (lambda path: path.write_bytes(png(WIDTH, HEIGHT)))

    @property
    def cards(self):
        return self.pages[min(self.opened, len(self.pages)) - 1]

    def nodes(self):
        if self.screen == "list":
            return LIST
        if self.screen == "history":
            return history_page(*self.cards)
        return ticket_page("1" if self.screen == "left" else self.screen, self.link)

    def dump_hierarchy(self, compressed=False):
        children = "".join(
            f"<node content-desc={quoteattr(desc, {chr(10): '&#10;'})} "
            f'bounds="[{box[0]},{box[1]}][{box[2]},{box[3]}]" '
            f'clickable="{"true" if clickable else "false"}" />'
            for desc, box, clickable in self.nodes()
        )
        root = f'<node content-desc="" bounds="[0,0][{WIDTH},{HEIGHT}]" clickable="true">'
        return f"<hierarchy>{root}{children}</node></hierarchy>"

    def click(self, x, y, label=""):
        hits = [
            (desc, box)
            for desc, box, clickable in self.nodes()
            if clickable and (desc == label if label else box[0] <= x <= box[2])
            if label or box[1] <= y <= box[3]
        ]
        assert hits, f"nothing to tap at ({x}, {y}) {label!r} on {self.screen}"
        desc, box = hits[0]
        self.taps.append(desc or box)
        if self.screen == "list" and box == ICON:
            self.opened += 1
            self.screen = "history"
        elif self.screen == "history" and desc:
            self.screen = parse_card(desc).code

    def press(self, key):
        self.screen = {"history": "list", "left": "list", "list": "list"}.get(
            self.screen, "history"
        )

    def screenshot(self, filename):
        from pathlib import Path

        self.take(Path(filename))


class Clock:
    """Time that passes only in sleeps, and a little with every look at it."""

    def __init__(self):
        self.now = 0.0
        self.slept = []

    def __call__(self):
        self.now += 0.01
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture
def read(tmp_path):
    """Return a function that reads the tickets of a scripted app."""

    def run(app, *wanted, seconds=90.0, sport="tennis"):
        clock = Clock()
        booker = Booker(app, Config(sport=sport, timeout=0.2))
        reader = TicketReader(booker, tmp_path / "tickets", seconds, clock, clock.sleep)
        run.clock, run.reader = clock, reader
        return reader.read(wanted)

    return run


WANTED = Wanted("2026-10-03", "19:00 - 20:00", "S6 - Sân tennis")


def test_a_card_gives_its_booking():
    assert parse_card(card("1234567")) == Ticket(
        code="1234567",
        utility="Sân Tennis",
        court="S6 - Sân tennis",
        play_date="2026-10-03",
        slot="19:00 - 20:00",
        status_text="Đã đăng ký",
        created_at="2026-10-01T06:00",
    )


def test_a_card_is_read_by_its_shape_in_another_language():
    label = (
        "Pickleball\nBooking code: 1234568\nPlace: S9 - Sân Pickleball\n"
        "Time: 03/10/2026 18:00 - 19:00\nStatus:\nRegistered\nCreated: 01/10/2026 - 06:00"
    )
    ticket = parse_card(label)
    assert (ticket.code, ticket.court, ticket.slot) == (
        "1234568",
        "S9 - Sân Pickleball",
        "18:00 - 19:00",
    )
    assert ticket.status == tickets.REGISTERED


@pytest.mark.parametrize(
    "label",
    [
        "",
        "Sân Tennis",
        "Lịch sử tiện ích",
        card("1234567").replace("03/10/2026", "31/02/2026"),
        card("1234567").replace("Mã đặt: 1234567", "Mã đặt:"),
        card("1234567").replace("Trạng thái:", "Trạng thái"),
        ticket_page("1234567")[4][0],
    ],
)
def test_another_element_is_no_card(label):
    assert parse_card(label) is None


def test_a_card_without_its_creation_time_still_counts():
    assert parse_card(card("1234567").rpartition("\n")[0]).created_at is None


@pytest.mark.parametrize(
    ("text", "status"),
    [
        ("Đã đăng ký", tickets.REGISTERED),
        ("Registered", tickets.REGISTERED),
        ("Đang xử lý", tickets.PROCESSING),
        ("Processing", tickets.PROCESSING),
        ("Đã huỷ", tickets.CANCELLED),
        ("Đã hủy", tickets.CANCELLED),
        ("Cancelled", tickets.CANCELLED),
        ("Đã sử dụng", tickets.OTHER),
    ],
)
def test_the_status_is_told_in_either_language(text, status):
    assert tickets.ticket_status(text) == status


def test_the_history_icon_is_the_one_unlabelled_button_at_the_right_of_the_header():
    screen = Screen([Node(*node) for node in LIST] + [Node("", (0, 0, WIDTH, HEIGHT), True)])
    assert tickets.history_icon(screen).box == ICON
    # A ticket's header ends with the labelled cancel button: no icon there.
    page = Screen([Node(*node) for node in ticket_page("1")])
    assert tickets.history_icon(page) is None


def test_the_picture_ends_under_the_directions_link():
    page = Screen([Node(*node) for node in ticket_page("1234567")])
    assert tickets.picture_end(page, "1234567") == 1140
    without = Screen([Node(*node) for node in ticket_page("1234567", link=False)])
    assert tickets.picture_end(without, "1234567") is None
    assert tickets.picture_end(page, "999") is None


@pytest.mark.parametrize("channels", [1, 3, 4])
def test_a_png_is_cut_to_its_first_rows(channels):
    data = png(4, 6, channels)
    cut = crop_png(data, 2)
    width, height, raw = rows(cut)
    assert (width, height) == (4, 2)
    assert raw == b"".join(b"\x00" + bytes([row]) * (4 * channels) for row in range(2))
    assert png_width(cut) == 4
    assert crop_png(data, 6) == data
    assert crop_png(data, 99) == data


@pytest.mark.parametrize(
    "data",
    [b"", b"GIF89a", png()[:20], png(interlace=1), png()[:-30], b"\x89PNG\r\n\x1a\n" + b"\0" * 30],
)
def test_a_png_that_cannot_be_cut_is_refused(data):
    with pytest.raises(ValueError):
        crop_png(data, 2)


def test_tickets_are_read_and_the_booked_one_pictured(read, tmp_path):
    app = HistoryApp([card("1234567"), card("1234501", "10:00 - 11:00", "Đã huỷ")])

    found = read(app, WANTED)

    assert [ticket.code for ticket in found.tickets] == ["1234567", "1234501"]
    assert found.photos == {"1234567": "1234567.png"}
    saved = (tmp_path / "tickets" / "1234567.png").read_bytes()
    assert rows(saved)[:2] == (WIDTH, 1150)
    assert [path.name for path in (tmp_path / "tickets").iterdir()] == ["1234567.png"]
    # The icon, then the card: nothing else, and never a ticket's cancel button.
    assert app.taps == [ICON, card("1234567")]


def test_each_booked_slot_gets_its_own_picture(read):
    app = HistoryApp([card("3"), card("22222", "18:00 - 19:00"), card("33333")])
    found = read(app, Wanted("2026-10-03", "18:00 - 19:00", "S6 - sân tennis"), WANTED)
    assert set(found.photos) == {"22222", "33333"}
    assert CANCEL not in app.taps


def test_the_newest_ticket_of_the_slot_is_the_one_booked(read):
    app = HistoryApp([card("22222"), card("11111")])
    assert set(read(app, WANTED).photos) == {"22222"}


def test_a_cancelled_ticket_of_the_same_slot_is_not_pictured(read, caplog):
    app = HistoryApp([card("11111", status="Đã huỷ")])
    with caplog.at_level(logging.WARNING):
        found = read(app, WANTED)
    assert found.photos == {}
    assert len(found.tickets) == 1
    assert "No ticket for 2026-10-03 19:00 - 20:00" in caplog.text


def test_a_ticket_still_processing_is_read_again(read):
    app = HistoryApp([card("11111", status="Đang xử lý")], [card("11111")])
    found = read(app, WANTED)
    assert found.tickets[0].status == tickets.REGISTERED
    assert found.photos == {"11111": "11111.png"}
    assert app.opened == 2


def test_a_ticket_that_stays_processing_is_pictured_as_it_is(read):
    app = HistoryApp([card("11111", status="Đang xử lý")])
    found = read(app, WANTED)
    assert found.tickets[0].status == tickets.PROCESSING
    assert found.photos == {"11111": "11111.png"}
    assert read.clock.now < tickets.REGISTER_WAIT + 15


def test_without_the_directions_link_the_picture_stays_whole(read, tmp_path, caplog):
    app = HistoryApp([card("11111")], link=False)
    with caplog.at_level(logging.WARNING):
        found = read(app, WANTED)
    assert found.photos == {"11111": "11111.png"}
    assert size((tmp_path / "tickets" / "11111.png").read_bytes()) == (WIDTH, HEIGHT)
    assert "kept whole" in caplog.text


def move_link(monkeypatch, app, bottoms):
    """Put the directions link of ``app``'s tickets at each of ``bottoms`` in turn."""
    places, nodes = iter(bottoms), app.nodes

    def moving():
        page = nodes()
        if app.screen in ("left", "list", "history"):
            return page
        bottom = next(places, 1140)
        box = (379, bottom - 49, 504, bottom)
        return [(d, box if d == "Chỉ đường" else b, c) for d, b, c in page]

    monkeypatch.setattr(app, "nodes", moving)


def test_a_picture_taken_while_the_ticket_moves_is_taken_again(read, tmp_path, monkeypatch):
    shots = []

    def screenshot(path):
        shots.append(path)
        path.write_bytes(png(WIDTH, HEIGHT))

    app = HistoryApp([card("11111")], screenshot=screenshot)
    # The link is read as the ticket opens and before the picture, then moves up.
    move_link(monkeypatch, app, [1372, 1372])
    read(app, WANTED)
    assert len(shots) == 2
    assert size((tmp_path / "tickets" / "11111.png").read_bytes()) == (WIDTH, 1150)


def test_a_ticket_that_never_holds_still_is_pictured_whole(read, tmp_path, monkeypatch, caplog):
    app = HistoryApp([card("11111")])
    move_link(monkeypatch, app, range(1000, 1300))
    with caplog.at_level(logging.WARNING):
        read(app, WANTED)
    assert size((tmp_path / "tickets" / "11111.png").read_bytes()) == (WIDTH, HEIGHT)
    assert "kept whole" in caplog.text


def test_a_landscape_picture_stays_whole(read, tmp_path):
    app = HistoryApp([card("11111")], screenshot=lambda path: path.write_bytes(png(1600, 540)))
    read(app, WANTED)
    assert size((tmp_path / "tickets" / "11111.png").read_bytes()) == (1600, 540)


def test_a_picture_that_fails_costs_only_itself(read, tmp_path, caplog):
    shots = iter([OSError("disk full"), None])

    def screenshot(path):
        error = next(shots)
        if error is not None:
            raise error
        path.write_bytes(png(WIDTH, HEIGHT))

    app = HistoryApp([card("11111"), card("22222", "18:00 - 19:00")], screenshot=screenshot)
    with caplog.at_level(logging.WARNING):
        found = read(app, WANTED, Wanted("2026-10-03", "18:00 - 19:00", "S6 - Sân tennis"))
    assert found.photos == {"22222": "22222.png"}
    assert "Could not save the picture of ticket 11111" in caplog.text


def test_an_empty_history_gives_nothing(read, monkeypatch, caplog):
    monkeypatch.setattr(tickets, "_PAGE_TIMEOUT", 0.1)
    with caplog.at_level(logging.WARNING):
        found = read(HistoryApp([]), WANTED)
    assert found.tickets == []
    assert "Could not read the tickets" in caplog.text


def test_no_time_left_taps_nothing(read):
    app = HistoryApp([card("11111")])
    assert read(app, WANTED, seconds=0.0).tickets == []
    assert app.taps == []


def test_a_list_still_changing_is_not_tapped(read, monkeypatch):
    """The icon is tapped by its place: only on a list that two reads show alike."""
    app = HistoryApp([card("11111")])
    moving = iter([(472, 42, 528, 100), (472, 44, 528, 102), (472, 44, 528, 102)])
    nodes = app.nodes

    def shifting():
        page = nodes()
        if app.screen != "list":
            return page
        box = next(moving, ICON)
        return [(desc, box if where == ICON else where, tap) for desc, where, tap in page]

    monkeypatch.setattr(app, "nodes", shifting)
    read(app, WANTED)
    assert len(read.clock.slept) >= 2
    assert CANCEL not in app.taps


def test_a_ticket_in_the_place_of_the_list_is_not_tapped(read, monkeypatch):
    """The cancel button of a ticket is where the history icon of the list is."""
    app = HistoryApp([card("11111")])
    nodes, reads = app.nodes, []

    def flickering():
        if app.screen != "list":
            return nodes()
        reads.append(1)
        # The list in one read, the ticket again in the next three, then the list.
        return ticket_page("1") if 2 <= len(reads) <= 4 else nodes()

    monkeypatch.setattr(app, "nodes", flickering)
    assert read(app, WANTED).photos == {"11111": "11111.png"}
    assert app.taps[0] == ICON
    assert CANCEL not in app.taps


def test_a_frozen_emulator_is_raised_with_what_was_read(read):
    def frozen(path):
        raise DeviceNotRespondingError("screenshot did not end")

    app = HistoryApp([card("11111")], screenshot=frozen)
    with pytest.raises(DeviceNotRespondingError):
        read(app, WANTED)
    assert [ticket.code for ticket in read.reader.collected.tickets] == ["11111"]


def test_the_oldest_pictures_go(tmp_path):
    import os

    for number in range(5):
        path = tmp_path / f"{number}.png"
        path.write_bytes(b"x")
        os.utime(path, (number, number))
    tickets.drop_old_photos(tmp_path, keep=2)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["3.png", "4.png"]
    tickets.drop_old_photos(tmp_path / "missing")
