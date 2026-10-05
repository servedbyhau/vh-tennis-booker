# SPEC: 0.2.0 Core

## Goal
Make the `court_booker` core ready to sit behind the 0.3.0 FastAPI backend: book a specific date,
report progress as structured events, stop a run on request, and find and connect to the emulator
without manual `adb connect`. CLI behaviour stays backward compatible.

## In scope
1. **Specific date:** `--date YYYY-MM-DD` and config key `date`; validated against the bookable range.
2. **Progress events:** typed lifecycle events delivered through a callback.
3. **Cancellation:** a thread-safe token honoured between steps and inside every wait/poll loop.
4. **ADB discovery and auto-connect:** reuse a running server, else start one with a found `adb`;
   explicit serial or `auto` port scan.
5. **Tests** for all of the above, using fake devices and fake ADB only.

## Out of scope
FastAPI/WebSocket, moving code to `backend/`, logging to file, bundled adb (0.5.0), reading the
device clock, any cleanup on the device after a cancel, several dates in one run, bypassing the
developer-mode check, tests against a real emulator in CI.

## Interfaces
- **Errors** (`errors.py`): new base `CourtBookerError`. Under it: `BookingError` (existing,
  aborts one round), `RequestError` → `DateOutOfRangeError`, `DeviceError` → `AdbNotFoundError`,
  `NoDeviceError`, `MultipleDevicesError(serials)`, `DeviceConnectionError`, and
  `RunCancelledError` (aborts the whole run).
- **Dates** (`dates.py`, pure): `bookable_range(today, max_days_ahead) -> tuple[date, date]`;
  `resolve_target_date(*, on=None, days_ahead=None, today, max_days_ahead) -> date`.
  "Today" is the host clock, passed in by the caller. Config gains `date: str | None = None` and
  `max_days_ahead: int = 2`. CLI `--date` and `--days` are mutually exclusive; a config file that
  sets both `date` and `days_ahead` raises `ConfigError`. Precedence: CLI > config `date` >
  config `days_ahead`.
- **Events** (`events.py`): `EventType` = `run_started, round_started, step_started,
  step_finished, round_finished, run_finished`. `Step` = `navigate, open_calendar, select_date,
  select_slot, select_venue, select_court, booking_details, confirm`. `Status` = `ok, failed,
  skipped, cancelled`. `Event` is a frozen dataclass: `type, ts, round, total_rounds, slot, step,
  status, message, elapsed`. `Event.to_dict()` returns JSON-safe values (enum values as strings,
  `ts` as ISO 8601). `EventHandler = Callable[[Event], None]`.
- **Cancellation** (`cancel.py`): `CancelToken` wraps `threading.Event` and offers `cancel()`,
  `cancelled` and `raise_if_cancelled()`. It is never checked after the final "Xác nhận" tap
  has been sent.
- **Runner** (`runner.py`): `run_booking(device, config, target, *, dry_run=False,
  on_event=None, cancel=None) -> RunResult`. The device is already connected; the CLI and 0.3.0
  both call this. `Booker(device, config, on_event=None, cancel=None)`. Blocking
  `.wait(timeout=...)` calls in `flow.py` become cancel-aware polling.
- **ADB** (`adb.py`): `find_adb(adb_path) -> Path` (config `adb_path`, then `PATH`);
  `ensure_server(adb)` (reuse port 5037 if it answers, else `adb start-server`);
  `discover(adb) -> list[str]` (already-attached devices plus `adb connect` to open ports: MuMu
  7555 and 16384+, LDPlayer/BlueStacks 5555+, Nox 62001); `resolve_device(config) -> str`.
  Config `device` defaults to `"auto"`; an explicit serial is connected alone, with no scan.
  The subprocess runner and port probe are injectable for tests.
- **CLI exit codes:** 0 all rounds ok · 1 a round failed · 2 bad arguments or date out of range ·
  3 device error · 130 cancelled (Ctrl+C).

## Done criteria

### 1. Specific date
- [ ] `--date 2026-10-07` books that date; `--date` together with `--days` exits 2 with an error message.
- [ ] A past date, or a date later than today + `max_days_ahead`, raises `DateOutOfRangeError` naming the valid range, before any device call; the CLI exits 2.
- [ ] A malformed date (`07/10/2026`, `2026-02-30`) exits 2.
- [ ] Config `date` is honoured; a config file with both `date` and `days_ahead` raises `ConfigError`.
- [ ] Without `date`/`--date`, behaviour equals 0.1.0 (`days_ahead`).

### 2. Progress events
- [ ] A successful 2-slot dry run emits, in order: `run_started`, then per round `round_started`, a `step_started`/`step_finished` pair for every step, and `round_finished`; then `run_finished`.
- [ ] `select_venue` reports `skipped` when the venue screen is absent.
- [ ] A failing step emits `step_finished(status=failed, message=<error>)`, then `round_finished(failed)`, and the next round still runs.
- [ ] `json.dumps(event.to_dict())` succeeds for every event type.
- [ ] With no `on_event`, the flow runs unchanged and the existing log output is kept.

### 3. Cancellation
- [ ] Cancelling before the run starts sends no device input and ends with `run_finished(cancelled)`.
- [ ] Cancelling while a wait or poll loop is running stops it within 0.5 s, emits `step_finished(cancelled)`, `round_finished(cancelled)` and `run_finished(cancelled)`, and skips the remaining rounds.
- [ ] Cancelling after the final confirm tap does not interrupt that step; its real outcome is reported.
- [ ] No device input is sent after a cancel, including any Back press.

### 4. ADB discovery and auto-connect
- [ ] A running server is reused, and `start-server` is not called.
- [ ] With no server running, the `adb` from `adb_path`, else from `PATH`, runs `start-server`; if neither is found, `AdbNotFoundError` explains how to fix it.
- [ ] An explicit serial is connected alone (no scan); failure raises `DeviceConnectionError`.
- [ ] `auto` with exactly one reachable device returns it; zero raises `NoDeviceError`; several raise `MultipleDevicesError` listing all serials.
- [ ] Closed ports are skipped without calling `adb connect`.
- [ ] Device errors make the CLI exit 3 with a readable message.

### 5. Tests and quality
- [ ] New tests: `test_dates.py`, `test_events.py`, `test_cancel.py`, `test_adb.py`, plus extended `test_flow.py`/runner tests using a scriptable fake device.
- [ ] The 11 existing tests still pass; no test needs an emulator, real adb or network access.
- [ ] `ruff check` and `ruff format --check` pass; CI is green on Python 3.9, 3.11, 3.12 and 3.13.
- [ ] `CHANGELOG.md` "Unreleased" lists the new features.

## Verification
- `python -m pytest -q`: all tests pass using fakes only (fake device, fake subprocess runner, fake port probe, fixed `today`).
- `python -m ruff check .` and `python -m ruff format --check .`
- Timing assertions for cancellation use a background thread and a 0.5 s bound.
- Runs on the real emulator are done manually by the user and are not part of this spec.
