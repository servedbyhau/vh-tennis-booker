# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-23.

## Start of a session

1. Check the time. From 05:45 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `%LOCALAPPDATA%\CourtBooker\logs` for failed rounds or new
   situations.

## Next task: the quota, in the installed app

What counts is known since 2026-11-23 ([field notes](../field-notes.md), "Dialogs"). Step 1, the
run reading it at 05:46 and after the tickets (`quota.py`), is in `feat/quota-read`; dry runs on
the three machines on 2026-11-23 counted what their history pages show, card by card. Step 2, the
last read of each account shown in the app, is in `feat/quota-shown`. Once both are merged,
install `develop` (not from 05:45 to 06:05) and check the next 06:00 run: a `quota_read` before
the rounds and one after the tickets on each machine, the time they took, and each account's
quota in the window.

Step 3, going on to another account of the same customer when too few are left, waits for the
user: what to do with one left and two slots chosen, and whether two accounts share an apartment
(the quota is the apartment's, a history the account's).

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
