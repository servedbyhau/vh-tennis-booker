# Progress

The current state of the project. Overwrite entries when the state changes; history belongs
in `CHANGELOG.md` and git. The next task is in [next.md](next.md), open bugs in
[known-issues.md](known-issues.md).

Last updated: 2026-11-03.

## Release and daily run

- Released: **1.0.0** (tag `v1.0.0`, 2026-11-03), the first complete version: the installer on
  its release page, the update button, and the uninstaller removing the daily task. 0.19.0 has
  no update button, so 1.0.0 is installed by hand over it; later versions update by the button.
- The Android app is developed in `servedbyhau/v-court`, which ports this repo's booking
  flow and driver; this repo is its behavior reference.
- Daily task `\court-booker`: runs the installed app,
  `%LOCALAPPDATA%\Court Booker\court-booker\court-booker.exe`, with the data folder's
  `config.toml`; logs and history are in `%LOCALAPPDATA%\CourtBooker`. It wakes the PC at
  05:45 and books at 06:00. The app's "Tự đặt" switch sets it.
- Runner folder: at `v0.18.1`, kept as a way back until 2026-11-10, then removed. To go back:
  `D:\VH-Booker\runner\.venv\Scripts\python.exe -m court_booker schedule install --config
  %LOCALAPPDATA%\CourtBooker\config.toml`.
- On 2026-11-03 MuMu instance 0 read a BS account, with the app in English.

## Last 06:00 runs

| Date | Version | Result |
|---|---|---|
| 2026-11-03 | 0.18.1, installed app | 2/2 (5.6 s, 3.9 s): the first run from the installed app, without Python |
| 2026-11-02 | 0.18.1 | 2/2 (6.6 s, 3.9 s) |
| 2026-11-01 | 0.18.1 | Both instances 2/2: Origami (4.5 s, 3.6 s), BS (4.8 s, 3.5 s); real BS and parallel bookings confirmed |
| 2026-10-31 | 0.18.1 | 2/2 (5.9 s, 3.8 s); both rounds switched to November and selected 2026-11-02 within 0.4 s |
| 2026-10-30 | 0.18.0 | 0/2 at 06:00: the day tap landed during the month slide; after the fix, a real run that day booked 2/2 for 2026-11-01 |
| 2026-10-29 | 0.17.0 | 2/2 (7.0 s, 3.6 s) |
| 2026-10-28 | 0.15.0 | 2/2 (7.1 s, 5.2 s) |

## Decisions in force

These are not written elsewhere (CLAUDE.md, the roadmap or the specs):

- UI: for end users, ready-made choices only; one screen without menus; light theme, desktop
  width and Vietnamese by default. It sends no request per step while a run is going, and does
  not check MuMu while the run lock is held.
- The installed app is the daily run; a release reaches it through the installer built from
  `main`: the app's update button, or the installer from the release page.
- The app is one PyInstaller folder inside a per-user NSIS installer, and the backend serves the
  built UI. The installer is built by the `Desktop` workflow, as this PC has no Rust.
- Choosing days of the week: later, not decided.
- From 1.0.0 each version has a GitHub release page with its installer; the pages of
  0.1.0 to 0.9.0 were deleted on 2026-11-03, their tags kept. Releases go ahead without
  asking again.
- Accounts, quotas, re-logins and adding instances to `config.toml` are the user's job.
- Test tickets booked during development are cancelled by the user.

## Test environment notes

- The UI suite run fully parallel on the dev machine has two tests time out; with
  `--maxWorkers=2` all pass.
- One process at a time against MuMu: when it freezes, shut MuMu down fully and run again.
- An installer test in a scratch folder leaves `HKCU\Software\servedbyhau\Court Booker`
  behind after uninstalling, and the next install defaults to that folder: delete the key
  after such a test.
