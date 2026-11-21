# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-19.

## Start of a session

1. Check the time. From 05:45 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `%LOCALAPPDATA%\CourtBooker\logs` for failed rounds or new
   situations.

## Next task: watch the 06:00 runs of 1.1.2

1.1.2 repairs getting ready by itself (`ready.py`, see [architecture](../architecture.md)).
Check each 06:00 log for `repaired` events and what they fixed; a failure that ended the run
before 05:58 is a gap to study.

Decided by the user (2026-11-19): during the rounds a frozen MuMu is only reported; the run
still waits on the home screen and opens the utilities list at 05:59, as before. Repairs
during the rounds come later, in their own task.

Known limits of the setup repairs: the deadline is checked between repairs, so a MuMu restart
begun just before 05:58 may end after the warm-up (worst case about two minutes, 41-49 s
seen); a fault in the last 15 s before the start is not repaired.

## After that

- Add each 06:00 run to [progress.md](progress.md). After a week without a failure, remove the
  runner folder (`git worktree remove ..\runner`) and its sections in CONTRIBUTING and
  CLAUDE.md.
- Open question (field notes, "Promotion popup"): whether ticking "Không hiện lại" before the X
  keeps the popup away; two tries froze MuMu. Not needed by the run.
- Ideas, not decided (2026-11-21): the number of machines and their MuMu CPU and RAM
  suggested from the PC's RAM and CPU, a guide to make a MuMu instance, and starting the
  instances one after another instead of at once.
- Ruled out for now: code signing (SmartScreen's "Run anyway" stays). Waiting on something:
  another subdivision's survey needs access to one, and choosing days of the week is not
  decided.
