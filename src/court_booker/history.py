"""The history database: every run, its slots, its steps and its log lines.

One SQLite file in the data folder holds the booking history and the activity log. Every run
writes to it, whoever started it (the scheduled task, a dry run, the command line); the app
only reads it. Times are local ISO strings, the same clock as the log files.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from court_booker.events import Event, EventKind
from court_booker.logging_setup import LOGGER_NAME

if TYPE_CHECKING:
    from court_booker.tickets import Ticket

logger = logging.getLogger(__name__)

BUSY_TIMEOUT = 0.5
"""Seconds to wait for another writer; longer would delay a booking round."""

MIGRATIONS = (
    """
    CREATE TABLE runs (
        id INTEGER PRIMARY KEY,
        trigger TEXT NOT NULL,
        dry_run INTEGER NOT NULL,
        version TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        play_date TEXT,
        court TEXT,
        status TEXT NOT NULL,
        error TEXT
    );
    CREATE TABLE run_slots (
        id INTEGER PRIMARY KEY,
        run_id INTEGER NOT NULL REFERENCES runs (id),
        slot TEXT NOT NULL,
        ok INTEGER NOT NULL,
        reason TEXT,
        finished_at TEXT NOT NULL,
        seconds REAL NOT NULL,
        commands INTEGER NOT NULL
    );
    CREATE TABLE events (
        id INTEGER PRIMARY KEY,
        run_id INTEGER REFERENCES runs (id),
        time TEXT NOT NULL,
        category TEXT NOT NULL,
        kind TEXT NOT NULL,
        data TEXT NOT NULL
    );
    CREATE TABLE log_lines (
        id INTEGER PRIMARY KEY,
        run_id INTEGER REFERENCES runs (id),
        time TEXT NOT NULL,
        level TEXT NOT NULL,
        message TEXT NOT NULL
    );
    CREATE INDEX run_slots_by_run ON run_slots (run_id);
    CREATE INDEX events_by_run ON events (run_id);
    CREATE INDEX log_lines_by_run ON log_lines (run_id);
    """,
    # The MuMu instance a run booked with, since runs can book side by side (0.13.0).
    """
    ALTER TABLE runs ADD COLUMN device INTEGER;
    """,
    # The accounts' tickets as the app's history page showed them (court_booker.tickets).
    """
    CREATE TABLE tickets (
        code TEXT PRIMARY KEY,
        device INTEGER NOT NULL,
        utility TEXT NOT NULL,
        court TEXT NOT NULL,
        play_date TEXT NOT NULL,
        slot TEXT NOT NULL,
        status TEXT NOT NULL,
        status_text TEXT NOT NULL,
        created_at TEXT,
        seen_at TEXT NOT NULL,
        photo TEXT
    );
    CREATE INDEX tickets_by_day ON tickets (play_date);
    """,
    # The customers and their accounts (court_booker.customers); logins are in the vault.
    """
    CREATE TABLE customers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        note TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE accounts (
        id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL REFERENCES customers (id),
        label TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX accounts_by_customer ON accounts (customer_id);
    """,
    # Who speaks for a customer, often one person for a group, and how to reach them.
    """
    ALTER TABLE customers ADD COLUMN representative TEXT NOT NULL DEFAULT '';
    ALTER TABLE customers ADD COLUMN contact TEXT NOT NULL DEFAULT '';
    """,
    # Whose account a run booked with and a ticket is of: which account, and the names it had
    # then, for once it is removed. Empty on a machine without a chosen account.
    """
    ALTER TABLE runs ADD COLUMN account_id TEXT;
    ALTER TABLE runs ADD COLUMN customer TEXT;
    ALTER TABLE runs ADD COLUMN account TEXT;
    ALTER TABLE tickets ADD COLUMN account_id TEXT;
    ALTER TABLE tickets ADD COLUMN customer TEXT;
    ALTER TABLE tickets ADD COLUMN account TEXT;
    """,
)
"""Schema changes in order; ``PRAGMA user_version`` counts the ones applied."""

SCHEMA_VERSION = len(MIGRATIONS)


def migrate(connection: sqlite3.Connection) -> int:
    """Apply the missing schema changes and return the schema version.

    A database written by a newer version is left as it is: its changes only add tables
    and columns, so older code can still write to it.
    """
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
        connection.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")
        logger.debug("History database schema %d applied", number)
    return max(version, SCHEMA_VERSION)


def connect(path: Path) -> sqlite3.Connection:
    """Open the database at ``path``, creating and migrating it as needed.

    Write-ahead logging lets the app read while a run writes, and without a disk flush on
    every commit a write takes well under a millisecond.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Log lines also come from the thread that runs device calls (court_booker.watchdog).
    connection = sqlite3.connect(path, timeout=BUSY_TIMEOUT, check_same_thread=False)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA foreign_keys = ON")
        migrate(connection)
    except sqlite3.Error:
        connection.close()
        raise
    return connection


def open_history(path: Path) -> History | None:
    """Open the history database at ``path`` and keep the package's log lines in it.

    Returns ``None`` if it cannot be opened: a run still books, it is only not recorded.
    """
    try:
        history = History(connect(path))
    except (OSError, sqlite3.Error):
        logger.warning("History database %s unavailable; run not recorded", path, exc_info=True)
        return None
    logger.debug("History in %s", path)
    logging.getLogger(LOGGER_NAME).addHandler(history.handler)
    return history


def close_history(history: History) -> None:
    """Stop keeping log lines and close the database opened by :func:`open_history`."""
    logging.getLogger(LOGGER_NAME).removeHandler(history.handler)
    history.close()


def _stamp(moment: datetime) -> str:
    return moment.isoformat(timespec="milliseconds")


_SLOT_KINDS = frozenset({EventKind.SLOT_STARTED, EventKind.SLOT_BOOKED})
_SETUP_KINDS = frozenset({EventKind.SETUP_STARTED, EventKind.SETUP_ITEM, EventKind.SETUP_FINISHED})


def category(event: Event) -> str:
    """Return the activity log filter of ``event``.

    One of ``step``, ``slot``, ``setup``, ``settings``, ``schedule`` or ``error``.
    """
    if event.kind is EventKind.SLOT_FAILED:
        return "error"
    if event.kind is EventKind.RUN_FINISHED and event.data.get("error"):
        return "error"
    if event.kind in _SETUP_KINDS:
        return "setup"
    if event.kind is EventKind.SETTINGS_SAVED:
        return "settings"
    if event.kind in (EventKind.SCHEDULE_ENABLED, EventKind.SCHEDULE_DISABLED):
        return "schedule"
    return "slot" if event.kind in _SLOT_KINDS else "step"


@dataclass(frozen=True)
class Holder:
    """Whose account a run books with, with the names it has now."""

    account_id: str
    customer: str
    account: str
    """The account's name, else its phone number with the middle hidden."""


class History:
    """Write the runs of this process to the history database; an event sink.

    Writing must never cost a booking: after the first database error, history stops for
    the rest of the process and the error is logged once.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.run_id: int | None = None
        self.holder: Holder | None = None
        self.failed = False
        self.writes = 0
        self.seconds = 0.0
        self._lock = threading.Lock()
        """One write at a time: events come from the run, log lines from any thread."""
        # Added to a logger by the caller, so that logger's lines are kept with the run.
        self.handler = HistoryHandler(self)

    def emit(self, event: Event) -> None:
        """Record ``event`` in the run tables and as a step of the activity log."""

        def write(db: sqlite3.Connection) -> None:
            self._record_run(db, event)
            db.execute(
                "INSERT INTO events (run_id, time, category, kind, data) VALUES (?, ?, ?, ?, ?)",
                (
                    self.run_id,
                    _stamp(event.time),
                    category(event),
                    event.kind.value,
                    json.dumps(event.data, ensure_ascii=False),
                ),
            )

        self._write(write)

    def set_holder(self, holder: Holder) -> None:
        """Record whose account this run books with, for it and the tickets it reads."""
        self.holder = holder
        self._write(
            lambda db: db.execute(
                "UPDATE runs SET account_id = ?, customer = ?, account = ? WHERE id = ?",
                (holder.account_id, holder.customer, holder.account, self.run_id),
            )
        )

    def interrupt_stale_runs(self) -> None:
        """Mark runs left ``running`` by a process that is gone as ``interrupted``.

        Call it while holding the run lock, when no other run can be going on.
        """
        counts: list[int] = []

        def write(db: sqlite3.Connection) -> None:
            cursor = db.execute(
                "UPDATE runs SET status = 'interrupted' WHERE status = 'running' AND id IS NOT ?",
                (self.run_id,),
            )
            counts.append(cursor.rowcount)

        self._write(write)
        if counts and counts[0]:
            logger.info("Marked %d run(s) left running as interrupted", counts[0])

    def add_log_lines(self, lines: list[tuple[str, str, str]]) -> None:
        """Store log lines given as ``(time, level, message)`` with the current run."""
        run_id = self.run_id
        self._write(
            lambda db: db.executemany(
                "INSERT INTO log_lines (run_id, time, level, message) VALUES (?, ?, ?, ?)",
                [(run_id, *line) for line in lines],
            )
        )

    def other_runs_going(self) -> bool:
        """Return whether another run is still recorded as running.

        A database that cannot be read tells of none.
        """
        with self._lock:
            try:
                row = self.connection.execute(
                    "SELECT 1 FROM runs WHERE status = 'running' AND id IS NOT ? LIMIT 1",
                    (self.run_id,),
                ).fetchone()
            except sqlite3.Error:
                return False
        return row is not None

    def last_account(self, device: int) -> str | None:
        """Return the masked phone number last seen logged in on MuMu instance ``device``."""
        with self._lock:
            try:
                row = self.connection.execute(
                    "SELECT events.data FROM events JOIN runs ON runs.id = events.run_id"
                    " WHERE events.kind = ? AND runs.device = ? ORDER BY events.id DESC LIMIT 1",
                    (EventKind.ACCOUNT_CHECKED.value, device),
                ).fetchone()
                return None if row is None else json.loads(row[0]).get("phone")
            except (sqlite3.Error, ValueError):
                return None

    def save_tickets(
        self, device: int, tickets: Sequence[Ticket], photos: Mapping[str, str], seen_at: datetime
    ) -> None:
        """Record ``tickets`` as MuMu instance ``device`` showed them at ``seen_at``.

        A ticket recorded before takes its new status; one without a new picture in
        ``photos`` (booking code to file name) keeps the one it has, and its account's holder
        while this run knows of none.
        """
        holder = self.holder
        names = (
            (None, None, None)
            if holder is None
            else (holder.account_id, holder.customer, holder.account)
        )
        rows = [
            (
                ticket.code,
                device,
                ticket.utility,
                ticket.court,
                ticket.play_date,
                ticket.slot,
                ticket.status,
                ticket.status_text,
                ticket.created_at,
                _stamp(seen_at),
                photos.get(ticket.code),
                *names,
            )
            for ticket in tickets
        ]
        self._write(
            lambda db: db.executemany(
                "INSERT INTO tickets (code, device, utility, court, play_date, slot, status,"
                " status_text, created_at, seen_at, photo, account_id, customer, account)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (code) DO UPDATE SET device = excluded.device,"
                " utility = excluded.utility, court = excluded.court,"
                " play_date = excluded.play_date, slot = excluded.slot,"
                " status = excluded.status, status_text = excluded.status_text,"
                " created_at = excluded.created_at, seen_at = excluded.seen_at,"
                " photo = COALESCE(excluded.photo, tickets.photo),"
                " account_id = COALESCE(excluded.account_id, tickets.account_id),"
                " customer = COALESCE(excluded.customer, tickets.customer),"
                " account = COALESCE(excluded.account, tickets.account)",
                rows,
            )
        )

    def close(self) -> None:
        """Store the held log lines and close the database, logging what writing cost.

        Remove :attr:`handler` from its logger first.
        """
        logger.debug("History: %d writes in %.1f ms", self.writes, self.seconds * 1000)
        self.handler.close()
        self.connection.close()

    def _write(self, write: Callable[[sqlite3.Connection], None]) -> None:
        """Run ``write`` in one transaction, unless an earlier write failed."""
        error: sqlite3.Error | None = None
        with self._lock:
            if self.failed:
                return
            started = time.perf_counter()
            try:
                with self.connection:
                    write(self.connection)
            except sqlite3.Error as exc:
                self.failed, error = True, exc
            finally:
                self.writes += 1
                self.seconds += time.perf_counter() - started
        if error is not None:
            # Outside the lock: the handler gets this line back and calls this method again.
            logger.warning("History database failed; history is off for this run", exc_info=error)

    def _record_run(self, db: sqlite3.Connection, event: Event) -> None:
        kind, data, stamp = event.kind, event.data, _stamp(event.time)
        if kind is EventKind.RUN_STARTED:
            cursor = db.execute(
                "INSERT INTO runs (trigger, dry_run, version, started_at, status, device)"
                " VALUES (?, ?, ?, ?, 'running', ?)",
                (data["trigger"], data["dry_run"], data["version"], stamp, data.get("device")),
            )
            self.run_id = cursor.lastrowid
        elif self.run_id is None:
            return
        elif kind is EventKind.BOOKING_STARTED:
            db.execute(
                "UPDATE runs SET play_date = ?, court = ? WHERE id = ?",
                (data["date"], data.get("court"), self.run_id),
            )
        elif kind in (EventKind.SLOT_BOOKED, EventKind.SLOT_FAILED):
            db.execute(
                "INSERT INTO run_slots (run_id, slot, ok, reason, finished_at, seconds, commands)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    self.run_id,
                    data["slot"],
                    kind is EventKind.SLOT_BOOKED,
                    data.get("reason"),
                    stamp,
                    data["seconds"],
                    data["commands"],
                ),
            )
            # The court the app booked, as it named it, in place of the configured one.
            if kind is EventKind.SLOT_BOOKED and data.get("shown_court"):
                db.execute(
                    "UPDATE runs SET court = ? WHERE id = ?", (data["shown_court"], self.run_id)
                )
        elif kind is EventKind.RUN_FINISHED:
            db.execute(
                "UPDATE runs SET finished_at = ?, status = ?, error = ? WHERE id = ?",
                (stamp, data["status"], data.get("error"), self.run_id),
            )


class HistoryHandler(logging.Handler):
    """Copy log records into ``log_lines``, the technical layer of the activity log.

    Lines logged before the run starts (the version, the Python in use) are held back and
    stored with the run once it starts; if no run starts, they are stored without one when
    the handler closes.
    """

    def __init__(self, history: History) -> None:
        super().__init__(logging.DEBUG)
        self.history = history
        self.setFormatter(logging.Formatter("%(message)s"))
        self._held: list[tuple[str, str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            moment = datetime.fromtimestamp(record.created)
            self._held.append((_stamp(moment), record.levelname, self.format(record)))
            if self.history.run_id is not None:
                self.flush()
        except Exception:  # a logging handler must not raise into the booking code
            self.handleError(record)

    def flush(self) -> None:
        """Store the held lines."""
        if self._held:
            lines, self._held = self._held, []
            self.history.add_log_lines(lines)

    def close(self) -> None:
        self.flush()
        super().close()
