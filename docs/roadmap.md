# Roadmap

## Product goal

Win the booking race: the app opens bookings at **06:00 every day**, and the user must not need
to be awake. Unattended, scheduled, as fast as possible.

- The target date is always today + 2 (`config.DAYS_AHEAD`), the newest day the app opens at
  06:00; neither the config nor the command line changes it.
- Windows Task Scheduler starts the run at `wake_at` (waking the PC). The run starts MuMu,
  connects ADB, restarts the app, waits on the home screen and opens the utilities list
  `warm_up_seconds` before the start, so only the booking taps happen after 06:00. A real run
  that ran its rounds closes MuMu at the end.
- More accounts book side by side: each other MuMu instance (`[[instances]]`) runs the same
  run in its own process, with its own account, court and slots, switched on in the UI ("Máy 2",
  "Máy 3", each with its switch). Each books only its own slots, so 4 hours take 2 slots on each of 2
  instances.
- Out of scope: getting around any check of the app, and accessibility services, which the app
  refuses (field notes, "Accessibility agent"). In scope: the project's own instrumentation
  driver (UiAutomation, as uiautomator2 uses); the app books with it running. Since
  2026-11-18 also logging in again with a login the user saved (the app logs an account out
  when it logs in on another device): typed in as the user would, once a run.

## Phases

The 0.x versions go through four phases toward 1.0.0: (1) it runs, (2) it handles every
situation, (3) it is fast, (4) it has a user-friendly UI. Releases 0.1.0 to 0.13.1 covered all
four (CHANGELOG); 0.13.0 ended phase 3 with MuMu instances side by side, confirmed by a real
two-instance run on 2026-11-01; 1.0.0 ended phase 4 with the installer, its release page and
the update button. Failures are fixed as the 06:00 logs show them. What is left:

| Phase | Next | Scope |
|---|---|---|
| 1 Runs | Other subdivisions | Origami and BS are in `catalog.py` with every sport; BS tennis at BCX3 was booked for real on 2026-11-01. BE7 tennis and basketball have dry-run coverage; other BS courts have only the survey. Left: survey each other subdivision with `dev-tools/survey/walk.py` and add it to the catalog |

## Situations

| Area | Situation | Today |
|---|---|---|
| App | Logged out (the account logged in on another device) | Closes the notice and types the login saved in the app's setup, tapping "Đăng nhập" once, again only if nothing changed for 20 s; refused, or none saved, the run stops at once (exit 4) with what to do |
| App | Logged in with another account than the one saved for the machine | Read on the account tab while getting ready: logged out and the saved login typed in, the number read again. Still another one, or a number that cannot be read on a machine no run saw this account on: the machine books nothing (exit 4) |
| App | App set to English | Works: the language is found on the first screen |
| App | Closed-hours notice (tap before 06:00) | Closed with Back and the utility tapped again until `open_retry_seconds`; the wait goes by NTP time on a counter, the first tap 0.1 s after the start |
| App | Promotion popup over the home screen | Closed with its X before the utilities list is opened (field notes); Back does not close it |
| App | Update prompt, other dialogs, network error | Not handled |
| App | App crash or freeze | While the run waits (to 05:58): a check every minute (the app in front, one screen read) finds it and the app is made ready again; at the warm-up (05:59) a failure is repaired until 05:59:45; during a round: not handled |
| App | Slow server | Every screen awaited up to `timeout` (30 s), a tap repeated every 2 s while its element still shows |
| Booking | New date not open yet | Calendar reloaded for `open_retry_seconds` |
| Booking | Slot or court fully booked | Round fails; no fallback slot or court (by decision) |
| Booking | Slot taken by someone else at "Xác nhận" | Round fails with the app's notice |
| Booking | Booked court differs from the tapped one | The court list moves under the tap (field notes); the booking details page must name the configured court, another one is left with Back and the court tapped again |
| Booking | Target date in the next month | Works: after the missed day tap at 06:00 on 30/10, the fix booked two real slots for 01/11 later that day; the 31/10 06:00 run on 0.18.1 booked two slots for 02/11 |
| Booking | Quota (2 slots a day, 8 a month per apartment) | Tracking is left to the user. The app's quota notice, after "Tiếp tục" or "Xác nhận", fails the round with "Booking quota used up" and skips the rounds left; the log and the notification say so (since 0.11.0). The 06:00 run books a new day, so there it means the month is used up |
| Device | MuMu not running / frozen | Started automatically. Frozen or hung before 05:59:45 (no answer to the ping in 10 s): its process ended and started again, ready about 40 s later (`ready.py`); during the rounds a device command over 60 s ends the run (exit 3), no restart (by decision) |
| Device | A MuMuManager command fails, Android does not boot, ADB or the driver does not connect (while getting ready) | Each MuMuManager command tried up to 3 times, 2 s apart; every layer repaired until 05:58, bottom up, the layer below too after 3 failures in a row (`ready.py`); the driver gives way to uiautomator2 after 2 failed starts |
| App | The app does not reach its home screen while getting ready (a hang, an unknown screen, no network yet) | Restarted after growing pauses (0, 5, 10, 20, 30 s) until 05:58; a logout without a saved login, a refused login or the app not installed stops at once |
| Device | One of several MuMu instances fails or freezes | Only its own process ends; the others book on, and the main log names its exit code. Its slots are not moved to another instance (by decision) |
| Device | ADB or the driver lost | While getting ready: connected or started again (`ready.py`); during the rounds: not handled |
| Device | Wrong MuMu resolution | Set by the run while MuMu is off; a running MuMu is logged (WARNING) and scrolls |
| Device | PC woke late, clock drift | Runs at once if under 10 min late; NTP time on a counter Windows does not set |
| Reporting | Every failure reported | Log file, history database, a Windows notification after every run; Telegram optional. A real run that stopped on a failure the app did not explain also saves the screen (`logs\screens`) |

## Ruled out

- Opening the calendar before 06:00, two slots in one booking, pre-recorded coordinates.
- Fallback slots and courts (other users book within seconds).
- Setting up Telegram (the optional code stays).
- An on-device accessibility agent: the app refuses to book while one is enabled.
- Counting the month's bookings in the app's history before the run: the user tracks the quota.
- MuMu tuning for speed (resolution, CPU and memory, frame rate, renderer) and tapping by the
  MuMu clock: about 80% of a round waits on the server (2026-10-24), the taps and dumps take
  milliseconds, and the retries after the closed-hours notice make up a slow clock. Turning
  off Play Store updates and locking the rotation: not worth the effort.
