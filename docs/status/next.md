# Next task

The plan of the one task to do next; rewrite it when that task is done.

Last updated: 2026-11-02.

## Start of a session

1. Check the time. From 05:50 to 06:05 run nothing against MuMu.
2. Read [progress.md](progress.md) and this file.
3. Check the newest 06:00 log in `logs/` (local only) for failed rounds or new situations.

## Next task: the packaged app, proven by a real 06:00 run

Build the installer, install it as a resident would, and let the task it sets book at 06:00 on
2026-11-03. Done when that run reaches the ticket from the installed app. Packaging version:
**0.19.0**. Packaging order and open points: the [spec](../specs/0.5.0-desktop-app.md),
"Packaging".

### What shapes the plan

- **The app is closed from 21:00 to 06:00**, so no dry run or booking can pass tonight. The
  first real proof is the 06:00 run itself, and a failed one loses that day: see the go/no-go.
- This PC has no Rust and no MSVC tools, and C: has about 5 GB free. Python, Node and WebView2
  are ready; D: has the space.
- `[sys.executable, "-m", "court_booker"]` fails in a frozen app, at `api/runs.py:34`,
  `cli.py:147` and `schedule.py:100` (also `windowless_python`, `schedule.py:74`).
- The backend serves `/api` only. The client already uses `window.location.origin`, and the
  fonts are bundled.
- History and the run lock are already in `%LOCALAPPDATA%\CourtBooker`, so the installed app
  reads the same history, passed dry runs included. No `config.toml` is there yet: `serve`
  writes the defaults on its first start.
- The quota is 8 slots a month per apartment: ask the user once whether this month has room. A
  quota notice at 06:00 proves the run up to the calendar, not the ticket.

### Decisions

- The backend serves the built UI. The window opens `http://127.0.0.1:8765`: one origin, no
  CORS, and browser storage keeps one fixed origin.
- PyInstaller **one folder**, not the spec's one `.exe`: a one-file app has a parent process
  that outlives a kill and unpacks to `%TEMP%` on every run, and the task needs a steady path.
  The resident still gets one installer. Update the spec.
- The Tauri build runs in a GitHub Actions Windows job, whose runner has Rust and MSVC, and
  `gh run download` fetches the installer. Only PyInstaller runs here, its output on D:.
- NSIS installer, per user (no admin rights), unsigned: SmartScreen's "Run anyway" is expected.
- PyInstaller builds with `console=False`: `sys.stdout` is `None`, as under `pythonw`, so pass
  `log_config=None` to `uvicorn.run`, whose default formatter calls `isatty()`.
- Nothing is merged before the 06:00 run proves it (CLAUDE.md, Rules). Each step is its own
  branch, stacked on the last and pushed; the installer is built from the last one.

### Steps

Times are the latest finish. Run the quick checks of the touched area on each branch, and
update the docs, CHANGELOG and tests in the same branch.

| By | Branch | Work |
|---|---|---|
| 00:15 | `feat/engine-command` | One function returns how to start the engine: the frozen exe alone, else `python -m court_booker`. All the places above use it; the task's command and arguments follow. Tests with `sys.frozen` patched |
| 00:45 | `feat/serve-built-ui` | `create_app` serves the built UI when a folder is given, with a fallback to `index.html` for the old addresses; `/api` and the live feed win. `serve` finds the folder beside the code, and development without a build stays as it is |
| 01:45 | `feat/pyinstaller-build` | `packaging/court-booker.spec` and a `tools/build_app.py` that builds the UI, then the folder on D:. Include the driver APK, the built UI, `uiautomator2` and `adbutils` data, and Uvicorn's and WebSockets' hidden imports. Check with Python off the `PATH`: `--version`, `serve`, the UI in a browser, the driver found |
| 03:30 | `feat/desktop-shell` | `desktop/` Tauri app: the PyInstaller folder as a resource, a sport-neutral icon, `minWidth` 1280, `minHeight` 720. Rust starts `court-booker.exe serve` without a window, waits for `/api/health`, then opens the backend's page; if the health check already answers it uses that backend; it stops only a backend it started. CI job that uploads the NSIS installer |
| 04:30 | none | Rehearsal, below, with the user |
| 05:00 | none | Go/no-go, below |

If the shell is not building by 03:30, drop it for tonight: a shortcut to the PyInstaller folder's
`serve` and the browser still proves the frozen engine at 06:00. Finish the shell afterwards.

### Rehearsal (the user installs, before 05:00)

1. Stop any development backend: the port is fixed.
2. Install from the downloaded installer; open the app from the Start menu.
3. Choose the same slots, subdivision, sport and court as the development `config.toml`, on the
   ticket, then compare the data folder's `config.toml` with it.
4. Run a dry run from the UI. It must start MuMu and the driver, tap the utility and meet the
   closed-hours notice, then fail as "not open yet"; the live steps, History and the log must
   show it, with no console window. Shut MuMu down afterwards.
5. Switch on "Máy 2" and repeat, to prove the second process starts; switch it off.
6. The switch shows on because the runner's task exists: turn it off and on, so the task is the
   app's. `schedule status` must show the installed `court-booker.exe`, the data folder's
   config and `Start In`, with wake and days as before.
7. Run that task once with `--scheduled` replaced by hand with `--dry-run --at <a few minutes
   ahead>` (`--scheduled` wins over `--at`), `schtasks /run`, and check the log; turn the switch
   off and on again to restore the arguments, and check them.

### Go/no-go at 05:00

Go only if every step above passed and the task's arguments have no `--dry-run`. Otherwise put
the runner back, and 06:00 books as it does every day:

```powershell
D:\VH-Booker\runner\.venv\Scripts\python.exe -m court_booker schedule install --config D:\VH-Booker\vh-tennis-booker\config.toml
```

Check `schedule status` shows the runner's Python. MuMu off, nothing running, no development
backend. From 05:50 to 06:05 touch nothing.

### After the 06:00 run

1. Check the log: code path in the install folder, target 2026-11-05, every round to the ticket.
   Check History and the notification too. Add the run to [progress.md](progress.md).
2. On failure put the runner back, as above, and log the cause in
   [known-issues.md](known-issues.md).
3. On success run the resident's first start from an empty `COURT_BOOKER_HOME`: the setup guide,
   a dry run that passes, the switch allowed. Do not switch it on there: it would point the task
   at that folder.
4. Merge in order, then release 0.19.0 with `tools/release.py`, its first real use. Move the
   `Environment` notes and the roadmap's phase 4 row once the installed app is the daily run.
5. Keep the runner until a week of 06:00 runs from the installed app.

### Later, not tonight

Uninstall removing the task, a test on a clean PC, code signing, updates, the release build on
each tag (spec, step 4), and the Windows Defender check over a few mornings.

## After that

Waiting on something: another subdivision's survey needs access to one, and choosing days of
the week is not decided.
