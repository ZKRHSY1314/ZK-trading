"""Independent M3 development input reconciliation; exact frozen DBs, read only.

No app/service/Claude-reader imports. No held-out OHLCVA is selected. The notebook
companion embeds this source; new outputs are audit evidence, never case reviews.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
M2 = ROOT / 'claude methods/_m2_codex_implementation_20260910'
RUN_ID = 'ths_v2_20260910_041710_97ef9c09'
SOURCE = M2 / 'staging_runs' / RUN_ID / ('run_' + RUN_ID)
START, END = '2023-09-04', '2025-03-31'
PINS = {
    SOURCE / 'trading.sqlite3': 'c0b26660ab903541e7e213ee312c565be73547bb3cc8c142486999717e3edeca',
    SOURCE / 'history.sqlite3': 'eda17434ab67496c33eed275b35045c140bad72802b4dcbf981ff22422c53003',
    M2 / 'qualification_v2_reviewed.json': '992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37',
    HERE / 'metadata_index_01/index.json': '14f1bad7d393b4e15bf73111a9d96a78c8b156784f9ccbb084d6b606d3a152e9',
}
DBS = tuple(p for p in PINS if p.suffix == '.sqlite3')
URIS = {p.as_uri() + '?mode=ro&immutable=1' for p in DBS}
PRICE_FIELDS = ('open', 'high', 'low', 'close', 'volume', 'amount')
LINEAGE_FIELDS = ('raw_sha256', 'request_sha256', 'producer_sha256', 'parser_sha256',
                  'capture_receipt_sha256', 'capture_producer_manifest_sha256', 'observed_at')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def value_sha(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def file_sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def file_state():
    result = {}
    for path, pin in PINS.items():
        require(path.resolve(strict=True) == path and path.is_file(), 'input_path')
        before = path.stat()
        digest = file_sha(path)
        after = path.stat()
        require(digest == pin and before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns, 'input_pin:' + path.name)
        result[str(path)] = dict(sha256=digest, bytes=after.st_size, mtime_ns=after.st_mtime_ns)
    for path in DBS:
        for suffix in ('-wal', '-shm', '-journal'):
            require(not Path(str(path) + suffix).exists(), 'unexpected_sidecar')
    return result


QUERIES = {
    'trading_prices': 'SELECT * FROM daily_bar_cache WHERE trade_date <= ? ORDER BY symbol,trade_date',
    'history_prices': 'SELECT * FROM daily_bars WHERE trade_date <= ? ORDER BY symbol,trade_date',
    'row_evidence': 'SELECT * FROM row_evidence WHERE trade_date <= ? ORDER BY symbol,trade_date',
    'coverage': 'SELECT * FROM coverage_inventory WHERE trade_date <= ? ORDER BY symbol,trade_date',
    'suspensions': 'SELECT * FROM suspension_records WHERE trade_date <= ? ORDER BY symbol,trade_date',
    'qualifications': 'SELECT * FROM qualification_records ORDER BY symbol',
    'contract': 'SELECT * FROM dataset_contract ORDER BY id',
    'ingest_run': 'SELECT * FROM ingest_runs ORDER BY id',
}


def main():
    output = Path(sys.argv[1]).resolve()
    require(output.parent == HERE and not output.exists(), 'new_direct_codex_output_required')
    before = file_state()
    output.mkdir()
    connections, denied, query_log = [], [], []

    def inside(path):
        return isinstance(path, (str, os.PathLike)) and Path(path).resolve().is_relative_to(output)

    def deny(event):
        denied.append(event)
        raise PermissionError('M3 independent audit blocked: ' + event)

    def audit(event, args):
        if event == 'sqlite3.connect':
            if args[0] not in URIS:
                deny('sqlite_path_or_mode')
            connections.append(args[0])
        if event.startswith('socket.') or event in {'subprocess.Popen', 'os.system', 'os.startfile', 'os.posix_spawn', 'os.spawn', 'os.exec'}:
            deny(event)
        if event == 'open':
            path, mode, flags = args
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing and not inside(path):
                deny('write_outside_output')
        if event in {'os.remove', 'os.rmdir', 'os.mkdir'} and not inside(args[0]):
            deny(event)
        if event == 'os.rename' and not (inside(args[0]) and inside(args[1])):
            deny(event)
        if event in {'os.link', 'os.symlink'}:
            deny(event)

    sys.dont_write_bytecode = True
    sys.addaudithook(audit)

    def authorize(action, arg1, arg2, database, trigger):
        # Queries are a fixed reviewed allowlist; deny mutating SQL and ATTACH.
        return sqlite3.SQLITE_OK if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION} else sqlite3.SQLITE_DENY

    def open_read(path):
        con = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA query_only=ON')
        require(con.execute('PRAGMA query_only').fetchone()[0] == 1, 'query_only')
        con.enable_load_extension(False)
        con.set_authorizer(authorize)
        return con

    def read(con, name, bounded=True):
        params = (END,) if bounded else ()
        rows = [dict(row) for row in con.execute(QUERIES[name], params)]
        query_log.append(dict(name=name, sql=QUERIES[name], parameters=list(params), rows=len(rows)))
        return rows

    def keyed(rows):
        result = {(r['symbol'], r['trade_date']): r for r in rows}
        require(len(result) == len(rows), 'duplicate_grain')
        require(all(key[1] <= END for key in result), 'heldout_key_selected')
        return result

    q = json.loads((M2 / 'qualification_v2_reviewed.json').read_bytes())
    meta = json.loads((HERE / 'metadata_index_01/index.json').read_bytes())
    scopes = {s['symbol']: s for s in q['scopes']}
    instruments = {s['symbol']: s for s in meta['instruments']}
    require(len(scopes) == 52 and set(scopes) == set(instruments), 'universe_inventory')
    tc = hc = None
    try:
        tc, hc = open_read(DBS[0]), open_read(DBS[1])
        trading = keyed(read(tc, 'trading_prices'))
        history = keyed(read(hc, 'history_prices'))
        evidence = keyed(read(tc, 'row_evidence'))
        tcov, hcov = keyed(read(tc, 'coverage')), keyed(read(hc, 'coverage'))
        tsusp, hsusp = keyed(read(tc, 'suspensions')), keyed(read(hc, 'suspensions'))
        qualifications = read(tc, 'qualifications', False)
        tcontract, hcontract = read(tc, 'contract', False), read(hc, 'contract', False)
        ingest = read(hc, 'ingest_run', False)
    finally:
        for connection in (tc, hc):
            if connection is not None:
                connection.close()
    require(set(trading) == set(history) == set(evidence), 'price_evidence_key_join')
    require(tcov == hcov and tsusp == hsusp, 'coverage_or_suspension_store_mismatch')
    require(tcontract == hcontract and len(tcontract) == 1, 'contract_mismatch')
    require(len(ingest) == 1 and ingest[0]['run_id'] == RUN_ID, 'ingest_identity')
    expected_prices = {(s['symbol'], d) for s in scopes.values() for d in s['expected_price_dates'] if d <= END}
    expected_halts = {(s['symbol'], d) for s in scopes.values() for d in s['suspended_dates'] if d <= END}
    require(set(trading) == expected_prices and set(tsusp) == expected_halts, 'qualification_key_mismatch')
    require(not expected_prices & expected_halts and set(tcov) == expected_prices | expected_halts, 'price_halt_partition')
    for key, row in tcov.items():
        require(row['classification'] == ('price' if key in trading else 'full_day_suspension'), 'classification_mismatch')
    require(len(qualifications) == 52 and {r['symbol'] for r in qualifications} == set(scopes), 'qualification_records_inventory')
    for row in qualifications:
        scope = scopes[row['symbol']]
        require(json.loads(row['record_json']) == scope and row['record_sha256'] == value_sha(scope), 'qualification_record_hash')
    qhalts = {(r['symbol'], r['date']): r for r in q['suspension_ledger'] if r['date'] <= END}
    for key, row in tsusp.items():
        require(json.loads(row['record_json']) == qhalts[key] and row['evidence_sha256'] == value_sha(qhalts[key]), 'suspension_record_hash')

    row_counts, units, source_status = Counter(), Counter(), Counter()
    numeric_digest = hashlib.sha256()
    evidence_digest = hashlib.sha256()
    seen_points = set()
    availability, nulls, extrema = [], Counter(), {field: [math.inf, -math.inf] for field in PRICE_FIELDS}
    for key, row in sorted(trading.items()):
        hist, ev, scope = history[key], evidence[key], scopes[key[0]]
        require([row[f] for f in PRICE_FIELDS] == [hist[f] for f in PRICE_FIELDS], 'numeric_store_mismatch:' + str(key))
        require(row['source'] == hist['provider'] == 'tonghuashun' and row['quality_status'] == 'qualified_candidate', 'source_status')
        require(row['adjustment_mode'] == hist['adjustment_mode'] == 'none', 'adjustment_mismatch')
        require(row['volume_unit'] == scope['volume_unit'], 'unit_mismatch')
        require(hist['fetched_at'] == ev['observed_at'] and hist['ingest_run_id'] == ingest[0]['id'], 'history_time_lineage')
        require(ev['qualification_sha256'] == value_sha(scope), 'row_qualification_hash')
        matches = [c for c in scope['captures'] if all(c.get(f) == ev[f] for f in LINEAGE_FIELDS)]
        require(len(matches) == 1, 'capture_lineage_ambiguous_or_missing')
        cap = matches[0]
        require(type(ev['point_index']) is int and 0 <= ev['point_index'] < cap['rows'], 'point_index_out_of_range')
        require(cap['start'] <= key[1] <= cap['end'], 'capture_date_range')
        point = (key[0], ev['raw_sha256'], ev['point_index'])
        require(point not in seen_points, 'duplicate_capture_point')
        seen_points.add(point)
        observed = datetime.fromisoformat(ev['observed_at'])
        require(observed.utcoffset() is not None, 'observation_timezone')
        availability.append(observed)
        for field in PRICE_FIELDS:
            value = row[field]
            if value is None:
                nulls[field] += 1
            require(type(value) in (int, float) and math.isfinite(value), 'nonfinite_numeric')
            extrema[field][0] = min(extrema[field][0], value)
            extrema[field][1] = max(extrema[field][1], value)
        require(0 < row['low'] <= min(row['open'], row['close']) <= max(row['open'], row['close']) <= row['high'], 'ohlc_order')
        require(row['volume'] >= 0 and row['amount'] >= 0, 'negative_aggregate')
        segment = 'development' if START <= key[1] else 'warmup'
        row_counts[(scope['instrument_class'], segment)] += 1
        units[(scope['instrument_class'], row['volume_unit'], scope['amount_unit'])] += 1
        source_status[ev['source_name_status']] += 1
        numeric_digest.update((canonical([*key, *[row[f] for f in PRICE_FIELDS]]) + '\n').encode())
        evidence_digest.update((canonical(ev) + '\n').encode())

    calendar = [d for d in meta['calendar']['sessions'] if START <= d <= END]
    stocks = [s for s in instruments.values() if s['instrument_class'] == 'stock']
    per_symbol, per_date = [], []
    for symbol, instrument in sorted(instruments.items()):
        expected = [d for d in calendar if instrument['listing_date'] is None or d >= instrument['listing_date']]
        prices = [d for s, d in trading if s == symbol and d >= START]
        halts = [d for s, d in tsusp if s == symbol and d >= START]
        require(set(expected) == set(prices) | set(halts), 'listed_calendar_coverage:' + symbol)
        warm = sum(s == symbol and d < START for s, d in trading)
        per_symbol.append(dict(symbol=symbol, role=instrument['instrument_class'], listing_date=instrument['listing_date'],
                               expected_development_sessions=len(expected), development_prices=len(prices), development_halts=len(halts),
                               warmup_prices=warm, prices_before_first_development_decision=warm))
    for day in calendar:
        cohort = [s['symbol'] for s in stocks if s['listing_date'] is None or s['listing_date'] <= day]
        prices = sum((s, day) in trading for s in cohort)
        halts = sum((s, day) in tsusp for s in cohort)
        require(prices + halts == len(cohort), 'development_cohort_key_gap')
        per_date.append(dict(date=day, listed_stocks=len(cohort), price_keys=prices, halt_keys=halts,
                             evidence_key_coverage=(prices + halts) / len(cohort) if cohort else None,
                             price_availability=prices / len(cohort) if cohort else None))
    after = file_state()
    require(before == after, 'input_modified_during_audit')
    result = dict(schema='m3.codex.development_input_audit.v1', checked_at_utc=datetime.now(timezone.utc).isoformat(),
        passed=True, producer_sha256=file_sha(Path(__file__)), sources_before=before, sources_after=after,
        database_connections=connections, sql_query_log=query_log, denied_events=denied,
        development=[START, END], development_sessions=len(calendar), price_keys_selected=len(trading),
        suspension_keys_selected=len(tsusp), prices_by_role_and_segment=[dict(role=k[0],segment=k[1],count=v) for k,v in sorted(row_counts.items())],
        units=[dict(role=k[0],volume_unit=k[1],amount_unit=k[2],count=v) for k,v in sorted(units.items())],
        numeric_rows_sha256=numeric_digest.hexdigest(), evidence_rows_sha256=evidence_digest.hexdigest(),
        null_counts={f:nulls[f] for f in PRICE_FIELDS}, numeric_extrema=extrema,
        observed_at_min=min(availability).isoformat(), observed_at_max=max(availability).isoformat(),
        source_name_status_counts=dict(source_status), per_symbol=per_symbol, per_date=per_date,
        original_historical_availability_proved=False, raw_capture_bodies_parsed=False,
        independent_market_source_corroboration=False, raw_vendor_value_accuracy_reproved=False,
        labels_generated=0, real_case_reviews=0, strict_pit=False, training_eligible=False,
        production_database_connections=0, network_requests=0, live_trading_enabled=False, M3_complete=False)
    (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('passed','development_sessions','price_keys_selected','suspension_keys_selected','prices_by_role_and_segment','numeric_rows_sha256')},ensure_ascii=False))


if __name__ == '__main__':
    main()
