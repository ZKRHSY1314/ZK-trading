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

function Test-TrackedProcessIdentity {
    param([object]$Metadata)

    if (
        $null -eq $Metadata -or
        $null -eq $Metadata.pid -or
        -not $Metadata.created_at -or
        -not $Metadata.executable_path -or
        -not $Metadata.command_line -or
        -not $Metadata.command_marker
    ) {
        return $false
    }
    $row = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$Metadata.pid)"
    if ($null -eq $row -or -not $row.ExecutablePath -or -not $row.CommandLine) {
        return $false
    }
    $actualCreatedAt = ([DateTime]$row.CreationDate).ToUniversalTime()
    $expectedCreatedAt = [DateTimeOffset]::Parse([string]$Metadata.created_at).UtcDateTime
    $actualExecutable = [IO.Path]::GetFullPath([string]$row.ExecutablePath)
    $expectedExecutable = [IO.Path]::GetFullPath([string]$Metadata.executable_path)
    return (
        [Math]::Abs(($actualCreatedAt - $expectedCreatedAt).TotalSeconds) -le 5 -and
        $actualExecutable.Equals($expectedExecutable, [StringComparison]::OrdinalIgnoreCase) -and
        [string]$row.CommandLine -eq [string]$Metadata.command_line -and
        ([string]$row.CommandLine).Contains([string]$Metadata.command_marker)
    )
}

function Get-HealthyStack {
    try {
        $health = Invoke-RestMethod -Uri "$ApiBase/health" -TimeoutSec 3
        if ($health.live_trading_enabled -ne $false) {
            throw "Unsafe backend detected: live_trading_enabled is not false."
        }
        $ready = Invoke-RestMethod -Uri "$ApiBase/readyz" -TimeoutSec 3
        $frontend = Invoke-WebRequest -Uri $FrontendBase -UseBasicParsing -TimeoutSec 3
        if (-not (Test-Path -LiteralPath $PidFile -PathType Leaf)) {
            return [ordered]@{ healthy = $false; reason = "tracked_pid_metadata_missing" }
        }
        $metadata = Get-Content -Raw -Encoding UTF8 -LiteralPath $PidFile | ConvertFrom-Json
        $controlHeartbeat = $ready.workers.control_plane
        $codexHeartbeat = $ready.workers.codex_market_pulse
        $controlHealthy = (
            (Test-TrackedProcessIdentity -Metadata $metadata.control_worker) -and
            $controlHeartbeat.status -notin @("missing", "invalid", "stale")
        )
        $codexHealthy = (
            -not $EnableCodexSearch -or
            (
                (Test-TrackedProcessIdentity -Metadata $metadata.codex_market_pulse) -and
                $codexHeartbeat.status -notin @("missing", "invalid", "stale")
            )
        )
        if (
            $ready.status -eq "ready" -and
            $frontend.StatusCode -ge 200 -and
            $frontend.StatusCode -lt 400 -and
            $controlHealthy -and
            $codexHealthy
        ) {
            return [ordered]@{
                healthy = $true
                health = $health
                ready = $ready
                frontend_status = $frontend.StatusCode
                control_worker_healthy = $controlHealthy
                codex_market_pulse_healthy = $codexHealthy
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
