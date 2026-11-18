; Hooks Tauri's NSIS installer runs (tauri.conf.json, bundle.windows.nsis.installerHooks).

; Before any file is copied, every process of this install is stopped: the window, the
; backend (`court-booker.exe serve`) and a dry run. Windows refuses to overwrite a running
; program, and on 2026-11-18 a backend the window had not started itself kept
; court-booker.exe, so the update stopped halfway: new UI, old engine. A real booking (the
; 06:00 run, or a run by hand: an engine process that is none of those) is never stopped: the
; install then ends before copying anything, with a message, and leaves the app as it was.
; Exit codes of the script: 0 all stopped, 2 a booking runs, 3 a process would not stop.
!macro NSIS_HOOK_PREINSTALL
  nsExec::Exec `"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -Command "function Mine { @(Get-CimInstance Win32_Process | Where-Object { $$_.ExecutablePath -like '$INSTDIR\*' }) }; $$booking = @(Mine | Where-Object { $$_.Name -eq 'court-booker.exe' -and $$_.CommandLine -notmatch ' (serve|setup|schedule)(\s|$$)|--(dry-run|version|help)' }); if ($$booking.Count) { exit 2 }; Mine | ForEach-Object { Stop-Process -Id $$_.ProcessId -Force -ErrorAction SilentlyContinue }; for ($$i = 0; $$i -lt 50; $$i++) { if (-not (Mine).Count) { exit 0 }; Start-Sleep -Milliseconds 200 }; exit 3"`
  Pop $0
  ${If} $0 == 2
    ; English, as the rest of the installer: NSIS reads this file in the ANSI code page.
    MessageBox MB_ICONSTOP "Court Booker is booking a court now. Nothing was changed: install the update once the booking is done." /SD IDOK
    SetErrorLevel 2
    Quit
  ${EndIf}
!macroend

; Uninstalling removes the daily task, but only when it runs this install: a task left behind
; would wake the PC every morning for nothing, and one that runs another copy is not ours. An
; update runs no uninstaller. A reinstall that uninstalls first does, and the app's "Tự đặt"
; switch then sets the task again. The data folder stays, as it does without this hook. A
; task made by schtasks /TR keeps quotes around its command; the app's own has none.
!macro NSIS_HOOK_PREUNINSTALL
  ${If} $UpdateMode <> 1
    nsExec::Exec `"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -Command "$$task = Get-ScheduledTask -TaskName 'court-booker' -ErrorAction SilentlyContinue; if ($$task -and $$task.Actions[0].Execute.Trim([char]34) -like '$INSTDIR\*') { Unregister-ScheduledTask -TaskName 'court-booker' -Confirm:$$false }"`
    Pop $0
  ${EndIf}
!macroend
