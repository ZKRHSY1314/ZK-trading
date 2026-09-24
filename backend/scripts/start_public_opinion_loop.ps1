param(
    [int]$IntervalSeconds = 900,
    [int]$Limit = 60,
    [string]$ApiBase = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
$Database = Join-Path $ProjectRoot "trading_local.sqlite3"

$env:PYTHONUTF8 = "1"
$env:DATABASE_PATH = $Database
$env:ENABLE_LIVE_TRADING = "false"

& $Python (Join-Path $ProjectRoot "backend\scripts\automation_loop.py") `
    --api-base $ApiBase `
    --mode public-opinion-capture `
    --interval-seconds $IntervalSeconds `
    --max-cycles 0 `
    --limit $Limit `
    --continue-on-error
