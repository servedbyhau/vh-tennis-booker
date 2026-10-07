# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Last updated: 2026-10-07.

## Commands

The Python `Scripts` folder is not on PATH on the dev machine, so prefix tools with `python -m`.

```bash
python -m pip install -e ".[dev]"                    # install package + pytest, ruff, pre-commit
python -m pytest                                     # all tests (no emulator needed)
python -m pytest tests/test_flow.py -k slot          # single file / single test
python -m ruff check . && python -m ruff format .    # CI runs `ruff format --check .`
python -m court_booker --dry-run --verbose           # real run against the emulator
python tools/inspect_screen.py --near "Tôi đã hiểu"  # dump nodes level with a label
```

Run `--dry-run` against the emulator whenever the booking flow changes; CI cannot.

## Goal

A learning project to build a realistic, CV-worthy product: Python code on Windows that drives the
**Vinhomes Resident** Android app (Flutter) inside the **MuMu Player** emulator to book a
tennis court. Personal use only; not published commercially.

**Known limitation (accepted):** the Vinhomes app refuses to work while Android developer
mode is on, which ADB requires. The automation therefore runs up to the final confirmation
step (`--dry-run` works end to end). Bypassing that check is out of scope and will not be done.
On-device automation (an Android app using AccessibilityService) is also out of scope for the
same reason.

## Current state: v0.1.0 (released on GitHub)

- Repo: `github.com/servedbyhau/vh-tennis-booker` (private), local path `D:\VH-Booker\vh-tennis-booker`
- Python package `court_booker` (src layout), CLI `court-booker` / `python -m court_booker`
- `tools/inspect_screen.py`: dumps the UI hierarchy and lists nodes level with a text
- 11 pytest tests with a fake device; CI on GitHub Actions: `lint` (ruff check + format)
  and `test` (Python 3.9, 3.11, 3.12, 3.13); all green
- Tooling: pre-commit (ruff, basic hooks), `.editorconfig`, `.gitattributes` (LF),
  Dependabot, PR and issue templates, `CONTRIBUTING.md`, `CHANGELOG.md` (Keep a Changelog)
- `CHANGELOG.md` has an "Unreleased" section (English translation, tooling, label `full`
  renamed to `fully_booked`); next release should be 0.2.0

## Code architecture

- `cli.py` parses args, applies overrides onto `Config`, connects with `uiautomator2.connect`
  (imported lazily so tests don't need it), then calls `Booker.book()` once per slot. Each slot
  is one round; a `BookingError` (or any exception) fails that round only and later rounds run.
- `flow.Booker` holds selectors as plain dicts (`Selector = dict[str, Any]`) built from
  `config.labels` in `__init__`, passed as `device(**selector)`. Every screen transition goes
  through `tap_and_advance(target, name, next_screen)`: wait for target, tap, poll
  (`wait_for_any`) for any of the next screen's selectors, retry the tap if the app lagged.
  `return_to_utilities()` presses Back until the utilities list or home appears, so a round can
  start from any screen.
- `geometry.py` is pure (bounds parsing, day/slot regexes, checkbox-beside check) and is where
  logic that can be unit-tested without a device belongs.
- `config.load_config` rejects unknown keys (`ConfigError`); the TOML key `continue` maps to
  `Labels.continue_`; keys ending in `_xy` become tuples. New config fields must be added to
  the dataclass and `config.example.toml`.
- Tests use hand-written fake devices (`tests/test_flow.py`: `FakeDevice`/`FakeElement`
  mimicking the uiautomator2 selector API) and monkeypatch `flow.time.sleep` to run instantly.
  `tests/conftest.py` puts `src/` on `sys.path`.

## Booking flow (app screens)

Home ("Tiện ích") → Utilities list ("Sân Tennis") → Calendar (pick date, then a slot appears;
pick slot; "Tiếp tục") → optional venue screen ("Origami…") → Court list ("S10 - Sân tennis")
→ Booking details ("Tiếp tục") → Confirmation ("Xác nhận đăng ký": tick consent checkbox,
"Xác nhận") → Ticket screen. One Back from the ticket returns to the Utilities list, where
the next round starts.

## Technical findings

- Flutter exposes text via `content-desc`, not `text`; select with `description=...`.
- Emulator screen is **540x960** (not 900x1600). Never use hard-coded coordinates.
- Day label format: `"2, Thứ Sáu, 2 tháng 10, 2026"`. Slot: `"09:00 - 10:00"`;
  full slot: `"18:00 - 19:00\nHết chỗ"`. Bookable range: today to today + 2.
- Consent checkbox has no label and `checkable=false`: it is the clickable View
  `[35,740][79,784]` left of caption `"Tôi đã hiểu và đồng ý với "` `[79,739][313,772]`.
  Located via `caption.left(clickable=True)` plus a same-row check; fallback hierarchy scan.
- "Xác nhận" is disabled until the checkbox is ticked; used to verify the tick.
- Flutter builds lazily: off-screen slots are absent from the tree, so the code scrolls until
  the slot is fully visible and not covered by the sticky "Tiếp tục" button.
- Success is verified by waiting for the confirmation screen to disappear.

## Environment

- Windows 11, Python 3.14, Git; Python `Scripts` folder not on PATH (use `python -m ...`)
- MuMu Player, ADB at `127.0.0.1:7555`, ADB from Google `platform-tools` (user must
  currently run `adb connect` manually)

## Product goal and decisions (2026-10-07)

The only goal is to win the booking race: the app opens bookings at **06:00 every day** and the
user must not need to be awake. Priority is unattended, scheduled, fastest-possible booking.

- Target date is always today + `days_ahead` (default 2); no specific `--date`.
- No stop button / cancellation token; Ctrl+C prints the summary instead.
- UI, backend and desktop packaging are **deferred** until unattended booking works.
- Each run waits on the utilities list ("Sân Tennis", screen 2) before the start time, so only
  the booking taps happen after 06:00.
- Open blocker: confirm whether "Xác nhận" can submit with developer mode on (see `SPEC.md`).

**ADB strategy:** reuse a running ADB server if present → user-configured adb path →
adb on PATH; then auto-detect emulator ports (MuMu 7555 and 16384+, LDPlayer/BlueStacks 5555+,
Nox 62001). MuMu is started with `C:/Program Files/Netease/MuMuPlayer/nx_main/MuMuManager.exe`
(`info -v 0` reports `is_android_started`).

## Roadmap

| Version | Scope |
|---|---|
| 0.2.0 Unattended | Start MuMu; ADB auto-connect; prepare app on screen 2; `--at` timed start with NTP offset; opening retry; keep awake; log file; Telegram summary; Task Scheduler install with wake; tests |
| 0.3.0 Hardening | Based on real 06:00 runs: timing measurements, faster taps, failure handling, health check before the start time |

Deferred (previous plan, revisit after 0.3.0): FastAPI backend with WebSocket progress, React +
TypeScript UI, Tauri desktop shell with PyInstaller sidecar, installer and release automation.

## Working conventions

- All code, comments, logs, commits and docs in English; app labels stay Vietnamese in config.
- Professional style: type hints, short imperative docstrings, comments explain why,
  module loggers, `BookingError` subclasses, named constants, Ruff line length 100.
- From 0.2.0: one branch per feature (`feat/...`, `fix/...`), Pull Request, green CI, merge,
  update CHANGELOG; Conventional Commits; Semantic Versioning; protect `main`.
- Never commit `config.toml`, screenshots or UI dumps (may contain personal data).

## Next step

Resolve the developer-mode blocker, enable branch protection on `main`, then implement 0.2.0
one feature branch at a time. The detailed design (errors, `emulator.py`, `adb.py`, `clock.py`,
`power.py`, `runner.py`, `notify.py`, `schedule.py`, config keys, exit codes) is in `SPEC.md`;
follow it.
