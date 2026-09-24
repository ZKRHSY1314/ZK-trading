"""Explicit service profiles for scripts/run_stack.ps1: what starts, where it writes.

Stdlib only; no application imports, no processes, no database access. The
``plan`` command prints the resolved profile so an operator (and run_stack.ps1)
can see, before anything starts, which components are selected, their exact
arguments, the database/manifest paths they target and the writes they make.

Profiles
--------
``full``    The historical run_stack.ps1 behaviour: backend, frontend and every
            worker; the two Codex workers only when Codex search is enabled.
``review``  Backend and frontend only. No scoring, forecasting, simulation,
            model-call, calibration, market-data or reference-data worker is
            started. Backend startup still runs ``SQLiteStore.init()`` (schema
            creation/migration and daily_bar_cache normalisation updates), and
            requests made from the cockpit can still write; neither is
            read-only, so the plan lists both and requires a backup first.

Exit codes: 0 plan printed, 2 invalid arguments.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

SCHEMA_VERSION = 'stack_plan.v1'
ROOT = Path(__file__).resolve().parents[2]
PROFILES = ('full', 'review')
DEFAULT_PROFILE = 'full'
CODEX_MODEL = 'gpt-5.5'
CODEX_REASONING_EFFORT = 'medium'
CODEX_COMPONENTS = ('codex_market_pulse', 'codex_decision_review')

# Write targets. Paths are resolved against the project root in build_plan().
RUNTIME_DB = 'runtime_database'
MARKET_HISTORY_DB = 'market_history_database'
UNIVERSE_MANIFEST = 'universe_manifest'
TARGET_PATHS = {
    RUNTIME_DB: 'trading_local.sqlite3',
    MARKET_HISTORY_DB: 'market_history.sqlite3',
    UNIVERSE_MANIFEST: 'backend/logs/current_a_share_universe.json',
}

# Order matches run_stack.ps1's launch order and its run_stack.pids.json keys.
# ``args`` are the exact tokens run_stack.ps1 passes after the script path;
# ``heartbeat_config`` is what the worker echoes into its heartbeat and what
# run_stack/ensure_stack/stack_diagnostics compare against.
COMPONENTS: dict[str, dict] = {
    'backend': {
        'kind': 'service',
        'command_marker': 'app.main:app',
        'args': ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '{backend_port}'],
        'heartbeat': None,
        'heartbeat_config': {},
        'categories': ['api'],
        'writes': [
            {'target': RUNTIME_DB, 'scope': 'SQLiteStore.init() at startup: CREATE TABLE/INDEX IF NOT '
             'EXISTS, ALTER TABLE migrations, decision-day run_kind and evaluation policy-version '
             'migrations, and daily_bar_cache normalisation UPDATEs (adjustment_mode, volume_unit, '
             'Sina-fallback quality_status)'},
            {'target': RUNTIME_DB, 'scope': 'request-driven writes: any POST from the cockpit or an '
             'API client (manual control-plane runs, backtests, proposals, ingest endpoints)'},
        ],
        'external_calls': ['on-demand market-data requests triggered by cockpit actions'],
    },
    'frontend': {
        'kind': 'service',
        'command_marker': 'node_modules/vite/bin/vite.js',
        'args': ['--host', '127.0.0.1', '--port', '{frontend_port}', '--strictPort'],
        'heartbeat': None,
        'heartbeat_config': {},
        'categories': ['ui'],
        'writes': [],
        'external_calls': [],
    },
    'control_worker': {
        'kind': 'worker',
        'script': 'backend/scripts/control_plane_loop.py',
        'args': ['--api-base', '{api_base}', '--profile', 'adaptive', '--interval-seconds', '900',
                 '--max-cycles', '0'],
        'heartbeat': 'control_plane',
        'heartbeat_config': {},
        'categories': ['scoring', 'forecasting', 'simulation', 'market_data_refresh'],
        'writes': [
            {'target': RUNTIME_DB, 'scope': 'POST /api/control-plane/run-once (adaptive): public-opinion '
             'runs, daily_bar_cache refresh of up to 25 symbols, decision snapshots '
             '(forecast_decisions, forecast_decision_days), forecast outcomes/evaluations, '
             'calibration proposals, training feedback; the full stage also runs the controlled '
             'simulation task chain'},
        ],
        'external_calls': ['market-data providers via the backend'],
    },
    'reference_data_worker': {
        'kind': 'worker',
        'script': 'backend/scripts/reference_data_loop.py',
        'args': ['--interval-seconds', '14400', '--max-cycles', '0', '--board-limit', '50',
                 '--disclosure-limit', '500', '--global-days', '30', '--rate-limit-seconds', '0.2',
                 '--cycle-timeout-seconds', '900', '--skip-sox'],
        'heartbeat': 'reference_data',
        'heartbeat_config': {},
        'categories': ['reference_data'],
        'writes': [
            {'target': RUNTIME_DB, 'scope': 'scripts.ingest_reference_data --apply: '
             'sector_membership_snapshots, sector_membership_snapshot_members, '
             'sector_membership_history, disclosure_facts, global_market_bars'},
        ],
        'external_calls': ['reference-data providers'],
    },
    'full_market_feature_worker': {
        'kind': 'worker',
        'script': 'backend/scripts/full_market_feature_loop.py',
        'args': ['--api-base', '{api_base}', '--interval-seconds', '14400', '--max-cycles', '0',
                 '--candidate-limit', '300', '--lookback-bars', '120', '--timeout-seconds', '300'],
        'heartbeat': 'full_market_feature',
        'heartbeat_config': {'interval_seconds': 14400, 'timeout_seconds': 300,
                             'candidate_limit': 300, 'lookback_bars': 120},
        'categories': ['scoring'],
        'writes': [
            {'target': RUNTIME_DB, 'scope': 'POST full-market-scan/run?persist=true: '
             'full_market_feature_runs, full_market_feature_state, auto_discovered_candidates '
             '(replaced)'},
        ],
        'external_calls': [],
    },
    'market_history_refresh_worker': {
        'kind': 'worker',
        'script': 'backend/scripts/market_history_refresh_loop.py',
        'args': ['--api-base', '{api_base}', '--interval-seconds', '14400',
                 '--retry-interval-seconds', '900', '--max-cycles', '0', '--days', '150',
                 '--batch-size', '200', '--max-workers', '20', '--seed-batch-size', '500',
                 '--gap-recovery-limit', '500', '--deadline-seconds', '900'],
        'heartbeat': 'market_history_refresh',
        'heartbeat_config': {'interval_seconds': 14400, 'retry_interval_seconds': 900,
                             'deadline_seconds': 900, 'days': 150, 'batch_size': 200,
                             'max_workers': 20, 'seed_batch_size': 500, 'gap_recovery_limit': 500},
        'categories': ['market_data_refresh', 'scoring'],
        'writes': [
            {'target': RUNTIME_DB, 'scope': 'daily_bar_cache refresh (network) and the persisted '
             'full-market scan'},
            {'target': MARKET_HISTORY_DB, 'scope': 'daily_bars, instruments, universe_snapshots, '
             'universe_members, ingest_runs'},
        ],
        'external_calls': ['market-data providers (tonghuasun_first, then Sina, then Tencent)'],
    },
    'capital_flow_refresh_worker': {
        'kind': 'worker',
        'script': 'backend/scripts/capital_flow_refresh_loop.py',
        'args': ['--api-base', '{api_base}', '--interval-seconds', '900', '--retry-seconds', '300',
                 '--max-cycles', '0'],
        'heartbeat': 'capital_flow_refresh',
        'heartbeat_config': {'interval_seconds': 900, 'retry_interval_seconds': 300},
        'categories': ['market_data_refresh'],
        'writes': [
            {'target': RUNTIME_DB, 'scope': 'capital_flow_ingestion_runs, capital_flow_snapshots '
             '(vendor market capital flow, not account funds)'},
        ],
        'external_calls': ['capital-flow data provider'],
    },
    'instrument_catalog_refresh_worker': {
        'kind': 'worker',
        'script': 'backend/scripts/instrument_catalog_refresh_loop.py',
        'args': ['--api-base', '{api_base}', '--interval-seconds', '86400', '--retry-seconds', '900',
                 '--minimum-member-count', '4000', '--minimum-retained-ratio', '0.9'],
        'heartbeat': 'instrument_catalog_refresh',
        'heartbeat_config': {'interval_seconds': 86400, 'retry_interval_seconds': 900,
                             'minimum_member_count': 4000, 'minimum_retained_ratio': 0.9},
        'categories': ['reference_data'],
        'writes': [
            {'target': MARKET_HISTORY_DB, 'scope': 'apply=True: instruments, universe_snapshots, '
             'universe_members, incoming_catalog_symbols'},
            {'target': UNIVERSE_MANIFEST, 'scope': 'rewritten after an accepted catalog refresh'},
        ],
        'external_calls': ['instrument-catalog provider'],
    },
    'full_market_calibration_worker': {
        'kind': 'worker',
        'script': 'backend/scripts/full_market_calibration_loop.py',
        'args': ['--api-base', '{api_base}', '--interval-seconds', '86400', '--retry-seconds', '1800',
                 '--deadline-seconds', '900', '--max-cycles', '0'],
        'heartbeat': 'full_market_calibration',
        'heartbeat_config': {'interval_seconds': 86400, 'retry_interval_seconds': 1800,
                             'deadline_seconds': 900},
        'categories': ['calibration'],
        'writes': [
            {'target': RUNTIME_DB, 'scope': 'POST full-market-calibration/run: '
             'full_market_score_calibration_runs and _bins'},
        ],
        'external_calls': [],
    },
    'codex_market_pulse': {
        'kind': 'worker',
        'script': 'backend/scripts/codex_market_pulse.py',
        'args': ['--api-base', '{api_base}', '--interval-seconds', '14400', '--max-cycles', '0',
                 '--timeout-seconds', '900', '--model', CODEX_MODEL,
                 '--reasoning-effort', CODEX_REASONING_EFFORT],
        'heartbeat': 'codex_market_pulse',
        'heartbeat_config': {'configured_model': CODEX_MODEL,
                             'reasoning_effort': CODEX_REASONING_EFFORT},
        'categories': ['model_calls'],
        'writes': [
            {'target': RUNTIME_DB, 'scope': 'POST public-opinion/evidence/ingest: public_opinion_runs, '
             '_items, _sector_signals'},
        ],
        'external_calls': ['codex exec model calls with browser use'],
    },
    'codex_decision_review': {
        'kind': 'worker',
        'script': 'backend/scripts/codex_decision_review.py',
        'args': ['--api-base', '{api_base}', '--interval-seconds', '14400', '--max-cycles', '0',
                 '--timeout-seconds', '900', '--model', CODEX_MODEL,
                 '--reasoning-effort', CODEX_REASONING_EFFORT],
        'heartbeat': 'codex_decision_review',
        'heartbeat_config': {'configured_model': CODEX_MODEL,
                             'reasoning_effort': CODEX_REASONING_EFFORT},
        'categories': ['model_calls'],
        'writes': [
            {'target': RUNTIME_DB, 'scope': 'SQLiteStore.init() and direct ai_model_audit_logs inserts'},
        ],
        'external_calls': ['codex exec model calls'],
    },
}

PROFILE_COMPONENTS = {
    'full': tuple(COMPONENTS),
    'review': ('backend', 'frontend'),
}


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def selected_components(profile: str, *, enable_codex_search: bool) -> list[str]:
    if profile not in PROFILE_COMPONENTS:
        raise ValueError(f'unknown service profile: {profile!r}')
    return [key for key in PROFILE_COMPONENTS[profile]
            if enable_codex_search or key not in CODEX_COMPONENTS]


def build_plan(profile: str = DEFAULT_PROFILE, *, project_root: Path = ROOT, backend_port: int = 8000,
               frontend_port: int = 3000, enable_codex_search: bool = True) -> dict:
    """Resolve a profile into an auditable start plan. Pure: no I/O."""
    root = Path(project_root)
    selected = selected_components(profile, enable_codex_search=enable_codex_search)
    substitutions = {'api_base': f'http://127.0.0.1:{backend_port}',
                     'backend_port': str(backend_port), 'frontend_port': str(frontend_port)}
    components = {}
    excluded = {}
    for key, spec in COMPONENTS.items():
        entry = copy.deepcopy(spec)
        entry['args'] = [token.format(**substitutions) for token in spec['args']]
        entry['selected'] = key in selected
        if spec.get('heartbeat'):
            entry['heartbeat_path'] = str(root / 'backend' / 'logs' / f"{spec['heartbeat']}_heartbeat.json")
        if not entry['selected']:
            excluded[key] = ('codex_search_disabled' if key in CODEX_COMPONENTS
                             and key in PROFILE_COMPONENTS[profile] else 'not_in_profile')
        components[key] = entry
    paths = {name: str(root / relative) for name, relative in TARGET_PATHS.items()}
    writes = [{'component': key, **write} for key in selected for write in COMPONENTS[key]['writes']]
    targets = sorted({write['target'] for write in writes})
    excluded_categories = sorted(
        {c for key in excluded for c in COMPONENTS[key]['categories']}
        - {c for key in selected for c in COMPONENTS[key]['categories']})
    plan = {
        'schema_version': SCHEMA_VERSION,
        'profile': profile,
        'live_trading_enabled': False,
        'review_only': True,
        'project_root': str(root),
        'backend_port': backend_port,
        'frontend_port': frontend_port,
        'enable_codex_search': enable_codex_search,
        'selected': selected,
        'excluded': excluded,
        'excluded_categories': excluded_categories,
        'paths': {**paths,
                  'pid_file': str(root / 'logs' / 'run_stack.pids.json'),
                  'plan_file': str(root / 'logs' / 'stack_plan.json'),
                  'heartbeat_dir': str(root / 'backend' / 'logs')},
        'expected_writes': writes,
        'write_targets': {target: paths[target] for target in targets},
        # Anything written is backed up first; heartbeat/log files are operational, not data.
        'backup_before_start': [{'target': target, 'path': paths[target]} for target in targets],
        'tonghuasun_readonly_validation': 'required',
        'components': components,
    }
    plan['plan_sha256'] = hashlib.sha256(_canonical(plan).encode('utf-8')).hexdigest()
    return plan


def heartbeat_config_mismatches(key: str, heartbeat: dict | None) -> list[str]:
    """Fields whose heartbeat echo differs from the profile contract (empty = matches)."""
    expected = COMPONENTS[key]['heartbeat_config']
    if not expected:
        return []
    if not isinstance(heartbeat, dict):
        return sorted(expected)
    mismatched = []
    for field, value in expected.items():
        actual = heartbeat.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                equal = float(actual) == float(value)
            except (TypeError, ValueError):
                equal = False
        else:
            equal = actual == value
        if not equal:
            mismatched.append(field)
    return mismatched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    plan_parser = sub.add_parser('plan', help='print the resolved start plan; starts nothing')
    plan_parser.add_argument('--profile', choices=PROFILES, default=DEFAULT_PROFILE)
    plan_parser.add_argument('--project-root', type=Path, default=ROOT)
    plan_parser.add_argument('--backend-port', type=int, default=8000)
    plan_parser.add_argument('--frontend-port', type=int, default=3000)
    plan_parser.add_argument('--enable-codex-search', type=int, choices=(0, 1), default=1)
    plan_parser.add_argument('--output', type=Path,
                             help='only <project-root>/logs/stack_plan.json is accepted')
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    target = root / 'logs' / 'stack_plan.json'
    # The plan record can never overwrite a database, manifest or heartbeat.
    if args.output and args.output.resolve() != target:
        parser.error('--output must be <project-root>/logs/stack_plan.json')
    plan = build_plan(args.profile, project_root=root, backend_port=args.backend_port,
                      frontend_port=args.frontend_port,
                      enable_codex_search=bool(args.enable_codex_search))
    encoded = json.dumps(plan, ensure_ascii=False, indent=2)
    if args.output:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.tmp')
        temporary.write_text(encoded + '\n', encoding='utf-8')
        temporary.replace(target)
    print(encoded)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
