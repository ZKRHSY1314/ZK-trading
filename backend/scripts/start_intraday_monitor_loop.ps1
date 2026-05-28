param(
    [int]$IntervalSeconds = 60,

    [int]$Limit = 5
)

$ErrorActionPreference = "Stop"
$BackendRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $BackendRoot

& ".\.venv\Scripts\python.exe" -X utf8 "scripts\automation_loop.py" `
    --mode monitor `
    --max-cycles 0 `
    --interval-seconds $IntervalSeconds `
    --limit $Limit `
    --continue-on-error
