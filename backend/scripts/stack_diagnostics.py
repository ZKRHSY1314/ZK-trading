"""Offline-capable stack inspection: no application imports, workers or database writes."""
from __future__ import annotations

import argparse
import base64
from datetime import date, datetime, timedelta, timezone
import http.client
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORKERS = {
    'control_worker': ('control_plane', 1800),
    'reference_data_worker': ('reference_data', 18000),
    'full_market_feature_worker': ('full_market_feature', 18000),
    'market_history_refresh_worker': ('market_history_refresh', 18000),
    'capital_flow_refresh_worker': ('capital_flow_refresh', 1800),
    'instrument_catalog_refresh_worker': ('instrument_catalog_refresh', 90000),
    'full_market_calibration_worker': ('full_market_calibration', 90000),
    'codex_market_pulse': ('codex_market_pulse', 18000),
    'codex_decision_review': ('codex_decision_review', 18000),
}


def read_json(path):
    try:
        if path.stat().st_size > 2_000_000:
            return None
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None


def heartbeat(payload, now, stale_after):
    """A heartbeat describes a cycle, never proves a process is still alive."""
    if not isinstance(payload, dict):
        return {'status': 'missing_or_invalid'}
    try:
        stamp = datetime.fromisoformat(str(payload['completed_at']).replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('ambiguous_time')
        age = (now - stamp).total_seconds()
    except (KeyError, ValueError, TypeError):
        return {'status': 'invalid_timestamp'}
    last = str(payload.get('status', 'unknown')).lower()
    if age < -60:
        status = 'future_timestamp'
    elif age > stale_after:
        status = 'stale'
    elif last == 'running':
        status = 'running'
    elif last in {'completed', 'healthy', 'ok', 'success', 'ready'}:
        status = 'healthy'
    else:
        status = 'degraded'
    return {'status': status, 'last_status': last, 'age_seconds': round(age, 1),
            'pid': payload.get('pid'), 'completed_at': payload['completed_at']}


def local_http(port, path, *, parse_json=True):
    """Fixed numeric loopback, GET only; do not follow redirects or expose bodies/errors."""
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
    try:
        connection.request('GET', path)
        response = connection.getresponse()
        body = response.read(1_000_001)
        result = {'reachable': True, 'http_status': response.status}
        if parse_json and len(body) <= 1_000_000:
            try:
                value = json.loads(body)
                if isinstance(value, dict):
                    result['status'] = value.get('status')
                    flag = value.get('live_trading_enabled')
                    result['live_trading_enabled'] = flag if isinstance(flag, bool) else None
            except (ValueError, UnicodeError):
                pass
        return result
    except (OSError, http.client.HTTPException):
        return {'reachable': False}
    finally:
        connection.close()


def process_snapshot(root):
    """Validate saved process identities locally; never return command lines or credentials."""
    shell = shutil.which('powershell.exe')
    if os.name != 'nt' or not shell:
        return {'status': 'unavailable', 'processes': {}}
    literal = str(root).replace("'", "''")
    script = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$root = '__ROOT__'
$rows = @{}
$metadataPath = Join-Path $root 'logs\run_stack.pids.json'
$metadata = if (Test-Path -LiteralPath $metadataPath) {
    try { Get-Content -Raw -Encoding UTF8 -LiteralPath $metadataPath | ConvertFrom-Json } catch { $null }
} else { $null }
foreach ($name in @('backend','frontend','control_worker','reference_data_worker',
 'full_market_feature_worker','market_history_refresh_worker','capital_flow_refresh_worker',
 'instrument_catalog_refresh_worker','full_market_calibration_worker','codex_market_pulse','codex_decision_review')) {
    $item = $metadata.$name
    $identity = 'missing_metadata'
    if ($item.pid -and $item.created_at -and $item.executable_path -and $item.command_line -and $item.command_marker) {
        try {
            $row = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$item.pid)"
            $identity = 'not_running'
            if ($row) {
                $identity = 'identity_mismatch'
                $matches = $row.ExecutablePath -and $row.CommandLine -and
                    [IO.Path]::GetFullPath($row.ExecutablePath).Equals([IO.Path]::GetFullPath($item.executable_path),[StringComparison]::OrdinalIgnoreCase) -and
                    $row.CommandLine -ceq $item.command_line -and $row.CommandLine.Contains($item.command_marker) -and
                    [Math]::Abs((([DateTime]$row.CreationDate).ToUniversalTime() - [DateTimeOffset]::Parse($item.created_at).UtcDateTime).TotalSeconds) -le 5
                if ($matches) { $identity = 'matched' }
            }
        } catch { $identity = 'unverifiable' }
    }
    $rows[$name] = @{identity=$identity; runtime_pid=$item.runtime_pid; enabled=$item.enabled}
}
$task = Get-ScheduledTask -TaskName 'ZKTrading-ReviewOnly-ControlPlane' -ErrorAction SilentlyContinue
$taskInfo = if ($task) { Get-ScheduledTaskInfo -InputObject $task }
$supervisor = @{installed=($null -ne $task); state=([string]$task.State);
    last_result=if ($taskInfo) {$taskInfo.LastTaskResult} else {$null};
    definition_valid=$false; operational_ok=$false}
if ($task) {
    # Reuse the existing read-only definition/principal/trigger/last-run validator.
    $codexFlag = if ($metadata.codex_market_pulse.enabled -eq $true) {1} else {0}
    try {
        $taskStatus = & (Join-Path $root 'scripts\control_plane_task.ps1') -Action Status -EnableCodexSearch $codexFlag | ConvertFrom-Json
        $supervisor.definition_valid = $taskStatus.definition_valid
        $supervisor.operational_ok = $taskStatus.operational_ok
    } catch { }
}
$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
@{status='observed'; processes=$rows; last_boot_at=$boot;
 supervisor=$supervisor} | ConvertTo-Json -Depth 5
'''.replace('__ROOT__', literal)
    environment = {k: v for k, v in os.environ.items() if k.upper() != 'PSMODULEPATH'}
    try:
        result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-EncodedCommand',
                                 base64.b64encode(script.encode('utf-16-le')).decode('ascii')],
                                capture_output=True, encoding='utf-8', timeout=30, env=environment)
        if result.returncode != 0:
            return {'status': 'unavailable', 'processes': {}}
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {'status': 'unavailable', 'processes': {}}


def market_snapshot(path, now):
    """Recent cache continuity; weekday lag is explicitly not an exchange calendar."""
    today = now.astimezone(timezone(timedelta(hours=8))).date()
    # A daily bar is not expected before 15:15 local time.
    local = now.astimezone(timezone(timedelta(hours=8)))
    expected = today - timedelta(days=int((local.hour, local.minute) < (15, 15)))
    while expected.weekday() > 4:
        expected -= timedelta(days=1)
    start = (today - timedelta(days=45)).isoformat()
    con = None
    try:
        con = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
        con.execute('PRAGMA query_only=ON')
        # Bound query time even if the cache has no suitable index.
        import time
        deadline = time.monotonic() + 10
        con.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
        rows = con.execute('''SELECT trade_date, quality_status, COUNT(*)
                              FROM daily_bar_cache GROUP BY trade_date, quality_status''').fetchall()
    except sqlite3.Error:
        return {'status': 'unavailable', 'read_only': True}
    finally:
        if con is not None:
            con.close()
    counts = {}
    invalid = future = 0
    latest_valid = None
    for value, quality, count in rows:
        try:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value:
                raise ValueError('noncanonical_date')
        except (TypeError, ValueError):
            invalid += count
            continue
        if parsed > today:
            future += count
            continue
        if quality != 'ready':
            continue
        latest_valid = max(latest_valid or value, value)
        if start <= value <= expected.isoformat():
            counts[value] = counts.get(value, 0) + count
    latest = max(counts, default=None)
    peak = max(counts.values(), default=0)
    current = counts.get(expected.isoformat(), 0)
    ratio = current / peak if peak else None
    lag = None
    if latest_valid:
        last = date.fromisoformat(latest_valid)
        lag = sum((last + timedelta(days=i)).weekday() < 5
                  for i in range(1, max(0, (expected-last).days) + 1))
    status = 'empty' if latest_valid is None else (
        'stale_or_incomplete' if not latest or not current or ratio < 0.9
        else 'calendar_unverified')
    return {'status': status, 'read_only': True, 'latest_valid_date': latest_valid,
            'expected_date_proxy': expected.isoformat(), 'calendar_source': 'weekday_proxy',
            'calendar_verified': False, 'weekday_lag_proxy': lag,
            'coverage_basis': 'recent_45_calendar_day_peak_ready_rows_not_asof_universe',
            'expected_date_ready_rows': current, 'recent_peak_ready_rows': peak,
            'coverage_ratio_proxy': round(ratio, 6) if ratio is not None else None,
            'invalid_date_rows': invalid, 'future_date_rows': future,
            'recent_ready_rows': dict(sorted(counts.items())[-10:])}


def inspect(root, now, *, runtime=None, http_get=local_http):
    runtime = process_snapshot(root) if runtime is None else runtime
    processes = runtime.get('processes', {})
    workers = {}
    for key, (filename, threshold) in WORKERS.items():
        tracked = processes.get(key, {})
        pulse = heartbeat(read_json(root / 'backend/logs' / (filename+'_heartbeat.json')),
                          now, threshold)
        disabled = key.startswith('codex_') and tracked.get('enabled') is False
        pid_matches = (isinstance(pulse.get('pid'), int) and pulse['pid'] > 0
                       and pulse['pid'] == tracked.get('runtime_pid'))
        workers[key] = {**pulse, 'process_identity': tracked.get('identity', 'unverifiable'),
                        'heartbeat_pid_matches': pid_matches,
                        'disabled': disabled}
        workers[key]['operational_status'] = (
            'disabled' if disabled and tracked.get('identity') == 'not_running' else
            'disabled' if disabled and tracked.get('identity') == 'missing_metadata' else
            'not_running_or_unverified' if tracked.get('identity') != 'matched' else
            'heartbeat_pid_mismatch' if not pid_matches else pulse['status'])
    health = http_get(8000, '/health')
    ready = http_get(8000, '/readyz')
    frontend = http_get(3000, '/', parse_json=False)
    issues = []
    if health.get('live_trading_enabled') is not False:
        issues.append('live_trading_state_unverified_or_unsafe')
    for name, response in [('backend', health), ('readiness', ready), ('frontend', frontend)]:
        if not response.get('reachable') or response.get('http_status') != 200:
            issues.append(name+'_unavailable')
    for name in ('backend', 'frontend'):
        if processes.get(name, {}).get('identity') != 'matched':
            issues.append(name+'_process_unverified')
    if ready.get('status') != 'ready' or ready.get('live_trading_enabled') is not False:
        issues.append('backend_not_ready_or_unsafe')
    if not runtime.get('supervisor', {}).get('installed'):
        issues.append('persistent_supervisor_missing_or_unverified')
    elif not (runtime['supervisor'].get('definition_valid') is True
              and runtime['supervisor'].get('operational_ok') is True):
        issues.append('persistent_supervisor_definition_and_run_require_validation')
    for name, value in workers.items():
        if value['operational_status'] not in {'healthy', 'disabled'}:
            issues.append(name+'_'+value['operational_status'])
    market = market_snapshot(root / 'trading_local.sqlite3', now)
    if market['status'] != 'healthy':
        issues.append('market_'+market['status'])
    if market.get('invalid_date_rows') or market.get('future_date_rows'):
        issues.append('market_invalid_or_future_dates')
    return {'schema_version': 'stack_diagnostics.v1', 'checked_at': now.isoformat(),
            'status': 'needs_attention' if issues else 'healthy', 'issues': issues,
            'read_only': True, 'database_writes': False, 'starts_workers': False,
            'live_trading_enabled': health.get('live_trading_enabled'),
            'runtime': runtime, 'backend': health, 'readiness': ready, 'frontend': frontend,
            'workers': workers, 'market': market,
            'automatic_restart_attempted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    # Diagnostic output cannot overwrite project inputs, heartbeats or the production database.
    target = args.project_root.resolve() / 'logs/stack_diagnostics.json'
    if args.output and args.output.resolve() != target:
        parser.error('--output must be <project-root>/logs/stack_diagnostics.json')
    report = inspect(args.project_root.resolve(), datetime.now(timezone.utc))
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.tmp')
        temporary.write_text(encoded+'\n', encoding='utf-8')
        temporary.replace(target)
    print(encoded)
    return 0 if report['status'] == 'healthy' else 2


if __name__ == '__main__':
    raise SystemExit(main())
