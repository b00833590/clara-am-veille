$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "run_$(Get-Date -Format 'yyyyMMdd').log"

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logFile -Value "=== Run started at $timestamp ==="

& "$PSScriptRoot\.venv\Scripts\python.exe" "$PSScriptRoot\main.py" *>> $logFile

Add-Content -Path $logFile -Value "=== Run finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="
