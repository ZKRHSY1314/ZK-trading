$ErrorActionPreference = "Stop"

$BackendRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $BackendRoot ".venv\Scripts\python.exe"
$Loop = Join-Path $BackendRoot "scripts\automation_loop.py"

if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found: $Python"
}

& $Python $Loop `
    --mode cycle `
    --api-base "http://127.0.0.1:8000" `
    --interval-seconds 300 `
    --max-cycles 0 `
    --limit 8 `
    --monitor-limit 5 `
    --review-symbol "SZ002081" `
    --continue-on-error
