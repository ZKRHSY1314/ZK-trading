"""Service-profile planner and its binding to scripts/run_stack.ps1 and ensure_stack.ps1.

Portable: the planner is stdlib-only and the PowerShell checks are static. What
run_stack.ps1 actually launches on Windows is part of the local acceptance
checklist (docs/RECOVERY_PROFILE.md), not proven here.
"""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT / 'backend/scripts/stack_profiles.py'
spec = importlib.util.spec_from_file_location('stack_profiles_under_test', SCRIPT)
profiles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profiles)

WORKERS = [key for key, value in profiles.COMPONENTS.items() if value['kind'] == 'worker']
RUN_STACK = (PROJECT / 'scripts/run_stack.ps1').read_text(encoding='utf-8-sig').replace('\r\n', '\n')
ENSURE_STACK = (PROJECT / 'scripts/ensure_stack.ps1').read_text(encoding='utf-8-sig').replace('\r\n', '\n')


def test_review_profile_starts_only_backend_and_frontend(tmp_path):
    plan = profiles.build_plan('review', project_root=tmp_path)
    assert plan['selected'] == ['backend', 'frontend']
    assert set(plan['excluded']) == set(WORKERS)
    assert set(plan['excluded'].values()) == {'not_in_profile'}
    assert plan['live_trading_enabled'] is False and plan['review_only'] is True
    # Nothing that scores, forecasts, simulates, calls models or calibrates.
    for category in ('scoring', 'forecasting', 'simulation', 'model_calls', 'calibration',
                     'market_data_refresh', 'reference_data'):
        assert category in plan['excluded_categories']
    for key in WORKERS:
        assert plan['components'][key]['selected'] is False


def test_review_profile_still_declares_its_database_writes(tmp_path):
    # Backend startup runs SQLiteStore.init(); "review" is not "read-only".
    plan = profiles.build_plan('review', project_root=tmp_path)
    assert set(plan['write_targets']) == {'runtime_database'}
    assert plan['write_targets']['runtime_database'] == str(tmp_path / 'trading_local.sqlite3')
    scopes = ' '.join(write['scope'] for write in plan['expected_writes'])
    assert 'SQLiteStore.init()' in scopes and 'daily_bar_cache normalisation' in scopes
    assert 'request-driven writes' in scopes
    assert plan['backup_before_start'] == [
        {'target': 'runtime_database', 'path': str(tmp_path / 'trading_local.sqlite3')}]
    assert 'market_history_database' not in plan['write_targets']
    assert 'universe_manifest' not in plan['write_targets']


def test_full_profile_is_the_historical_worker_set(tmp_path):
    plan = profiles.build_plan('full', project_root=tmp_path)
    assert plan['selected'] == list(profiles.COMPONENTS)
    assert plan['excluded'] == {}
    assert set(plan['write_targets']) == {'runtime_database', 'market_history_database',
                                          'universe_manifest'}
    no_codex = profiles.build_plan('full', project_root=tmp_path, enable_codex_search=False)
    assert no_codex['excluded'] == {'codex_market_pulse': 'codex_search_disabled',
                                    'codex_decision_review': 'codex_search_disabled'}


def test_plan_is_deterministic_and_identity_covers_its_content(tmp_path):
    first = profiles.build_plan('review', project_root=tmp_path)
    assert first == profiles.build_plan('review', project_root=tmp_path)
    assert first['plan_sha256'] != profiles.build_plan('full', project_root=tmp_path)['plan_sha256']
    assert first['plan_sha256'] != profiles.build_plan(
        'review', project_root=tmp_path, backend_port=8001)['plan_sha256']


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError):
        profiles.build_plan('everything')
    result = subprocess.run([sys.executable, '-B', str(SCRIPT), 'plan', '--profile', 'everything'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 2


def test_cli_plan_writes_only_the_plan_record(tmp_path):
    database = tmp_path / 'trading_local.sqlite3'
    database.write_bytes(b'SYNTHETIC-NOT-A-DATABASE')
    refused = subprocess.run([sys.executable, '-B', str(SCRIPT), 'plan', '--profile', 'review',
                              '--project-root', str(tmp_path), '--output', str(database)],
                             capture_output=True, text=True, timeout=30)
    assert refused.returncode == 2
    assert database.read_bytes() == b'SYNTHETIC-NOT-A-DATABASE'

    printed = subprocess.run([sys.executable, '-B', str(SCRIPT), 'plan', '--profile', 'review',
                              '--project-root', str(tmp_path)],
                             capture_output=True, text=True, timeout=30)
    assert printed.returncode == 0
    assert json.loads(printed.stdout)['selected'] == ['backend', 'frontend']
    assert not (tmp_path / 'logs').exists()  # printing a plan writes nothing

    target = tmp_path / 'logs' / 'stack_plan.json'
    recorded = subprocess.run([sys.executable, '-B', str(SCRIPT), 'plan', '--profile', 'review',
                               '--project-root', str(tmp_path), '--output', str(target)],
                              capture_output=True, text=True, timeout=30)
    assert recorded.returncode == 0
    assert json.loads(target.read_text(encoding='utf-8')) == json.loads(recorded.stdout)
    assert sorted(path.name for path in tmp_path.rglob('*')) == sorted(
        ['logs', 'stack_plan.json', 'trading_local.sqlite3'])


def test_heartbeat_config_mismatch_detection():
    key = 'market_history_refresh_worker'
    good = dict(profiles.COMPONENTS[key]['heartbeat_config'])
    assert profiles.heartbeat_config_mismatches(key, good) == []
    assert profiles.heartbeat_config_mismatches(key, {**good, 'days': 500}) == ['days']
    assert profiles.heartbeat_config_mismatches(key, None) == sorted(good)
    assert profiles.heartbeat_config_mismatches('instrument_catalog_refresh_worker', {
        'interval_seconds': 86400, 'retry_interval_seconds': 900, 'minimum_member_count': 4000,
        'minimum_retained_ratio': 0.9}) == []
    assert profiles.heartbeat_config_mismatches('codex_market_pulse', {
        'configured_model': 'another-model', 'reasoning_effort': 'medium'}) == ['configured_model']
    assert profiles.heartbeat_config_mismatches('control_worker', None) == []


def _ps_array(variable):
    """Return the tokens of `$variable = @( ... )` in run_stack.ps1."""
    match = re.search(r'\$' + variable + r' = @\((.*?)\n\s*\)', RUN_STACK, re.S)
    assert match, variable
    return re.findall(r'"([^"]*)"|(\$\w+)', match.group(1))


@pytest.mark.parametrize('key,variable', [
    ('control_worker', 'workerArgs'),
    ('reference_data_worker', 'referenceArgs'),
    ('full_market_feature_worker', 'fullMarketFeatureArgs'),
    ('market_history_refresh_worker', 'marketHistoryRefreshArgs'),
    ('capital_flow_refresh_worker', 'capitalFlowRefreshArgs'),
    ('instrument_catalog_refresh_worker', 'instrumentCatalogArgs'),
    ('full_market_calibration_worker', 'fullMarketCalibrationArgs'),
    ('codex_market_pulse', 'codexPulseArgs'),
    ('codex_decision_review', 'codexDecisionArgs'),
])
def test_planner_arguments_match_what_run_stack_launches(key, variable):
    tokens = [literal or {'$ApiBase': '{api_base}', '$CodexPulseModel': profiles.CODEX_MODEL,
                          '$CodexPulseReasoningEffort': profiles.CODEX_REASONING_EFFORT}.get(name, name)
              for literal, name in _ps_array(variable)]
    # run_stack prefixes "-X utf8 <script>"; the rest must be the planner's contract.
    assert tokens[:2] == ['-X', 'utf8']
    assert tokens[3:] == profiles.COMPONENTS[key]['args']


@pytest.mark.parametrize('key', WORKERS)
def test_every_worker_launch_is_gated_on_the_resolved_plan(key):
    if key in profiles.CODEX_COMPONENTS:
        assert 'if ($CodexComponentsSelected) {\n        $codexPulseArgs = @(' in RUN_STACK
        return
    gate = f'if (Test-ComponentSelected "{key}") {{'
    # Once for the launch, once for the recorded metadata.
    assert RUN_STACK.count(gate) == 2
    assert f'New-ExcludedComponentMetadata -Name "{key}"' in RUN_STACK


def test_run_stack_records_profile_and_plan_before_launching():
    assert '[ValidateSet("full", "review")]\n    [string]$ServiceProfile = "full"' in RUN_STACK
    assert 'schema_version = "run_stack_pids.v2"' in RUN_STACK
    assert 'service_profile = $ServiceProfile' in RUN_STACK
    assert 'plan_sha256 = [string]$StackPlan.plan_sha256' in RUN_STACK
    # Codex excluded by profile must be recorded as disabled, not as the raw switch.
    assert 'enabled = $EnableCodexSearch' not in RUN_STACK
    recorded = RUN_STACK.index('$recordedPlanText = & $Python @planArgs --output $PlanFile')
    # The plan file is written after the preflight refusals and before the first launch.
    assert RUN_STACK.index('A tracked stack is still running') < recorded
    assert RUN_STACK.index('is already in use') < recorded
    assert recorded < RUN_STACK.index('$backend = Start-Process')
    # The live-trading refusal and backend safety gates are unchanged.
    assert 'throw "ENABLE_LIVE_TRADING must be false before starting the stack."' in RUN_STACK
    assert 'Backend safety gate failed: /health.live_trading_enabled is not false.' in RUN_STACK


def test_ensure_stack_check_only_still_exits_before_any_helper():
    check_only = ENSURE_STACK.index('if ($CheckOnly) {')
    exit_check_only = ENSURE_STACK.index('exit $LASTEXITCODE', check_only)
    for marker in ('$StackProfileScript', '$StackRecoveryScript', 'tonghuasun_readonly.ps1',
                   '& $RunScript', '& $StopScript', '& $Python'):
        assert ENSURE_STACK.index(marker) > exit_check_only, marker


def test_ensure_stack_is_profile_aware_and_budgets_restarts():
    assert '-ServiceProfile $ServiceProfile' in ENSURE_STACK
    assert '$profileMatches -and' in ENSURE_STACK
    mismatch = ENSURE_STACK.index('status = "profile_mismatch"')
    decide = ENSURE_STACK.index('$StackRecoveryScript decide')
    stop = ENSURE_STACK.index('& $StopScript')
    run = ENSURE_STACK.index('& $RunScript')
    assert mismatch < decide < stop < run
    assert '--outcome failed' in ENSURE_STACK and '--outcome started' in ENSURE_STACK


# --- db_inventory.py: backup / rollback verification helper ------------------------

_inv_spec = importlib.util.spec_from_file_location(
    'db_inventory_under_test', PROJECT / 'backend/scripts/db_inventory.py')
db_inventory = importlib.util.module_from_spec(_inv_spec)
_inv_spec.loader.exec_module(db_inventory)


def _synthetic_database(path):
    import sqlite3
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE daily_bar_cache(symbol TEXT, trade_date TEXT)')
        connection.executemany('INSERT INTO daily_bar_cache VALUES (?, ?)',
                               [('SYN_A', '2026-09-01'), ('SYN_B', '2026-09-01')])
    return path


def test_inventory_is_read_only_and_detects_changes(tmp_path):
    import sqlite3
    database = _synthetic_database(tmp_path / 'synthetic.sqlite3')
    before_bytes = database.read_bytes()
    before = db_inventory.inventory(database)
    assert database.read_bytes() == before_bytes
    assert before['status'] == 'ok' and before['row_counts'] == {'daily_bar_cache': 2}
    assert before['sha256'] == db_inventory.file_sha256(database)

    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO daily_bar_cache VALUES ('SYN_C', '2026-09-02')")
        connection.execute('CREATE TABLE added(x)')
    after = db_inventory.inventory(database)
    diff = db_inventory.compare(before, after)
    assert diff['bytes_identical'] is False and diff['schema_identical'] is False
    assert diff['row_count_changes']['daily_bar_cache'] == {'before': 2, 'after': 3}
    assert diff['row_count_changes']['added'] == {'before': None, 'after': 0}

    # A restored copy is byte-identical to the backup it came from.
    restored = tmp_path / 'restored.sqlite3'
    restored.write_bytes(before_bytes)
    assert db_inventory.compare(before, db_inventory.inventory(restored))['bytes_identical'] is True


def test_inventory_never_creates_a_database_and_writes_only_its_record(tmp_path):
    missing = tmp_path / 'absent.sqlite3'
    assert db_inventory.inventory(missing)['status'] == 'unavailable'
    assert not missing.exists()
    database = _synthetic_database(tmp_path / 'synthetic.sqlite3')
    script = PROJECT / 'backend/scripts/db_inventory.py'
    refused = subprocess.run([sys.executable, '-B', str(script), '--database', str(database),
                              '--project-root', str(tmp_path), '--label', '../escape'],
                             capture_output=True, text=True, timeout=30)
    assert refused.returncode == 2
    written = subprocess.run([sys.executable, '-B', str(script), '--database', str(database),
                              '--project-root', str(tmp_path), '--label', 'before'],
                             capture_output=True, text=True, timeout=30)
    assert written.returncode == 0
    assert json.loads((tmp_path / 'logs/db_inventory_before.json').read_text())['row_counts'] == {
        'daily_bar_cache': 2}
