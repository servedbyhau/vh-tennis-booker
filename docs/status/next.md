# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-27.

## Start of a session

1. Check the time. From 05:45 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `%LOCALAPPDATA%\CourtBooker\logs` for failed rounds or new
   situations.

## Gathering: the opening's clocks

Since 2026-11-25 each 06:00 run logs "Opening: ..." on each machine (`opening.py`). The user
asked for 5-7 days of it before deciding whether the first tap should wait until the PC clock
(and so Android's) has passed 06:00 too: the "chỉ nhận đăng ký từ 06:00" notice showed on about
half the days, costing 0.5-1 s. Compare, per day, Android's offset, the first tap by Android's
clock and the attempt that opened the calendar.

## Next task: the Setup page

Asked by the user on 2026-11-27 so a new PC needs only MuMu Player, the Vinhomes file and the
app: a page that takes it through six steps, each checked (drawn and agreed first; short words,
icons where needed). Three stacked branches: the checks per MuMu instance (`feat/setup-report`,
#342), the page with the panel beside the ticket renamed Settings (`feat/setup-page`; a machine
switched on without its MuMu instance leads to the page), then the count of the steps left in
the header and a line on the booking page. Merge in order, install `develop` (not from 05:45 to
06:05), the user tries it; then a release.

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
- Decided 2026-11-24: three machines, two cores and 2 GB each (the user's own and two for
  customers), as the app lets three through at once (known issues).
- Ruled out for now: code signing (SmartScreen's "Run anyway" stays). Waiting on something:
  another subdivision's survey needs access to one, and choosing days of the week is not
  decided.
