"""Fault injection for the offline supervisor probe; synthetic SQLite only."""
import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/stack_diagnostics.py'
spec = importlib.util.spec_from_file_location('stack_diagnostics_under_test', SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
NOW = datetime(2026, 9, 13, 4, tzinfo=timezone.utc)


def database(root, rows=()):
    path = root / 'trading_local.sqlite3'
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE daily_bar_cache(symbol TEXT, trade_date TEXT, quality_status TEXT)')
        con.executemany('INSERT INTO daily_bar_cache VALUES (?,?,?)', rows)
    return path


@pytest.mark.parametrize('payload,status', [
    (None, 'missing_or_invalid'),
    ([], 'missing_or_invalid'),
    ({'completed_at': 'bad'}, 'invalid_timestamp'),
    ({'completed_at': '2026-09-13T04:00:00'}, 'invalid_timestamp'),
    ({'completed_at': (NOW+timedelta(days=1)).isoformat()}, 'future_timestamp'),
    ({'completed_at': (NOW-timedelta(days=2)).isoformat(), 'status': 'completed'}, 'stale'),
    ({'completed_at': NOW.isoformat(), 'status': 'running'}, 'running'),
    ({'completed_at': NOW.isoformat(), 'status': 'failed'}, 'degraded'),
    ({'completed_at': NOW.isoformat(), 'status': 'new_unknown_status'}, 'degraded'),
    ({'completed_at': NOW.isoformat(), 'status': 'completed'}, 'healthy'),
])
def test_heartbeat_does_not_infer_success_or_trust_future_time(payload, status):
    assert probe.heartbeat(payload, NOW, 1800)['status'] == status


def test_latest_single_row_does_not_hide_partial_market_and_bad_dates(tmp_path):
    rows = [(f'SYN_{i}', '2026-09-10', 'ready') for i in range(10)]
    rows += [('SYN_0', '2026-09-11', 'ready'), ('BAD', 'ERROR', 'error'),
             ('BAD2', '2026-99-11', 'ready'), ('FUTURE', '2099-01-01', 'ready')]
    path = database(tmp_path, rows)
    before = path.read_bytes()
    result = probe.market_snapshot(path, NOW)
    assert path.read_bytes() == before
    assert result['latest_valid_date'] == '2026-09-11'
    assert result['expected_date_proxy'] == '2026-09-11'
    assert result['invalid_date_rows'] == 2
    assert result['future_date_rows'] == 1
    assert result['coverage_ratio_proxy'] == 0.1
    assert result['status'] == 'stale_or_incomplete'


def test_no_db_is_not_created_and_empty_cache_is_not_ready(tmp_path):
    path = tmp_path / 'trading_local.sqlite3'
    assert probe.market_snapshot(path, NOW)['status'] == 'unavailable'
    assert not path.exists()
    database(tmp_path)
    assert probe.market_snapshot(path, NOW)['status'] == 'empty'


def test_weekend_and_preclose_are_labelled_calendar_proxy(tmp_path):
    path = database(tmp_path, [('SYN_A', '2026-09-11', 'ready')])
    sunday = probe.market_snapshot(path, NOW)
    assert sunday['weekday_lag_proxy'] == 0
    assert sunday['status'] == 'calendar_unverified'
    monday_morning = probe.market_snapshot(path, datetime(2026, 9, 14, 1, tzinfo=timezone.utc))
    assert monday_morning['expected_date_proxy'] == '2026-09-11'
    assert monday_morning['calendar_verified'] is False


def test_offline_keeps_actual_live_state_unknown_and_does_not_expose_heartbeat_error(tmp_path):
    path = tmp_path / 'backend/logs'
    path.mkdir(parents=True)
    (path/'control_plane_heartbeat.json').write_text(json.dumps({
        'pid': 10, 'status': 'completed', 'completed_at': NOW.isoformat(),
        'error': 'SYNTHETIC_SECRET_MUST_NOT_LEAK'}))
    result = probe.inspect(tmp_path, NOW, runtime={'processes': {
        'control_worker': {'identity': 'not_running', 'runtime_pid': 10}}},
        http_get=lambda *args, **kwargs: {'reachable': False})
    worker = result['workers']['control_worker']
    assert worker['status'] == 'healthy'
    assert worker['operational_status'] == 'not_running_or_unverified'
    assert result['live_trading_enabled'] is None
    assert result['automatic_restart_attempted'] is False
    assert 'SYNTHETIC_SECRET' not in json.dumps(result)
    assert not (tmp_path/'trading_local.sqlite3').exists()


def test_pid_mismatch_does_not_pass_with_good_endpoint_and_heartbeat(tmp_path):
    folder = tmp_path / 'backend/logs'
    folder.mkdir(parents=True)
    (folder/'control_plane_heartbeat.json').write_text(json.dumps({
        'pid': 10, 'status': 'completed', 'completed_at': NOW.isoformat()}))
    result = probe.inspect(tmp_path, NOW, runtime={'processes': {
        'control_worker': {'identity': 'matched', 'runtime_pid': 20}}},
        http_get=lambda *args, **kwargs: {'reachable': True, 'http_status': 200,
                                         'status': 'ready', 'live_trading_enabled': False})
    assert result['workers']['control_worker']['operational_status'] == 'heartbeat_pid_mismatch'
    assert result['status'] == 'needs_attention'


def test_unsafe_endpoint_never_reports_ready(tmp_path):
    result = probe.inspect(tmp_path, NOW, runtime={}, http_get=lambda *args, **kwargs: {
        'reachable': True, 'http_status': 200, 'status': 'ready', 'live_trading_enabled': True})
    assert 'live_trading_state_unverified_or_unsafe' in result['issues']
    assert result['status'] == 'needs_attention'
    assert result['starts_workers'] is False


def test_output_cannot_overwrite_database(tmp_path):
    path = database(tmp_path)
    before = path.read_bytes()
    result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--project-root', str(tmp_path),
                             '--output', str(path)], capture_output=True, timeout=15)
    assert result.returncode == 2
    assert path.read_bytes() == before


def test_check_only_entrypoint_cannot_reach_start_or_stop(tmp_path):
    shell = probe.shutil.which('powershell.exe')
    if not shell:
        pytest.skip('Windows PowerShell integration')
    root = tmp_path
    scripts = root/'scripts'
    scripts.mkdir()
    project = SCRIPT.parents[2]
    (scripts/'ensure_stack.ps1').write_bytes((project/'scripts/ensure_stack.ps1').read_bytes())
    (scripts/'check_stack.ps1').write_text("'{\"read_only\":true}'; exit 2", encoding='utf-8')
    for name in ('run_stack.ps1', 'stop_stack.ps1', 'tonghuasun_readonly.ps1'):
        (scripts/name).write_text("throw 'MUTATING_OR_PLUGIN_PATH_REACHED'")
    result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                             '-File', str(scripts/'ensure_stack.ps1'), '-CheckOnly'],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 2
    assert json.loads(result.stdout)['read_only'] is True
    assert 'MUTATING_OR_PLUGIN_PATH_REACHED' not in result.stderr


def test_real_process_identity_rejects_reused_pid_metadata(tmp_path):
    shell = probe.shutil.which('powershell.exe')
    if not shell or os.name != 'nt':
        pytest.skip('Windows process identity integration')
    (tmp_path/'logs').mkdir()
    path = str(tmp_path/'logs/run_stack.pids.json').replace("'", "''")
    helper = r'''
$r = Get-CimInstance Win32_Process -Filter "ProcessId = $PID"
@{backend=@{pid=$PID; created_at=$r.CreationDate.ToUniversalTime().ToString('o');
executable_path=$r.ExecutablePath; command_line=$r.CommandLine; command_marker='-EncodedCommand'}} |
ConvertTo-Json -Depth 3 | Set-Content -LiteralPath '__PATH__' -Encoding UTF8
[Console]::WriteLine('ready')
[Console]::ReadLine() | Out-Null
'''.replace('__PATH__', path)
    environment = {k: v for k, v in os.environ.items() if k.upper() != 'PSMODULEPATH'}
    encoded = probe.base64.b64encode(helper.encode('utf-16-le')).decode('ascii')
    child = subprocess.Popen([shell, '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        metadata_path = tmp_path/'logs/run_stack.pids.json'
        deadline = time.monotonic()+10
        while probe.read_json(metadata_path) is None and time.monotonic() < deadline:
            assert child.poll() is None
            time.sleep(0.05)
        assert probe.read_json(metadata_path) is not None
        assert probe.process_snapshot(tmp_path)['processes']['backend']['identity'] == 'matched'
        data = json.loads(metadata_path.read_text(encoding='utf-8-sig'))
        data['backend']['created_at'] = '2000-01-01T00:00:00Z'
        metadata_path.write_text(json.dumps(data), encoding='utf-8')
        assert probe.process_snapshot(tmp_path)['processes']['backend']['identity'] == 'identity_mismatch'
    finally:
        try:
            child.communicate(input='\n', timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate(timeout=5)
