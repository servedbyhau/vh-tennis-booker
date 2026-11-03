# Install the app on a clean Windows PC, serve it without Python, and uninstall it.
#
# The Desktop workflow runs it on its runner after building the installer. It creates and
# removes a scheduled task named court-booker, so never run it on a PC that books.
#
# Usage: powershell -File tools/check_installer.ps1 <installer.exe>

param([Parameter(Mandatory = $true)][string]$Installer)

$ErrorActionPreference = "Stop"
$Task = "court-booker"
$Folder = Join-Path $env:LOCALAPPDATA "Court Booker"
$Engine = Join-Path $Folder "court-booker\court-booker.exe"
$Window = Join-Path $Folder "court-booker-desktop.exe"

function Install-App {
    Start-Process -FilePath $Installer -ArgumentList "/S" -Wait
    if (-not (Test-Path $Engine) -or -not (Test-Path $Window)) { throw "The app was not installed in $Folder" }
}

function Uninstall-App {
    Start-Process -FilePath (Join-Path $Folder "uninstall.exe") -ArgumentList "/S" -Wait
    # The uninstaller goes on from a copy of itself; wait for the files to go.
    for ($i = 0; $i -lt 60 -and (Test-Path $Window); $i++) { Start-Sleep -Seconds 1 }
    if (Test-Path $Window) { throw "The app was not uninstalled" }
}

function Set-Task([string]$Command) {
    schtasks /Create /TN $Task /TR "`"$Command`" --scheduled" /SC DAILY /ST 05:45 /F | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "schtasks /Create failed" }
}

function Test-Task {
    return $null -ne (Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue)
}

Install-App
Write-Output "Installed in $Folder"

# The backend serves the API and the UI without Python.
$data = Join-Path $env:RUNNER_TEMP "court-booker-data"
$env:COURT_BOOKER_HOME = $data
$path = $env:PATH
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
$backend = Start-Process -FilePath $Engine -ArgumentList "serve" -PassThru
$env:PATH = $path
$health = $null
for ($i = 0; $i -lt 60 -and $null -eq $health; $i++) {
    Start-Sleep -Seconds 1
    try { $health = Invoke-RestMethod "http://127.0.0.1:8765/api/health" -TimeoutSec 2 } catch { }
}
if ($null -eq $health -or $health.status -ne "ok") { throw "The backend did not answer" }
$page = Invoke-WebRequest "http://127.0.0.1:8765/" -UseBasicParsing
if ($page.Content -notmatch '<div id="root">') { throw "The backend did not serve the UI" }
Stop-Process -Id $backend.Id -Force
Write-Output "Served version $($health.version) without Python"

# A task that runs another copy (the runner folder, say) outlives the uninstaller.
Set-Task "C:\runner\.venv\Scripts\pythonw.exe"
Uninstall-App
if (-not (Test-Task)) { throw "The uninstaller removed a task it does not own" }
Write-Output "Another copy's task was kept"

# The app's own task goes with the app; its data stays.
Install-App
Set-Task $Engine
Uninstall-App
if (Test-Task) { throw "The uninstaller left the app's task behind" }
if (-not (Test-Path (Join-Path $data "config.toml"))) { throw "The uninstaller removed the data" }
Write-Output "The app's task was removed and the data kept"
