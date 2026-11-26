# Running from source

The app's installer is all a resident needs ([README](../README.md#install)). This page is for
developers: running the booking engine, the backend and the UI from a clone, and every
command, setting and exit code. The checks, branches and releases are in
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Requirements

- Windows (used on Windows 11) with [MuMu Player](https://www.mumuplayer.com/); ADB ships
  with MuMu
- The Vinhomes Resident app installed in MuMu and logged in
- Python 3.9 or later
- Node.js 22.12 or later, only for the UI

## Install

```bash
git clone https://github.com/servedbyhau/vh-tennis-booker.git
cd vh-tennis-booker
pip install -e ".[app]"            # "app" adds the backend of the UI
cp config.example.toml config.toml
```

If `court-booker` is not found afterwards (Python's `Scripts` folder is not on `PATH`), use
`python -m court_booker` instead.

## Configure

Edit `config.toml`, or use the UI. The keys you usually change:

| Key | Example | Meaning |
|---|---|---|
| `slots` | `["18:00 - 19:00", "19:00 - 20:00"]` | Slots to book, one round each, in this order: put the most wanted first |
| `days` | `[]` | The days of the week the day of play may fall on for the daily task to book with this machine, 0 Monday to 6 Sunday; empty books every day. Each `[[instances]]` table has its own (every day unless given). A machine off that day neither boots nor books, and the machines after it do not wait for it; the first machine still starts the others. Runs started by hand book whatever the day |
| `sport` | `"tennis"` | What to book: `tennis`, `multi`, `volleyball`, `table-tennis`, `basketball`, `football`, `pickleball` or `badminton` |
| `court` | `"S10 - Sân tennis"` | The court, as the app names it (S6, S8, S9 or S10 for tennis at Origami; BE7 or BCX3/CX2 01-02 at BS) |
| `subdivision` | `""` | The account's subdivision, `origami` or `bs`; empty follows the account. The run books by `court` either way |
| `start_at` | `"06:00"` | When the app opens bookings |
| `wake_at` | `"05:45"` | When the daily task wakes the PC and starts preparing |

Everything else (the app's labels, timeouts, the MuMu folder) has a working default,
explained in `config.example.toml`.

To book with more accounts at once, clone the MuMu instance in MuMu's multi-instance manager,
log the clone in to another account, and add an `[[instances]]` table for it (example in
`config.example.toml`): its `mumu_index`, and any of `slots`, `subdivision`, `sport`, `court` and
`venue_keyword` that differ. The UI shows a tab for each machine on top of the ticket, with its
own settings and, in the Setup beside it, its account; each MuMu instance on the PC is there (three at least), and each
one's switch in the Setup adds or removes its `[[instances]]` table.

## Set up the PC and the emulator

```bash
court-booker setup                         # check MuMu, its screen, wake timers and the app
court-booker setup --auto                  # fix by hand what the runs and schedule fix
court-booker setup --auto --restart-mumu   # also restart a running MuMu to apply its screen
```

Nothing here is needed before a run: each run finds MuMu when `mumu_manager` points
elsewhere (without rewriting `config.toml`) and sets the screen of a stopped MuMu to
540x1600 at 220 DPI before starting it (the whole slot list then fits without scrolling), with
2 cores and 2 GB, no more and no less (a running MuMu with another screen or other ones is only
logged). Switching the schedule on allows wake
timers on mains and battery. `setup --auto` also saves the MuMu folder to `config.toml`.

## Try a dry run

```bash
court-booker --dry-run --at 14:05     # a time a few minutes from now
```

A dry run walks the whole flow and stops before "Xác nhận", so nothing is booked. Close MuMu
first to test the whole chain, as at 06:00. The Vinhomes app takes bookings from 06:00 to
21:00; outside those hours a run ends with "not open". Exit code 4 usually means the app is
logged out.

## Book every morning

```bash
court-booker schedule install   # daily task at wake_at; it books for real at start_at
court-booker schedule status    # the task, its last and next run
```

The ticket's "Auto-book" switch does the same, once a dry run has passed.
`court-booker schedule remove` deletes the task. The task runs the engine of whatever
installed it: on a PC that books with the installed app, do not install it from a clone. A
real run closes MuMu once its rounds are done; the next run starts it again. A dry run leaves
it open.

## The UI in development

```bash
court-booker serve --config config.toml   # backend on http://127.0.0.1:8765, API docs at /api/docs
cd ui && npm ci && npm run dev            # then open http://localhost:5173
```

`--config config.toml` makes the UI read and save the same file as the command line. The
backend listens on 127.0.0.1 only. From a clone it serves `/api` alone and Vite serves the UI;
the installed app's backend serves both. Saving settings rewrites `config.toml` (its comments
are dropped); the next run reads it.

## Commands

| Command | What it does |
|---|---|
| `court-booker` | Book the slots in `config.toml` now |
| `court-booker --dry-run` | Walk the whole flow and stop before "Xác nhận" |
| `court-booker --at 06:00` | Prepare now, start booking at 06:00:00 |
| `court-booker --scheduled` | The same at `start_at` (what the daily task runs) |
| `court-booker --slots "18:00 - 19:00"` | Other slots, for this run only |
| `court-booker --verbose` | Also print every screen read and every tap |
| `court-booker --driver instrumentation` / `--driver uiautomator2` | Use only that driver; the default `auto` tries instrumentation, then falls back to uiautomator2 |
| `court-booker setup [--auto]` | Check the PC and the emulator, or fix them |
| `court-booker new-machine` | Make another MuMu instance, a copy of the first machine's with its app, set up to book (540x1600 at 220 DPI, 2 cores, 2 GB, Vulkan); refused without the RAM (2 GB an instance besides 4 GB for Windows) or the disk for it; exit 0 once made, 1 if not, 2 refused, 3 MuMu failed, 5 if a run goes on |
| `court-booker quota [--instance N]` | Read what is left of the quota of MuMu instance N's account in its app, for each sport it plays in the month of today + 2; exit 0 once read, 1 if not, 2 around the scheduled run, 5 if a run uses the machine |
| `court-booker cancel <code> [--instance N]` | Cancel ticket `<code>` (its "Mã đặt") in the app of MuMu instance N (default: the config's first), then read that sport's quota again; exit 0 once the app shows it cancelled, 1 if not, 2 around the scheduled run, 5 if a run uses the machine |
| `court-booker schedule install` / `status` / `remove` | The daily task |
| `court-booker serve --config config.toml` | The backend of the UI |

Every command takes `--config` (default: `config.toml` in the current folder; for `serve`,
the one in the data folder).

| Exit code | Meaning |
|---|---|
| 0 | every round succeeded |
| 1 | a round failed |
| 2 | bad arguments or config, the start time has passed, or a dry run around the scheduled run |
| 3 | emulator or ADB error, or the emulator stopped answering (frozen) |
| 4 | the app did not reach its home screen (for example, logged out) |
| 5 | another run holds the run lock |
| 130 | interrupted with Ctrl+C |

- **Logs**: each run appends to `logs/court-booker-YYYY-MM-DD.log` beside its `config.toml`,
  with every screen it read and every tap; each other MuMu instance to its own
  `…-mumuN.log`.
- **Data folder**: the history database `booker.db`, the ticket pictures (`tickets`, personal
  data), the power values the PC had before the Setup kept it on (`power-plan.json`) and the run
  lock `run.lock` (and
  `run-mumuN.lock` for each other instance) are in `%LOCALAPPDATA%\CourtBooker`, where the
  installed app also keeps its `config.toml` and `logs`; set `COURT_BOOKER_HOME` to move them.
- **One run at a time**: a second run is refused (exit code 5), and the scheduled run waits
  for a run already going, then stops it two minutes before the start time. No dry run or
  auto setup starts from `wake_at` to five minutes after `start_at`.
