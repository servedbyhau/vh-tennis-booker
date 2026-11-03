# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-03.

## Start of a session

1. Check the time. From 05:45 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `%LOCALAPPDATA%\CourtBooker\logs` for failed rounds or new
   situations.

## Next task: install 1.0.0 and prove the update button

1. Once the `Tag` workflow has published the 1.0.0 release page, the user installs
   `CourtBooker-setup.exe` from it over 0.19.0 (0.19.0 has no update button). Check that the
   daily task still runs `%LOCALAPPDATA%\Court Booker\court-booker\court-booker.exe`.
2. Check that the window reaches its commands: started with
   `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=<port>`, the page's
   `invoke("update_version")` answers `null` (no newer version).
3. The first press of the button that installs something is the next release's; note in
   [progress.md](progress.md) whether it went through, kept the data and the task, and reopened
   the app.

## After that

- Add each 06:00 run to [progress.md](progress.md). After a week without a failure
  (2026-11-10), remove the runner folder (`git worktree remove ..\runner`) and its sections in
  CONTRIBUTING and CLAUDE.md.
- Ruled out for now: code signing (SmartScreen's "Run anyway" stays). Waiting on something:
  another subdivision's survey needs access to one, and choosing days of the week is not
  decided.
