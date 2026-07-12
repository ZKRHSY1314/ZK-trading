[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [int]$StartupTimeoutSeconds = 45,
    [bool]$EnableCodexSearch = $true
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
$CodexPulseScript = Join-Path $BackendRoot "scripts\codex_market_pulse.py"
$ViteCommand = Join-Path $FrontendRoot "node_modules\.bin\vite.cmd"
$ViteEntry = Join-Path $FrontendRoot "node_modules\vite\bin\vite.js"
$PidFile = Join-Path $LogsRoot "run_stack.pids.json"
$HeartbeatFile = Join-Path $BackendRoot "logs\control_plane_heartbeat.json"
$ReferenceHeartbeatFile = Join-Path $BackendRoot "logs\reference_data_heartbeat.json"
$ApiBase = "http://127.0.0.1:$BackendPort"
$FrontendBase = "http://127.0.0.1:$FrontendPort"

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

    # Stop the launcher first so it cannot create another child after a tree snapshot.
    Stop-Process -Id $RootProcessId -Force -ErrorAction SilentlyContinue
    $deadline = [DateTime]::UtcNow.AddSeconds(3)
    do {
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
        for ($index = $targets.Count - 1; $index -ge 0; $index--) {
            Stop-Process -Id $targets[$index] -Force -ErrorAction SilentlyContinue
        }
        if ($targets.Count -eq 0 -or [DateTime]::UtcNow -ge $deadline) {
            break
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
if ($EnableCodexSearch) {
    Assert-FileExists -LiteralPath $CodexPulseScript -Label "Codex market-pulse worker"
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
            $previous.codex_market_pulse
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
try {
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

    $codexPulse = $null
    $codexPulseHeartbeat = $null
    if ($EnableCodexSearch) {
        $codexPulseArgs = @(
            "-X", "utf8", $CodexPulseScript,
            "--api-base", $ApiBase,
            "--interval-seconds", "14400",
            "--max-cycles", "0",
            "--timeout-seconds", "900"
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
    $codexMetadata = [ordered]@{ enabled = $EnableCodexSearch }
    if ($null -ne $codexPulse) {
        $codexMetadata = Get-StartedProcessMetadata -Process $codexPulse -CommandMarker $CodexPulseScript
        $codexMetadata["enabled"] = $true
        $codexMetadata["interval_seconds"] = 14400
        $codexMetadata["heartbeat_path"] = Join-Path $BackendRoot "logs\codex_market_pulse_heartbeat.json"
        $codexMetadata["runtime_pid"] = [int]$codexPulseHeartbeat.pid
    }

    $metadata = [ordered]@{
        schema_version = "run_stack_pids.v1"
        started_at = [DateTimeOffset]::Now.ToString("o")
        project_root = $ProjectRoot
        database_path = $DatabasePath
        live_trading_enabled = $false
        backend = $backendMetadata
        frontend = $frontendMetadata
        control_worker = $workerMetadata
        reference_data_worker = $referenceMetadata
        codex_market_pulse = $codexMetadata
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
