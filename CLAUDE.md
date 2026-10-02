# CLAUDE.md

Context for AI assistants working on vh-tennis-booker. Last updated: 2026-10-02.

## Goal

A learning project to build a realistic, CV-worthy product: a Windows desktop app where a user
picks a court, a date and time slots in a UI, and Python code underneath drives the
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
- Modules: `cli.py`, `config.py` (dataclasses + `config.toml`), `errors.py` (`BookingError`
  hierarchy), `flow.py` (`Booker`, one method per screen), `geometry.py` (pure helpers),
  `logging_setup.py` (logging with per-step elapsed time)
- `tools/inspect_screen.py`: dumps the UI hierarchy and lists nodes level with a text
- 11 pytest tests with a fake device; CI on GitHub Actions: `lint` (ruff check + format)
  and `test` (Python 3.9, 3.11, 3.12, 3.13); all green
- Tooling: pre-commit (ruff, basic hooks), `.editorconfig`, `.gitattributes` (LF),
  Dependabot, PR and issue templates, `CONTRIBUTING.md`, `CHANGELOG.md` (Keep a Changelog)
- `CHANGELOG.md` has an "Unreleased" section (English translation, tooling, label `full`
  renamed to `fully_booked`); next release should be 0.2.0

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

## Decided architecture (target)

| Layer | Technology |
|---|---|
| UI | React (web, not React Native) + TypeScript, built with Vite |
| Desktop shell | Tauri (WebView2), backend launched as a sidecar |
| Backend | Python FastAPI + Pydantic, WebSocket for live progress, localhost only |
| Core | Existing `court_booker` + uiautomator2 |

Monorepo target layout: `backend/`, `frontend/`, `src-tauri/`, `docs/`, `.github/`.

**ADB strategy:** reuse a running ADB server if present → user-configured adb path →
adb on PATH (0.2.0) / bundled Google adb (0.5.0); then auto-detect emulator ports
(MuMu 7555 and 16384+, LDPlayer/BlueStacks 5555+, Nox 62001).

## Roadmap

| Version | Scope |
|---|---|
| 0.2.0 Core | Specific `--date`; structured progress events; cancellation; ADB discovery and auto-connect; tests |
| 0.3.0 Backend | Move Python to `backend/`; FastAPI endpoints (`/device`, `/device/connect`, `/options`, `/runs`, `/runs/{id}/stop`, `WS /runs/{id}/events`); single active run; log to file; API tests |
| 0.4.0 Web UI | React + TS: device status, court select, date picker limited to bookable dates, slot checkboxes, dry-run toggle, start/stop, live step progress, remembered choices, settings; Vitest; CI for both |
| 0.5.0 Desktop | PyInstaller `backend.exe`; Tauri sidecar on a random port; first-run system check (MuMu, ADB, emulator, Vinhomes app); auto-update; installer |
| 0.6.0 Release | CI builds installer on tag and attaches to Release; version sync; README demo GIF, architecture diagram, system requirements, troubleshooting (SmartScreen, antivirus) |

## Working conventions

- All code, comments, logs, commits and docs in English; app labels stay Vietnamese in config.
- Professional style: type hints, short imperative docstrings, comments explain why,
  module loggers, `BookingError` subclasses, named constants, Ruff line length 100.
- From 0.2.0: one branch per feature (`feat/...`, `fix/...`), Pull Request, green CI, merge,
  update CHANGELOG; Conventional Commits; Semantic Versioning; protect `main`.
- Never commit `config.toml`, screenshots or UI dumps (may contain personal data).

## Next step

Start 0.2.0: enable branch protection on `main`, create the first feature branch,
then implement the core upgrades.
