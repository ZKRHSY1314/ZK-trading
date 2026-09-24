"""Bind every delivered development core to the frozen source and replay policy.

The Claude reader is not imported. One exact candidate SQLite is read through
fixed development-bounded SELECTs; its values must match Codex's earlier two-store
reconciliation digest. The accepted, separately tested label kernel is then used
to regenerate each core from independently assembled requests. This is exhaustive
implementation/data validation, not individual investment-case reviews.

V2 adapts only the documented universe source-reference format in dev_run_02
(from an absolute path to filename plus its existing frozen hash). It reruns all
source-to-core checks; the earlier successful execution and source remain intact.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RUNS = ROOT / 'claude methods/_m3_20260910/claude_02/runs'
M2 = ROOT / 'claude methods/_m2_codex_implementation_20260910'
DBROOT = M2 / 'staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09'
DB = DBROOT / 'trading.sqlite3'
LABELS = ROOT / 'backend/app/research/m3_labels.py'
META = HERE / 'metadata_index_01/index.json'
INPUT_AUDIT = HERE / 'development_input_audit_01/result.json'
START, END = '2023-09-04', '2025-03-31'
ASSEMBLY = '2026-09-10T06:52:37.442011+00:00'
PINNED = {
    DB: 'c0b26660ab903541e7e213ee312c565be73547bb3cc8c142486999717e3edeca',
    DBROOT / 'history.sqlite3': 'eda17434ab67496c33eed275b35045c140bad72802b4dcbf981ff22422c53003',
    LABELS: 'e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393',
    META: '14f1bad7d393b4e15bf73111a9d96a78c8b156784f9ccbb084d6b606d3a152e9',
    INPUT_AUDIT: 'dd3ac6ffde13ba0127a39163d23e3cebb148ca9a93f90d25c17cd4a22402d157',
}
POLICY_HASH = 'd436ba1402f9d0b53e1008c2a2bd50678a457c3e050561a59ded30dbbd21c025'
NUMERIC_FIELDS = ('open', 'high', 'low', 'close', 'volume', 'amount')
URI = DB.as_uri() + '?mode=ro&immutable=1'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def source_state():
    state = {}
    for path, pin in PINNED.items():
        digest = sha(path)
        require(digest == pin, 'source_pin:' + str(path))
        stat = path.stat()
        state[str(path)] = dict(sha256=digest, bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)
        if path.suffix == '.sqlite3':
            require(all(not Path(str(path) + s).exists() for s in ('-wal', '-shm', '-journal')), 'sidecar')
    return state


def main():
    run = Path(sys.argv[1]).resolve(strict=True)
    output = Path(sys.argv[2]).resolve()
    require(run.parent == RUNS and output.parent == HERE and not output.exists(), 'exact_scope')
    before = source_state()
    output.mkdir()
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()
    opened, denied, queries = [], [], []

    def inside(path):
        return isinstance(path, (str, os.PathLike)) and Path(path).resolve().is_relative_to(output)

    def deny(event):
        denied.append(event)
        raise PermissionError('Independent chronology validation denied: ' + event)

    def audit(event, args):
        if event == 'sqlite3.connect':
            if args[0] != URI:
                deny('sqlite_path_or_mode')
            opened.append(args[0])
        if event.startswith('socket.') or event in {'subprocess.Popen', 'os.system', 'os.startfile', 'os.spawn', 'os.exec', 'os.posix_spawn'}:
            deny(event)
        if event == 'open':
            path, mode, flags = args
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing and not inside(path):
                deny('write_outside_output')
        if event in {'os.mkdir', 'os.remove', 'os.rmdir'} and not inside(args[0]):
            deny(event)
        if event == 'os.rename' and not (inside(args[0]) and inside(args[1])):
            deny(event)
        if event in {'os.link', 'os.symlink'}:
            deny(event)

    sys.dont_write_bytecode = True
    sys.addaudithook(audit)
    spec = importlib.util.spec_from_file_location('m3_frozen_labels_independent_source_review', LABELS)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    require(m.POLICY_HASH == POLICY_HASH and m.assert_policy_integrity() == POLICY_HASH, 'policy_pin')

    meta = json.loads(META.read_text(encoding='utf-8'))
    baseline = json.loads(INPUT_AUDIT.read_text(encoding='utf-8'))
    instruments = {x['symbol']: x for x in meta['instruments']}
    stocks = sorted(s for s, x in instruments.items() if x['instrument_class'] == 'stock')
    by_symbol, halts = defaultdict(list), defaultdict(list)
    numeric = hashlib.sha256()
    con = sqlite3.connect(URI, uri=True)
    try:
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA query_only=ON')
        require(con.execute('PRAGMA query_only').fetchone()[0] == 1, 'query_only_readback')
        con.enable_load_extension(False)
        con.set_authorizer(lambda action, *args: sqlite3.SQLITE_OK if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION} else sqlite3.SQLITE_DENY)
        sql = ('SELECT p.*,e.observed_at,e.point_index FROM daily_bar_cache p JOIN row_evidence e '
               'ON p.symbol=e.symbol AND p.trade_date=e.trade_date WHERE p.trade_date<=? ORDER BY p.symbol,p.trade_date')
        queries.append({'sql': sql, 'parameters': [END]})
        for row in con.execute(sql, (END,)):
            v = dict(row)
            by_symbol[v['symbol']].append(v)
            numeric.update((canonical([v['symbol'], v['trade_date'], *[v[f] for f in NUMERIC_FIELDS]]) + '\n').encode())
        sql = 'SELECT symbol,trade_date,evidence_sha256 FROM suspension_records WHERE trade_date<=? ORDER BY symbol,trade_date'
        queries.append({'sql': sql, 'parameters': [END]})
        for row in con.execute(sql, (END,)):
            halts[row['symbol']].append(dict(row))
    finally:
        con.close()
    require(numeric.hexdigest() == baseline['numeric_rows_sha256'], 'independent_two_store_numeric_digest')
    require(sum(map(len, by_symbol.values())) == 27900 and sum(map(len, halts.values())) == 200, 'bounded_source_counts')

    first = min(v[0]['trade_date'] for v in by_symbol.values())
    sessions = tuple(d for d in meta['calendar']['sessions'] if first <= d <= END)
    dates = [d for d in sessions if d >= START]
    calendar_pin = 'f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656'
    calendar = m.SessionCalendar(sessions, f'calendar.json sha256={calendar_pin} slice {sessions[0]}..{sessions[-1]}', ASSEMBLY, synthetic=False)
    universe_pin = '97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe'
    universe = m.FrozenUniverse(frozenset(stocks), f'pilot_symbols.csv sha256={universe_pin}', universe_pin)
    cohort = {x['date']: x for x in baseline['per_date']}

    def observations(symbol):
        role = instruments[symbol]['instrument_class']
        observations = [m.Observation(symbol=symbol, trade_date=v['trade_date'], kind='price', available_at=v['observed_at'],
            source_ref=f"{v['trade_date']}#{v['point_index']}", adjustment_mode='none', volume_unit=v['volume_unit'],
            amount_unit='not_applicable' if role == 'benchmark' else 'CNY', **{f:v[f] for f in NUMERIC_FIELDS}) for v in by_symbol[symbol]]
        observations.extend(m.Observation(symbol=symbol, trade_date=v['trade_date'], kind='full_day_suspension',
            available_at=ASSEMBLY, source_ref='suspension#' + v['evidence_sha256'][:16]) for v in halts[symbol])
        return sorted(observations, key=lambda x:x.trade_date)

    benchmark = observations('SH000300')
    input_files = {}
    index_path = run / 'chronology_index.json'
    input_files[str(index_path)] = sha(index_path)
    index = json.loads(index_path.read_text(encoding='utf-8'))
    require(set(index['files']) == set(stocks), 'full_fifty_stock_inventory')
    comparisons, phase, selection, current = [], Counter(), Counter(), Counter()
    errors = []
    total = 0
    for symbol in stocks:
        info = instruments[symbol]
        all_obs = observations(symbol)
        expected_dates = [d for d in dates if info['listing_date'] is not None and d >= info['listing_date']]
        path = run / 'chronology' / (symbol + '.jsonl.gz')
        digest = sha(path)
        require(digest == index['files'][symbol]['sha256_gzip'], 'chronology_file_pin:' + symbol)
        input_files[str(path)] = digest
        plain = gzip.decompress(path.read_bytes())
        require(hashlib.sha256(plain).hexdigest() == index['files'][symbol]['sha256_jsonl'], 'chronology_plain_pin:' + symbol)
        envelopes = [json.loads(x) for x in plain.decode('utf-8').splitlines()]
        actual_dates = [e['record']['cutoff']['decision_date'] for e in envelopes]
        require(actual_dates == expected_dates and len(envelopes) == index['files'][symbol]['records'], 'complete_listed_chronology:' + symbol)
        ev = info.get('listing_evidence') or {}
        grade = ev.get('identity_kind') or ev.get('status') or 'unknown'
        raw_events = info.get('known_cash_events', [])
        for envelope, day in zip(envelopes, expected_dates):
            record = envelope['record']
            known = [e for e in raw_events if e['ex_date'] <= day]
            refs = [f'pilot_symbols.csv sha256={universe_pin} list_date; grade={grade}']
            refs += ['document_sha256:' + e['document_sha256'] if e.get('document_sha256') else 'frozen_qualification_control_boundary:' + e['ex_date'] for e in known]
            security = m.SecurityContext(listing_date=info['listing_date'], name=None, st_status='unknown',
                corporate_action_status=m.CA_PARTIAL_KNOWN if raw_events else m.CA_UNKNOWN,
                known_ex_dates=tuple(e['ex_date'] for e in known), float_shares=None, turnover_available=False,
                evidence_refs=tuple(refs), facts_available_at=ASSEMBLY)
            counts = cohort[day]
            coverage = m.Coverage(counts['evidence_key_coverage'],
                f"m3_frozen_reader cohort {day}: {counts['price_keys']}+{counts['halt_keys']}/{counts['listed_stocks']}", ASSEMBLY)
            req = m.LabelRequest(symbol=symbol, observations=[o for o in all_obs if o.trade_date <= day],
                cutoff=m.Cutoff(day, day + 'T16:00:00+08:00', 'retrospective'), calendar=calendar, security=security,
                benchmark_symbol='SH000300', benchmark_observations=[o for o in benchmark if o.trade_date <= day],
                universe_coverage_on_decision_date=coverage, synthetic=False, universe=universe)
            generated = m.generate_labels(req)
            m.verify_record(record)
            m.validate_ledger(record)
            changed = [key for key in generated if generated[key] != record.get(key)]
            extra = sorted(set(record) - set(generated))
            if changed or extra:
                errors.append({'symbol':symbol, 'date':day, 'different_fields':changed, 'extra_fields':extra,
                    'expected_record_hash':generated['record_hash'], 'delivered_record_hash':record['record_hash']})
            comparisons.append([symbol, day, generated['record_hash'], record['record_hash'], not changed and not extra])
            total += 1
            phase[generated['labels']['phase']['label']] += 1
            selection[generated['labels']['selection']['label']] += 1
            current[generated['current_state']] += 1
        require(sha(path) == digest, 'chronology_changed_while_reviewing')
        print(json.dumps({'progress_symbol':symbol, 'records_replayed':total, 'mismatch_count':len(errors)}), flush=True)

    require(total == 17554 == index['total_records'], 'total_decision_count')
    for path, pin in input_files.items():
        require(sha(Path(path)) == pin, 'delivery_input_changed')
    after = source_state()
    require(before == after, 'frozen_input_modified')
    result = dict(schema='m3.codex.source_to_chronology_validation.v1', run=str(run),
        started_at_utc=started, finished_at_utc=datetime.now(timezone.utc).isoformat(),
        elapsed_seconds=time.perf_counter()-t0, producer_sha256=sha(Path(__file__)),
        sources_before=before, sources_after=after, actual_sqlite_connections=opened,
        sql_queries=queries, denied_events=denied, production_connections=0,
        records_replayed=total, phase=dict(phase), selection=dict(selection), current_state=dict(current),
        mismatch_count=len(errors), mismatches=errors, input_files=input_files,
        record_comparisons=comparisons, passed=not errors, real_case_reviews=0, M3_complete=False)
    (output/'source.py').write_bytes(Path(__file__).read_bytes())
    (output/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed':not errors, 'records_replayed':total, 'mismatch_count':len(errors),
        'result_sha256':sha(output/'result.json'), 'elapsed_seconds':result['elapsed_seconds']}), flush=True)
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
