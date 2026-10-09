"""Runner tests with a fake booker; no device required."""

from datetime import datetime

import court_booker.runner as runner
from court_booker.config import Config
from court_booker.errors import SlotUnavailableError


class FakeBooker:
    def __init__(self, device, config):
        self.booked = []
        self.events = []
        self.commands = 0

    def prepare(self):
        self.events.append("prepare")

    def locate_entry(self):
        self.events.append("locate")

    def book(self, slot, target, dry_run=False):
        if slot == "18:00 - 19:00":
            raise SlotUnavailableError("Slot 18:00 - 19:00 is fully booked")
        self.booked.append(slot)


class FakeDevice:
    def app_current(self):
        return {"package": "com.vinhomes.resident"}


def test_failed_round_does_not_stop_later_rounds(monkeypatch):
    monkeypatch.setattr(runner, "Booker", FakeBooker)
    config = Config(slots=["18:00 - 19:00", "19:00 - 20:00"])
    results = []

    returned = runner.run_booking(FakeDevice(), config, dry_run=True, results=results)

    assert returned is results
    assert [(r.slot, r.ok) for r in results] == [("18:00 - 19:00", False), ("19:00 - 20:00", True)]
    assert results[1].detail == "dry run passed"


def test_entry_is_located_just_before_the_start_time(monkeypatch):
    bookers = []

    def make_booker(device, config):
        bookers.append(FakeBooker(device, config))
        return bookers[-1]

    monkeypatch.setattr(runner, "Booker", make_booker)
    monkeypatch.setattr(
        runner, "wait_until", lambda target, offset: bookers[0].events.append(target)
    )
    start = datetime(2026, 10, 10, 6, 0)

    runner.run_booking(FakeDevice(), Config(slots=["19:00 - 20:00"]), start=start)

    assert bookers[0].events == ["prepare", start - runner.LOCATE_AHEAD, "locate", start]
