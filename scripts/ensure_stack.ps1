[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [int]$StartupTimeoutSeconds = 45,
    [ValidateSet(0, 1)]
    [int]$EnableCodexSearch = 1,
    [string]$TonghuasunProfile = ""
)

$ErrorActionPreference = "Stop"
$CodexSearchEnabled = [bool]$EnableCodexSearch

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RunScript = Join-Path $PSScriptRoot "run_stack.ps1"
$StopScript = Join-Path $PSScriptRoot "stop_stack.ps1"
$PidFile = Join-Path $ProjectRoot "logs\run_stack.pids.json"
$ApiBase = "http://127.0.0.1:$BackendPort"
$FrontendBase = "http://127.0.0.1:$FrontendPort"
$CodexPulseModel = "gpt-5.5"
$CodexPulseReasoningEffort = "medium"
$CodexPulseHeartbeatFile = Join-Path $ProjectRoot "backend\logs\codex_market_pulse_heartbeat.json"
$CodexDecisionHeartbeatFile = Join-Path $ProjectRoot "backend\logs\codex_decision_review_heartbeat.json"
$FullMarketFeatureHeartbeatFile = Join-Path $ProjectRoot "backend\logs\full_market_feature_heartbeat.json"
$MarketHistoryRefreshHeartbeatFile = Join-Path $ProjectRoot "backend\logs\market_history_refresh_heartbeat.json"
$CapitalFlowRefreshHeartbeatFile = Join-Path $ProjectRoot "backend\logs\capital_flow_refresh_heartbeat.json"
$InstrumentCatalogHeartbeatFile = Join-Path $ProjectRoot "backend\logs\instrument_catalog_refresh_heartbeat.json"
$FullMarketCalibrationHeartbeatFile = Join-Path $ProjectRoot "backend\logs\full_market_calibration_heartbeat.json"

. (Join-Path $PSScriptRoot "tonghuasun_readonly.ps1")
$TonghuasunReadOnly = Get-TonghuasunReadOnlyContext -ProfilePath $TonghuasunProfile

function Read-JsonFileStatus {
    param([string]$LiteralPath)

    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        return [pscustomobject]@{ status = "missing" }
    }
    try {
        return Get-Content -Raw -Encoding UTF8 -LiteralPath $LiteralPath | ConvertFrom-Json
    }
    catch {
        return [pscustomobject]@{ status = "invalid" }
    }
}

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
    $failureReason = $null
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
        $referenceHeartbeat = $ready.workers.reference_data
        $fullMarketFeatureReadyHeartbeat = $ready.workers.full_market_features
        $fullMarketFeatureHeartbeat = Read-JsonFileStatus `
            -LiteralPath $FullMarketFeatureHeartbeatFile
        $marketHistoryRefreshReadyHeartbeat = $ready.workers.market_history_refresh
        $marketHistoryRefreshHeartbeat = Read-JsonFileStatus `
            -LiteralPath $MarketHistoryRefreshHeartbeatFile
        $capitalFlowRefreshReadyHeartbeat = $ready.workers.capital_flow_refresh
        $capitalFlowRefreshHeartbeat = Read-JsonFileStatus `
            -LiteralPath $CapitalFlowRefreshHeartbeatFile
        $instrumentCatalogReadyHeartbeat = $ready.workers.instrument_catalog_refresh
        $instrumentCatalogHeartbeat = Read-JsonFileStatus `
            -LiteralPath $InstrumentCatalogHeartbeatFile
        $fullMarketCalibrationReadyHeartbeat = $ready.workers.full_market_calibration
        $fullMarketCalibrationHeartbeat = Read-JsonFileStatus `
            -LiteralPath $FullMarketCalibrationHeartbeatFile
        $codexReadyHeartbeat = $ready.workers.codex_market_pulse
        $codexHeartbeat = Read-JsonFileStatus -LiteralPath $CodexPulseHeartbeatFile
        $codexDecisionReadyHeartbeat = $ready.workers.codex_decision_review
        $codexDecisionHeartbeat = Read-JsonFileStatus -LiteralPath $CodexDecisionHeartbeatFile
        $controlHealthy = (
            (Test-TrackedProcessIdentity -Metadata $metadata.control_worker) -and
            $controlHeartbeat.status -notin @("missing", "invalid", "stale")
        )
        $referenceHealthy = (
            (Test-TrackedProcessIdentity -Metadata $metadata.reference_data_worker) -and
            $referenceHeartbeat.status -notin @("missing", "invalid", "stale")
        )
        $fullMarketFeatureProcessTracked = Test-TrackedProcessIdentity `
            -Metadata $metadata.full_market_feature_worker
        $fullMarketFeatureConfigurationMatches = (
            $null -ne $metadata.full_market_feature_worker -and
            [int]$metadata.full_market_feature_worker.interval_seconds -eq 14400 -and
            [int]$metadata.full_market_feature_worker.timeout_seconds -eq 300 -and
            [int]$metadata.full_market_feature_worker.candidate_limit -eq 300 -and
            [int]$metadata.full_market_feature_worker.lookback_bars -eq 120 -and
            [int]$fullMarketFeatureHeartbeat.interval_seconds -eq 14400 -and
            [int]$fullMarketFeatureHeartbeat.timeout_seconds -eq 300 -and
            [int]$fullMarketFeatureHeartbeat.candidate_limit -eq 300 -and
            [int]$fullMarketFeatureHeartbeat.lookback_bars -eq 120 -and
            $metadata.full_market_feature_worker.review_only -eq $true -and
            $metadata.full_market_feature_worker.simulation_only -eq $true -and
            $fullMarketFeatureHeartbeat.review_only -eq $true -and
            $fullMarketFeatureHeartbeat.simulation_only -eq $true -and
            $fullMarketFeatureHeartbeat.live_trading_enabled -eq $false
        )
        $fullMarketFeatureHealthy = (
            $fullMarketFeatureProcessTracked -and
            $fullMarketFeatureConfigurationMatches -and
            $null -ne $fullMarketFeatureReadyHeartbeat -and
            $fullMarketFeatureReadyHeartbeat.status -notin @("missing", "invalid", "stale") -and
            $fullMarketFeatureHeartbeat.status -notin @("missing", "invalid", "stale")
        )
        $marketHistoryRefreshProcessTracked = Test-TrackedProcessIdentity `
            -Metadata $metadata.market_history_refresh_worker
        $marketHistoryRefreshHeartbeatPidMatches = (
            $null -ne $marketHistoryRefreshHeartbeat.pid -and
            $null -ne $metadata.market_history_refresh_worker.runtime_pid -and
            [int]$marketHistoryRefreshHeartbeat.pid -eq `
                [int]$metadata.market_history_refresh_worker.runtime_pid
        )
        $marketHistoryRefreshConfigurationMatches = (
            $null -ne $metadata.market_history_refresh_worker -and
            [int]$metadata.market_history_refresh_worker.interval_seconds -eq 14400 -and
            [int]$metadata.market_history_refresh_worker.retry_interval_seconds -eq 900 -and
            [int]$metadata.market_history_refresh_worker.deadline_seconds -eq 900 -and
            [int]$metadata.market_history_refresh_worker.days -eq 150 -and
            [int]$metadata.market_history_refresh_worker.batch_size -eq 200 -and
            [int]$metadata.market_history_refresh_worker.max_workers -eq 20 -and
            [int]$metadata.market_history_refresh_worker.seed_batch_size -eq 500 -and
            [int]$metadata.market_history_refresh_worker.gap_recovery_limit -eq 500 -and
            [int]$marketHistoryRefreshHeartbeat.interval_seconds -eq 14400 -and
            [int]$marketHistoryRefreshHeartbeat.retry_interval_seconds -eq 900 -and
            [int]$marketHistoryRefreshHeartbeat.deadline_seconds -eq 900 -and
            [int]$marketHistoryRefreshHeartbeat.days -eq 150 -and
            [int]$marketHistoryRefreshHeartbeat.batch_size -eq 200 -and
            [int]$marketHistoryRefreshHeartbeat.max_workers -eq 20 -and
            [int]$marketHistoryRefreshHeartbeat.seed_batch_size -eq 500 -and
            [int]$marketHistoryRefreshHeartbeat.gap_recovery_limit -eq 500 -and
            $metadata.market_history_refresh_worker.review_only -eq $true -and
            $metadata.market_history_refresh_worker.simulation_only -eq $true -and
            $marketHistoryRefreshHeartbeat.review_only -eq $true -and
            $marketHistoryRefreshHeartbeat.simulation_only -eq $true -and
            $marketHistoryRefreshHeartbeat.live_trading_enabled -eq $false -and
            $marketHistoryRefreshHeartbeatPidMatches
        )
        $marketHistoryRefreshHealthy = (
            $marketHistoryRefreshProcessTracked -and
            $marketHistoryRefreshConfigurationMatches -and
            $null -ne $marketHistoryRefreshReadyHeartbeat -and
            $marketHistoryRefreshReadyHeartbeat.status -notin @("missing", "invalid", "stale") -and
            $marketHistoryRefreshHeartbeat.status -notin @("missing", "invalid", "stale")
        )
        $capitalFlowRefreshProcessTracked = Test-TrackedProcessIdentity `
            -Metadata $metadata.capital_flow_refresh_worker
        $capitalFlowRefreshHeartbeatPidMatches = (
            $null -ne $capitalFlowRefreshHeartbeat.pid -and
            $null -ne $metadata.capital_flow_refresh_worker.runtime_pid -and
            [int]$capitalFlowRefreshHeartbeat.pid -eq `
                [int]$metadata.capital_flow_refresh_worker.runtime_pid
        )
        $capitalFlowRefreshConfigurationMatches = (
            $null -ne $metadata.capital_flow_refresh_worker -and
            [int]$metadata.capital_flow_refresh_worker.interval_seconds -eq 900 -and
            [int]$metadata.capital_flow_refresh_worker.retry_interval_seconds -eq 300 -and
            [int]$capitalFlowRefreshHeartbeat.interval_seconds -eq 900 -and
            [int]$capitalFlowRefreshHeartbeat.retry_interval_seconds -eq 300 -and
            $metadata.capital_flow_refresh_worker.review_only -eq $true -and
            $metadata.capital_flow_refresh_worker.simulation_only -eq $true -and
            $capitalFlowRefreshHeartbeat.review_only -eq $true -and
            $capitalFlowRefreshHeartbeat.simulation_only -eq $true -and
            $capitalFlowRefreshHeartbeat.live_trading_enabled -eq $false -and
            $capitalFlowRefreshHeartbeatPidMatches
        )
        $capitalFlowRefreshHealthy = (
            $capitalFlowRefreshProcessTracked -and
            $capitalFlowRefreshConfigurationMatches -and
            $null -ne $capitalFlowRefreshReadyHeartbeat -and
            $capitalFlowRefreshReadyHeartbeat.status -notin @("missing", "invalid", "stale") -and
            $capitalFlowRefreshHeartbeat.status -notin @("missing", "invalid", "stale")
        )
        $instrumentCatalogProcessTracked = Test-TrackedProcessIdentity `
            -Metadata $metadata.instrument_catalog_refresh_worker
        $instrumentCatalogHeartbeatPidMatches = (
            $null -ne $instrumentCatalogHeartbeat.pid -and
            $null -ne $metadata.instrument_catalog_refresh_worker.runtime_pid -and
            [int]$instrumentCatalogHeartbeat.pid -eq `
                [int]$metadata.instrument_catalog_refresh_worker.runtime_pid
        )
        $instrumentCatalogConfigurationMatches = (
            $null -ne $metadata.instrument_catalog_refresh_worker -and
            [int]$metadata.instrument_catalog_refresh_worker.interval_seconds -eq 86400 -and
            [int]$metadata.instrument_catalog_refresh_worker.retry_interval_seconds -eq 900 -and
            [int]$metadata.instrument_catalog_refresh_worker.minimum_member_count -eq 4000 -and
            [double]$metadata.instrument_catalog_refresh_worker.minimum_retained_ratio -eq 0.9 -and
            [int]$instrumentCatalogHeartbeat.interval_seconds -eq 86400 -and
            [int]$instrumentCatalogHeartbeat.retry_interval_seconds -eq 900 -and
            [int]$instrumentCatalogHeartbeat.minimum_member_count -eq 4000 -and
            [double]$instrumentCatalogHeartbeat.minimum_retained_ratio -eq 0.9 -and
            $metadata.instrument_catalog_refresh_worker.review_only -eq $true -and
            $metadata.instrument_catalog_refresh_worker.simulation_only -eq $true -and
            $instrumentCatalogHeartbeat.review_only -eq $true -and
            $instrumentCatalogHeartbeat.simulation_only -eq $true -and
            $instrumentCatalogHeartbeat.live_trading_enabled -eq $false -and
            $instrumentCatalogHeartbeatPidMatches
        )
        $instrumentCatalogHealthy = (
            $instrumentCatalogProcessTracked -and
            $instrumentCatalogConfigurationMatches -and
            $null -ne $instrumentCatalogReadyHeartbeat -and
            $instrumentCatalogReadyHeartbeat.status -notin @("missing", "invalid", "stale") -and
            $instrumentCatalogHeartbeat.status -notin @("missing", "invalid", "stale")
        )
        $fullMarketCalibrationProcessTracked = Test-TrackedProcessIdentity `
            -Metadata $metadata.full_market_calibration_worker
        $fullMarketCalibrationHeartbeatPidMatches = (
            $null -ne $fullMarketCalibrationHeartbeat.pid -and
            $null -ne $metadata.full_market_calibration_worker.runtime_pid -and
            [int]$fullMarketCalibrationHeartbeat.pid -eq `
                [int]$metadata.full_market_calibration_worker.runtime_pid
        )
        $fullMarketCalibrationConfigurationMatches = (
            $null -ne $metadata.full_market_calibration_worker -and
            [int]$metadata.full_market_calibration_worker.interval_seconds -eq 86400 -and
            [int]$metadata.full_market_calibration_worker.retry_interval_seconds -eq 1800 -and
            [int]$metadata.full_market_calibration_worker.deadline_seconds -eq 900 -and
            [int]$fullMarketCalibrationHeartbeat.interval_seconds -eq 86400 -and
            [int]$fullMarketCalibrationHeartbeat.retry_interval_seconds -eq 1800 -and
            [int]$fullMarketCalibrationHeartbeat.deadline_seconds -eq 900 -and
            $metadata.full_market_calibration_worker.review_only -eq $true -and
            $metadata.full_market_calibration_worker.simulation_only -eq $true -and
            $fullMarketCalibrationHeartbeat.review_only -eq $true -and
            $fullMarketCalibrationHeartbeat.simulation_only -eq $true -and
            $fullMarketCalibrationHeartbeat.live_trading_enabled -eq $false -and
            $fullMarketCalibrationHeartbeatPidMatches
        )
        $fullMarketCalibrationHealthy = (
            $fullMarketCalibrationProcessTracked -and
            $fullMarketCalibrationConfigurationMatches -and
            $null -ne $fullMarketCalibrationReadyHeartbeat -and
            $fullMarketCalibrationReadyHeartbeat.status -notin @("missing", "invalid", "stale") -and
            $fullMarketCalibrationHeartbeat.status -notin @("missing", "invalid", "stale")
        )
        $codexEnabledValue = $metadata.codex_market_pulse.enabled
        $codexProcessTracked = Test-TrackedProcessIdentity -Metadata $metadata.codex_market_pulse
        $codexModelMatches = (
            [string]$metadata.codex_market_pulse.model -eq $CodexPulseModel
        )
        $codexReasoningEffortMatches = (
            [string]$metadata.codex_market_pulse.reasoning_effort -eq $CodexPulseReasoningEffort
        )
        $codexHeartbeatConfigurationMatches = (
            (-not $CodexSearchEnabled) -or (
                [string]$codexHeartbeat.configured_model -eq $CodexPulseModel -and
                [string]$codexHeartbeat.reasoning_effort -eq $CodexPulseReasoningEffort
            )
        )
        $codexConfigurationMatches = (
            $null -ne $metadata.codex_market_pulse -and
            $codexEnabledValue -is [bool] -and
            $codexEnabledValue -eq $CodexSearchEnabled -and
            ((-not $CodexSearchEnabled) -or (
                $codexModelMatches -and
                $codexReasoningEffortMatches -and
                $codexHeartbeatConfigurationMatches
            ))
        )
        $codexHealthy = $codexConfigurationMatches -and (
            ((-not $CodexSearchEnabled) -and (-not $codexProcessTracked)) -or (
                $CodexSearchEnabled -and
                $codexProcessTracked -and
                $null -ne $codexReadyHeartbeat -and
                $codexReadyHeartbeat.status -notin @("missing", "invalid", "stale") -and
                $codexHeartbeat.status -notin @("missing", "invalid", "stale")
            )
        )
        $codexDecisionEnabledValue = $metadata.codex_decision_review.enabled
        $codexDecisionProcessTracked = Test-TrackedProcessIdentity `
            -Metadata $metadata.codex_decision_review
        $codexDecisionModelMatches = (
            [string]$metadata.codex_decision_review.model -eq $CodexPulseModel
        )
        $codexDecisionReasoningEffortMatches = (
            [string]$metadata.codex_decision_review.reasoning_effort -eq `
                $CodexPulseReasoningEffort
        )
        $codexDecisionHeartbeatConfigurationMatches = (
            (-not $CodexSearchEnabled) -or (
                [string]$codexDecisionHeartbeat.configured_model -eq $CodexPulseModel -and
                [string]$codexDecisionHeartbeat.reasoning_effort -eq $CodexPulseReasoningEffort
            )
        )
        $codexDecisionHeartbeatPidMatches = (
            (-not $CodexSearchEnabled) -or (
                $null -ne $codexDecisionHeartbeat.pid -and
                $null -ne $metadata.codex_decision_review.runtime_pid -and
                [int]$codexDecisionHeartbeat.pid -eq `
                    [int]$metadata.codex_decision_review.runtime_pid
            )
        )
        $codexDecisionSafetyMatches = (
            (-not $CodexSearchEnabled) -or (
                $metadata.codex_decision_review.review_only -eq $true -and
                $codexDecisionHeartbeat.review_only -eq $true -and
                $codexDecisionHeartbeat.live_trading_enabled -eq $false
            )
        )
        $codexDecisionConfigurationMatches = (
            $null -ne $metadata.codex_decision_review -and
            $codexDecisionEnabledValue -is [bool] -and
            $codexDecisionEnabledValue -eq $CodexSearchEnabled -and
            ((-not $CodexSearchEnabled) -or (
                $codexDecisionModelMatches -and
                $codexDecisionReasoningEffortMatches -and
                $codexDecisionHeartbeatConfigurationMatches -and
                $codexDecisionHeartbeatPidMatches -and
                $codexDecisionSafetyMatches
            ))
        )
        $codexDecisionHealthy = $codexDecisionConfigurationMatches -and (
            ((-not $CodexSearchEnabled) -and (-not $codexDecisionProcessTracked)) -or (
                $CodexSearchEnabled -and
                $codexDecisionProcessTracked -and
                $null -ne $codexDecisionReadyHeartbeat -and
                $codexDecisionReadyHeartbeat.status -notin @("missing", "invalid", "stale") -and
                $codexDecisionHeartbeat.status -notin @("missing", "invalid", "stale")
            )
        )
        if (
            $ready.status -eq "ready" -and
            $frontend.StatusCode -ge 200 -and
            $frontend.StatusCode -lt 400 -and
            $controlHealthy -and
            $referenceHealthy -and
            $fullMarketFeatureHealthy -and
            $marketHistoryRefreshHealthy -and
            $capitalFlowRefreshHealthy -and
            $instrumentCatalogHealthy -and
            $fullMarketCalibrationHealthy -and
            $codexHealthy -and
            $codexDecisionHealthy
        ) {
            return [ordered]@{
                healthy = $true
                health = $health
                ready = $ready
                frontend_status = $frontend.StatusCode
                control_worker_healthy = $controlHealthy
                reference_data_worker_healthy = $referenceHealthy
                full_market_feature_worker_healthy = $fullMarketFeatureHealthy
                full_market_feature_worker_configuration_matches = `
                    $fullMarketFeatureConfigurationMatches
                full_market_feature_worker_process_tracked = `
                    $fullMarketFeatureProcessTracked
                market_history_refresh_worker_healthy = $marketHistoryRefreshHealthy
                market_history_refresh_worker_configuration_matches = `
                    $marketHistoryRefreshConfigurationMatches
                market_history_refresh_worker_process_tracked = `
                    $marketHistoryRefreshProcessTracked
                market_history_refresh_worker_heartbeat_pid_matches = `
                    $marketHistoryRefreshHeartbeatPidMatches
                capital_flow_refresh_worker_healthy = $capitalFlowRefreshHealthy
                capital_flow_refresh_worker_configuration_matches = `
                    $capitalFlowRefreshConfigurationMatches
                capital_flow_refresh_worker_process_tracked = `
                    $capitalFlowRefreshProcessTracked
                capital_flow_refresh_worker_heartbeat_pid_matches = `
                    $capitalFlowRefreshHeartbeatPidMatches
                instrument_catalog_refresh_worker_healthy = $instrumentCatalogHealthy
                instrument_catalog_refresh_worker_configuration_matches = `
                    $instrumentCatalogConfigurationMatches
                instrument_catalog_refresh_worker_process_tracked = `
                    $instrumentCatalogProcessTracked
                instrument_catalog_refresh_worker_heartbeat_pid_matches = `
                    $instrumentCatalogHeartbeatPidMatches
                full_market_calibration_worker_healthy = $fullMarketCalibrationHealthy
                full_market_calibration_worker_configuration_matches = `
                    $fullMarketCalibrationConfigurationMatches
                full_market_calibration_worker_process_tracked = `
                    $fullMarketCalibrationProcessTracked
                full_market_calibration_worker_heartbeat_pid_matches = `
                    $fullMarketCalibrationHeartbeatPidMatches
                codex_market_pulse_healthy = $codexHealthy
                codex_market_pulse_configuration_matches = $codexConfigurationMatches
                codex_market_pulse_process_tracked = $codexProcessTracked
                codex_market_pulse_model_matches = $codexModelMatches
                codex_market_pulse_reasoning_effort_matches = $codexReasoningEffortMatches
                codex_market_pulse_heartbeat_configuration_matches = $codexHeartbeatConfigurationMatches
                codex_decision_review_healthy = $codexDecisionHealthy
                codex_decision_review_configuration_matches = $codexDecisionConfigurationMatches
                codex_decision_review_process_tracked = $codexDecisionProcessTracked
                codex_decision_review_model_matches = $codexDecisionModelMatches
                codex_decision_review_reasoning_effort_matches = `
                    $codexDecisionReasoningEffortMatches
                codex_decision_review_heartbeat_configuration_matches = `
                    $codexDecisionHeartbeatConfigurationMatches
                codex_decision_review_heartbeat_pid_matches = $codexDecisionHeartbeatPidMatches
                codex_decision_review_safety_matches = $codexDecisionSafetyMatches
            }
        }
    }
    catch {
        if ($_.Exception.Message -like "Unsafe backend detected:*") {
            throw
        }
        $failureReason = $_.Exception.Message
    }
    return [ordered]@{
        healthy = $false
        reason = $failureReason
        ready_status = $ready.status
        frontend_status = $frontend.StatusCode
        control_worker_healthy = $controlHealthy
        reference_data_worker_healthy = $referenceHealthy
        full_market_feature_worker_healthy = $fullMarketFeatureHealthy
        full_market_feature_worker_configuration_matches = `
            $fullMarketFeatureConfigurationMatches
        market_history_refresh_worker_healthy = $marketHistoryRefreshHealthy
        market_history_refresh_worker_configuration_matches = `
            $marketHistoryRefreshConfigurationMatches
        capital_flow_refresh_worker_healthy = $capitalFlowRefreshHealthy
        capital_flow_refresh_worker_configuration_matches = `
            $capitalFlowRefreshConfigurationMatches
        instrument_catalog_refresh_worker_healthy = $instrumentCatalogHealthy
        instrument_catalog_refresh_worker_configuration_matches = `
            $instrumentCatalogConfigurationMatches
        full_market_calibration_worker_healthy = $fullMarketCalibrationHealthy
        full_market_calibration_worker_configuration_matches = `
            $fullMarketCalibrationConfigurationMatches
        codex_market_pulse_healthy = $codexHealthy
        codex_market_pulse_configuration_matches = $codexConfigurationMatches
        codex_decision_review_healthy = $codexDecisionHealthy
        codex_decision_review_configuration_matches = $codexDecisionConfigurationMatches
    }
}

$current = Get-HealthyStack
if ($current.healthy) {
    $trackedStartup = Get-Content -LiteralPath $PidFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $tonghuasunConfigurationMatches = (
        $trackedStartup.tonghuasun_readonly.product_home -eq $TonghuasunReadOnly.product_home -and
        $trackedStartup.tonghuasun_readonly.daily_bar_source_policy -eq "akshare_first" -and
        $trackedStartup.tonghuasun_readonly.live_trading_enabled -eq $false
    )
    [ordered]@{
        schema_version = "ensure_stack.v1"
        status = "already_running"
        checked_at = [DateTimeOffset]::Now.ToString("o")
        live_trading_enabled = $false
        backend = $ApiBase
        frontend = $FrontendBase
        tonghuasun_readonly = $TonghuasunReadOnly
        tonghuasun_startup_configuration_matches = $tonghuasunConfigurationMatches
        tonghuasun_pending_normal_restart = (-not $tonghuasunConfigurationMatches)
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
    -EnableCodexSearch:$CodexSearchEnabled `
    -TonghuasunProfile $TonghuasunProfile

if ($LASTEXITCODE -ne 0) {
    throw "run_stack.ps1 failed with exit code $LASTEXITCODE"
}

$started = Get-HealthyStack
if (-not $started.healthy) {
    $diagnostics = $started | ConvertTo-Json -Compress -Depth 5
    throw "Stack startup returned without reaching healthy review-only state. Diagnostics: $diagnostics"
}

[ordered]@{
    schema_version = "ensure_stack.v1"
    status = "started"
    checked_at = [DateTimeOffset]::Now.ToString("o")
    live_trading_enabled = $false
    backend = $ApiBase
    frontend = $FrontendBase
    tonghuasun_readonly = $TonghuasunReadOnly
} | ConvertTo-Json -Depth 5
