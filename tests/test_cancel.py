"""Cancelling a ticket on a scripted app; no device required."""

import json
import logging
import sqlite3
from dataclasses import replace
from datetime import datetime
from xml.sax.saxutils import quoteattr

import pytest

from court_booker import cancel, cli, machine_task
from court_booker.cancel import cancel_ticket
from court_booker.config import Config
from court_booker.errors import LockHeldError, NavigationError, TicketNotCancelledError
from court_booker.flow import Booker
from court_booker.history import Holder
from court_booker.machine_task import machine_config
from court_booker.tickets import CANCELLED, Ticket

WIDTH, HEIGHT = 540, 1600
ICON = (472, 42, 528, 100)
CANCEL = "Hủy tiện ích"
QUESTION = "Bạn chắc chắn muốn hủy tiện ích?"
LIST = [
    ("", (6, 38, 72, 104), True),
    ("Danh sách tiện ích", (141, 52, 399, 89), False),
    ("", ICON, True),
    ("Sân Tennis", (388, 240, 505, 425), True),
    ("Sân cầu lông", (388, 425, 505, 609), True),
]


def card(code, status):
    """Return a card's label as the history page read on 2026-11-24."""
    return (
        f"Sân cầu lông\nMã đặt: {code}\nVị trí: S6 - Sân cầu lông\n"
        f"Thời gian: 26/11/2026 10:00 - 11:00\nTrạng thái:\n{status}\n"
        "Thời gian tạo: 24/11/2026 - 13:53"
    )


class CancelApp:
    """The app from its utilities list: the history page, a ticket, the question, the cancel.

    ``codes`` are the cards of the history page, newest first, four to a screen; a swipe shows
    the next four. After "Xác nhận" the page shows again with the card's old status until it
    is opened again, as the app does; ``refuse`` keeps the ticket booked, and without ``ask``
    the cancel button opens no question.
    """

    def __init__(self, *codes, cancelled=(), refuse=False, ask=True):
        self.codes = list(codes)
        self.status = {code: "Đã huỷ" if code in cancelled else "Đã đăng ký" for code in codes}
        self.shown = dict(self.status)
        self.refuse = refuse
        self.ask = ask
        self.screen = "list"
        self.ticket = None
        self.top = 0
        self.taps = []

    def nodes(self):
        if self.screen == "list":
            return LIST
        if self.screen == "history":
            page = [
                ("", (6, 38, 72, 104), True),
                ("Lịch sử tiện ích", (164, 52, 376, 89), False),
                ("", (472, 43, 528, 99), True),
            ]
            for row, code in enumerate(self.codes[self.top : self.top + 4]):
                top = 132 + row * 381
                page.append((card(code, self.shown[code]), (23, top, 517, top + 359), True))
            return page
        if self.screen == "dialog":
            return [
                (CANCEL, (0, 33, 540, 1600), False),
                (QUESTION, (46, 773, 494, 803), False),
                ("Hủy bỏ", (69, 827, 264, 921), True),
                ("Xác nhận", (276, 827, 471, 921), True),
            ]
        details = f"Sân cầu lông\nMã đặt lịch\n{self.ticket}\nMã giao dịch\n7654321"
        return [
            ("", (6, 38, 72, 104), True),
            ("Chi tiết đặt lịch", (99, 52, 311, 89), False),
            (CANCEL, (376, 38, 528, 104), True),
            ("qr code", (133, 165, 408, 440), False),
            (details, (0, 642, 540, 1463), False),
            ("Đặt lịch khác", (35, 1490, 505, 1584), True),
        ]

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
        if self.screen == "list" and box == ICON:
            self.taps.append("history")
            self.screen, self.top, self.shown = "history", 0, dict(self.status)
        elif self.screen == "history" and desc:
            self.ticket = desc.split("\n")[1].removeprefix("Mã đặt: ")
            self.taps.append(self.ticket)
            self.screen = "ticket"
        elif self.screen == "ticket" and desc == CANCEL:
            self.taps.append(desc)
            self.screen = "dialog" if self.ask else "ticket"
        elif self.screen == "dialog":
            self.taps.append(desc)
            if desc == "Xác nhận":
                self.screen = "history"  # the old statuses still show
                if not self.refuse:
                    self.status[self.ticket] = "Đã huỷ"
            else:
                self.screen = "ticket"
        else:
            self.taps.append(desc or box)

    def press(self, key):
        self.screen = {"history": "list", "list": "list", "dialog": "ticket"}.get(
            self.screen, "history"
        )

    def swipe(self, x1, y1, x2, y2, duration=0.1):
        self.top += 4


class Clock:
    """Time that passes only in sleeps, and a little with every look at it."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 0.01
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def run(app, code, seconds=60.0):
    clock = Clock()
    booker = Booker(app, Config(sport="badminton", timeout=0.2))
    return cancel_ticket(booker, code, seconds, clock, clock.sleep)


def test_a_ticket_is_cancelled_through_its_page_and_the_question():
    app = CancelApp("2546028", "1111111")

    listed = run(app, "2546028")

    assert app.taps == ["history", "2546028", CANCEL, "Xác nhận", "history"]
    (ticket,) = [shown for shown in listed if shown.code == "2546028"]
    assert ticket.status == CANCELLED
    assert {shown.code for shown in listed} == {"2546028", "1111111"}


def test_one_cancelled_already_is_left_as_it_is(caplog):
    caplog.set_level(logging.INFO, logger="court_booker")
    app = CancelApp("2546028", cancelled=["2546028"])

    listed = run(app, "2546028")

    assert app.taps == ["history"]
    assert listed[0].status == CANCELLED
    assert "Ticket 2546028 is cancelled already" in caplog.text


def test_a_ticket_further_down_is_found_by_swiping():
    codes = [str(1000000 + n) for n in range(6)]
    app = CancelApp(*codes)

    listed = run(app, codes[5])

    assert app.taps[1] == codes[5]
    assert next(t for t in listed if t.code == codes[5]).status == CANCELLED


def test_a_ticket_not_among_the_newest_is_never_tapped():
    codes = [str(1000000 + n) for n in range(30)]
    app = CancelApp(*codes)

    with pytest.raises(NavigationError, match="not among the newest"):
        run(app, codes[-1])
    assert app.taps == ["history"]


def test_without_the_question_nothing_is_confirmed(monkeypatch):
    monkeypatch.setattr(cancel, "_DIALOG_WAIT", 0.3)
    app = CancelApp("2546028", ask=False)

    with pytest.raises(NavigationError, match="question"):
        run(app, "2546028")
    assert "Xác nhận" not in app.taps
    assert app.status["2546028"] == "Đã đăng ký"


def test_a_ticket_the_app_keeps_is_not_cancelled():
    app = CancelApp("2546028", refuse=True)

    with pytest.raises(TicketNotCancelledError, match="still reads 'Đã đăng ký'"):
        run(app, "2546028")
    # The page is opened again after the confirm, as the one it shows holds the old status.
    assert app.taps.count("history") == 1 + cancel._CHECKS


def test_the_page_shown_after_the_confirm_is_not_trusted():
    app = CancelApp("2546028")

    run(app, "2546028")

    assert app.taps.count("history") == 2  # the page that showed it cancelled was opened anew


def test_a_machine_takes_its_own_settings_or_the_first_ones():
    config = Config(
        mumu_index=0,
        sport="tennis",
        instances=[{"mumu_index": 1, "sport": "pickleball", "court": "S9 - Sân Pickleball"}],
    )

    assert machine_config(config, None) is config
    assert machine_config(config, 0) is config
    assert machine_config(config, 1).sport == "pickleball"
    # A machine switched off in the Setup: its own index, the first machine's settings.
    off = machine_config(config, 2)
    assert (off.mumu_index, off.sport, off.instances) == (2, "tennis", [])
    assert replace(off, mumu_index=0, instances=config.instances) == config


class At(datetime):
    """The time of day the command runs at, 10:00 unless set."""

    moment = datetime(2026, 11, 24, 10, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.moment


class FakeDevice:
    connected = True
    hung = False

    def __init__(self):
        self.closed = 0

    def close(self):
        self.closed += 1


class FakeSupervisor:
    def __init__(self, config, driver, report):
        self.config = config
        self.device = FakeDevice()
        made.append(self)

    def prepare(self, booker, deadline):
        self.prepared = deadline


made = []
TICKET = Ticket(
    "2546028", "Sân cầu lông", "S6 - Sân cầu lông", "2026-11-26", "10:00 - 11:00", "Đã huỷ", None
)


@pytest.fixture
def command(monkeypatch, tmp_path):
    """Run ``court-booker cancel`` with a fake device; return its exit code and quota reads."""
    made.clear()
    monkeypatch.setattr(machine_task, "datetime", At)
    monkeypatch.setattr(machine_task, "Supervisor", FakeSupervisor)
    monkeypatch.setattr(machine_task, "_mumu_off", lambda config: False)
    monkeypatch.setattr(cancel, "cancel_ticket", lambda booker, code, deadline: [TICKET])
    reads = []
    monkeypatch.setattr(
        cancel, "read_quota", lambda booker, day, moment, report, **kw: reads.append((day, kw))
    )

    def run(*argv):
        return cli.main(["cancel", "--config", str(tmp_path / "missing.toml"), *argv])

    run.reads = reads
    return run


def events(data_home):
    with sqlite3.connect(data_home / "booker.db") as db:
        return [
            (kind, json.loads(data)) for kind, data in db.execute("SELECT kind, data FROM events")
        ]


def test_the_command_cancels_records_the_ticket_and_reads_its_quota(command, data_home):
    assert command("2546028") == cli.EXIT_OK

    (done,) = [data for kind, data in events(data_home) if kind == "ticket_cancelled"]
    assert done == {
        "code": "2546028",
        "utility": "Sân cầu lông",
        "court": "S6 - Sân cầu lông",
        "play_date": "2026-11-26",
        "slot": "10:00 - 11:00",
    }
    with sqlite3.connect(data_home / "booker.db") as db:
        rows = db.execute("SELECT code, device, status FROM tickets").fetchall()
    assert rows == [("2546028", 0, "cancelled")]
    ((day, kw),) = command.reads
    assert day.isoformat() == "2026-11-26"
    assert (kw["utility"], kw["sport"]) == ("Sân cầu lông", "badminton")
    assert made[0].device.closed == 1  # the driver is stopped once done


def test_no_cancel_in_the_quiet_time(command, data_home, monkeypatch):
    monkeypatch.setattr(At, "moment", datetime(2026, 11, 24, 5, 50))

    assert command("2546028") == cli.EXIT_BAD_REQUEST

    assert made == []  # MuMu is not touched
    ((kind, data),) = events(data_home)
    assert kind == "ticket_not_cancelled"
    assert data["code"] == "2546028"
    assert "No cancel from 05:45" in data["reason"]


def test_a_ticket_the_app_keeps_fails_the_command(command, data_home, monkeypatch):
    def refuse(booker, code, deadline):
        raise TicketNotCancelledError("Ticket 2546028 still reads 'Đã đăng ký' after the cancel")

    monkeypatch.setattr(cancel, "cancel_ticket", refuse)

    assert command("2546028") == cli.EXIT_ROUND_FAILED

    (failed,) = [data for kind, data in events(data_home) if kind == "ticket_not_cancelled"]
    assert "still reads" in failed["reason"]
    assert command.reads == []


def test_a_machine_busy_with_a_run_cancels_nothing(command, data_home, monkeypatch):
    def busy(self, trigger):
        raise LockHeldError("Another run is in progress")

    monkeypatch.setattr(machine_task.RunLock, "acquire", busy)

    assert command("2546028") == cli.EXIT_BUSY
    assert made == []


def test_the_quota_read_after_a_cancel_counts_for_the_account(command, data_home, monkeypatch):
    holder = Holder("acc-1", "An", "Căn A")
    monkeypatch.setattr(cli, "note_holder", lambda history, device: history.set_holder(holder))

    assert command("2546028", "--instance", "0") == cli.EXIT_OK

    ((_, kw),) = command.reads
    assert kw["account_id"] == "acc-1"
