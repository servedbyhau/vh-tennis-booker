; Hooks Tauri's NSIS installer runs (tauri.conf.json, bundle.windows.nsis.installerHooks).

; Uninstalling removes the daily task, but only when it runs this install: a task left behind
; would wake the PC every morning for nothing, and one that runs another copy is not ours. An
; update runs no uninstaller. A reinstall that uninstalls first does, and the app's "Tự đặt"
; switch then sets the task again. The data folder stays, as it does without this hook.
!macro NSIS_HOOK_PREUNINSTALL
  ${If} $UpdateMode <> 1
    nsExec::Exec `"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -Command "$$task = Get-ScheduledTask -TaskName 'court-booker' -ErrorAction SilentlyContinue; if ($$task -and $$task.Actions[0].Execute -like '$INSTDIR\*') { Unregister-ScheduledTask -TaskName 'court-booker' -Confirm:$$false }"`
    Pop $0
  ${EndIf}
!macroend
