[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [int]$StartupTimeoutSeconds = 45,
    [bool]$EnableCodexSearch = $true,
    [string]$TonghuasunProfile = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendRoot = Join-Path $ProjectRoot "backend"
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$LogsRoot = Join-Path $ProjectRoot "logs"
$DatabasePath = Join-Path $ProjectRoot "trading_local.sqlite3"
$Python = Join-Path $BackendRoot ".venv\Scripts\python.exe"
$WorkerScript = Join-Path $BackendRoot "scripts\control_plane_loop.py"
$ReferenceWorkerScript = Join-Path $BackendRoot "scripts\reference_data_loop.py"
$FullMarketFeatureScript = Join-Path $BackendRoot "scripts\full_market_feature_loop.py"
$MarketHistoryRefreshScript = Join-Path $BackendRoot "scripts\market_history_refresh_loop.py"
$CapitalFlowRefreshScript = Join-Path $BackendRoot "scripts\capital_flow_refresh_loop.py"
$InstrumentCatalogScript = Join-Path $BackendRoot "scripts\instrument_catalog_refresh_loop.py"
$FullMarketCalibrationScript = Join-Path $BackendRoot "scripts\full_market_calibration_loop.py"
$CodexPulseScript = Join-Path $BackendRoot "scripts\codex_market_pulse.py"
$CodexDecisionScript = Join-Path $BackendRoot "scripts\codex_decision_review.py"
$ViteCommand = Join-Path $FrontendRoot "node_modules\.bin\vite.cmd"
$ViteEntry = Join-Path $FrontendRoot "node_modules\vite\bin\vite.js"
$PidFile = Join-Path $LogsRoot "run_stack.pids.json"
$HeartbeatFile = Join-Path $BackendRoot "logs\control_plane_heartbeat.json"
$ReferenceHeartbeatFile = Join-Path $BackendRoot "logs\reference_data_heartbeat.json"
$FullMarketFeatureHeartbeatFile = Join-Path $BackendRoot "logs\full_market_feature_heartbeat.json"
$MarketHistoryRefreshHeartbeatFile = Join-Path $BackendRoot "logs\market_history_refresh_heartbeat.json"
$CapitalFlowRefreshHeartbeatFile = Join-Path $BackendRoot "logs\capital_flow_refresh_heartbeat.json"
$InstrumentCatalogHeartbeatFile = Join-Path $BackendRoot "logs\instrument_catalog_refresh_heartbeat.json"
$FullMarketCalibrationHeartbeatFile = Join-Path $BackendRoot "logs\full_market_calibration_heartbeat.json"
$CodexDecisionHeartbeatFile = Join-Path $BackendRoot "logs\codex_decision_review_heartbeat.json"
$ApiBase = "http://127.0.0.1:$BackendPort"
$FrontendBase = "http://127.0.0.1:$FrontendPort"
$CodexPulseModel = "gpt-5.5"
$CodexPulseReasoningEffort = "medium"

. (Join-Path $PSScriptRoot "tonghuasun_readonly.ps1")
$TonghuasunReadOnly = Get-TonghuasunReadOnlyContext -ProfilePath $TonghuasunProfile
if ($TonghuasunReadOnly.host_status -eq "not_running") {
    Write-Warning "Tonghuashun is not running. The stack keeps akshare_first; start the client explicitly with scripts\start_tonghuasun_readonly.ps1 when needed."
}

function Assert-FileExists {
    param([string]$LiteralPath, [string]$Label)

    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        throw "$Label not found: $LiteralPath"
    }
}

function Test-ListeningPort {
    param([int]$Port)

    return @(
        Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    ).Count -gt 0
}

function Wait-JsonEndpoint {
    param([string]$Uri, [int]$TimeoutSeconds)

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $lastError = $null
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            return Invoke-RestMethod -Uri $Uri -TimeoutSec 3
        }
        catch {
            $lastError = $_.Exception.Message
            Start-Sleep -Seconds 1
        }
    }
    throw "Timed out waiting for $Uri. Last error: $lastError"
}

function Wait-HttpEndpoint {
    param([string]$Uri, [int]$TimeoutSeconds)

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $lastError = $null
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                return
            }
        }
        catch {
            $lastError = $_.Exception.Message
            Start-Sleep -Seconds 1
        }
    }
    throw "Timed out waiting for $Uri. Last error: $lastError"
}

function Test-RootOrDescendantProcess {
    param([int]$RootProcessId, [int]$CandidateProcessId)

    if ($CandidateProcessId -eq $RootProcessId) {
        return $true
    }
    $rows = @(Get-CimInstance Win32_Process)
    $byId = @{}
    foreach ($row in $rows) {
        $byId[[int]$row.ProcessId] = [int]$row.ParentProcessId
    }
    $visited = [System.Collections.Generic.HashSet[int]]::new()
    $current = $CandidateProcessId
    while ($byId.ContainsKey($current) -and $visited.Add($current)) {
        $current = [int]$byId[$current]
        if ($current -eq $RootProcessId) {
            return $true
        }
    }
    return $false
}

function Wait-WorkerHeartbeat {
    param([string]$LiteralPath, [int]$ExpectedPid, [int]$TimeoutSeconds)

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $LiteralPath -PathType Leaf) {
            try {
                $heartbeat = Get-Content -Raw -Encoding UTF8 -LiteralPath $LiteralPath | ConvertFrom-Json
                $heartbeatPid = [int]$heartbeat.pid
                if (Test-RootOrDescendantProcess -RootProcessId $ExpectedPid -CandidateProcessId $heartbeatPid) {
                    return $heartbeat
                }
            }
            catch {
                # The worker replaces the heartbeat atomically; retry partial reads.
            }
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Timed out waiting for worker heartbeat: $LiteralPath"
}

function Get-StartedProcessMetadata {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$CommandMarker
    )

    $row = Get-CimInstance Win32_Process -Filter "ProcessId = $($Process.Id)"
    if ($null -eq $row -or -not $row.ExecutablePath -or -not $row.CommandLine) {
        throw "Unable to capture process identity for PID $($Process.Id)."
    }
    return [ordered]@{
        pid = $Process.Id
        executable_path = [IO.Path]::GetFullPath([string]$row.ExecutablePath)
        command_line = [string]$row.CommandLine
        command_marker = $CommandMarker
        created_at = ([DateTime]$row.CreationDate).ToUniversalTime().ToString("o")
    }
}

function Stop-StartedProcessTree {
    param([int]$RootProcessId)

    # Snapshot descendants while the launcher still exists.  Stopping the
    # launcher first reparents its Python/Node child on Windows, which can
    # otherwise leave an untracked backend holding the port after startup
    # fails.
    $rows = @(Get-CimInstance Win32_Process)
    $targets = [System.Collections.Generic.List[int]]::new()
    $queue = [System.Collections.Generic.Queue[int]]::new()
    $queue.Enqueue($RootProcessId)
    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        foreach ($child in $rows | Where-Object { [int]$_.ParentProcessId -eq $current }) {
            $childPid = [int]$child.ProcessId
            if (-not $targets.Contains($childPid)) {
                $targets.Add($childPid)
                $queue.Enqueue($childPid)
            }
        }
    }

    # Stop the launcher first so it cannot create another child, then stop the
    # already captured descendants from the leaves upward.
    Stop-Process -Id $RootProcessId -Force -ErrorAction SilentlyContinue
    for ($index = $targets.Count - 1; $index -ge 0; $index--) {
        Stop-Process -Id $targets[$index] -Force -ErrorAction SilentlyContinue
    }

    $allTargets = @($RootProcessId) + @($targets)
    $deadline = [DateTime]::UtcNow.AddSeconds(3)
    do {
        $remaining = @(
            foreach ($processId in $allTargets) {
                Get-Process -Id $processId -ErrorAction SilentlyContinue
            }
        )
        if ($remaining.Count -eq 0 -or [DateTime]::UtcNow -ge $deadline) {
            break
        }
        foreach ($process in $remaining) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 100
    } while ($true)
}

function Test-TrackedProcessIdentity {
    param([object]$Metadata)

    if (
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

Assert-FileExists -LiteralPath $DatabasePath -Label "Repository-root database"
Assert-FileExists -LiteralPath $Python -Label "Backend Python runtime"
Assert-FileExists -LiteralPath $WorkerScript -Label "Control-plane worker"
Assert-FileExists -LiteralPath $ReferenceWorkerScript -Label "Reference-data worker"
Assert-FileExists -LiteralPath $FullMarketFeatureScript -Label "Full-market feature worker"
Assert-FileExists -LiteralPath $MarketHistoryRefreshScript -Label "Market-history refresh worker"
Assert-FileExists -LiteralPath $CapitalFlowRefreshScript -Label "Capital-flow refresh worker"
Assert-FileExists -LiteralPath $InstrumentCatalogScript -Label "Instrument-catalog refresh worker"
Assert-FileExists -LiteralPath $FullMarketCalibrationScript -Label "Full-market calibration worker"
if ($EnableCodexSearch) {
    Assert-FileExists -LiteralPath $CodexPulseScript -Label "Codex market-pulse worker"
    Assert-FileExists -LiteralPath $CodexDecisionScript -Label "Codex decision-review worker"
}
Assert-FileExists -LiteralPath $ViteCommand -Label "Frontend Vite dependency"
Assert-FileExists -LiteralPath $ViteEntry -Label "Frontend Vite runtime"

$NpmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($null -eq $NpmCommand) {
    throw "npm.cmd is not available on PATH."
}
$NodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if ($null -eq $NodeCommand) {
    throw "node.exe is not available on PATH."
}
$CodexCommand = Get-Command codex -ErrorAction SilentlyContinue
if ($EnableCodexSearch -and $null -eq $CodexCommand) {
    throw "codex is not available on PATH; use -EnableCodexSearch:`$false to run fixed-source capture only."
}

$configuredLive = [string]$env:ENABLE_LIVE_TRADING
if ($configuredLive -and $configuredLive.Trim().ToLowerInvariant() -notin @("false", "0", "no", "off")) {
    throw "ENABLE_LIVE_TRADING must be false before starting the stack."
}

if (Test-ListeningPort -Port $BackendPort) {
    throw "Backend port $BackendPort is already in use. Stop the existing process or choose another port."
}
if (Test-ListeningPort -Port $FrontendPort) {
    throw "Frontend port $FrontendPort is already in use. Stop the existing process or choose another port."
}

if (Test-Path -LiteralPath $PidFile -PathType Leaf) {
    $previous = Get-Content -Raw -Encoding UTF8 -LiteralPath $PidFile | ConvertFrom-Json
    $liveTracked = @(
        foreach ($component in @(
            $previous.backend,
            $previous.frontend,
            $previous.control_worker,
            $previous.reference_data_worker,
            $previous.full_market_feature_worker,
            $previous.market_history_refresh_worker,
            $previous.capital_flow_refresh_worker,
            $previous.instrument_catalog_refresh_worker,
            $previous.full_market_calibration_worker,
            $previous.codex_market_pulse,
            $previous.codex_decision_review
        )) {
            if ($null -ne $component.pid -and (Test-TrackedProcessIdentity -Metadata $component)) {
                Get-Process -Id ([int]$component.pid) -ErrorAction SilentlyContinue
            }
        }
    )
    if ($liveTracked.Count -gt 0) {
        $ids = ($liveTracked | ForEach-Object Id) -join ", "
        throw "A tracked stack is still running (PID: $ids). Run scripts\stop_stack.ps1 first."
    }
}

& $Python -c "import fastapi, uvicorn" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Backend dependencies are incomplete."
}
& $NpmCommand.Source --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "npm dependency check failed."
}

New-Item -ItemType Directory -Path $LogsRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $HeartbeatFile) -Force | Out-Null

$env:PYTHONUTF8 = "1"
$env:DATABASE_PATH = $DatabasePath
$env:ENABLE_LIVE_TRADING = "false"
$env:TRADING_API_BASE = $ApiBase
$env:TRADING_WEB_URL = $FrontendBase

$startedProcesses = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()
$priorTonghuasunDirectory = [Environment]::GetEnvironmentVariable("TONGHUASUN_AGENT_HOME", "Process")
$priorDailyBarPolicy = [Environment]::GetEnvironmentVariable("DAILY_BAR_SOURCE_POLICY", "Process")
try {
    $env:TONGHUASUN_AGENT_HOME = $TonghuasunReadOnly.product_home
    $env:DAILY_BAR_SOURCE_POLICY = "akshare_first"
    $backendArgs = @(
        "-X", "utf8", "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1", "--port", [string]$BackendPort
    )
    $backend = Start-Process -FilePath $Python -ArgumentList $backendArgs `
        -WorkingDirectory $BackendRoot `
        -RedirectStandardOutput (Join-Path $LogsRoot "backend.out.log") `
        -RedirectStandardError (Join-Path $LogsRoot "backend.err.log") `
        -WindowStyle Hidden -PassThru
    $startedProcesses.Add($backend)

    $health = Wait-JsonEndpoint -Uri "$ApiBase/health" -TimeoutSeconds $StartupTimeoutSeconds
    if ($health.live_trading_enabled -ne $false) {
        throw "Backend safety gate failed: /health.live_trading_enabled is not false."
    }
    $ready = Wait-JsonEndpoint -Uri "$ApiBase/readyz" -TimeoutSeconds $StartupTimeoutSeconds
    if ($ready.status -ne "ready" -or $ready.live_trading_enabled -ne $false) {
        throw "Backend readiness gate failed: $($ready | ConvertTo-Json -Compress)"
    }

    $frontendArgs = @(
        $ViteEntry, "--host", "127.0.0.1",
        "--port", [string]$FrontendPort, "--strictPort"
    )
    $frontend = Start-Process -FilePath $NodeCommand.Source -ArgumentList $frontendArgs `
        -WorkingDirectory $FrontendRoot `
        -RedirectStandardOutput (Join-Path $LogsRoot "frontend.out.log") `
        -RedirectStandardError (Join-Path $LogsRoot "frontend.err.log") `
        -WindowStyle Hidden -PassThru
    $startedProcesses.Add($frontend)
    Wait-HttpEndpoint -Uri $FrontendBase -TimeoutSeconds $StartupTimeoutSeconds

    $workerArgs = @(
        "-X", "utf8", $WorkerScript,
        "--api-base", $ApiBase,
        "--profile", "adaptive",
        "--interval-seconds", "900",
        "--max-cycles", "0"
    )
    $worker = Start-Process -FilePath $Python -ArgumentList $workerArgs `
        -WorkingDirectory $BackendRoot `
        -RedirectStandardOutput (Join-Path $LogsRoot "control-worker.out.log") `
        -RedirectStandardError (Join-Path $LogsRoot "control-worker.err.log") `
        -WindowStyle Hidden -PassThru
    $startedProcesses.Add($worker)
    Start-Sleep -Milliseconds 500
    if ($worker.HasExited) {
        throw "Control-plane worker exited during startup with code $($worker.ExitCode)."
    }
    $workerHeartbeat = Wait-WorkerHeartbeat -LiteralPath $HeartbeatFile -ExpectedPid $worker.Id `
        -TimeoutSeconds $StartupTimeoutSeconds

    $referenceArgs = @(
        "-X", "utf8", $ReferenceWorkerScript,
        "--interval-seconds", "14400",
        "--max-cycles", "0",
        "--board-limit", "50",
        "--disclosure-limit", "500",
        "--global-days", "30",
        "--rate-limit-seconds", "0.2",
        "--cycle-timeout-seconds", "900",
        "--skip-sox"
    )
    $referenceWorker = Start-Process -FilePath $Python -ArgumentList $referenceArgs `
        -WorkingDirectory $BackendRoot `
        -RedirectStandardOutput (Join-Path $LogsRoot "reference-data-worker.out.log") `
        -RedirectStandardError (Join-Path $LogsRoot "reference-data-worker.err.log") `
        -WindowStyle Hidden -PassThru
    $startedProcesses.Add($referenceWorker)
    Start-Sleep -Milliseconds 500
    if ($referenceWorker.HasExited) {
        throw "Reference-data worker exited during startup with code $($referenceWorker.ExitCode)."
    }
    $referenceHeartbeat = Wait-WorkerHeartbeat `
        -LiteralPath $ReferenceHeartbeatFile `
        -ExpectedPid $referenceWorker.Id `
        -TimeoutSeconds $StartupTimeoutSeconds

    $fullMarketFeatureArgs = @(
        "-X", "utf8", $FullMarketFeatureScript,
        "--api-base", $ApiBase,
        "--interval-seconds", "14400",
        "--max-cycles", "0",
        "--candidate-limit", "300",
        "--lookback-bars", "120",
        "--timeout-seconds", "300"
    )
    $fullMarketFeatureWorker = Start-Process -FilePath $Python `
        -ArgumentList $fullMarketFeatureArgs `
        -WorkingDirectory $BackendRoot `
        -RedirectStandardOutput (Join-Path $LogsRoot "full-market-feature-worker.out.log") `
        -RedirectStandardError (Join-Path $LogsRoot "full-market-feature-worker.err.log") `
        -WindowStyle Hidden -PassThru
    $startedProcesses.Add($fullMarketFeatureWorker)
    Start-Sleep -Milliseconds 500
    if ($fullMarketFeatureWorker.HasExited) {
        throw "Full-market feature worker exited during startup with code $($fullMarketFeatureWorker.ExitCode)."
    }
    $fullMarketFeatureHeartbeat = Wait-WorkerHeartbeat `
        -LiteralPath $FullMarketFeatureHeartbeatFile `
        -ExpectedPid $fullMarketFeatureWorker.Id `
        -TimeoutSeconds $StartupTimeoutSeconds

    $marketHistoryRefreshArgs = @(
        "-X", "utf8", $MarketHistoryRefreshScript,
        "--api-base", $ApiBase,
        "--interval-seconds", "14400",
        "--retry-interval-seconds", "900",
        "--max-cycles", "0",
        "--days", "150",
        "--batch-size", "200",
        "--max-workers", "20",
        "--seed-batch-size", "500",
        "--gap-recovery-limit", "500",
        "--deadline-seconds", "900"
    )
    $marketHistoryRefreshWorker = Start-Process -FilePath $Python `
        -ArgumentList $marketHistoryRefreshArgs `
        -WorkingDirectory $BackendRoot `
        -RedirectStandardOutput (Join-Path $LogsRoot "market-history-refresh-worker.out.log") `
        -RedirectStandardError (Join-Path $LogsRoot "market-history-refresh-worker.err.log") `
        -WindowStyle Hidden -PassThru
    $startedProcesses.Add($marketHistoryRefreshWorker)
    Start-Sleep -Milliseconds 500
    if ($marketHistoryRefreshWorker.HasExited) {
        throw "Market-history refresh worker exited during startup with code $($marketHistoryRefreshWorker.ExitCode)."
    }
    $marketHistoryRefreshHeartbeat = Wait-WorkerHeartbeat `
        -LiteralPath $MarketHistoryRefreshHeartbeatFile `
        -ExpectedPid $marketHistoryRefreshWorker.Id `
        -TimeoutSeconds $StartupTimeoutSeconds
    if (
        [int]$marketHistoryRefreshHeartbeat.interval_seconds -ne 14400 -or
        [int]$marketHistoryRefreshHeartbeat.retry_interval_seconds -ne 900 -or
        [int]$marketHistoryRefreshHeartbeat.deadline_seconds -ne 900 -or
        [int]$marketHistoryRefreshHeartbeat.days -ne 150 -or
        [int]$marketHistoryRefreshHeartbeat.batch_size -ne 200 -or
        [int]$marketHistoryRefreshHeartbeat.max_workers -ne 20 -or
        [int]$marketHistoryRefreshHeartbeat.seed_batch_size -ne 500 -or
        [int]$marketHistoryRefreshHeartbeat.gap_recovery_limit -ne 500 -or
        $marketHistoryRefreshHeartbeat.review_only -ne $true -or
        $marketHistoryRefreshHeartbeat.simulation_only -ne $true -or
        $marketHistoryRefreshHeartbeat.live_trading_enabled -ne $false
    ) {
        throw "Market-history refresh worker started with an unexpected or unsafe configuration."
    }

    $capitalFlowRefreshArgs = @(
        "-X", "utf8", $CapitalFlowRefreshScript,
        "--api-base", $ApiBase,
        "--interval-seconds", "900",
        "--retry-seconds", "300",
        "--max-cycles", "0"
    )
    $capitalFlowRefreshWorker = Start-Process -FilePath $Python `
        -ArgumentList $capitalFlowRefreshArgs `
        -WorkingDirectory $BackendRoot `
        -RedirectStandardOutput (Join-Path $LogsRoot "capital-flow-refresh-worker.out.log") `
        -RedirectStandardError (Join-Path $LogsRoot "capital-flow-refresh-worker.err.log") `
        -WindowStyle Hidden -PassThru
    $startedProcesses.Add($capitalFlowRefreshWorker)
    Start-Sleep -Milliseconds 500
    if ($capitalFlowRefreshWorker.HasExited) {
        throw "Capital-flow refresh worker exited during startup with code $($capitalFlowRefreshWorker.ExitCode)."
    }
    $capitalFlowRefreshHeartbeat = Wait-WorkerHeartbeat `
        -LiteralPath $CapitalFlowRefreshHeartbeatFile `
        -ExpectedPid $capitalFlowRefreshWorker.Id `
        -TimeoutSeconds $StartupTimeoutSeconds
    if (
        [int]$capitalFlowRefreshHeartbeat.interval_seconds -ne 900 -or
        [int]$capitalFlowRefreshHeartbeat.retry_interval_seconds -ne 300 -or
        $capitalFlowRefreshHeartbeat.review_only -ne $true -or
        $capitalFlowRefreshHeartbeat.simulation_only -ne $true -or
        $capitalFlowRefreshHeartbeat.live_trading_enabled -ne $false
    ) {
        throw "Capital-flow refresh worker started with an unexpected or unsafe configuration."
    }

    $instrumentCatalogArgs = @(
        "-X", "utf8", $InstrumentCatalogScript,
        "--api-base", $ApiBase,
        "--interval-seconds", "86400",
        "--retry-seconds", "900",
        "--minimum-member-count", "4000",
        "--minimum-retained-ratio", "0.9"
    )
    $instrumentCatalogWorker = Start-Process -FilePath $Python `
        -ArgumentList $instrumentCatalogArgs `
        -WorkingDirectory $BackendRoot `
        -RedirectStandardOutput (Join-Path $LogsRoot "instrument-catalog-refresh-worker.out.log") `
        -RedirectStandardError (Join-Path $LogsRoot "instrument-catalog-refresh-worker.err.log") `
        -WindowStyle Hidden -PassThru
    $startedProcesses.Add($instrumentCatalogWorker)
    Start-Sleep -Milliseconds 500
    if ($instrumentCatalogWorker.HasExited) {
        throw "Instrument-catalog refresh worker exited during startup with code $($instrumentCatalogWorker.ExitCode)."
    }
    $instrumentCatalogHeartbeat = Wait-WorkerHeartbeat `
        -LiteralPath $InstrumentCatalogHeartbeatFile `
        -ExpectedPid $instrumentCatalogWorker.Id `
        -TimeoutSeconds $StartupTimeoutSeconds
    if (
        [int]$instrumentCatalogHeartbeat.interval_seconds -ne 86400 -or
        [int]$instrumentCatalogHeartbeat.retry_interval_seconds -ne 900 -or
        [int]$instrumentCatalogHeartbeat.minimum_member_count -ne 4000 -or
        [double]$instrumentCatalogHeartbeat.minimum_retained_ratio -ne 0.9 -or
        $instrumentCatalogHeartbeat.review_only -ne $true -or
        $instrumentCatalogHeartbeat.simulation_only -ne $true -or
        $instrumentCatalogHeartbeat.live_trading_enabled -ne $false
    ) {
        throw "Instrument-catalog refresh worker started with an unexpected or unsafe configuration."
    }

    $fullMarketCalibrationArgs = @(
        "-X", "utf8", $FullMarketCalibrationScript,
        "--api-base", $ApiBase,
        "--interval-seconds", "86400",
        "--retry-seconds", "1800",
        "--deadline-seconds", "900",
        "--max-cycles", "0"
    )
    $fullMarketCalibrationWorker = Start-Process -FilePath $Python `
        -ArgumentList $fullMarketCalibrationArgs `
        -WorkingDirectory $BackendRoot `
        -RedirectStandardOutput (Join-Path $LogsRoot "full-market-calibration-worker.out.log") `
        -RedirectStandardError (Join-Path $LogsRoot "full-market-calibration-worker.err.log") `
        -WindowStyle Hidden -PassThru
    $startedProcesses.Add($fullMarketCalibrationWorker)
    Start-Sleep -Milliseconds 500
    if ($fullMarketCalibrationWorker.HasExited) {
        throw "Full-market calibration worker exited during startup with code $($fullMarketCalibrationWorker.ExitCode)."
    }
    $fullMarketCalibrationHeartbeat = Wait-WorkerHeartbeat `
        -LiteralPath $FullMarketCalibrationHeartbeatFile `
        -ExpectedPid $fullMarketCalibrationWorker.Id `
        -TimeoutSeconds $StartupTimeoutSeconds
    if (
        [int]$fullMarketCalibrationHeartbeat.interval_seconds -ne 86400 -or
        [int]$fullMarketCalibrationHeartbeat.retry_interval_seconds -ne 1800 -or
        [int]$fullMarketCalibrationHeartbeat.deadline_seconds -ne 900 -or
        $fullMarketCalibrationHeartbeat.review_only -ne $true -or
        $fullMarketCalibrationHeartbeat.simulation_only -ne $true -or
        $fullMarketCalibrationHeartbeat.live_trading_enabled -ne $false
    ) {
        throw "Full-market calibration worker started with an unexpected or unsafe configuration."
    }

    $codexPulse = $null
    $codexPulseHeartbeat = $null
    $codexDecision = $null
    $codexDecisionHeartbeat = $null
    if ($EnableCodexSearch) {
        $codexPulseArgs = @(
            "-X", "utf8", $CodexPulseScript,
            "--api-base", $ApiBase,
            "--interval-seconds", "14400",
            "--max-cycles", "0",
            "--timeout-seconds", "900",
            "--model", $CodexPulseModel,
            "--reasoning-effort", $CodexPulseReasoningEffort
        )
        $codexPulse = Start-Process -FilePath $Python -ArgumentList $codexPulseArgs `
            -WorkingDirectory $BackendRoot `
            -RedirectStandardOutput (Join-Path $LogsRoot "codex-market-pulse.out.log") `
            -RedirectStandardError (Join-Path $LogsRoot "codex-market-pulse.err.log") `
            -WindowStyle Hidden -PassThru
        $startedProcesses.Add($codexPulse)
        Start-Sleep -Milliseconds 500
        if ($codexPulse.HasExited) {
            throw "Codex market-pulse worker exited during startup with code $($codexPulse.ExitCode)."
        }
        $codexPulseHeartbeat = Wait-WorkerHeartbeat `
            -LiteralPath (Join-Path $BackendRoot "logs\codex_market_pulse_heartbeat.json") `
            -ExpectedPid $codexPulse.Id `
            -TimeoutSeconds $StartupTimeoutSeconds
        if (
            [string]$codexPulseHeartbeat.configured_model -ne $CodexPulseModel -or
            [string]$codexPulseHeartbeat.reasoning_effort -ne $CodexPulseReasoningEffort
        ) {
            throw "Codex market-pulse worker started with an unexpected model profile."
        }

        $codexDecisionArgs = @(
            "-X", "utf8", $CodexDecisionScript,
            "--api-base", $ApiBase,
            "--interval-seconds", "14400",
            "--max-cycles", "0",
            "--timeout-seconds", "900",
            "--model", $CodexPulseModel,
            "--reasoning-effort", $CodexPulseReasoningEffort
        )
        $codexDecision = Start-Process -FilePath $Python -ArgumentList $codexDecisionArgs `
            -WorkingDirectory $BackendRoot `
            -RedirectStandardOutput (Join-Path $LogsRoot "codex-decision-review.out.log") `
            -RedirectStandardError (Join-Path $LogsRoot "codex-decision-review.err.log") `
            -WindowStyle Hidden -PassThru
        $startedProcesses.Add($codexDecision)
        Start-Sleep -Milliseconds 500
        if ($codexDecision.HasExited) {
            throw "Codex decision-review worker exited during startup with code $($codexDecision.ExitCode)."
        }
        $codexDecisionHeartbeat = Wait-WorkerHeartbeat `
            -LiteralPath $CodexDecisionHeartbeatFile `
            -ExpectedPid $codexDecision.Id `
            -TimeoutSeconds $StartupTimeoutSeconds
        if (
            [string]$codexDecisionHeartbeat.configured_model -ne $CodexPulseModel -or
            [string]$codexDecisionHeartbeat.reasoning_effort -ne $CodexPulseReasoningEffort
        ) {
            throw "Codex decision-review worker started with an unexpected model profile."
        }
    }

    $backendMetadata = Get-StartedProcessMetadata -Process $backend -CommandMarker "app.main:app"
    $backendMetadata["url"] = $ApiBase
    $frontendMetadata = Get-StartedProcessMetadata -Process $frontend -CommandMarker $ViteEntry
    $frontendMetadata["url"] = $FrontendBase
    $workerMetadata = Get-StartedProcessMetadata -Process $worker -CommandMarker $WorkerScript
    $workerMetadata["profile"] = "adaptive"
    $workerMetadata["interval_seconds"] = 900
    $workerMetadata["heartbeat_path"] = $HeartbeatFile
    $workerMetadata["runtime_pid"] = [int]$workerHeartbeat.pid
    $referenceMetadata = Get-StartedProcessMetadata `
        -Process $referenceWorker `
        -CommandMarker $ReferenceWorkerScript
    $referenceMetadata["interval_seconds"] = 14400
    $referenceMetadata["heartbeat_path"] = $ReferenceHeartbeatFile
    $referenceMetadata["runtime_pid"] = [int]$referenceHeartbeat.pid
    $referenceMetadata["review_only"] = $true
    $fullMarketFeatureMetadata = Get-StartedProcessMetadata `
        -Process $fullMarketFeatureWorker `
        -CommandMarker $FullMarketFeatureScript
    $fullMarketFeatureMetadata["interval_seconds"] = 14400
    $fullMarketFeatureMetadata["timeout_seconds"] = 300
    $fullMarketFeatureMetadata["candidate_limit"] = 300
    $fullMarketFeatureMetadata["lookback_bars"] = 120
    $fullMarketFeatureMetadata["heartbeat_path"] = $FullMarketFeatureHeartbeatFile
    $fullMarketFeatureMetadata["runtime_pid"] = [int]$fullMarketFeatureHeartbeat.pid
    $fullMarketFeatureMetadata["review_only"] = $true
    $fullMarketFeatureMetadata["simulation_only"] = $true
    $marketHistoryRefreshMetadata = Get-StartedProcessMetadata `
        -Process $marketHistoryRefreshWorker `
        -CommandMarker $MarketHistoryRefreshScript
    $marketHistoryRefreshMetadata["interval_seconds"] = 14400
    $marketHistoryRefreshMetadata["retry_interval_seconds"] = 900
    $marketHistoryRefreshMetadata["deadline_seconds"] = 900
    $marketHistoryRefreshMetadata["days"] = 150
    $marketHistoryRefreshMetadata["batch_size"] = 200
    $marketHistoryRefreshMetadata["max_workers"] = 20
    $marketHistoryRefreshMetadata["seed_batch_size"] = 500
    $marketHistoryRefreshMetadata["gap_recovery_limit"] = 500
    $marketHistoryRefreshMetadata["heartbeat_path"] = $MarketHistoryRefreshHeartbeatFile
    $marketHistoryRefreshMetadata["runtime_pid"] = [int]$marketHistoryRefreshHeartbeat.pid
    $marketHistoryRefreshMetadata["review_only"] = $true
    $marketHistoryRefreshMetadata["simulation_only"] = $true
    $capitalFlowRefreshMetadata = Get-StartedProcessMetadata `
        -Process $capitalFlowRefreshWorker `
        -CommandMarker $CapitalFlowRefreshScript
    $capitalFlowRefreshMetadata["interval_seconds"] = 900
    $capitalFlowRefreshMetadata["retry_interval_seconds"] = 300
    $capitalFlowRefreshMetadata["heartbeat_path"] = $CapitalFlowRefreshHeartbeatFile
    $capitalFlowRefreshMetadata["runtime_pid"] = [int]$capitalFlowRefreshHeartbeat.pid
    $capitalFlowRefreshMetadata["review_only"] = $true
    $capitalFlowRefreshMetadata["simulation_only"] = $true
    $instrumentCatalogMetadata = Get-StartedProcessMetadata `
        -Process $instrumentCatalogWorker `
        -CommandMarker $InstrumentCatalogScript
    $instrumentCatalogMetadata["interval_seconds"] = 86400
    $instrumentCatalogMetadata["retry_interval_seconds"] = 900
    $instrumentCatalogMetadata["minimum_member_count"] = 4000
    $instrumentCatalogMetadata["minimum_retained_ratio"] = 0.9
    $instrumentCatalogMetadata["heartbeat_path"] = $InstrumentCatalogHeartbeatFile
    $instrumentCatalogMetadata["runtime_pid"] = [int]$instrumentCatalogHeartbeat.pid
    $instrumentCatalogMetadata["review_only"] = $true
    $instrumentCatalogMetadata["simulation_only"] = $true
    $fullMarketCalibrationMetadata = Get-StartedProcessMetadata `
        -Process $fullMarketCalibrationWorker `
        -CommandMarker $FullMarketCalibrationScript
    $fullMarketCalibrationMetadata["interval_seconds"] = 86400
    $fullMarketCalibrationMetadata["retry_interval_seconds"] = 1800
    $fullMarketCalibrationMetadata["deadline_seconds"] = 900
    $fullMarketCalibrationMetadata["heartbeat_path"] = $FullMarketCalibrationHeartbeatFile
    $fullMarketCalibrationMetadata["runtime_pid"] = [int]$fullMarketCalibrationHeartbeat.pid
    $fullMarketCalibrationMetadata["review_only"] = $true
    $fullMarketCalibrationMetadata["simulation_only"] = $true
    $codexMetadata = [ordered]@{
        enabled = $EnableCodexSearch
        model = $CodexPulseModel
        reasoning_effort = $CodexPulseReasoningEffort
    }
    if ($null -ne $codexPulse) {
        $codexMetadata = Get-StartedProcessMetadata -Process $codexPulse -CommandMarker $CodexPulseScript
        $codexMetadata["enabled"] = $true
        $codexMetadata["interval_seconds"] = 14400
        $codexMetadata["model"] = $CodexPulseModel
        $codexMetadata["reasoning_effort"] = $CodexPulseReasoningEffort
        $codexMetadata["heartbeat_path"] = Join-Path $BackendRoot "logs\codex_market_pulse_heartbeat.json"
        $codexMetadata["runtime_pid"] = [int]$codexPulseHeartbeat.pid
    }
    $codexDecisionMetadata = [ordered]@{
        enabled = $EnableCodexSearch
        model = $CodexPulseModel
        reasoning_effort = $CodexPulseReasoningEffort
    }
    if ($null -ne $codexDecision) {
        $codexDecisionMetadata = Get-StartedProcessMetadata `
            -Process $codexDecision `
            -CommandMarker $CodexDecisionScript
        $codexDecisionMetadata["enabled"] = $true
        $codexDecisionMetadata["interval_seconds"] = 14400
        $codexDecisionMetadata["model"] = $CodexPulseModel
        $codexDecisionMetadata["reasoning_effort"] = $CodexPulseReasoningEffort
        $codexDecisionMetadata["heartbeat_path"] = $CodexDecisionHeartbeatFile
        $codexDecisionMetadata["runtime_pid"] = [int]$codexDecisionHeartbeat.pid
        $codexDecisionMetadata["review_only"] = $true
    }

    $metadata = [ordered]@{
        schema_version = "run_stack_pids.v1"
        started_at = [DateTimeOffset]::Now.ToString("o")
        project_root = $ProjectRoot
        database_path = $DatabasePath
        live_trading_enabled = $false
        tonghuasun_readonly = $TonghuasunReadOnly
        backend = $backendMetadata
        frontend = $frontendMetadata
        control_worker = $workerMetadata
        reference_data_worker = $referenceMetadata
        full_market_feature_worker = $fullMarketFeatureMetadata
        market_history_refresh_worker = $marketHistoryRefreshMetadata
        capital_flow_refresh_worker = $capitalFlowRefreshMetadata
        instrument_catalog_refresh_worker = $instrumentCatalogMetadata
        full_market_calibration_worker = $fullMarketCalibrationMetadata
        codex_market_pulse = $codexMetadata
        codex_decision_review = $codexDecisionMetadata
    }
    $metadata | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $PidFile -Encoding UTF8
    $metadata | ConvertTo-Json -Depth 5
}
catch {
    foreach ($process in $startedProcesses) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-StartedProcessTree -RootProcessId $process.Id
        }
    }
    throw
}
finally {
    [Environment]::SetEnvironmentVariable("TONGHUASUN_AGENT_HOME", $priorTonghuasunDirectory, "Process")
    [Environment]::SetEnvironmentVariable("DAILY_BAR_SOURCE_POLICY", $priorDailyBarPolicy, "Process")
}
