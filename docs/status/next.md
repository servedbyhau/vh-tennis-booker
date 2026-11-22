# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-23.

## Start of a session

1. Check the time. From 05:45 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `%LOCALAPPDATA%\CourtBooker\logs` for failed rounds or new
   situations.

## Next task: check the 06:00 run of 2026-11-23

It is the first of the account check, of the ticket reading at 06:03 and of three machines with
2 cores each. Check: the account each machine booked with and whether it had to change; that
each ticket booked has its picture and reads as registered, and when the reading started and
ended; the time from the slot to the court list (2.1-3.3 s on two machines, 2.9-4.4 s on three
with 4 cores); whether a launch failed again ([known issues](known-issues.md)).

Then install `develop` (#286 to #290: what is ready, whose account a run and a ticket are of, the
copied picture, the question before a removal), not before 06:05, and look at each in the desktop
window.

## Under study: the quota

What counts is known since 2026-11-23 ([field notes](../field-notes.md), "Dialogs"): the history
page tells it, at any hour, in 5-9 s. Counting what the app itself booked would be wrong, as
residents book and cancel by hand and rain refunds come a day later. The plan to decide with the
user: read it while getting ready, after the account check (05:46, when no booking can change it
any more), and again with the tickets; show what is left per account and sport with when it was
read; go on to another account of the same customer when none is left.

Put off by the user: the days each machine books on (a schedule), and sending results and tickets
over Zalo.

## After that

- Add each 06:00 run to [progress.md](progress.md). After a week without a failure (none since
  2026-11-20), remove the
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
