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
3. `feat/ready-watch` (done, not merged): while the run waits on the home screen, it checks
   every 60 s until 05:58 (the app in front, one screen read) and repairs what broke; the
   warm-up at 05:59 repairs too. Tried on MuMu: the app stopped by hand was found by the
   next check and restarted (6 s); the driver stopped before the warm-up was restarted
   there (1.5 s).
4. `fix/mumu-freeze-recovery` (done, not merged): a frozen or hung MuMu (no answer to `am
   get-current-user` in 10 s) has its `MuMuNxDevice` process ended, not through MuMuManager,
   which hangs then, and is started again. Tried on a really hung instance 0: ready 41 s
   after the ping gave up.

Done on the real MuMu (2026-11-19), each repaired: the app and the driver stopped by hand, a
really hung Android (41 s to ready), a suspended `MuMuNxDevice` found by the minute check
(49 s to ready; the warm-up and the rounds then ran on time). Merged into `develop`
(#257-#260). Left: a real booking on `develop` (ask the user for free slots), then the
release.

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
