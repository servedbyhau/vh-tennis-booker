# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-23.

## Start of a session

1. Check the time. From 05:45 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `%LOCALAPPDATA%\CourtBooker\logs` for failed rounds or new
   situations.

## Next task: the quota, in the installed app

What counts is known since 2026-11-23 ([field notes](../field-notes.md), "Dialogs"). In
`develop`: the run reads it at 05:46 and after the tickets (`quota.py`; dry runs on the three
machines on 2026-11-23 counted what their history pages show, card by card), each account shows
the last read, and a run warns when the next day's has too few left (`feat/quota-warning`). Once
merged, install `develop` (not from 05:45 to 06:05) and check the next 06:00 run: a `quota_read`
before the rounds and one after the tickets on each machine, the time they took, the warning
where one is due, and each account's quota in the window.

Decided with the user on 2026-11-23: a run never changes the account by itself (a login at 05:46
could cost the booking, a customer's phone may be logged out, two accounts may share an
apartment's quota); with one left and two slots, the app books the first and refuses the second.
Sharing the bookings out over a customer's accounts belongs with the schedule.

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
