# Run by build.bat: copies the widget it just built to ..\@ActiveInProduction\UsageWidget, the owner's live folder.
# Only from main, so a feature branch or worktree never replaces production, and only if that folder's parent exists.
# The widget is closed politely (no /F): a force-killed one-file exe leaves its unpacked copy behind in %TEMP%.
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$from = Join-Path $repo 'dist\UsageWidget\UsageWidget.exe'
$live = Join-Path (Split-Path $repo -Parent) '@ActiveInProduction'
$dir = Join-Path $live 'UsageWidget'
$to = Join-Path $dir 'UsageWidget.exe'

if (-not (Test-Path -LiteralPath $live)) { exit 0 }
$branch = & git -C $repo rev-parse --abbrev-ref HEAD
if ($branch -ne 'main') {
    Write-Host "On $branch, not main: not copying the widget to production."
    exit 0
}

function Get-Live { @(Get-Process UsageWidget -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $to }) }
$running = Get-Live
foreach ($p in $running) { & cmd /c "taskkill /PID $($p.Id) >nul 2>nul" }
for ($i = 0; $i -lt 50 -and (Get-Live); $i++) { Start-Sleep -Milliseconds 200 }
if (Get-Live) { throw 'The production UsageWidget did not close; close it and build again.' }

New-Item -ItemType Directory -Force $dir | Out-Null
Copy-Item -LiteralPath $from -Destination $to -Force
if ((Get-FileHash -LiteralPath $from).Hash -ne (Get-FileHash -LiteralPath $to).Hash) { throw 'The copy of UsageWidget.exe differs.' }
Write-Host "Copied to $to"
if ($running) {
    Start-Process -FilePath $to
    Write-Host 'Started it again.'
}
