# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-19.

## Start of a session

1. Check the time. From 05:45 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `%LOCALAPPDATA%\CourtBooker\logs` for failed rounds or new
   situations.

## Next task: getting ready repairs itself

On 2026-11-19 a failed MuMuManager command ended machine 1's run at 05:45. Decided with the
user that day: before 06:00 every passing failure is repaired, only one no repair can change
ends the run. One branch a part, each stacked on the one before, all PR'd into `develop`:

1. `fix/startup-repair` (done, not merged): MuMuManager commands tried 3 times (today's
   failure); a first version of the other repairs, which 2 replaces.
2. `fix/setup-supervisor` (done, not merged): `ready.py` repairs MuMu, ADB, the driver and the
   app layer by layer until 05:58, escalating to the layer below, with waits from measured
   times. Tested by unit tests and a dry run from cold.
3. `feat/ready-watch`: while the run waits on the home screen, check every 60 s until 05:58
   (one screen read and the app in front) and repair what broke.
4. `fix/mumu-freeze-recovery`: a frozen MuMu (no adb answer) is ended by its
   `MuMuNxDevice` process (field notes), not by MuMuManager, which hangs then, and started
   again.

Then: fault-injection dry runs on the real MuMu (stop the driver, the app, disconnect ADB,
suspend `MuMuNxDevice`), a real booking (ask the user for free slots), a release.

Decided by the user (2026-11-19): during the rounds a frozen MuMu is only reported; the run
still waits on the home screen and opens the utilities list at 05:59, as before. The check
every minute before 05:58 replaces the ruled-out "health check before 06:00".

## After that

- Add each 06:00 run to [progress.md](progress.md). After a week without a failure, remove the
  runner folder (`git worktree remove ..\runner`) and its sections in CONTRIBUTING and
  CLAUDE.md.
- Open question (field notes, "Promotion popup"): whether ticking "Không hiện lại" before the X
  keeps the popup away; two tries froze MuMu. Not needed by the run.
- Ruled out for now: code signing (SmartScreen's "Run anyway" stays). Waiting on something:
  another subdivision's survey needs access to one, and choosing days of the week is not
  decided.
