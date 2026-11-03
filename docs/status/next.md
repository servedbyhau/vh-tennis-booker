# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-03.

## Start of a session

1. Check the time. From 05:45 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `%LOCALAPPDATA%\CourtBooker\logs` for failed rounds or new
   situations.

## Next task: install 0.19.0 and watch the week

1. Once `Release v0.19.0` is merged into `main`, fetch the installer the `Desktop` workflow
   builds from it (`gh run download <run> -n court-booker-installer`) and install it over the
   app. The install folder stays the same, so the task needs no change; check
   `python -m court_booker schedule status` anyway.
2. Add each 06:00 run to [progress.md](progress.md). After a week without a failure
   (2026-11-10), remove the runner folder (`git worktree remove ..\runner`) and its section in
   CONTRIBUTING.

## After that

The packaging left before 1.0.0 (the spec, "Packaging"): the installer built on each version
tag, the uninstaller removing the task, a test on a clean PC, code signing, updates, and the
Windows Defender check over a few mornings. Waiting on something: another subdivision's survey
needs access to one, and choosing days of the week is not decided.
