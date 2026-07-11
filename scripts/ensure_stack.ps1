[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [int]$StartupTimeoutSeconds = 45,
    [bool]$EnableCodexSearch = $true
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RunScript = Join-Path $PSScriptRoot "run_stack.ps1"
$StopScript = Join-Path $PSScriptRoot "stop_stack.ps1"
$PidFile = Join-Path $ProjectRoot "logs\run_stack.pids.json"
$ApiBase = "http://127.0.0.1:$BackendPort"
$FrontendBase = "http://127.0.0.1:$FrontendPort"

function Get-HealthyStack {
    try {
        $health = Invoke-RestMethod -Uri "$ApiBase/health" -TimeoutSec 3
        if ($health.live_trading_enabled -ne $false) {
            throw "Unsafe backend detected: live_trading_enabled is not false."
        }
        $ready = Invoke-RestMethod -Uri "$ApiBase/readyz" -TimeoutSec 3
        $frontend = Invoke-WebRequest -Uri $FrontendBase -UseBasicParsing -TimeoutSec 3
        if ($ready.status -eq "ready" -and $frontend.StatusCode -ge 200 -and $frontend.StatusCode -lt 400) {
            return [ordered]@{
                healthy = $true
                health = $health
                ready = $ready
                frontend_status = $frontend.StatusCode
            }
        }
    }
    catch {
        if ($_.Exception.Message -like "Unsafe backend detected:*") {
            throw
        }
    }
    return [ordered]@{ healthy = $false }
}

$current = Get-HealthyStack
if ($current.healthy) {
    [ordered]@{
        schema_version = "ensure_stack.v1"
        status = "already_running"
        checked_at = [DateTimeOffset]::Now.ToString("o")
        live_trading_enabled = $false
        backend = $ApiBase
        frontend = $FrontendBase
    } | ConvertTo-Json -Depth 5
    exit 0
}

if (Test-Path -LiteralPath $PidFile -PathType Leaf) {
    try {
        & $StopScript | Out-Null
    }
    catch {
        throw "Tracked stack is unhealthy and could not be stopped safely: $($_.Exception.Message)"
    }
}

$env:ENABLE_LIVE_TRADING = "false"
& $RunScript `
    -BackendPort $BackendPort `
    -FrontendPort $FrontendPort `
    -StartupTimeoutSeconds $StartupTimeoutSeconds `
    -EnableCodexSearch:$EnableCodexSearch

if ($LASTEXITCODE -ne 0) {
    throw "run_stack.ps1 failed with exit code $LASTEXITCODE"
}

$started = Get-HealthyStack
if (-not $started.healthy) {
    throw "Stack startup returned without reaching healthy review-only state."
}

[ordered]@{
    schema_version = "ensure_stack.v1"
    status = "started"
    checked_at = [DateTimeOffset]::Now.ToString("o")
    live_trading_enabled = $false
    backend = $ApiBase
    frontend = $FrontendBase
} | ConvertTo-Json -Depth 5
