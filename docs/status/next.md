# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-28.

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
clock and the attempt that opened the calendar. Seen so far: the notice showed exactly on the
days Android's clock was behind NTP (27/11: -0.23 s, all three machines, calendar after 0.53 s
instead of 0.07-0.26 s).

## Next task: results and tickets on Zalo

Asked by the user on 2026-11-28, through their own Zalo Bot (the official way for one person:
Zalo OA and ZNS are for businesses, personal-account libraries risk a ban). First the user's own
chat (they forward to customers); sending straight to each customer, who writes to the bot
once, may follow. Two stacked branches: sending and the routes (`feat/zalo-send`), then the
Settings row that links the bot (`feat/zalo-settings`). Not known from the docs, to try for
real: whether the bot may still write after a night or days without a message from the user
(error 422), and the free plan's monthly quota (3,000 messages and 50 people per bot by
third-party pages). Then a release with the Setup page (installed since #344).

Decided with the user on 2026-11-23: a run never changes the account by itself (a login at 05:46
could cost the booking, a customer's phone may be logged out, two accounts may share an
apartment's quota); with one left and two slots, the app books the first and refuses the second.
Sharing the bookings out over a customer's accounts belongs with the schedule.

Put off by the user: the days each machine books on (a schedule).

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
