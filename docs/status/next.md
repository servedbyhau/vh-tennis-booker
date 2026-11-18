# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-18.

## Start of a session

1. Check the time. From 05:45 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `%LOCALAPPDATA%\CourtBooker\logs` for failed rounds or new
   situations.

## Next task: try logging in again on the device, then release

The backend protection and the login again are written and tested (not committed: the user
commits when they say so), in two parts: `fix/backend-local-only`, then the login on a branch
stacked on it.

1. The user saves the login of MuMu 1 under "Tự đăng nhập lại" (a development backend writes
   the same Windows vault the installed app reads), with MuMu 1 logged out (it is since the
   survey on 2026-11-18).
2. A timed dry run of instance 1 a few minutes ahead logs in by itself: the log shows the
   masked phone, "Logged in again", then the rounds. Note in the field notes what the app
   showed after "Đăng nhập".
3. Commit when asked, in the two branches; release; the user updates by the button.
4. Open question (field notes, "Promotion popup"): whether ticking "Không hiện lại" before the X
   keeps the popup away; two tries froze MuMu. Not needed by the run.

## After that

- Add each 06:00 run to [progress.md](progress.md). After a week without a failure
  (2026-11-10), remove the runner folder (`git worktree remove ..\runner`) and its sections in
  CONTRIBUTING and CLAUDE.md.
- Ruled out for now: code signing (SmartScreen's "Run anyway" stays). Waiting on something:
  another subdivision's survey needs access to one, and choosing days of the week is not
  decided.
