# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-24.

## Start of a session

1. Check the time. From 05:45 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `%LOCALAPPDATA%\CourtBooker\logs` for failed rounds or new
   situations.

## Next task: what needed MuMu, from the app

Chosen by the user on 2026-11-24, one branch each: (1) `court-booker cancel <code>`
(#302; a real cancel of a ticket booked for the test went through), (2) its button on a
ticket of the tickets section (`feat/cancel-ticket-button`; a real cancel through the API went
through), (3, `feat/read-quota`, a real read on MuMu 0 went through) a button that reads
an account's quota again, (4) one that opens a machine's MuMu. Adding or deleting machines stays
by hand (three at most, on or off in the Setup). The quota read since #292 is in the installed
app since #299; the first 06:00 runs read it on every machine.

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
- Decided 2026-11-24: three machines, two cores and 3 GB each (the user's own and two for
  customers), as the app lets three through at once (known issues). Ideas, not decided: a guide
  to make a MuMu instance.
- Ruled out for now: code signing (SmartScreen's "Run anyway" stays). Waiting on something:
  another subdivision's survey needs access to one, and choosing days of the week is not
  decided.
