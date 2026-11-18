# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-18.

## Start of a session

1. Check the time. From 05:45 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `%LOCALAPPDATA%\CourtBooker\logs` for failed rounds or new
   situations.

## Next task: update to 1.1.1 by the button, then watch the 06:00 runs

1. Once the release page of 1.1.1 is up, the user presses "Cập nhật lên 1.1.1" outside
   05:45-06:05. It proves the installer fix: check that the engine, the window and Windows all
   report 1.1.1 and that no process of the app was left; then remove the update issue from
   [known-issues.md](known-issues.md).
2. The login of MuMu 1 is saved in the vault (2026-11-18); the user may change the Vinhomes
   password and save the new one under "Tự đăng nhập lại" of machine 2.
3. Watch the next 06:00 logs; a run that logged in again shows "Logged in again", and one that
   stopped on an unexplained failure saved a screenshot in `logs\screens`.
4. Open question (field notes, "Promotion popup"): whether ticking "Không hiện lại" before the X
   keeps the popup away; two tries froze MuMu. Not needed by the run.

## After that

- Add each 06:00 run to [progress.md](progress.md). After a week without a failure
  (2026-11-10), remove the runner folder (`git worktree remove ..\runner`) and its sections in
  CONTRIBUTING and CLAUDE.md.
- Ruled out for now: code signing (SmartScreen's "Run anyway" stays). Waiting on something:
  another subdivision's survey needs access to one, and choosing days of the week is not
  decided.
