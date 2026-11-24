# Progress

The current state of the project. Overwrite entries when the state changes; history belongs
in `CHANGELOG.md` and git. The next task is in [next.md](next.md), open bugs in
[known-issues.md](known-issues.md).

Last updated: 2026-11-23.

## Release and daily run

- Released: **1.1.2** (tag `v1.1.2`, 2026-11-19): getting ready before 06:00 repairs itself
  (`ready.py`): MuMu, ADB, the driver and the app layer by layer until 05:58, a check every
  minute while waiting, a frozen MuMu restarted by ending its process. A real timed booking
  on `develop` booked 2/2 to the ticket before the release. 1.1.1 (2026-11-18): the installer
  stops the app's processes before an update, and a run that stops on an unexplained failure
  saves the screen. 1.1.0 (same day) logs in
  again with the saved login; its update by the button stopped halfway and was installed by
  hand. 1.0.1 closed the promotion popup; 1.0.0
  (2026-11-03) was the first complete version.
- The Android app is developed in `servedbyhau/v-court`, which ports this repo's booking
  flow and driver; this repo is its behavior reference.
- Daily task `\court-booker`: runs the installed app,
  `%LOCALAPPDATA%\Court Booker\court-booker\court-booker.exe`, with the data folder's
  `config.toml`; logs and history are in `%LOCALAPPDATA%\CourtBooker`. It wakes the PC at
  05:45 and books at 06:00. The app's "Tự đặt" switch sets it.
- Since 2026-11-22 the installed app on the dev PC is a local build of `develop`, to try it before
  a release; it is at #299 since 2026-11-23. The apps before are in
  `D:\VH-Booker\app-backup-2026-11-22` (before the tickets) and `...-tickets` (before the account
  check). #300 is merged and not installed.
- Runner folder: at `v0.18.1`, still there as a way back (it was to go after 2026-11-10). To go back:
  `D:\VH-Booker\runner\.venv\Scripts\python.exe -m court_booker schedule install --config
  %LOCALAPPDATA%\CourtBooker\config.toml`.
- On 2026-11-03 MuMu instance 0 read a BS account, with the app in English.
- Merged since 1.1.2, not released: the tickets (#265 to #269), the customers, their accounts and
  the account check (#270 to #272), the pages and their look (#273 to #285), what is ready, whose
  account a run and a ticket are of, the copied picture and the question before a removal (#286 to
  #290), the quota (#292 to #298), launching in turn and every MuMu instance's tab (#297, #299),
  the history held during the rounds (#300). No open branch but the docs.
- Tried on real machines: the ticket reading on three accounts, the account check and a forced change
  of account on one. Not yet: either after a real 06:00 booking, a change between two different
  accounts, a changed phone number, whose account a run is of.
- Since 2026-11-23 pull requests are opened with `gh`, described and seen through CI; the user only
  merges them.

## Last 06:00 runs

| Date | Version | Result |
|---|---|---|
| 2026-11-24 | local `develop` build | Five machines, 2 cores and 2 GB each, launched in turn (all ready at 05:47:35), 5/10: instance 0 0/2, 1 1/2 (8.7 s), 2 1/2 (6.7 s), 4 2/2 (5.4 s, 4.8 s), 5 1/2. The two whose day tap came last (06:00:01.07, 01.22) got the 60 s notice; three got the "not open yet" notice (the PC clock 0.15 s behind NTP); each lost 0.2-0.8 s waiting for another's history write, and instances 4 and 5 turned history off (fixed in #300) |
| 2026-11-23 | local `develop` build | Three machines, 3/6: instance 0 1/2 (5.6 s, the court full for the second), 1 2/2 (5.7 s, 3.5 s), 2 1/2 (5.4 s) |
| 2026-11-22 | 1.1.2 | First run of three machines, 4 cores and 3 GB each, 4/6: instance 0 1/2 (7.2 s), instance 1 2/2 (6.7 s, 5.5 s), instance 2 1/2 (5.7 s); both lost slots were second ones, full by 06:00:10.5. The PC clock was 3.18 s slow after a power cut; the run made up for it |
| 2026-11-21 | 1.1.2 | Instance 0 2/2 (6.3 s, 6.5 s), instance 1 2/2 (5.5 s, 3.8 s) |
| 2026-11-20 | 1.1.2 | Instance 0 1/2 (4.4 s): the first slot was taken by someone else at "Xác nhận" (06:00:05); instance 1 2/2 (6.0 s, 3.3 s) |
| 2026-11-19 | 1.1.1 | Instance 0 0/2: `MuMuManager control launch` failed once at 05:45 ("nemu-api init failed"), the run stopped (fixed in 1.1.2); instance 1 1/1 (6.7 s) |
| 2026-11-18 | 1.0.1 (by the update button) | Instance 0 1/1 (6.0 s), instance 1 2/2 (5.5 s, 3.9 s); no popup showed |
| 2026-11-17 | 1.0.0 | Both instances 0: a promotion popup over the home screen, which Back does not close (fixed in 1.0.1) |
| 2026-11-16 | 1.0.0 | Instance 0 1/1, instance 1 2/2 |
| 2026-11-15 | 1.0.0 | Instance 0 1/1 (5.1 s), instance 1 2/2 (4.9 s, 3.2 s) |
| 2026-11-14 | 1.0.0 | 1/2: the second slot was taken by someone else at "Xác nhận" (06:00:09) |
| 2026-11-13 | 1.0.0 | 1/2: the court of the first slot was full by 06:00:05.9 |
| 2026-11-01 | 0.18.1 | Both instances 2/2: Origami (4.5 s, 3.6 s), BS (4.8 s, 3.5 s); real BS and parallel bookings confirmed |
| 2026-10-30 | 0.18.0 | 0/2 at 06:00: the day tap landed during the month slide; after the fix, a real run that day booked 2/2 for 2026-11-01 |

## Decisions in force

These are not written elsewhere (CLAUDE.md, the roadmap or the specs):

- UI: for end users, ready-made choices only; three pages, the booking, the management and the guide; light theme, desktop
  width and Vietnamese by default. It sends no request per step while a run is going, and does
  not check MuMu while the run lock is held.
- The installed app is the daily run; a release reaches it through the installer built from
  `main`: the app's update button, or the installer from the release page.
- The app is one PyInstaller folder inside a per-user NSIS installer, and the backend serves the
  built UI. The installer is built by the `Desktop` workflow, as this PC has no Rust.
- Choosing days of the week: later, not decided.
- Three machines book (MuMu 0, 1, 2; two cores and 2 GB each), since 2026-11-24: the app lets
  only three through when more select the day in the same second (known issues). Five were tried
  on 2026-11-23 and 24.
- From 1.0.0 each version has a GitHub release page with its installer; the pages of
  0.1.0 to 0.9.0 were deleted on 2026-11-03, their tags kept. Releases go ahead without
  asking again.
- Accounts, the first login and making MuMu instances are the user's job, and so is choosing
  another account when the quota a run read is short (it only reads it). Each
  MuMu instance on the PC is a machine in the UI, switched on there.
  Logging in again after a logout is the app's, with a login the user saved (2026-11-18); the
  "ping-pong" with another device on the same account is the user's to set up.
- Test tickets booked during development are cancelled by the user.

## Test environment notes

- The UI suite run fully parallel on the dev machine has two tests time out; with
  `--maxWorkers=2` all pass.
- One process at a time against MuMu: when it freezes, shut MuMu down fully and run again.
- An installer test in a scratch folder leaves `HKCU\Software\servedbyhau\Court Booker`
  behind after uninstalling, and the next install defaults to that folder: delete the key
  after such a test.
