from pathlib import Path


def test_run_stack_starts_guarded_hidden_processes():
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "scripts" / "run_stack.ps1"

    source = script_path.read_text(encoding="utf-8")

    assert "trading_local.sqlite3" in source
    assert "ENABLE_LIVE_TRADING" in source
    assert "/health" in source
    assert "live_trading_enabled" in source
    assert "control_plane_loop.py" in source
    assert '"--profile", "adaptive"' in source
    assert '"--interval-seconds", "900"' in source
    assert "codex_market_pulse.py" in source
    assert "codex_decision_review.py" in source
    assert "EnableCodexSearch" in source
    assert '$CodexPulseModel = "gpt-5.5"' in source
    assert '$CodexPulseReasoningEffort = "medium"' in source
    assert '"--model", $CodexPulseModel' in source
    assert '"--reasoning-effort", $CodexPulseReasoningEffort' in source
    assert '$codexMetadata["model"] = $CodexPulseModel' in source
    assert '$codexMetadata["reasoning_effort"] = $CodexPulseReasoningEffort' in source
    assert "$codexPulseHeartbeat.configured_model" in source
    assert "$codexDecisionHeartbeat.configured_model" in source
    assert '$codexDecisionMetadata["review_only"] = $true' in source
    assert "codex_decision_review = $codexDecisionMetadata" in source
    assert "$env:TRADING_API_BASE = $ApiBase" in source
    assert "stop_stack.ps1" in source
    assert "Get-StartedProcessMetadata" in source
    assert "Test-TrackedProcessIdentity" in source
    assert "Test-RootOrDescendantProcess" in source
    assert '$workerMetadata["runtime_pid"]' in source
    assert "reference_data_loop.py" in source
    assert "reference_data_heartbeat.json" in source
    assert "$referenceWorker" in source
    assert '$referenceMetadata["runtime_pid"]' in source
    assert '"--board-limit", "50"' in source
    assert '"--disclosure-limit", "500"' in source
    assert '"--global-days", "30"' in source
    assert '"--cycle-timeout-seconds", "900"' in source
    assert '"--skip-sox"' in source
    assert "executable_path" in source
    assert "command_line" in source
    assert "created_at" in source
    assert '"--interval-seconds", "14400"' in source
    assert source.count("Start-Process") >= 6
    assert source.count("-WindowStyle Hidden") >= 6
    assert "run_stack.pids.json" in source


def test_full_market_feature_worker_is_started_and_managed_by_the_stack():
    project_root = Path(__file__).resolve().parents[2]
    run_source = (project_root / "scripts" / "run_stack.ps1").read_text(
        encoding="utf-8"
    )
    ensure_source = (project_root / "scripts" / "ensure_stack.ps1").read_text(
        encoding="utf-8"
    )
    stop_source = (project_root / "scripts" / "stop_stack.ps1").read_text(
        encoding="utf-8"
    )

    assert "full_market_feature_loop.py" in run_source
    assert "full_market_feature_heartbeat.json" in run_source
    assert '"--candidate-limit", "300"' in run_source
    assert '"--lookback-bars", "120"' in run_source
    assert '"--timeout-seconds", "300"' in run_source
    assert '$fullMarketFeatureMetadata["interval_seconds"] = 14400' in run_source
    assert '$fullMarketFeatureMetadata["review_only"] = $true' in run_source
    assert '$fullMarketFeatureMetadata["simulation_only"] = $true' in run_source
    assert "full_market_feature_worker = $fullMarketFeatureMetadata" in run_source
    worker_start = run_source.split(
        "$fullMarketFeatureWorker = Start-Process", 1
    )[1].split("$startedProcesses.Add($fullMarketFeatureWorker)", 1)[0]
    assert "-WindowStyle Hidden" in worker_start

    assert "$metadata.full_market_feature_worker" in ensure_source
    assert "$ready.workers.full_market_features" in ensure_source
    assert "full_market_feature_worker_healthy" in ensure_source
    assert (
        '$fullMarketFeatureHeartbeat.live_trading_enabled -eq $false'
        in ensure_source
    )

    assert 'name = "full_market_feature_worker"' in stop_source


def test_market_history_refresh_worker_is_started_and_managed_by_the_stack():
    project_root = Path(__file__).resolve().parents[2]
    run_source = (project_root / "scripts" / "run_stack.ps1").read_text(
        encoding="utf-8"
    )
    ensure_source = (project_root / "scripts" / "ensure_stack.ps1").read_text(
        encoding="utf-8"
    )
    stop_source = (project_root / "scripts" / "stop_stack.ps1").read_text(
        encoding="utf-8"
    )

    assert "market_history_refresh_loop.py" in run_source
    assert "market_history_refresh_heartbeat.json" in run_source
    for expected_argument in [
        '"--interval-seconds", "14400"',
        '"--retry-interval-seconds", "900"',
        '"--max-cycles", "0"',
        '"--days", "150"',
        '"--batch-size", "200"',
        '"--max-workers", "20"',
        '"--seed-batch-size", "500"',
        '"--gap-recovery-limit", "500"',
        '"--deadline-seconds", "900"',
    ]:
        assert expected_argument in run_source
    for expected_metadata in [
        '$marketHistoryRefreshMetadata["interval_seconds"] = 14400',
        '$marketHistoryRefreshMetadata["retry_interval_seconds"] = 900',
        '$marketHistoryRefreshMetadata["deadline_seconds"] = 900',
        '$marketHistoryRefreshMetadata["days"] = 150',
        '$marketHistoryRefreshMetadata["batch_size"] = 200',
        '$marketHistoryRefreshMetadata["max_workers"] = 20',
        '$marketHistoryRefreshMetadata["seed_batch_size"] = 500',
        '$marketHistoryRefreshMetadata["gap_recovery_limit"] = 500',
        '$marketHistoryRefreshMetadata["review_only"] = $true',
        '$marketHistoryRefreshMetadata["simulation_only"] = $true',
        '$marketHistoryRefreshMetadata["runtime_pid"]',
        "market_history_refresh_worker = $marketHistoryRefreshMetadata",
    ]:
        assert expected_metadata in run_source
    worker_start = run_source.split(
        "$marketHistoryRefreshWorker = Start-Process", 1
    )[1].split("$startedProcesses.Add($marketHistoryRefreshWorker)", 1)[0]
    assert "-WindowStyle Hidden" in worker_start

    assert "$metadata.market_history_refresh_worker" in ensure_source
    assert "$ready.workers.market_history_refresh" in ensure_source
    assert "market_history_refresh_worker_healthy" in ensure_source
    assert "marketHistoryRefreshHeartbeatPidMatches" in ensure_source
    assert "$marketHistoryRefreshHeartbeat.review_only -eq $true" in ensure_source
    assert "$marketHistoryRefreshHeartbeat.simulation_only -eq $true" in ensure_source
    assert "$marketHistoryRefreshHeartbeat.live_trading_enabled -eq $false" in ensure_source
    assert "marketHistoryRefreshHeartbeat.gap_recovery_limit" in ensure_source

    assert 'name = "market_history_refresh_worker"' in stop_source


def test_capital_flow_refresh_worker_is_started_and_managed_by_the_stack():
    project_root = Path(__file__).resolve().parents[2]
    run_source = (project_root / "scripts" / "run_stack.ps1").read_text(
        encoding="utf-8"
    )
    ensure_source = (project_root / "scripts" / "ensure_stack.ps1").read_text(
        encoding="utf-8"
    )
    stop_source = (project_root / "scripts" / "stop_stack.ps1").read_text(
        encoding="utf-8"
    )

    assert "capital_flow_refresh_loop.py" in run_source
    assert "capital_flow_refresh_heartbeat.json" in run_source
    assert '"--interval-seconds", "900"' in run_source
    assert '"--retry-seconds", "300"' in run_source
    assert '$capitalFlowRefreshMetadata["runtime_pid"]' in run_source
    assert '$capitalFlowRefreshMetadata["review_only"] = $true' in run_source
    assert '$capitalFlowRefreshMetadata["simulation_only"] = $true' in run_source
    assert "capital_flow_refresh_worker = $capitalFlowRefreshMetadata" in run_source
    worker_start = run_source.split(
        "$capitalFlowRefreshWorker = Start-Process", 1
    )[1].split("$startedProcesses.Add($capitalFlowRefreshWorker)", 1)[0]
    assert "-WindowStyle Hidden" in worker_start

    assert "$metadata.capital_flow_refresh_worker" in ensure_source
    assert "$ready.workers.capital_flow_refresh" in ensure_source
    assert "capital_flow_refresh_worker_healthy" in ensure_source
    assert "$capitalFlowRefreshHeartbeat.review_only -eq $true" in ensure_source
    assert "$capitalFlowRefreshHeartbeat.simulation_only -eq $true" in ensure_source
    assert "$capitalFlowRefreshHeartbeat.live_trading_enabled -eq $false" in ensure_source

    assert 'name = "capital_flow_refresh_worker"' in stop_source


def test_p2_daily_research_workers_are_started_and_managed_by_the_stack():
    project_root = Path(__file__).resolve().parents[2]
    run_source = (project_root / "scripts" / "run_stack.ps1").read_text(
        encoding="utf-8"
    )
    ensure_source = (project_root / "scripts" / "ensure_stack.ps1").read_text(
        encoding="utf-8"
    )
    stop_source = (project_root / "scripts" / "stop_stack.ps1").read_text(
        encoding="utf-8"
    )

    for script_name, heartbeat_name in [
        (
            "instrument_catalog_refresh_loop.py",
            "instrument_catalog_refresh_heartbeat.json",
        ),
        ("full_market_calibration_loop.py", "full_market_calibration_heartbeat.json"),
    ]:
        assert script_name in run_source
        assert heartbeat_name in run_source

    for metadata_name in (
        "instrument_catalog_refresh_worker",
        "full_market_calibration_worker",
    ):
        assert f"{metadata_name} = $" in run_source
        assert f"$metadata.{metadata_name}" in ensure_source
        assert f'name = "{metadata_name}"' in stop_source

    assert '"--interval-seconds", "86400"' in run_source
    assert '"--minimum-member-count", "4000"' in run_source
    assert '"--minimum-retained-ratio", "0.9"' in run_source
    assert '"--retry-seconds", "900"' in run_source
    assert '"--retry-seconds", "1800"' in run_source
    assert '"--deadline-seconds", "900"' in run_source
    assert '$instrumentCatalogMetadata["runtime_pid"]' in run_source
    assert '$fullMarketCalibrationMetadata["runtime_pid"]' in run_source
    assert "$ready.workers.instrument_catalog_refresh" in ensure_source
    assert "$ready.workers.full_market_calibration" in ensure_source
    assert "instrument_catalog_refresh_worker_healthy" in ensure_source
    assert "full_market_calibration_worker_healthy" in ensure_source
    assert "$instrumentCatalogHeartbeat.live_trading_enabled -eq $false" in ensure_source
    assert "$fullMarketCalibrationHeartbeat.live_trading_enabled -eq $false" in ensure_source


def test_stop_stack_requires_exact_process_identity():
    project_root = Path(__file__).resolve().parents[2]
    source = (project_root / "scripts" / "stop_stack.ps1").read_text(encoding="utf-8")

    assert "creation_time_mismatch" in source
    assert "executable_path_mismatch" in source
    assert "command_line_mismatch" in source
    assert "tracked_root_missing" in source
    assert "shutdownDeadline" in source
    assert "Get-DescendantProcessIds" in source
    assert "remaining_descendant_pids" in source
    assert '"stale_metadata_removed"' in source
    assert "foreach ($rootPid in $validatedRoots)" in source
    assert "Remove-Item -LiteralPath $PidFile" in source
    assert 'name = "reference_data_worker"' in source
    assert 'name = "codex_decision_review"' in source


def test_run_stack_failure_cleanup_snapshots_descendants_before_stopping_launcher():
    project_root = Path(__file__).resolve().parents[2]
    source = (project_root / "scripts" / "run_stack.ps1").read_text(encoding="utf-8")
    cleanup = source.split("function Stop-StartedProcessTree", 1)[1].split(
        "function Test-TrackedProcessIdentity", 1
    )[0]

    snapshot_index = cleanup.index("$rows = @(Get-CimInstance Win32_Process)")
    stop_launcher_index = cleanup.index("Stop-Process -Id $RootProcessId")
    assert snapshot_index < stop_launcher_index
    assert "$allTargets" in cleanup


def test_ensure_stack_is_idempotent_and_refuses_unsafe_backend():
    project_root = Path(__file__).resolve().parents[2]
    source = (project_root / "scripts" / "ensure_stack.ps1").read_text(encoding="utf-8")

    assert 'status = "already_running"' in source
    assert "live_trading_enabled -ne $false" in source
    assert '$env:ENABLE_LIVE_TRADING = "false"' in source
    assert "[ValidateSet(0, 1)]" in source
    assert "$CodexSearchEnabled = [bool]$EnableCodexSearch" in source
    assert "stop_stack.ps1" in source
    assert "run_stack.ps1" in source
    assert "Test-TrackedProcessIdentity" in source
    assert "$metadata.control_worker" in source
    assert "$metadata.reference_data_worker" in source
    assert "$metadata.codex_market_pulse" in source
    assert "$metadata.codex_decision_review" in source
    assert '$controlHeartbeat.status -notin @("missing", "invalid", "stale")' in source
    assert "$EnableCodexSearch" in source
    assert "$codexConfigurationMatches" in source
    assert "$codexEnabledValue -is [bool]" in source
    assert "$codexEnabledValue -eq $CodexSearchEnabled" in source
    assert "$codexProcessTracked" in source
    assert '$CodexPulseModel = "gpt-5.5"' in source
    assert '$CodexPulseReasoningEffort = "medium"' in source
    assert "$codexModelMatches" in source
    assert "$codexReasoningEffortMatches" in source
    assert "$codexHeartbeatConfigurationMatches" in source
    assert "$codexHeartbeat.configured_model" in source
    assert "$null -ne $codexReadyHeartbeat" in source
    assert "$codexReadyHeartbeat.status" in source
    assert "$codexHeartbeat.reasoning_effort" in source
    assert "$codexDecisionHeartbeat.configured_model" in source
    assert "$codexDecisionHeartbeat.reasoning_effort" in source
    assert "$codexDecisionHeartbeat.live_trading_enabled -eq $false" in source
    assert "$null -ne $codexDecisionReadyHeartbeat" in source
    assert "$codexDecisionReadyHeartbeat.status" in source
    assert "$codexDecisionHeartbeatPidMatches" in source
    assert "$codexDecisionSafetyMatches" in source
    assert "$codexDecisionHealthy" in source
    assert "$ready.workers.reference_data" in source
    assert "reference_data_worker_healthy" in source
    assert "Stack startup returned without reaching healthy review-only state" in source


def test_control_plane_task_runs_hidden_review_only_health_ensure():
    project_root = Path(__file__).resolve().parents[2]
    source = (project_root / "scripts" / "control_plane_task.ps1").read_text(
        encoding="utf-8"
    )

    assert "ZKTrading-ReviewOnly-ControlPlane" in source
    assert "ensure_stack.ps1" in source
    assert "-WindowStyle" in source and "Hidden" in source
    assert "New-ScheduledTaskPrincipal" in source
    assert "-RunLevel Limited" in source
    assert "-MultipleInstances IgnoreNew" in source
    assert "never enables live trading" in source
    assert "Test-TaskDefinition" in source
    assert "Test-PrincipalMatchesCurrentUser" in source
    assert "$CurrentUserSid" in source
    assert "NTAccount" in source
    assert ".Translate(" in source
    assert "$principalSid.Value -eq $CurrentUserSid" in source
    assert "$AllowedArguments" in source
    assert '@("-EnableCodexSearch", "1")' in source
    assert '@("-EnableCodexSearch", "0")' in source
    assert "-EnableCodexSearch:$CodexFlag" not in source
    assert "$LegacyArguments" in source
    assert "legacy_boolean_arguments" in source
    assert "task_definition_upgrade" in source
    assert "[int]$EnableCodexSearch = 1" in source
    assert "$CodexFlag = [string]$EnableCodexSearch" in source
    assert "definition_migratable" in source
    assert "MSFT_TaskLogonTrigger" in source
    assert "MSFT_TaskTimeTrigger" in source
    assert "repeat_interval_safe" in source
    assert "repeat_interval_matches_requested" in source
    assert "arguments_match_requested" in source
    assert "configuration_matches" in source
    assert "indefinite_repeat" in source
    assert "start_boundary_active" in source
    assert "no_random_delay" in source
    assert "logon_type" in source
    assert "multiple_instances" in source
    assert "not_idle_only" in source
    assert "allow_demand_start" in source
    assert "allow_hard_terminate" in source
    assert "network_not_required" in source
    assert "allow_start_on_batteries" in source
    assert "continue_on_batteries" in source
    assert "-AllowStartIfOnBatteries" in source
    assert "-DontStopIfGoingOnBatteries" in source
    assert "EndBoundary" in source
    assert "Repetition.Duration" in source
    assert "DateTimeOffset]::Parse" in source
    assert "RandomDelay" in source
    assert "-RunOnlyIfIdle:$false" in source
    assert "-DisallowDemandStart:$false" in source
    assert "-DisallowHardTerminate:$false" in source
    assert "-RunOnlyIfNetworkAvailable:$false" in source
    assert "Get-ScheduledTaskInfo" in source
    assert "operational_status" in source
    assert "last_task_result" in source
    assert "next_run_time" in source
    assert "missed_runs" in source
    assert "task_definition_mismatch" in source
    assert "Refusing to run mismatched scheduled task" in source
    assert "Refusing to remove mismatched scheduled task" in source
    assert "Refusing to overwrite mismatched scheduled task" in source


def test_github_ci_enforces_tests_build_and_live_disabled():
    project_root = Path(__file__).resolve().parents[2]
    source = (project_root / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "actions/checkout@v7" in source
    assert "actions/setup-python@v6" in source
    assert 'ENABLE_LIVE_TRADING: "false"' in source
    assert "$env:RUNNER_TEMP" in source
    assert 'DATABASE_PATH: ":memory:"' not in source
    assert "python -m pytest -q" in source
    assert "python -m ruff check app tests" in source
    assert "Parse PowerShell entrypoints" in source
    assert "Language.Parser" in source
    assert "npm test" in source
    assert "npm run build" in source


def test_stack_inherits_fixed_readonly_profile_without_launching_or_restarting_client():
    project_root = Path(__file__).resolve().parents[2]
    run_source = (project_root / "scripts" / "run_stack.ps1").read_text(encoding="utf-8")
    ensure_source = (project_root / "scripts" / "ensure_stack.ps1").read_text(encoding="utf-8")

    for source in (run_source, ensure_source):
        assert "Get-TonghuasunReadOnlyContext -ProfilePath $TonghuasunProfile" in source
        assert "Start-TonghuasunReadOnlyClient" not in source
        assert "tonghuasun_readonly = $TonghuasunReadOnly" in source
    assert '$env:TONGHUASUN_AGENT_HOME = $TonghuasunReadOnly.product_home' in run_source
    assert '$env:DAILY_BAR_SOURCE_POLICY = "akshare_first"' in run_source
    assert run_source.index("$env:TONGHUASUN_AGENT_HOME =") < run_source.index("$backend = Start-Process")
    assert '[Environment]::SetEnvironmentVariable("TONGHUASUN_AGENT_HOME", $priorTonghuasunDirectory, "Process")' in run_source
    assert '[Environment]::SetEnvironmentVariable("DAILY_BAR_SOURCE_POLICY", $priorDailyBarPolicy, "Process")' in run_source
    healthy_branch = ensure_source.split("if ($current.healthy) {", 1)[1].split("exit 0", 1)[0]
    assert "tonghuasun_pending_normal_restart" in healthy_branch
    assert "& $StopScript" not in healthy_branch
    assert "& $RunScript" not in healthy_branch
    assert "-TonghuasunProfile $TonghuasunProfile" in ensure_source
