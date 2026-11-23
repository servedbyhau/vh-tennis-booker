"""Quota tests: what the history page's tickets leave of the quota; no device required."""

from datetime import date
from types import SimpleNamespace

import pytest

import court_booker.quota as quota
from court_booker.events import EventKind, MemorySink, Reporter
from court_booker.flow import Booker
from court_booker.quota import (
    AFTER,
    BEFORE,
    Quota,
    count,
    first_booking_day,
    next_short,
    read_back,
)
from court_booker.screen import Node, Screen
from court_booker.tickets import Ticket

TENNIS = "Sân Tennis"


def ticket(code, play_date, status="Đã đăng ký", utility=TENNIS, created=None):
    return Ticket(code, utility, "S6 - Sân tennis", play_date, "18:00 - 19:00", status, created)


def card(code, play_date, created, status="Đã đăng ký", utility=TENNIS):
    """A card of the history page, as the app labels it."""
    year, month, day = play_date.split("-")
    made_year, made_month, made_day = created.split("-")
    label = "\n".join(
        (
            utility,
            f"Mã đặt: {code.rjust(7, '0')}",  # codes have seven digits
            "Vị trí: S6 - Sân tennis",
            f"Thời gian: {day}/{month}/{year} 18:00 - 19:00",
            "Trạng thái:",
            status,
            f"Thời gian tạo: {made_day}/{made_month}/{made_year} - 06:00",
        )
    )
    return Node(label, (20, 0, 520, 300), True)


def page(*cards):
    root = Node("", (0, 0, 540, 1600), False)
    tops = [200 + 320 * i for i in range(len(cards))]
    placed = [Node(c.desc, (20, top, 520, top + 300), True) for c, top in zip(cards, tops)]
    return Screen([root, *placed])


def test_every_ticket_counts_but_a_cancelled_one():
    tickets = [
        ticket("1", "2026-11-26"),
        ticket("2", "2026-11-20", "Đã sử dụng"),
        ticket("3", "2026-11-19", "Không sử dụng"),  # unused counts
        ticket("4", "2026-11-18", "Đã huỷ"),  # cancelled, by hand or for rain
        ticket("5", "2026-11-17", "Đã hủy"),
        ticket("6", "2026-11-16", "Đang xử lý"),
        ticket("7", "2026-11-15", "Sân đã được đặt"),  # words not known here count
    ]

    found = count(tickets, TENNIS, date(2026, 11, 26))

    assert (found.used, found.day_used) == (5, 1)


def test_only_the_utility_and_month_of_play_count():
    tickets = [
        ticket("1", "2026-11-26", utility="Sân Pickleball"),
        ticket("2", "2026-12-01"),  # booked in November, played in December
        ticket("3", "2026-10-31"),
        ticket("4", "2026-11-02", utility="sân tennis"),
    ]

    found = count(tickets, TENNIS, date(2026, 11, 26))

    assert found == Quota(TENNIS, "2026-11", 1, "2026-11-26", 0)


@pytest.mark.parametrize(
    ("used", "day_used", "left"),
    [(0, 0, 2), (7, 0, 1), (8, 0, 0), (3, 1, 1), (3, 2, 0), (9, 0, 0)],
)
def test_what_is_left_is_the_smaller_of_the_month_and_the_day(used, day_used, left):
    assert Quota(TENNIS, "2026-11", used, "2026-11-26", day_used).left == left


def test_a_month_begins_two_days_before_its_first():
    assert first_booking_day(date(2026, 12, 1)) == date(2026, 11, 29)
    assert first_booking_day(date(2026, 11, 26)) == date(2026, 10, 30)


def test_the_event_tells_what_is_left_and_what_the_run_wants():
    found = Quota(TENNIS, "2026-11", 7, "2026-11-26", 0)

    assert found.event_data(BEFORE, 2) == {
        "moment": "before",
        "utility": TENNIS,
        "month": "2026-11",
        "used": 7,
        "month_limit": 8,
        "play_date": "2026-11-26",
        "day_used": 0,
        "day_limit": 2,
        "left": 1,
        "slots": 2,
    }
    assert "slots" not in found.event_data(AFTER)
    assert quota.describe(found, 2).endswith("1 slot(s) left, 2 wanted: 1 short")


class FakeHistory:
    """The history page as pages of cards: each swipe shows the next; past the last, the last."""

    def __init__(self, pages, deadline=float("inf")):
        self.pages = pages
        self.shown = 0
        self.swipes = 0
        self.deadline = deadline
        self.labels = SimpleNamespace(utility=TENNIS)
        self.config = SimpleNamespace(sport="tennis")

    def open_history(self):
        self.shown = 0
        return self.pages[0]

    def snapshot(self):
        return self.pages[min(self.shown, len(self.pages) - 1)]

    def scroll_page(self, screen):
        self.swipes += 1
        self.shown += 1


def read(history, since=date(2026, 10, 30)):
    return read_back(history, history, since, clock=lambda: 0.0, sleep=lambda seconds: None)


def test_the_page_is_read_down_to_a_ticket_booked_before_the_month():
    history = FakeHistory(
        [
            page(card("9", "2026-11-25", "2026-11-23"), card("8", "2026-11-24", "2026-11-22")),
            page(card("8", "2026-11-24", "2026-11-22"), card("7", "2026-11-01", "2026-10-30")),
            page(card("6", "2026-10-31", "2026-10-29")),  # October: the reading stops here
            page(card("5", "2026-10-28", "2026-10-26")),
        ]
    )

    found = read(history)

    assert [t.code.lstrip("0") for t in found] == ["9", "8", "7", "6"]
    assert history.swipes == 2


def test_a_short_history_is_read_to_its_end():
    history = FakeHistory([page(card("9", "2026-11-25", "2026-11-23"))])

    found = read(history)

    assert [t.code.lstrip("0") for t in found] == ["9"]
    assert history.swipes == 2  # one more swipe once one brought nothing new


def test_a_page_read_too_late_tells_nothing():
    pages = [page(card(str(n), "2026-11-25", "2026-11-23")) for n in range(1, 41)]
    history = FakeHistory(pages, deadline=0.0)

    assert read(history) is None


def test_a_page_that_never_ends_tells_nothing():
    pages = [page(card(str(n), "2026-11-25", "2026-11-23")) for n in range(1, 41)]

    assert read(FakeHistory(pages)) is None


def test_the_quota_read_is_reported(monkeypatch):
    history = FakeHistory(
        [
            page(
                card("9", "2026-11-26", "2026-11-24"),
                card("8", "2026-11-20", "2026-11-18", "Đã huỷ"),
                card("7", "2026-10-29", "2026-10-27"),
            )
        ]
    )
    monkeypatch.setattr(quota, "TicketReader", lambda booker, folder, deadline: history)
    monkeypatch.setattr(quota, "read_back", lambda booker, reader, since: read(reader, since))
    sink = MemorySink()

    found = quota.read_quota(history, date(2026, 11, 26), BEFORE, Reporter(sink), 2)

    assert found == Quota(TENNIS, "2026-11", 1, "2026-11-26", 1)
    (event,) = sink.events
    assert event.kind is EventKind.QUOTA_READ
    assert (event.data["left"], event.data["slots"]) == (1, 2)


def test_a_page_swipe_is_one_command():
    swipes = []
    device = SimpleNamespace(swipe=lambda *args: swipes.append(args))
    booker = SimpleNamespace(device=device, commands=0)

    Booker.scroll_page(booker, Screen([Node("", (0, 0, 540, 1600), False)]))

    assert booker.commands == 1
    ((x1, y1, x2, y2, _),) = swipes
    assert (x1, x2) == (270, 270) and y1 > y2


@pytest.mark.parametrize(
    ("used", "play_date", "slots", "short"),
    [
        (7, "2026-11-25", 2, 1),
        (8, "2026-11-25", 1, 0),
        (6, "2026-11-25", 2, None),  # two left: enough
        (8, "2026-11-30", 2, None),  # the next run books for December
    ],
)
def test_the_next_run_is_short_only_in_the_same_month(used, play_date, slots, short):
    assert next_short(Quota(TENNIS, "2026-11", used, play_date, 2), slots) == short
