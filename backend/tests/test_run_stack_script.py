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
    assert "EnableCodexSearch" in source
    assert "$env:TRADING_API_BASE = $ApiBase" in source
    assert "stop_stack.ps1" in source
    assert "Get-StartedProcessMetadata" in source
    assert "Test-TrackedProcessIdentity" in source
    assert "Test-RootOrDescendantProcess" in source
    assert '$workerMetadata["runtime_pid"]' in source
    assert "executable_path" in source
    assert "command_line" in source
    assert "created_at" in source
    assert '"--interval-seconds", "14400"' in source
    assert source.count("Start-Process") >= 4
    assert source.count("-WindowStyle Hidden") >= 4
    assert "run_stack.pids.json" in source


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
    assert "Remove-Item -LiteralPath $PidFile" in source


def test_ensure_stack_is_idempotent_and_refuses_unsafe_backend():
    project_root = Path(__file__).resolve().parents[2]
    source = (project_root / "scripts" / "ensure_stack.ps1").read_text(encoding="utf-8")

    assert 'status = "already_running"' in source
    assert "live_trading_enabled -ne $false" in source
    assert '$env:ENABLE_LIVE_TRADING = "false"' in source
    assert "stop_stack.ps1" in source
    assert "run_stack.ps1" in source
    assert "Test-TrackedProcessIdentity" in source
    assert "$metadata.control_worker" in source
    assert "$metadata.codex_market_pulse" in source
    assert '$controlHeartbeat.status -notin @("missing", "invalid", "stale")' in source
    assert "$EnableCodexSearch" in source
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
    assert "$AllowedArguments" in source
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
    assert "runner.temp" in source
    assert 'DATABASE_PATH: ":memory:"' not in source
    assert "python -m pytest -q" in source
    assert "python -m ruff check app tests" in source
    assert "Parse PowerShell entrypoints" in source
    assert "Language.Parser" in source
    assert "npm test" in source
    assert "npm run build" in source
