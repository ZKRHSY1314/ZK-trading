"""Restart budget for ensure_stack.ps1, and ensure_stack's non-CheckOnly refusals.

The budget helper is stdlib-only and tested directly. The ensure_stack cases run
the real script under PowerShell 7 (pwsh) with run_stack/stop_stack replaced by
scripts that throw, so they prove which paths can and cannot reach a start or
stop. They need a POSIX pwsh (a shell-script python.exe stand-in); on Windows the
same paths are part of the local acceptance checklist, not claimed here.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT / 'backend/scripts/stack_recovery.py'
spec = importlib.util.spec_from_file_location('stack_recovery_under_test', SCRIPT)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
NOW = datetime(2026, 9, 24, 8, tzinfo=timezone.utc)


def _state(path, *stamps, outcome='failed'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'schema_version': recovery.SCHEMA_VERSION, 'attempts': [
        {'at': stamp.isoformat(), 'outcome': outcome} for stamp in stamps]}), encoding='utf-8')
    return path


def test_first_restart_is_allowed_and_nothing_is_written(tmp_path):
    path = tmp_path / 'logs/ensure_stack_restarts.json'
    decision = recovery.decide(path, NOW)
    assert decision['action'] == 'restart' and decision['attempts_in_window'] == 0
    assert not path.exists()


def test_repeated_restarts_within_the_window_are_suppressed(tmp_path):
    path = _state(tmp_path / 'r.json', NOW - timedelta(minutes=50), NOW - timedelta(minutes=20),
                  NOW - timedelta(minutes=5))
    decision = recovery.decide(path, NOW)
    assert decision['action'] == 'suppress'
    assert decision['reason'] == 'restart_budget_exhausted'
    assert decision['attempts_in_window'] == 3
    assert decision['next_allowed_at'] == (NOW + timedelta(minutes=10)).isoformat()
    # Once the oldest attempt leaves the window, one more restart is allowed.
    assert recovery.decide(path, NOW + timedelta(minutes=11))['action'] == 'restart'


def test_successful_starts_also_count_against_the_budget(tmp_path):
    # A stack that "starts" and dies three times an hour is still a storm.
    path = _state(tmp_path / 'r.json', NOW - timedelta(minutes=30), NOW - timedelta(minutes=20),
                  NOW - timedelta(minutes=10), outcome='started')
    assert recovery.decide(path, NOW)['action'] == 'suppress'


@pytest.mark.parametrize('content,reason', [
    ('{not json', 'state_file_unreadable'),
    ('{"schema_version": "other", "attempts": []}', 'state_file_schema_mismatch'),
    ('{"schema_version": "ensure_stack_restarts.v1", "attempts": {}}', 'state_file_malformed'),
    ('{"schema_version": "ensure_stack_restarts.v1", "attempts": [{"at": "bad", "outcome": "failed"}]}',
     'state_file_malformed'),
    ('{"schema_version": "ensure_stack_restarts.v1", "attempts": '
     '[{"at": "2026-09-24T08:00:00", "outcome": "failed"}]}', 'state_file_malformed'),
    ('{"schema_version": "ensure_stack_restarts.v1", "attempts": '
     '[{"at": "2026-09-24T08:00:00+00:00", "outcome": "maybe"}]}', 'state_file_malformed'),
])
def test_untrusted_state_fails_closed(tmp_path, content, reason):
    path = tmp_path / 'r.json'
    path.write_text(content, encoding='utf-8')
    decision = recovery.decide(path, NOW)
    assert (decision['action'], decision['reason']) == ('suppress', reason)
    with pytest.raises(RuntimeError):
        recovery.record(path, NOW, 'failed')
    assert path.read_text(encoding='utf-8') == content  # never silently replaced


def test_future_dated_attempts_fail_closed(tmp_path):
    path = _state(tmp_path / 'r.json', NOW + timedelta(hours=2))
    decision = recovery.decide(path, NOW)
    assert (decision['action'], decision['reason']) == ('suppress', 'state_file_future_timestamp')


def test_record_appends_and_bounds_the_log(tmp_path):
    path = tmp_path / 'logs/ensure_stack_restarts.json'
    for index in range(recovery.MAX_ENTRIES + 5):
        recovery.record(path, NOW - timedelta(days=10) + timedelta(minutes=index), 'started',
                        profile='review')
    attempts = json.loads(path.read_text(encoding='utf-8'))['attempts']
    assert len(attempts) == recovery.MAX_ENTRIES
    assert attempts[-1]['profile'] == 'review'
    with pytest.raises(ValueError):
        recovery.record(path, NOW, 'unknown')


def test_cli_exit_codes(tmp_path):
    decide = [sys.executable, '-B', str(SCRIPT), 'decide', '--project-root', str(tmp_path)]
    assert subprocess.run(decide, capture_output=True, timeout=30).returncode == 0
    for _ in range(3):
        subprocess.run([sys.executable, '-B', str(SCRIPT), 'record', '--project-root', str(tmp_path),
                        '--outcome', 'failed'], capture_output=True, timeout=30, check=True)
    suppressed = subprocess.run(decide, capture_output=True, text=True, timeout=30)
    assert suppressed.returncode == recovery.EXIT_SUPPRESSED
    assert json.loads(suppressed.stdout)['reason'] == 'restart_budget_exhausted'


# --- ensure_stack.ps1 under pwsh with mutating scripts replaced by throws ---------

PWSH = shutil.which('pwsh')
requires_posix_pwsh = pytest.mark.skipif(
    PWSH is None or os.name == 'nt',
    reason='POSIX pwsh integration (Windows paths are in the local acceptance checklist)')
MUTATION = 'MUTATING_PATH_REACHED'


def _project(tmp_path):
    root = tmp_path / 'project'
    (root / 'scripts').mkdir(parents=True)
    (root / 'backend/scripts').mkdir(parents=True)
    (root / 'backend/.venv/Scripts').mkdir(parents=True)
    (root / 'logs').mkdir()
    shutil.copy(PROJECT / 'scripts/ensure_stack.ps1', root / 'scripts/ensure_stack.ps1')
    for name in ('stack_profiles.py', 'stack_recovery.py'):
        shutil.copy(PROJECT / 'backend/scripts' / name, root / 'backend/scripts' / name)
    for name in ('run_stack.ps1', 'stop_stack.ps1'):
        (root / 'scripts' / name).write_text(f"throw '{MUTATION}'\n", encoding='utf-8')
    (root / 'scripts/tonghuasun_readonly.ps1').write_text(
        "function Get-TonghuasunReadOnlyContext { param([string]$ProfilePath) "
        "[pscustomobject]@{ product_home = 'SYNTHETIC'; daily_bar_source_policy = 'tonghuasun_first'; "
        "live_trading_enabled = $false } }\n", encoding='utf-8')
    python = root / 'backend/.venv/Scripts/python.exe'
    python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding='utf-8')
    python.chmod(0o755)
    return root


def _ensure(root, *args):
    # Ports nothing listens on: the health probe fails and the stack reads as down.
    return subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-File',
                           str(root / 'scripts/ensure_stack.ps1'), '-BackendPort', '18999',
                           '-FrontendPort', '18998', *args],
                          capture_output=True, text=True, timeout=120)


@requires_posix_pwsh
def test_ensure_never_switches_a_tracked_profile_implicitly(tmp_path):
    root = _project(tmp_path)
    (root / 'logs/run_stack.pids.json').write_text(
        json.dumps({'schema_version': 'run_stack_pids.v2', 'service_profile': 'review'}), encoding='utf-8')
    result = _ensure(root)  # default profile: full
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert (payload['status'], payload['tracked_service_profile']) == ('profile_mismatch', 'review')
    assert MUTATION not in result.stdout + result.stderr
    assert not (root / 'logs/ensure_stack_restarts.json').exists()
    # v1 metadata predates profiles and means "full".
    (root / 'logs/run_stack.pids.json').write_text(
        json.dumps({'schema_version': 'run_stack_pids.v1'}), encoding='utf-8')
    v1 = _ensure(root, '-ServiceProfile', 'review')
    assert v1.returncode == 2 and json.loads(v1.stdout)['tracked_service_profile'] == 'full'
    assert MUTATION not in v1.stdout + v1.stderr


@requires_posix_pwsh
def test_ensure_suppresses_a_restart_storm_before_stop_or_start(tmp_path):
    root = _project(tmp_path)
    now = datetime.now(timezone.utc)
    _state(root / 'logs/ensure_stack_restarts.json', now, now, now)
    result = _ensure(root, '-ServiceProfile', 'review')
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload['status'] == 'restart_suppressed'
    assert payload['restart_decision']['reason'] == 'restart_budget_exhausted'
    assert MUTATION not in result.stdout + result.stderr


@requires_posix_pwsh
def test_ensure_records_a_failed_start_and_propagates_it(tmp_path):
    root = _project(tmp_path)
    result = _ensure(root, '-ServiceProfile', 'review')
    assert result.returncode != 0
    assert MUTATION in result.stdout + result.stderr  # reached the (stubbed) start
    attempts = json.loads((root / 'logs/ensure_stack_restarts.json').read_text(encoding='utf-8'))['attempts']
    assert [(a['outcome'], a['profile']) for a in attempts] == [('failed', 'review')]
