# SPEC: 0.2.0 Unattended booking

## Goal
Book a court at the moment the app opens bookings (06:00 every day) without anyone at the
computer. Windows Task Scheduler wakes the PC; `court-booker` starts MuMu, connects ADB, opens
the Vinhomes app, waits on the utilities list ("Sân Tennis"), and at the exact start time books
the configured slots for today + `days_ahead` (default 2). Speed at the start time is the only
performance goal: everything slow happens before it.

## Blocking precondition (open)
The Vinhomes app rejects use while developer mode is on, and ADB needs developer mode. Before
implementing, the user checks manually what happens when "Xác nhận" is tapped with developer
mode on. If the booking cannot be submitted, this spec cannot reach its goal and is re-planned.
Bypassing the check stays out of scope.

## In scope
1. **Emulator start:** launch MuMu instance `mumu_index` with `MuMuManager.exe` and wait until
   Android has booted.
2. **ADB discovery and auto-connect:** reuse a running server, else start one; explicit serial or
   `auto` port scan.
3. **App preparation:** start the Vinhomes app and navigate to the utilities list before the
   start time; fail early if the app is not usable (e.g. logged out).
4. **Timed start:** `--at HH:MM[:SS]` waits until that local time, corrected by an NTP offset,
   then starts the first round.
5. **Opening retry:** if the target date or slot is not yet bookable at the start time, leave the
   calendar and re-enter until `open_retry_seconds` have passed.
6. **Keep awake:** prevent Windows from going back to sleep while a run is in progress.
7. **Run report:** log to a daily file; optional Telegram message with the summary.
8. **Scheduler setup:** `court-booker schedule install|remove|status` manages a Task Scheduler
   task that wakes the PC and runs the booking.
9. **Ctrl+C** prints the summary of finished rounds before exiting.
10. **Tests** for all of the above, using fakes only.

## Out of scope
Specific `--date` (the target is always today + `days_ahead`), a stop button or cancellation
token, structured progress events, FastAPI, any UI, waking from shutdown (only Sleep), automating
login or OTP, emulators other than MuMu for the start step (ADB discovery still covers them),
bypassing the developer-mode check, tests against a real emulator or network in CI.

## Interfaces
- **Errors** (`errors.py`): new base `CourtBookerError`. Under it: `BookingError` (existing,
  aborts one round); `RequestError` (bad arguments or config, e.g. start time already passed);
  `DeviceError` → `AdbNotFoundError`, `NoDeviceError`, `MultipleDevicesError(serials)`,
  `DeviceConnectionError`, `EmulatorError` (MuMu not found, launch failed, boot timeout);
  `AppNotReadyError` (neither the home nor the utilities screen appeared after launch).
- **Emulator** (`emulator.py`): `MuMu(manager: Path, index: int, run=subprocess.run)` with
  `is_started() -> bool` (from `MuMuManager.exe info -v <index>`, field
  `is_android_started`), `launch()` (`control -v <index> launch`), `wait_until_started(timeout)`
  and `shutdown()` (`control -v <index> shutdown`). Already started means no launch. Exact
  `MuMuManager` arguments are confirmed on the dev machine before coding.
- **ADB** (`adb.py`): `find_adb(adb_path) -> Path` (config `adb_path`, then `PATH`);
  `ensure_server(adb)` (reuse port 5037 if it answers, else `adb start-server`);
  `discover(adb) -> list[str]` (attached devices plus `adb connect` to open ports: MuMu 7555 and
  16384+, LDPlayer/BlueStacks 5555+, Nox 62001); `resolve_device(config) -> str`. Config
  `device` defaults to `"auto"`; an explicit serial is connected alone, with no scan. Subprocess
  runner and port probe are injectable.
- **Clock** (`clock.py`): `parse_start_time(text, now) -> datetime` (today at that time; past
  raises `RequestError`); `ntp_offset(server, timeout) -> float | None` (seconds to add to the
  local clock; `None` on failure, logged as a warning); `wait_until(target, *, now, sleep)`
  sleeps coarsely, then in short steps for the last second. Clock and sleep are injectable.
- **Power** (`power.py`): `keep_awake()` context manager using `SetThreadExecutionState`
  (`ES_CONTINUOUS | ES_SYSTEM_REQUIRED`); a no-op off Windows.
- **Flow** (`flow.py`): `Booker.prepare()` launches the app if needed and returns on the
  utilities list (raises `AppNotReadyError`). `Booker.book()` gains opening retry: if the date or
  slot is absent (not "Hết chỗ"), press Back to the utilities list and re-enter, until
  `open_retry_seconds`. "Hết chỗ" still fails the round at once.
- **Runner** (`runner.py`): `run_booking(device, config, *, start_at=None, dry_run=False)
  -> list[RoundResult]`: prepare, wait for `start_at` if given, compute the target date from the
  start time, run one round per slot. The CLI calls it inside `keep_awake()`.
- **Notify** (`notify.py`): `send_telegram(token, chat_id, text, post=...)`; failures are logged,
  never raised. Skipped when the token is empty.
- **Scheduler** (`schedule.py`): builds Task Scheduler XML (daily trigger, `WakeToRun`, run only
  when the user is logged on, working directory = config folder) and calls
  `schtasks /Create /XML`, `/Delete`, `/Query`. The command line runs
  `<python> -m court_booker --at <start_at> --config <absolute path>`. XML building is pure and
  tested; `schtasks` calls are injectable.
- **Config** (new keys, added to the dataclass and `config.example.toml`): `device = "auto"`,
  `adb_path = ""`, `mumu_manager = "C:/Program Files/Netease/MuMuPlayer/nx_main/MuMuManager.exe"`,
  `mumu_index = 0`, `boot_timeout = 180`, `close_emulator_after = false`, `start_at = "06:00:00"`,
  `wake_at = "05:45"`, `ntp_server = "pool.ntp.org"` (empty disables), `open_retry_seconds = 60`,
  `log_dir = "logs"`, `telegram_token = ""`, `telegram_chat_id = ""`.
- **CLI:** `court-booker [--at HH:MM[:SS]] [--dry-run] ...` runs now, or at the given time.
  `court-booker schedule install|remove|status` is dispatched when the first argument is
  `schedule`. Exit codes: 0 all rounds ok · 1 a round failed · 2 bad arguments or config ·
  3 device or emulator error · 4 app not ready · 130 Ctrl+C.

## Done criteria

### 1. Emulator start
- [ ] MuMu already started: no launch call. Not started: launch, then poll until started.
- [ ] Boot not finished within `boot_timeout`, or `MuMuManager.exe` missing: `EmulatorError`, exit 3.
- [ ] `close_emulator_after = true` shuts the instance down after the run, whatever the outcome.

### 2. ADB discovery and auto-connect
- [ ] A running server is reused and `start-server` is not called.
- [ ] With no server, `adb` from `adb_path`, else `PATH`, runs `start-server`; if neither exists, `AdbNotFoundError` says how to fix it.
- [ ] An explicit serial is connected alone; failure raises `DeviceConnectionError`.
- [ ] `auto`: one device is returned; zero raises `NoDeviceError`; several raise `MultipleDevicesError` listing all serials.
- [ ] Closed ports are skipped without calling `adb connect`.

### 3. App preparation
- [ ] The app is started when not in the foreground and the run continues on the utilities list.
- [ ] If neither home nor utilities appears within `boot_timeout`, `AppNotReadyError`, exit 4, and the notification says the app needs attention.

### 4. Timed start
- [ ] `--at 06:00` started at 05:45 taps "Sân Tennis" no earlier than 06:00:00.000 and, with fake clocks, within 50 ms after it.
- [ ] A start time already passed today exits 2 before any device call.
- [ ] The NTP offset is applied when available; an NTP failure logs a warning and the local clock is used.
- [ ] The target date is the start date + `days_ahead`.

### 5. Opening retry
- [ ] Date or slot missing at the start time: re-enter until it appears, then book; give up after `open_retry_seconds` with a `BookingError`.
- [ ] A "Hết chỗ" slot fails the round without retry.

### 6. Keep awake, report, scheduler, Ctrl+C
- [ ] `keep_awake()` sets and clears the execution state (tested with a fake `SetThreadExecutionState`).
- [ ] Each run appends to `logs/court-booker-YYYY-MM-DD.log`; a Telegram message with the summary is sent when configured, and its failure does not change the exit code.
- [ ] `schedule install` produces XML with the daily trigger at `wake_at`, `WakeToRun`, and the `--at` command; `remove` and `status` call `schtasks` correctly.
- [ ] Ctrl+C prints the summary of finished rounds and exits 130.

### 7. Tests and quality
- [ ] New tests: `test_emulator.py`, `test_adb.py`, `test_clock.py`, `test_power.py`, `test_notify.py`, `test_schedule.py`, extended `test_flow.py` and runner tests.
- [ ] The 11 existing tests still pass; no test needs an emulator, real adb, Task Scheduler or network.
- [ ] `ruff check` and `ruff format --check` pass; CI green on Python 3.9, 3.11, 3.12 and 3.13.
- [ ] `CHANGELOG.md` "Unreleased" lists the new features; README documents the one-time Windows setup.

## One-time Windows setup (documented in README)
PC left in Sleep, not shut down; plugged in; "Allow wake timers" enabled; Windows stays signed in
(MuMu needs an interactive session); Windows Update active hours cover the early morning; the
Vinhomes app stays logged in inside MuMu.

## Verification
- `python -m pytest -q` with fakes only (fake device, runner, port probe, clock, `schtasks`, HTTP).
- `python -m ruff check .` and `python -m ruff format --check .`
- Manual, by the user: `court-booker --at <now + 3 min> --dry-run` with MuMu closed; then the
  scheduled task with `--dry-run` from Sleep; before 06:00 once, dump the calendar with
  `tools/inspect_screen.py` to see how a not-yet-open date or slot looks.
