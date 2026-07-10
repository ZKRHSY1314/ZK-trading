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
