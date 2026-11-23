# Known issues

Open bugs, by severity: **1** may cost the 06:00 run, **2** reports wrongly or too little,
**3** UI or docs. Remove an issue once it is fixed and confirmed (`CHANGELOG.md` keeps the
history). Ideas the user ruled out are listed last, so they are not proposed again.

Last updated: 2026-11-23.

## Severity 1

- **Several MuMu instances launched at once** (within 0.25 s of each other) trip over each other:
  `MuMuManager control launch` failed with "nemu-api init failed" on 2026-11-19 (machine 1 lost
  the morning, before 1.1.2) and 2026-11-22 (the second try, 2 s later, started it); on
  2026-11-21 at 15:21 three cold starts froze all three, which the runs restarted. The repairs
  hold so far. Idea: launch them one after another, as on 2026-11-22 all were ready by 05:46:09.

## Severity 2

- **"Xác nhận" swallowed**: in 6 of 68 rounds booked since 2026-10-13 the tap 0.2 s after the
  consent did nothing and was repeated 3 s later, 5 of them in a second round, where the 3 s may
  cost the slot. Idea: wait about 0.1 s longer; needs a real booking.

## Severity 3

- The desktop window can open taller than the screen, its lower part under the taskbar. The fix
  (Tauri's `preventOverflow`) needs an installer build.

## Unhandled situations

See the roadmap's "Situations": an update or unknown dialog, a network error, the app
crashing mid-round, ADB lost mid-run. Fixed when a log shows one.

## Ruled out by the user

- Throttling screen reads while a screen stays long (2026-10-27): MuMu froze only under test
  bursts, never in a real run.
- Other subdivisions as a bug: they are a feature (the subdivision choice), not a defect.
- A PC that did not wake (the user had shut it down). A scrolled home screen where Back
  leaves the app (only after someone touched it).
- The schedule switch in a development UI replacing the app's task (2026-10-16, not fixed:
  never switch the schedule from a development backend).
- Tapping by MuMu's clock instead of NTP (2026-10-24): it would save a few hundred
  milliseconds at most. Measured at 21:00 on 2026-10-24: MuMu ran 0.71 s behind NTP, and the
  app seems to check against MuMu's clock; the 0.2 s re-tap covers most of it.
- Backup slots or courts, Telegram setup, opening the calendar before 06:00, booking two
  slots in one flow, double taps, an AccessibilityService agent. (A check while the run
  waits, ruled out at first, is done since 2026-11-19: one read a minute until 05:58.)
- Risks reviewed on 2026-10-10, fixed only if a log shows them: a slow first tap after a long
  idle, the 2 s re-tap threshold, load from continuous screen reads, uiautomator2 not pinned,
  Windows Update restarting the PC.
