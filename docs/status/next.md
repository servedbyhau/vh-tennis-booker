# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-19.

## Start of a session

1. Check the time. From 05:45 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `%LOCALAPPDATA%\CourtBooker\logs` for failed rounds or new
   situations.

## Next task: a run that repairs itself

On 2026-11-19 a failed MuMuManager command ended machine 1's run at 05:45. The user asked
that every part of a run repair what it can instead of stopping. One branch a part:

1. `fix/startup-repair` (done, not merged): before 06:00, MuMuManager commands tried again,
   MuMu restarted once when Android does not boot, the serial connected once again, the app
   stopped and opened again when it does not reach its home screen (up to 3 tries). Tested by
   unit tests; a dry run with both instances started from cold checks that nothing else
   changed. Then release, so the 06:00 run gets it.
2. `fix/app-restart`: the app hanging or closing while the run waits or books. Not in the
   foreground, or the utilities list not opened at the warm-up (05:59:00, as on 2026-11-17):
   stop and open it again, prepare, go on. A round is run again only when it failed before
   "Xác nhận" (a failure after it may have booked). A booking flow change: a real booking.
3. `fix/driver-reconnect`: the driver connection lost (seen on 2026-11-03, every later round
   then failed at once) is started again and the round goes on; a driver that does not
   answer in 10 s is checked over adb first: adb answering means the driver hangs (start it
   again), adb silent means MuMu froze. A real booking.

Every repair has a limit (about 3 a kind a run), so a broken part cannot loop.

Decided by the user (2026-11-19): MuMu frozen during a run is only reported (a restart takes
too long to book after); the run still waits on the home screen and opens the utilities list
at 05:59, as before.

## After that

- Add each 06:00 run to [progress.md](progress.md). After a week without a failure, remove the
  runner folder (`git worktree remove ..\runner`) and its sections in CONTRIBUTING and
  CLAUDE.md.
- Open question (field notes, "Promotion popup"): whether ticking "Không hiện lại" before the X
  keeps the popup away; two tries froze MuMu. Not needed by the run.
- Ruled out for now: code signing (SmartScreen's "Run anyway" stays). Waiting on something:
  another subdivision's survey needs access to one, and choosing days of the week is not
  decided.
