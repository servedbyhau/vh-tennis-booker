# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-03.

## Start of a session

1. Check the time. From 05:45 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `%LOCALAPPDATA%\CourtBooker\logs` for failed rounds or new
   situations.

## Next task: 1.0.0, the first complete version

A resident downloads one installer from the release page, installs, sets up in the app, and
later updates with one button. Each part is its own branch, PR'd into `develop` in this order:

| Branch | Work |
|---|---|
| `feat/desktop-release` | The `Tag` workflow calls `Desktop` with the tag, which publishes the release page: the installer under one name for every version, `latest.json` for the update button, the CHANGELOG section as notes |
| `feat/desktop-updater` | The update button: Rust commands behind a `remote` capability for `http://127.0.0.1:8765/*`; the window stops its backend before the installer runs; the UI shows the button only in the window, locked while a run holds the lock and in the quiet time |
| `fix/desktop-uninstall-task` | The uninstaller removes the daily task when it runs this install (not on an update); the `Desktop` workflow installs, serves and uninstalls on a clean runner |
| `docs/readme-1.0` | README for residents (download, install, set up, update, remove) with new screenshots; the command line and the build move to CONTRIBUTING |
| `chore/release-1.0.0` | `tools/release.py 1.0.0` |

The user adds two repository secrets before the release: `TAURI_SIGNING_PRIVATE_KEY` (the
content of `D:\VH-Booker\dev-tools\keys\court-booker-updater.key`) and
`TAURI_SIGNING_PRIVATE_KEY_PASSWORD` (empty). 0.19.0 has no update button: 1.0.0 is installed
by hand over it, later versions by the button.

## After that

- Add each 06:00 run to [progress.md](progress.md). After a week without a failure
  (2026-11-10), remove the runner folder (`git worktree remove ..\runner`) and its sections in
  CONTRIBUTING and CLAUDE.md.
- Ruled out for now: code signing (SmartScreen's "Run anyway" stays). Waiting on something:
  another subdivision's survey needs access to one, and choosing days of the week is not
  decided.
