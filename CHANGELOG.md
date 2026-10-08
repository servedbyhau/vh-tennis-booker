# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/) and the project
uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- A `commit-msg` hook rejects commit messages with an AI co-author trailer.

## [0.2.0] - 2026-10-08

### Changed
- Project text, logs and errors are now in English.
- Logging uses the standard `logging` module; added `--verbose`.
- Errors are raised as `BookingError` subclasses.
- Config label `full` renamed to `fully_booked`.
- Default `device` is now `"auto"`.
- The summary is logged instead of printed, so it also reaches the log file.

### Added
- Unattended booking: `court-booker schedule install` registers a daily Windows scheduled
  task (default 05:45) that wakes the PC and runs `court-booker --scheduled`.
- Emulator start: MuMu is launched through `MuMuManager.exe` when Android is not running.
- ADB auto-connect: adb is found on `adb_path`, `PATH` or in the MuMu folder, a running server
  is reused, and the emulator's own serial is connected; no manual `adb connect`.
- App preparation: the app is restarted (`restart_app`) and the run waits on the utilities
  list; a logged-out app fails early with exit code 4.
- Timed start: `--at HH:MM[:SS]` and `--scheduled` (`start_at`, default 06:00) wait for the
  exact time, corrected against an NTP server, and keep Windows awake during the run.
- Opening retry: the calendar is reloaded for up to `open_retry_seconds` while the new date
  or slot is not listed yet.
- Daily log file in `logs/`; optional Telegram summary (`telegram_token`, `telegram_chat_id`).
- Exit codes: 1 round failed, 2 bad arguments or config, 3 emulator or ADB error, 4 app not
  ready, 130 interrupted (finished rounds are still summarized).
- Pre-commit hooks, EditorConfig, Dependabot, issue and pull request templates,
  contribution guide; CI runs lint and format checks separately from tests.

## [0.1.0] - 2026-10-02

First release.

### Added
- Label-based UI automation of the tennis-court booking flow: every button is located
  at runtime by its accessibility label, with no hard-coded coordinates.
- Consent checkbox located as the small clickable node beside and level with its caption.
- Lag-tolerant navigation: tap as soon as a button appears, retry if the next screen
  does not show.
- Scroll-into-view for time slots below the fold; a slot is tapped only when fully
  visible and not covered by the sticky bottom button.
- Multiple booking rounds; each round after the first starts from the utilities list.
- Success verified by leaving the confirmation screen.
- Step logger with millisecond timing.
- `config.toml` for all settings and UI labels; command-line overrides.
- `tools/inspect_screen.py` to dump and inspect the UI tree.
- Unit tests with a fake device and GitHub Actions CI.
