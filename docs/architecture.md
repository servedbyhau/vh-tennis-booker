# Architecture

Three parts: the **engine** (`engine.py` says how to start it: `python -m court_booker`, or the
packaged app's own exe) books a court in a run of its own; the
**backend** (`court_booker.api`, FastAPI) serves the app's screens; the **UI** (`ui/`, React)
is those screens. The 06:00 task runs the engine alone. How the flow reads the app:
[how-it-works.md](how-it-works.md); facts about the app and MuMu: [field-notes.md](field-notes.md);
the desktop app's design and packaging: [specs/0.5.0-desktop-app.md](specs/0.5.0-desktop-app.md).
Details live in the docstrings; this page says where things are and what must stay true.

## Engine: one run

- `cli.py` parses the arguments (`schedule ...` goes to `schedule.main`), applies them onto
  `Config`, adds the log file, measures the clock, and inside `power.keep_awake()` takes the run
  lock, connects the device and runs the rounds. Errors map to exit codes (`RequestError` 2,
  `DeviceError` 3, `AppNotReadyError` 4, `LockHeldError` 5, Ctrl+C 130; a failed round 1). On
  every path it logs the summary, records the run, sends the optional Telegram summary and the
  Windows notification (`notify.py`; a failure only logs a warning). After a real run with at
  least one round, `close_emulator` shuts MuMu down.
- Other MuMu instances (`[[instances]]` in the config, each with its own account and its own
  `mumu_index`, `slots`, `subdivision`, `sport`, `court`, `venue_keyword`;
  `config.instance_config`):
  the run's process, once it holds the lock and has cleared stale runs, starts one process per
  entry (`start_instances`: the same command with `--instance N`, without `--slots`,
  `--device`; console output dropped) and waits for them, holding its lock. Each such process
  is a whole run of its own with its instance's settings: its lock `run-mumu<N>.lock`, its log file
  `court-booker-<date>-mumu<N>.log`, its history run, its notification titled "MuMu N · …"
  (the first instance's too, as "MuMu 0"); it never clears stale runs. So an instance that
  fails or freezes holds up no other. Several instances need `mumu_manager` and
  `device = "auto"`; otherwise, or for an entry repeating an instance, the run books with its
  own instance alone (warning). Each run's `run_started` names its instance as `device`.
- `lock.py` + `processes.py`: the run lock `run.lock` in the data folder (pid and process start
  time, so a reused pid is never taken for the holder). A scheduled run takes over a holder
  2 minutes before the start; a stale lock is cleared. The quiet time refuses a dry run or auto
  setup from `wake_at` to start + 5 min.
- `ready.Supervisor` gets the run ready and repairs what fails, until a minute before the
  warm-up (`setup_deadline`: 05:58 for 06:00; at least 2 minutes for a run started late, 5 for
  an untimed one). A run rests on four layers, bottom up: MuMu (`emulator.py`, MuMuManager),
  its ADB connection (`adb.py`), the driver (`driver.py`; uiautomator2 after `DRIVER_STARTS`
  failed starts, `--driver` picks one) and the app on its home screen (`Booker.prepare`). Each
  pass checks every layer and repairs the first that fails: MuMu restarted (shutdown, checked
  stopped, launched, booted in `BOOT_RETRY_WAIT`; the first boot waits `boot_timeout`, and is
  made once the machines before this one in the config have booted, `launch_after` from
  `cli`, `LAUNCH_TURN` each at most and never past half the time to the deadline), the
  serial disconnected alone and connected again (the adb server is shared by the instances'
  processes), the driver started again, the app restarted after growing pauses
  (`APP_BACKOFF`, as a PC just woken may join its network late). `Adb.ping` (`am
  get-current-user`, a call to Android's system server) tells a frozen or hung Android (no
  answer in 10 s) from a lost connection; no answer restarts MuMu at once by ending its
  `MuMuNxDevice` process (`MuMu.kill`, found by its command line), as MuMuManager hangs on
  a frozen instance; another restart shuts it down through MuMuManager and ends the process
  only if it still runs after 20 s. Once booted, MuMu is not asked again: the ping tells
  whether it answers. A layer failing `ESCALATE_AFTER` times in a row gets the one below repaired too.
  Failures no repair can change end the run at once (`PERMANENT_ERRORS`: config, MuMu or adb
  missing, the app not installed, a logout without a saved login, a refused login); limits
  stop a failure that keeps coming back (`MUMU_RESTARTS`, `REPAIRS_MAX`). Each repair logs a
  warning and a `repaired` step (`layer`, `action`, `error`); the notification counts them.
  The flow drives a `DeviceHandle`, which a repair points at the new device; a device whose
  call hung is given up without another call. Each MuMuManager command is tried up to 3 times,
  2 s apart, within 20 s each (`emulator.CALL_ATTEMPTS`, `MUMU_TIMEOUT`; the setup checks and
  the backend try once). Every device call runs on one worker thread (`watchdog.py`) and
  fails with `DeviceNotRespondingError` after 60 s; a run that ends on one, or that gave up a
  hung device, exits through `os._exit`, as the stuck thread could hold the exit.
- `runner.run_booking`: `Supervisor.prepare` (above; `prepare()` turns animations and
  notification banners off in one shell command, restarts the app and stops on its home
  screen, `prepare(restart=True)` also without `restart_app`). Then wait on the home screen,
  checked every minute until the deadline (`Supervisor.watch`: `Booker.check_home`, the app
  in front and one screen read, a popup closed; a failure is repaired as above), until
  `start - warm_up_seconds` (the history is held from then, "Events and history"), measure
  the clock again, open the utilities list (`locate_entry`,
  through `Supervisor.run_step`: a failure is repaired and the list opened again, until 15 s
  before the start, `WARM_UP_REPAIRS_END`),
  read it again 2 s before the start, wait until start + 0.1 s, then one round per slot.
  A `BookingError` fails its round only, except: `DeviceNotRespondingError` ends the run after
  its round, and `QuotaFullError` leaves the rounds left unrun ("Skipped: the booking quota is
  used up", no device command). A failure logs the last screen read (`log_last_screen`).
- `runner.save_screen`: a real run that stops on a failure the app did not explain (anything
  but a full slot or court and the app's notices) saves a PNG of the screen in the log
  folder's `screens` (`adb exec-out screencap`, or uiautomator2's `screenshot`; about 1 s),
  logs its path and records a `screen_saved` step: when the app is not made ready, or when
  such a failure ends the last round. One in an earlier round saves none, so the next round
  is not late. A run that books, a dry run and a frozen emulator save none; a screenshot
  that fails only logs. The 30 newest are kept; they hold personal data and stay on the PC.
- `clock.py`: NTP (the configured server, then fallbacks; the answer with the shortest round
  trip) anchored on `time.perf_counter()`, so Windows setting the PC clock during the wait
  changes nothing. Without an answer it is the PC clock, with a warning.

## Engine: the booking flow (`flow.Booker`)

- `screen.Screen` is one `dump_hierarchy` parsed into `Node`s (label, visible bounds,
  clickable); `screen.Match` finds nodes locally. One read per screen state, no element queries.
- The device is used only through `snapshot()`, `tap()`/`tap_point()` (label and point),
  `press_back()`, `_scroll()`, `scroll_page()` (the history page) and `type_text()` (the login only), each counted in `commands`. A full round costs 16 commands
  (tests hold it). A screen that differs from the last read is logged at debug level, so the
  log holds every screen of a run.
- Labels come from `app_language.app_languages(config.labels, config.sport)`: Vietnamese from
  `[labels]`, English built in; the utility tapped is the tile of `sport` (`config.SPORTS`,
  `app_language.ENGLISH_SPORTS`) unless `[labels] utility` names one. `prepare()` finds the
  language on the first screen and uses it; a language without a tile for the sport stops the
  run there.
- Logged out (field notes): `prepare()` also takes the start's notice and the login screen
  (a `password` field) as the first screen. A notice is closed with Back, pressed again only
  while it still shows (Back on the login screen leaves the app); the login screen goes to
  `log_in`, which reads the saved login (`credentials.py`) only then: without one,
  `LoggedOutError` at once. Else it types the phone and the password (`type_text`), taps the
  enabled login button, once more only if nothing changed for 20 s (the app locks an account after
  5 wrong passwords and was seen to take 11 s to answer), and waits for the home screen (`logged_in` step) or a refusal, a notice or a message inside
  a field: `LoginFailedError`. Both are `AppNotReadyError` (exit 4). The masked phone is
  logged, never the phone or the password; `Node` keeps no field text.
- `tickets.py`: after a real run that booked, once its result is recorded and notified, reads
  the app's history page (`TicketReader`, through the run's own `Booker`, which `run_booking`
  hands over by `on_booker`) and saves a picture of each ticket just booked in
  `<data folder>\tickets\<code>.png`, cut under the directions link. `cli.read_tickets` starts
  it 3 min after the start of a timed run (06:03) and once no other run is recorded as
  running, 30 s later all the same (a killed run stays recorded so), and limits it to 90 s;
  the lock is held and MuMu stays open meanwhile. Nothing in it changes the run's result or
  exit code. A ticket that does not open costs no other ticket's picture, and what could not be
  read is tried once more. `forget_expired` deletes the tickets whose day of play is over, whatever their
  status, and their pictures: at the end of a real run, once every machine's has ended, and
  when the backend starts. The runs in the history stay.
  It taps two things only, the history icon (on a list that two reads show alike, as a
  ticket's cancel button is in the same place) and a card by its whole label; pages are
  recognised by their shape, not by captions, so in either language. A picture counts only if
  the directions link is at the same place before and after it.
- `machine_task.py`: a task on one machine's app outside any run, `court-booker cancel` and
  `court-booker quota`, each a task of its own like auto setup: refused in the scheduled run's
  quiet time, the machine's run lock held (its trigger the task's name), no run in the history,
  its steps in the activity log (a failure as the task's own error step, with the reason). It
  brings MuMu, the driver and the app up as a run does, checks the account, does its work and
  shuts MuMu again if it started it. A machine switched off in the Setup is driven with the
  first machine's settings (`machine_config`).
- `cancel.py`: `court-booker cancel <code> [--instance N]` cancels a ticket in the app of its
  machine (`ticket_cancelled`, or `ticket_not_cancelled`). `cancel_ticket` opens the history page, finds the card among the newest (3 swipes at most),
  opens the ticket, taps its cancel button on the page of that code only, and "Xác nhận" only
  in the dialog that asks the question (labels `cancel_ticket`, `cancel_question`); without the
  question nothing is confirmed. The page the app shows after it still holds the old status,
  so the ticket counts as cancelled once a page opened again shows it so; the tickets read
  then are saved, and the quota of the ticket's utility is read again (`moment` `cancel`,
  with the account's id in the event, as no run holds it).
- `quota_command.py`: `court-booker quota [--instance N]` reads the quota of the account on the
  machine when asked: the history page once, back to the month of today + 2, and a `quota_read`
  (`moment` `asked`, with the account's id) for the machine's own utility and each other one
  with a ticket that month (`quota.read_quotas`); `quota_not_read` when the page was not read
  far enough.
- `money.py`: the charges of the tickets booked for customers (schema 8: `charges`, kept once
  the ticket is gone; `prices` by sport and `money_settings` for the golden hours; the customers'
  `free`). `History.save_tickets` makes a charge of each ticket of a chosen account still to play
  (the ones played before are never charged) and cancels the charge of a ticket read cancelled.
  `list_charges` prices them: the amount set by hand, else the price list's (golden for a slot
  starting in the golden hours), nothing for a cancelled ticket or a customer booked for free.
- `requests.py`: what each customer asks to book (schema 9: `requests`, the court, slots,
  `days` and `machine` as JSON and columns). It books nothing itself: the UI applies one to its
  machine's settings. A machine's `days` (config, `[[instances]]` each its own, `books_on`)
  keep the daily task from booking for another day of play: `cli.main` returns before the run
  for an instance off that day, and the first machine off that day still starts the others and
  waits for them; `launch_after` leaves out the machines off that day.
- `opening.py`: the log of the opening of a timed run, to learn what the app's 06:00 is checked
  against before changing when the first tap comes. Android's clock is read through adb
  (`Adb.device_time`, `date +%s.%N`; the best of 3 reads) during the warm-up and again once the
  rounds are over, never between them; during the first round `OpeningWatch` stands for the
  booker's reporter and only notes when its calendar opened. After the rounds one log line
  ("Opening: ...") and an `opening_measured` event hold the PC clock's and Android's offsets
  from NTP time, the first tap by NTP and by Android's clock, when the calendar opened and the
  attempt that opened it.
- `quota.py`: what the account used of the quota of the utility it books, for the day of play
  (today + 2): the tickets of that month of play, and of that day, all but cancelled ones
  (`count`; 8 a month, 2 a day, field notes "Dialogs"). `read_back` swipes the history page
  (`scroll_page`) down to its first card booked before the month could be (the 1st minus 2
  days), or to its end (a swipe that brought no card, then one more); neither within 25 swipes
  and 60 s, and it tells nothing, as cards left unread would show more left than there is.
  `run_booking` reads it once the app is ready (`check_quota`, 05:46), unless less than 5 min
  are left before the start: from 21:00 to 06:00 nothing can be booked, so it is what the app
  checks at 06:00. `cli.read_tickets` reads it again after the tickets. Each read is a
  `quota_read` event (`moment` before or after, the run's `sport`, what is used, what is left,
  and before the rounds the slots wanted) and a log line, a warning when the slots wanted are more
  than what is left. It only reports: a failure logs, then the home screen is checked as while
  waiting (`check_home`, repaired until the deadline), and the rounds are the same. After the
  tickets, `next_short` tells whether the next day's run has fewer left in the month than its
  slots (no booking can be made yet for its day; another month's quota is whole), and
  `cli.warn_short_quota` says so in the log and a Windows notification
  (`notify.format_quota_warning`, when notifications are on), naming whose account it is: the
  user has the day to choose another. A run never changes the account by itself (logging in to
  another one at 05:46 could cost the booking, and may log the customer's phone out).
- `customers.py` (`CustomerBook`): the customers and the Vinhomes accounts each one gave. The
  database holds names and notes only; an account's login is in the vault under its id.
  Attaching an account to a machine saves its login as that instance's, the one a run reads,
  so a run needs nothing of customers to book (it only notes whose account it is, `holder_on`),
  and an instance's account is the one with its phone number: one account, one machine. Nothing of a machine's login changes while a run holds the
  lock. Logins saved before there were customers get one each when the backend starts (`adopt`).
- `credentials.py`: one `Login` per MuMu instance and per customer account in Windows
  Credential Manager (a data folder set by `COURT_BOOKER_HOME` has names of its own there;
  `advapi32`,
  generic credential `CourtBooker/vinhomes/mumu-N`, kept for this Windows user on this PC,
  whom the daily task runs as); in memory where Windows is missing. `Login`'s repr hides the
  password. The run reads its own instance's (`cli` → `run_booking(login_for=...)`).
- `prepare()` makes sure of the account (`check_account`) when a login is saved for the machine:
  it opens the account tab, reads the phone number, and logs out and in with the saved login
  if it is another one, once a run; then the number must be right (`WrongAccountError`, not
  repaired). A number that cannot be read is tried again after a restart, then the run goes
  on only if an earlier run saw this account on this machine (`History.last_account`, from
  `account_checked` events, which hold the masked number). A run begun less than 2 minutes
  before its start skips the check then (`Booker.hurry`). Labels, never places, are tapped:
  the button above "Đăng xuất" deletes the account. No log holds a whole number.
- `prepare()` then tells the account's subdivision (`read_account`) from the apartment code
  on the home screen it read anyway ("BS…" → `bs`, "S…" → `origami`; 0 commands). Only the
  subdivision is logged and reported (`account_subdivision`), never the code (personal data).
  A court the catalog lists in another subdivision is a warning in the log and the Windows
  notification (`cli.AccountSink`), not an error: the guess may be wrong. Any failure there
  only logs.
- Every transition is `tap_and_advance(screen, target, name, find_next)`: tap, then read until
  `find_next` finds the next screen, up to `timeout` (30 s). The tap is repeated every 2 s
  while `target` still shows (a swallowed tap), never while the app loads (target gone).
  Closed loop everywhere: act on what the read shows, never on a fixed delay alone.
- Round: `open_slot` (utility → calendar; a notice in its place, such as the closed-hours one,
  is closed and the utility tapped again until `open_retry_seconds`, 15 s, whose old default
  of 60 s, written into every saved config until 1.2.0, reads as 15; a date or slot not listed
  yet reloads the calendar) → `select_date` (the day tapped once clickable, again every
  0.5 s while the calendar's prompt stays) → `select_slot` (tapped once "Tiếp tục" shows
  enabled) → "Tiếp tục" → `_after_calendar` (court list, the venue page, the booking details
  page of a utility with a single court, or a notice, which fails the round at once) →
  `select_court` (or `check_single_court` when a page with one choice passed on to the
  details page by itself: it must name the configured court)
  → "Tiếp tục" → confirmation page → `accept_and_confirm`.
- Venue page (`_venue_entry`): a single venue is tapped whatever its name; of several, the one
  `catalog.py` lists the court under (its name before the line break), else the one naming
  `venue_keyword` (a court typed by hand). A full venue ("Hết chỗ") fails the round at once.
- `catalog.py`: the subdivisions (`origami`, `bs`), their sports in the app's order, venues and
  courts (app name; block, kind and number for the UI's label, the kind one of
  `COURT_KINDS`), from the field notes. The run needs no subdivision: the
  court names its venue. The `subdivision` setting (empty: the account's) only checks the
  settings (`validate_config`: a known subdivision that has the sport).
- A court cut off by the bottom edge is tapped without a swipe: it is in the tree, and the
  driver clicks it by its label (seven basketball courts).
- `select_court`: the court list can move under the tap (field notes), so the booking details
  page must name the configured court; another court is left with Back and tapped again.
- `accept_and_confirm`: tick, then "Xác nhận" at least 0.2 s later. Booked only once the
  ticket's title shows; a notice fails the round (`BookingRejectedError`, `QuotaFullError` when
  it holds the `quota_full` label). "Xác nhận" is tapped again every 3 s while the page still
  shows it enabled; a notice after such a second tap, or nothing within `timeout`, is
  "Outcome unknown" (`BookingUnconfirmedError`). A dry run stops before "Xác nhận".
- Navigation back (`return_to_utilities`, `return_to_home`, `go_back`) presses the next Back as
  soon as the screen before shows; Back is never pressed on the home screen (it leaves the app).
  A promotion popup over the home screen (`dont_show_again` label) does not close with Back:
  both close it with its unlabelled X (`close_popup`) and wait for the home screen.
  `prepare()` also tells the language by the popup's label, and watches the home screen 2 s
  for it (`_POPUP_WAIT`), so it is closed before a round taps "Tiện ích".
- `book()` returns `Booked`: date, slot and court read on the confirmation page (a difference is
  a warning only) and the ticket's status, from reads the round makes anyway.
- Pure modules (testable without a device): `geometry.py`, `screen.py`, `app_language.py`,
  `catalog.py`,
  most of `clock.py`.

## Events and history

- `events.py`: progress events beside the log lines. `EventKind` values are stable strings
  (database values, UI message keys). `Reporter` swallows sink errors: reporting never costs a
  booking. The CLI emits `run_started`, `device_ready`, `run_finished`; `run_booking` the run's
  steps and `slot_booked`/`slot_failed`; `Booker` the steps of a round.
- `history.py`: `booker.db` (SQLite, WAL, migrations by `PRAGMA user_version`) as an event sink:
  `runs` (with the MuMu instance as `device`, from schema 2; empty for older runs; `court` is
  the configured court until a slot is booked, then the court the app booked; whose account it
  books with, from schema 6), `run_slots`,
  `events`, the tickets with whose account they are of, and the run's log lines (about 0.13 ms per
  row written). Whose it is (`Holder`: the account's id, and the customer's and account's names)
  is the chosen account's, noted once the run holds its lock (`cli.note_holder`), as a run books
  with that account or not at all; empty on a machine without a chosen one. It never costs a
  booking. Reading it back gives the names of today, those of then once the customer is removed.
  A timed run holds its writes in memory from the warm-up to the end of the rounds
  (`run_booking`'s `on_race`, `History.hold`) and writes them in one transaction after
  (`release`, also on `close`): machines booking at once never wait for each other's writes.
  Outside that, a write waits up to 5 s for another writer (`BUSY_TIMEOUT`). The first
  database error turns history off for the process.
  Schema changes only add columns, so an older runner still writes to a newer database.
- `history_read.py`: read-only queries for the backend (runs, one run, events, the live feed's
  `events_after`, `dry_run_passed`, `account_subdivisions`: the subdivision each
  MuMu instance last told); it migrates an older database first.

## Configuration and data folder

- `config.py`: `load_config` refuses unknown keys but never validates, so an existing config
  never stops the 06:00 run. `validate_config` runs before every save. `save_config` writes
  atomically, without comments, with only the labels that differ from the defaults and the keys
  of `_WRITTEN_WHEN_CHANGED` (and an instance's `sport`) only when changed: an older runner
  refuses keys it does not know.
  New fields go into the dataclass and `config.example.toml`.
- `paths.data_folder()`: `%LOCALAPPDATA%\CourtBooker` (`COURT_BOOKER_HOME` overrides) with
  `booker.db`, `run.lock`, `logs/` and the app's `config.toml`. The CLI's config comes from
  `--config`; a relative `log_dir` resolves beside it.
- `device_setup.py`: checks (MuMu installed, MuMu screen settings, wake timers, app installed)
  and `auto_setup` for the fixable ones (`court-booker setup [--auto]`; `GET /api/setup` only
  checks). The screen and the app are checked on every instance (`[[instances]]` too) as one
  item: the worst status, each instance's detail ("MuMu 1: …"); auto setup sets each wrong
  screen. Without a button: `ready.Supervisor` finds MuMuManager.exe when the configured
  path is wrong (`find_manager`, the config is not rewritten) and calls `prepare_screen`
  before starting each instance (a stopped MuMu gets 540x1600 at 220 DPI; a running one with
  another screen is only logged, never restarted before the start); `schedule install` and
  `PUT /api/schedule` call `ensure_wake_timers` (`powercfg`).
- `schedule.py`: the Windows task (`schtasks`) that wakes the PC at `wake_at` and runs the
  engine of whatever installed it: the runner folder's Python, or the packaged app.

## Desktop window (`desktop/`)

A Tauri shell around the backend, built by the `Desktop` workflow; the PyInstaller folder
(`packaging/court-booker.spec`, `tools/build_app.py`) is one of its resources. It shows a waiting
page, starts `court-booker.exe serve` without a window, waits for `/api/health` and moves on to the
backend's page. A backend that already answers is used as it is, and only a backend started here
is stopped on leaving. The backend starts from a plain path, without Tauri's `\\?\` prefix, as it
writes its own path into the daily task. It must stay true that nothing about a booking runs in the
window: the daily task runs `court-booker.exe` alone, with the window closed.

The update button: the page reaches two Rust commands, `update_version` and `install_update`,
through the `updates` capability, the only one for the remote page `http://127.0.0.1:8765/*`
(`build.rs` names the commands, so nothing else is reachable). The updater reads `latest.json`
from the newest release page and installs only what the updater key signed. `install_update`
refuses while a run holds the lock (`GET /api/status`), and stops the backend it started before
the installer runs, since both use the files the installer replaces. In `ui/`, `desktop.ts`
calls the commands; `UpdateButton` shows only in the window, when a newer version is out, and
is locked while a run holds the lock and in the quiet time.

Before copying a file, the installer (`windows/hooks.nsh`, `NSIS_HOOK_PREINSTALL`) stops every
process of the install folder, whoever started it: the window, the backend, a dry run. Windows
refuses to overwrite a running program, and a backend the window had not started left an update
half done on 2026-11-18. A real booking (an engine process without `serve`, `setup`,
`schedule` or `--dry-run`: the 06:00 run, a run by hand) is never stopped: the installer then
ends at once with exit code 2 and a message, before changing anything.

The uninstaller removes the daily task when its command is in the install folder
(`windows/hooks.nsh`), not on an update, which runs no uninstaller. `tools/check_installer.ps1`
proves install, serve, an update over a running backend, an update refused during a booking and
uninstall on the `Desktop` workflow's clean runner.

## Backend (`court_booker.api`)

`create_app(AppContext)`; `court-booker serve` listens on 127.0.0.1:8765, docs at `/api/docs`.
With a built UI in `court_booker/ui` beside the code, as in the packaged app, it serves that too
(`api/ui.py`), so the window has one origin and needs no CORS: `/api` and the live feed win, and
any other address that is no file answers `index.html`. In development the folder is absent and
Vite serves the UI.
It has no login, so `api/local_only.py` refuses (403 `forbidden`, a WebSocket closed with 1008)
every request whose `Host` is not 127.0.0.1 or localhost (a name pointed at this PC by a site)
or whose `Origin`, when sent, is not a page of this PC on any port (the window, Vite): a page
of another site open in a browser cannot start a dry run or read or change the settings.
`cli.serve` imports it lazily, so a run never loads FastAPI. Route modules skip
`from __future__ import annotations` and use `Optional` (Python 3.9 evaluates them).
`CourtBookerError`s become `Problem` JSON with an `error` code (409 `lock_held`, 400
`bad_request`, 503 `device`/`app_not_ready`/`notification`/`schedule`, 500 `engine`); invalid
values 422 `invalid_request`.

| Route | Does |
|---|---|
| `GET /api/health` | Version; no device access |
| `GET /api/status` | The Overview in one call: running run (with `runs`: the lock holder's run, then those of the instances it started), schedule, last run, `wake_blocked` (the schedule on but wake timers off: `powercfg`, asked only with no run going on); never calls MuMu |
| `GET /api/runs`, `/api/runs/{id}`, `/api/runs/months` | Runs newest first (filters, paging by id or by days) with whose account each booked with, one run with steps and log lines, months of real bookings |
| `GET /api/events` | Activity steps newest first |
| `GET`/`PUT /api/settings` | Booking settings without the hidden keys (`HIDDEN`: Telegram, the notification), with each `[[instances]]` entry in full; `PUT` validates, refuses added or removed instances, saves only on a change |
| `GET /api/mumu-instances` | The MuMu instances MuMuManager knows, lowest first (`emulator.instance_indexes`); empty when it is not found or fails |
| `PUT /api/instances/{mumu_index}` | A machine beside the first on or off: adds its `[[instances]]` table (taking every setting from the top) or removes it; no `enabled` key, which an older runner would refuse |
| `GET`/`PUT /api/notifications`, `POST .../test` | The Windows notification's switch and language; a sample notification |
| `GET /api/setup` | Device checks; nothing is changed (auto setup is the command line's) |
| `GET`/`PUT /api/schedule` | The task: state, times, whether a dry run ever passed; switching on needs none and allows wake timers. Never switch it on from a development backend: the task would run the development Python |
| `POST /api/runs/dry-run` | Starts a dry run in its own process (refused in the quiet time or while a run holds the lock) |
| `GET /api/tickets`, `/api/tickets/{code}/photo` | Every machine's tickets as the runs last read them (`history_read.list_tickets`), with whose account each is of and the machine that can cancel it now (`machine`: the one its account is attached to, the one that read it when no chosen account did, empty when its account is on no machine), and a ticket's picture from the data folder's `tickets`, by its code alone |
| `GET`, `PUT /api/money/prices`; `GET /api/money/charges?month=`; `PUT /api/money/charges/{code}`, `/api/money/paid`, `/api/money/customers/{id}/free` | The price list; the charges of a month of play, priced, with the months that have charges and the customers booked for free; a charge marked paid or its amount set by hand (`reset_amount` takes the price list's again); several marked paid at once; a customer booked for free or not (`court_booker.money`) |
| `GET`, `POST /api/requests`, `PUT`, `DELETE /api/requests/{id}` | Each customer's requests (`court_booker.requests`): 404 for an unknown customer or request, 422 for no slot, more than two, or a day out of 0-6 |
| `PUT /api/tickets/{code}/sent` | Mark the ticket sent to its customer now (`sent_at`, schema 7), or not; a later run reading it again keeps the mark |
| `POST /api/tickets/{code}/cancel`, `GET /api/tickets/cancel` | Start `court-booker cancel` for the ticket on its `machine` (refused for a ticket cancelled already, 409 `ticket_cancelled`, or on no machine, 409 `no_machine`), and how the one started last goes (`running`, its `exit_code`) |
| `POST /api/machines/{mumu_index}/open` | Launch the machine's MuMu, or show its window if it runs (`MuMu.show_window`); refused as a task is (no process of its own), 503 `device` without MuMuManager |
| `POST /api/machines/{mumu_index}/quota`, `GET /api/machines/quota` | Start `court-booker quota` on the machine (refused for one without a chosen account, 409 `no_machine`), and how the one started last goes. Both are tasks (`api/tasks.py`): each in its own process like the dry run, one at a time, refused in the quiet time and while a run, a dry run or another task goes on (409 `lock_held`); `/api/status` shows one running (its kind as the trigger), and no dry run starts meanwhile |
| `GET`, `POST /api/customers`, `PUT`, `DELETE /api/customers/{id}` | The customers with their accounts (phone numbers whole, never a password; logs and events still mask them), each with the last quota read of every utility and month from this one on (`quota`, from the `quota_read` events of the runs that knew the account, `history_read.quota_readings`; the app shows the month of the next booking); one with an attached account is not removed (409 `account_attached`) unless `detach` is asked for |
| `POST /api/customers/{id}/accounts`, `PUT`, `DELETE /api/customer-accounts/{id}` | A customer's accounts; one phone number, one account (409 `phone_taken`); a new phone number or password is its machine's too, refused while a run goes on (409 `lock_held`) |
| `GET /api/customer-accounts/{id}/login` | The saved phone number and password, whole, for the account's form; `no-store`, and only this PC reaches it (`local_only.py`). The only route that answers a password |
| `PUT`, `DELETE /api/machines/{mumu_index}/account` | Attach an account to a machine (it moves from another one), or none; refused while a run goes on (409 `lock_held`) |
| `GET /api/accounts` | The subdivision each MuMu instance's account told last (`history_read.account_subdivisions`); one the catalog no longer lists is left out |
| `WS /api/live` | Pushes each new step |

After a route, model or catalog change: `python tools/export_openapi.py` (writes
`ui/openapi.json` and `ui/src/catalog.json`), then `npm run api:types`
(`tests/api/test_api_schema.py`, `tests/test_catalog.py` and CI fail until they match).

## UI (`ui/`)

- Vite, React 19, strict TypeScript, ESLint (type-aware), Prettier, Vitest + Testing Library
  (jsdom). Version holds that need Node 22.22 (jsdom 30, React Router 8) are skipped by Dependabot.
- `src/paths.ts` names the three pages and the old addresses that lead to them, keeping
  `?run=`; `routes.tsx` maps them to `pages/`. `i18n/` (Vietnamese
  default, English; same keys, checked by a test). `styles/` holds the tokens (contrast checked
  by `tokens.test.ts`); components use CSS Modules on them. Every icon is one of Lucide's,
  named in `components/Icon.tsx`; a button of an icon alone is an `IconButton`, whose label is its
  tooltip too.
- `src/api/`: types generated from `openapi.json` (`schema.d.ts`), a typed client, React Query
  hooks (`queries.ts`, `mutations.ts`) and the live feed (`live.ts`, one WebSocket, reconnects
  with `?after=`). Data is refreshed only at run boundaries (`staleKeysFor`): a run's own steps
  send no request, so the UI never slows a booking.
- `steps.ts` words each event kind (a new kind fails the type check); `reasons.ts` turns the
  engine's English reasons into a few words (`notify.REASONS` holds the same words; a test
  compares them).
- Three pages, a press apart in the middle of the header: the booking, the guide
  (`pages/GuidePage.tsx`: three steps to start, the user's ticks for each machine, the mornings and
  the problems; the header counts the ticks left) and the management
  (`pages/ManagementPage.tsx`, parts in `pages/management/`), whose sections each have an
  address: `OverviewTab` (the index: this month's figures, the machines in a table, the tickets of
  the next days and the alerts of `board.ts`), `QuotaTab` (`CustomerList` with its search, a customer marked
  when an account has one booking or none left of a sport; beside it the one in the address,
  `?customer=`, else the first found: a row an account, a column a sport it was read for, what
  was booked of the limit, "Full" at it, from the readings of the month chosen; the overview's
  alert of a machine short of quota opens its customer there), `MoneyTab` (the month's sums, a card per customer
  from `money.ts`, the price list), `StatsTab` (the scheduled runs of the last 30 days summed by
  `stats.ts`: by machine, by slot, the reasons of the slots lost), `RequestsTab` (a card per
  customer with their requests, the form, and "apply to the machine": `requests.ts` sets the
  machine's court, slots and days in the settings, switching it on first), the first two from
  `machineFacts.ts` (the settings, the customers and the newest scheduled run of each MuMu
  instance, `useRuns` limited to 60) and styled by `Board.module.css`; `CustomersTab` (`CustomerList` with its search, `customerSearch.ts`: by name and facts without
  Vietnamese marks, an account by its name or, for digits, its phone number; and `CustomerDetail`
  beside it, the one in the address, `?customer=`, else the first found: who they are and their
  accounts, each phone number whole with a copy button, those found marked; one form is open at a time, under what it changes,
  an account's filled with its saved login, read then and kept nowhere else, a removal is beside each edit and
  asks first over the page (`RemoveQuestion`), naming the accounts lost and the machines left without
  one), `TicketsTab` (the tickets still to use by day of play, of one customer or
  all, no cancelled ones, each day with how many are not sent; a card a ticket, the stamp only for
  a status other than registered, the account (and the customer while several show) under the
  slot, and its sent button beside it (`useMarkSent`); those whose holder is not known name the machine, picked in `tickets.ts` without a request; a press opens
  `TicketDialog` with the picture, which a plain download link saves under `photoFileName`; read
  again after `tickets_saved`. A ticket whose slot is still to come has a cancel button there:
  a question over the picture first (`TicketCancel`; for a ticket on no machine, why it cannot),
  then how it goes, read every 2 s (`cancelling.ts`), and how it ended; the customers' quotas are
  read again once it is over, the tickets once its words are put away, as a cancelled ticket
  leaves the list) and `HistoryTab` (runs ten days at a time, real bookings unless
  dry runs are ticked; `?run=` shows one run's slots, steps and log beside the list). What a
  section lists is kept while another shows (`state.ts`).
- The booking page (`pages/HomePage.tsx`, parts in `pages/home/`): the ticket (`BookingTicket`:
  on top what is set: the play day and court side by side, the slots
  on a row of their own (fixed rows, whatever the court's name), and a line only while the
  switch is off, for the machine chosen on its tabs on top (`MachineBar`, "Máy 1", "Máy 2",
  "Máy 3": one per MuMu instance, by its index, always three at least: those the
  `[[instances]]` lack are the lowest MuMu instances free (MuMu 1, MuMu 2), switched off and
  pale, so each keeps its name whichever of the others is on; a red mark on a machine that
  books with setup of its own left),
  following each press as its save goes out; under the perforation, while that machine books,
  its subdivision, sport, court and up to two slots, saved on each press;
  or `LiveTicket` while a booking or a dry run goes on: one ticket per run of `running.runs`,
  named "MuMu N" when several instances book side by side) and `SetupPanel` beside it:
  `SetupSwitches.tsx` (the daily booking, the result notification and, for a machine beside the
  first, its own, `PUT /api/instances/{mumu_index}`; the first and the last locked while a run
  goes on), the account of the machine chosen on the ticket, which `HomePage` holds, and the dry run
  (`DryRun`). `AccountPicker` shows the account in use under its title and, once pressed, the
  customers who have accounts; a customer pressed, their accounts (back to the customers above
  them, each opening starts from the customers); a press saves one, and one that another machine
  books with moves only after a question.
  On the machines' cards, `components/QuotaLine.tsx` shows what is left
  of each utility's quota in the month the next booking is for (`quota.ts`, from the schedule's
  `next_play_date`), as the last run read it ("Tennis còn 1/8", the sport in the interface's language, the app's words for a read without it), none left marked, when it was
  read in the tooltip. The header's status line (`components/StatusLine.tsx`)
  shows the run going on, else the one thing to do; `readiness.ts` finds the machines that book
  without an account (while a customer has one to choose), the courts and slots that two would
  book, and the machines whose account has fewer left in that month for their sport than their
  slots (`shortOfQuota`), which only their tabs and the account picker show (set off as for
  no account), not the status line. `machines.ts` lists the machines from the
  settings and from the MuMu instances on the PC (`GET /api/mumu-instances`, read once): every
  instance shows, three at least, those the settings lack switched off. `manualSteps.ts` keeps the user's ticks in `localStorage` (memory when storage
  fails): MuMu's once, the app's and the login's for each machine; `setupState.ts` counts the
  setup tasks left over the machines that book. `booking.ts` holds the slots and the two-slot limit, and reads
  the subdivisions, sports and courts from `catalog.json`, written from `catalog.py`.
  `useFormat`'s `courtLabel` tells a court from the others of its sport ("BE7 · tập ném 01",
  in English "BE7 · shooting 01": the app keeps court names in Vietnamese in both languages,
  so the kind's words are in `courtKinds` of the language files) and `court` adds the sport
  ("Tennis S6"). The ticket's subdivision is the one the settings
  name, else the one the account told last (`GET /api/accounts`, refreshed when a run ends,
  "Theo tài khoản"), else Origami; pressing one saves it, keeps the sport if the subdivision
  has it (else its first sport) and takes the first court. The UI never calls `GET /api/setup` or
  `POST /api/notifications/test` (the routes stay for the command line and tools).

## Driver (`android/`)

An instrumentation APK (`dev.courtbooker.driver`), started with `am instrument`. It uses
UiAutomation, like uiautomator2, so only one of them runs at a time; it is not an
accessibility service, which the app refuses (field notes). `tools/build_driver.py` builds it
with the SDK tools into `src/court_booker/assets/court-driver.apk` (committed; a test fails
when the sources change without a rebuild). `driver.py` installs it when its SHA-256 differs,
forwards a port and talks to it; no answer within 10 s per command is
`DeviceNotRespondingError`.

Protocol 2, one JSON object per line each way (`op`, arguments, optional `id`; the reply has
`ok`, `error`):

| `op` | Does |
|---|---|
| `hello` | `protocol`, `version`, `sdk` |
| `dump` | The window as uiautomator2's XML (visible nodes, bounds clipped), with `editable` and `password` on each node |
| `click` `label x y` | Clicks the node labelled `label` nearest (x, y) where it is now (`ACTION_CLICK`, else a touch at its middle); `clicked` false when gone |
| `click_at` `x y` | The same for the smallest clickable node at (x, y): unlabelled elements |
| `set_text` `x y text` | Sets the text of the smallest editable node at (x, y) (`ACTION_SET_TEXT`); `set` false without one. The text, maybe a password, is never logged |
| `back`, `swipe x1 y1 x2 y2 ms` | Injected key or touch |
| `current` | Package of the active window |
| `stop` | Ends the driver |

## Tests

- External effects are injectable; nothing in the suite touches a device, adb, the network,
  Task Scheduler, MuMu, PowerShell or the Windows vault. `tests/conftest.py` points
  `COURT_BOOKER_HOME` at a temporary folder and keeps the logins in memory.
- `tests/test_flow.py`: `FakeApp`, a scripted app (screens as node lists, taps and Back switch
  screens), with a fake clock; `in_english` turns it English. A full round costs 16 commands.
- Backend tests are in `tests/api/` (skipped without FastAPI); UI tests sit beside the code.
