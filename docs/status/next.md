# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-02.

## Start of a session

1. Check the time. From 05:50 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `logs/` (local only) for failed rounds or new situations.

## Next task

Packaging the desktop app, the last step before 1.0.0; the steps are in the
[spec](../specs/0.5.0-desktop-app.md), "Packaging". One branch per step, starting with the
PyInstaller build of the backend and engine. Before that step, decide with the user:

- The spec's open choice, how the UI reaches the backend. Recommended: the backend serves the
  built UI, so one origin needs no CORS; today it serves only `/api`.
- The version number the packaging work starts at.

Not started because they wait on something: another subdivision's survey needs access to one,
and choosing days of the week is not decided.
