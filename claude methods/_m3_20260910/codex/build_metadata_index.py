"""Index frozen M2 structural evidence; never open a database or price body.

This is preparation for a separately reviewed real-case reader.  It does not
adopt a label policy, assign a split, infer a signal, or establish strict PIT.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
M2 = ROOT / 'claude methods/_m2_codex_implementation_20260910'
OUT = Path(__file__).resolve().parent / 'metadata_index_01'
Q_PATH = M2 / 'qualification_v2_reviewed.json'
Q_SHA = '992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37'
RESEARCH_START, RESEARCH_END = '2023-09-04', '2026-09-04'


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition: bool, description: str) -> None:
    if not condition:
        raise ValueError(description)


def main() -> None:
    require(not OUT.exists(), 'New output directory required; preserve old receipts')
    require(sha(Q_PATH) == Q_SHA, 'Frozen qualification changed')
    q = json.loads(Q_PATH.read_text(encoding='utf-8'))
    verified = {str(Q_PATH): Q_SHA}

    def verify_pin(path: Path, expected: str | None = None) -> None:
        path = path.resolve()
        require(path.is_relative_to(ROOT), f'Outside workspace: {path}')
        require(path.suffix.lower() not in ('.sqlite', '.sqlite3', '.db'), 'No database access')
        pinned = q['input_pins'].get(str(path))
        require(pinned is not None, f'Not in frozen input pins: {path}')
        require(expected is None or expected == pinned, f'Conflicting evidence hash: {path}')
        require(sha(path) == pinned, f'Changed evidence: {path}')
        verified[str(path)] = pinned

    def read_json(path: Path):
        verify_pin(path)
        return json.loads(path.read_text(encoding='utf-8'))

    pilot_path = ROOT / 'claude methods/_m1_closure/pilot_symbols.csv'
    verify_pin(pilot_path)
    with pilot_path.open(encoding='utf-8-sig', newline='') as stream:
        pilot_rows = list(csv.DictReader(stream))
    pilot = {r['symbol']: r for r in pilot_rows}
    scopes = {s['symbol']: s for s in q['scopes']}
    require(len(pilot_rows) == len(pilot) == len(q['scopes']) == len(scopes) == 52,
            'Universe duplicates or scope drift')
    require(pilot.keys() == scopes.keys(), 'Pilot and M2 membership differ')
    require(Counter(s['instrument_class'] for s in scopes.values()) ==
            {'stock': 50, 'benchmark': 2}, 'Unexpected instrument classes')

    calendar_path = ROOT / 'backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json'
    raw_calendar = read_json(calendar_path)
    calendar = [datetime.strptime(d, '%Y%m%d').date().isoformat() for d in raw_calendar]
    require(calendar == sorted(set(calendar)), 'Calendar not ordered and unique')
    research_calendar = [d for d in calendar if RESEARCH_START <= d <= RESEARCH_END]
    require(len(research_calendar) == 728, 'Research calendar changed')
    calendar_set = set(calendar)

    identities = read_json(M2 / 'official/identity_facts.json')
    identity_map = {r['symbol']: r for r in identities}
    require(len(identity_map) == len(identities) == 9, 'Identity fact cardinality')
    for fact in identities:
        verify_pin(Path(fact['document_path']), fact['document_sha256'])
        require(fact['official_listing_date'] == pilot[fact['symbol']]['list_date'],
                'Official and pilot listing dates disagree')

    cash_events = read_json(M2 / 'official/corporate_action_facts.json')
    require(len(cash_events) == 9 and Counter(e['symbol'] for e in cash_events) ==
            {'BJ920000': 6, 'SH600011': 3}, 'Known event set changed')
    require(len({(e['symbol'], e['ex_date']) for e in cash_events}) == 9,
            'Duplicate cash events')
    for event in cash_events:
        verify_pin(Path(event['document_path']), event['document_sha256'])
        require(event['ex_date'] in calendar_set, 'Ex-date not in retained calendar')

    ledger = q['suspension_ledger']
    require(len(ledger) == len({(r['symbol'], r['date']) for r in ledger}) == 298,
            'Suspension ledger duplicate or cardinality drift')
    for entry in ledger:
        for evidence in entry['evidence']:
            if 'source' in evidence:
                verify_pin(M2 / evidence['source'], evidence['sha256'])
            for source in evidence.get('sources', []):
                verify_pin(M2 / source['path'], source['sha256'])

    instruments = []
    for symbol, scope in sorted(scopes.items()):
        p = pilot[symbol]
        listed = p['list_date'] or None
        if listed:
            require(date.fromisoformat(listed).isoformat() == listed, 'Invalid listing date')
        prices, halts = scope['expected_price_dates'], scope['suspended_dates']
        require(prices == sorted(set(prices)), f'{symbol}: unordered/duplicate price keys')
        require(halts == sorted(set(halts)), f'{symbol}: unordered/duplicate halt keys')
        require(set(prices).isdisjoint(halts), f'{symbol}: price/halt overlap')
        require(set(prices + halts) <= calendar_set, f'{symbol}: non-session keys')
        require(all(not listed or d >= listed for d in prices + halts),
                f'{symbol}: pre-listing keys')
        expected_research = [d for d in research_calendar if not listed or d >= listed]
        research_prices = [d for d in prices if RESEARCH_START <= d <= RESEARCH_END]
        research_halts = [d for d in halts if RESEARCH_START <= d <= RESEARCH_END]
        require(sorted(research_prices + research_halts) == expected_research,
                f'{symbol}: unexplained research calendar gap')
        require(len(prices) == scope['rows'] and len(research_prices) == scope['research_rows']
                and len(prices) - len(research_prices) == scope['warmup_rows'],
                f'{symbol}: qualification count mismatch')
        require(set(halts) == {r['date'] for r in ledger if r['symbol'] == symbol},
                f'{symbol}: scope/ledger disagreement')
        for capture in scope['captures']:
            require(datetime.fromisoformat(capture['observed_at']).utcoffset() is not None,
                    'Capture timestamp missing timezone')
        instruments.append({
            'symbol': symbol, 'instrument_class': scope['instrument_class'],
            'pilot_selection_stratum': p['stratum'],
            'listing_date': listed,
            'listing_evidence': identity_map.get(symbol) or {
                'status': 'retained_pilot_metadata_only' if listed else 'not_applicable_index',
                'path': str(pilot_path), 'sha256': verified[str(pilot_path)],
                'original_source_and_historical_availability_not_established_here': True},
            'historical_st_status': 'unknown',
            'name_used_as_historical_status': False,
            'research_listed_session_count': len(expected_research),
            'research_price_rows': len(research_prices),
            'research_observed_halt_rows': len(research_halts),
            'warmup_price_rows': scope['warmup_rows'],
            'expected_price_dates': prices, 'observed_halt_dates': halts,
            'captures': scope['captures'],
            'capture_time_is_original_market_availability': False,
            'whole_record_strict_pit': False,
            'vendor_basis': scope['vendor_basis'],
            'vendor_basis_status': scope['vendor_basis_status'],
            'unit_status': scope['unit_status'],
            'volume_unit': scope['volume_unit'], 'amount_unit': scope['amount_unit'],
            'price_domain_exceptions': scope['price_domain_exceptions'],
            'known_cash_events': [e for e in cash_events if e['symbol'] == symbol],
            'corporate_action_completeness': 'unknown',
            'corporate_action_original_available_at': None,
        })

    require(sum(s['research_price_rows'] for s in instruments) == 35943, 'Price row total')
    require(sum(s['research_observed_halt_rows'] for s in instruments) == 250, 'Halt total')
    require(sum(s['warmup_price_rows'] for s in instruments) == 9742, 'Warmup total')
    for path, expected in verified.items():
        require(sha(Path(path)) == expected, f'Input changed during index: {path}')

    payload = {
        'schema': 'm3.frozen_structural_evidence_index.v1',
        'assembled_at_utc': datetime.now(timezone.utc).isoformat(),
        'purpose': 'API-neutral structural preparation; no real-case feature extraction',
        'qualification_path': str(Q_PATH), 'qualification_sha256': Q_SHA,
        'verified_input_pins': dict(sorted(verified.items())),
        'calendar': {'path': str(calendar_path), 'sha256': verified[str(calendar_path)],
                     'source': 'retained M2 AkShare calendar file; not a new exchange fetch',
                     'sessions': calendar, 'research_start': RESEARCH_START,
                     'research_end': RESEARCH_END, 'research_session_count': 728,
                     'historical_available_at': None},
        'instruments': instruments,
        'retrospective_suspension_ledger': ledger,
        'listing_depth_shortfalls': q['listing_depth_shortfalls'],
        'block_scope_condition': q['block_scope'],
        'limits': [
            'Document byte hashes checked; no new interpretation or document extraction.',
            'Listing dates outside nine BJ official facts retain pilot-only source qualification.',
            'Pilot strata are selection provenance; old pilot coverage ratios are not reused.',
            'Known cash events are partial evidence, never a complete adjustment register.',
            'Publication dates, local mtime and document assembly dates do not prove historical availability.',
            'Suspension evidence includes subsequent resumption notices and is retrospective.',
            'Expected keys are frozen metadata; this run did not read or validate any SQLite price value.',
            'Indexes are benchmarks and cannot serve as stock liquidity controls.',
            'SZ002115 and SZ002081 are absent; no seed case evidence is fabricated.',
            'No policy/split adoption, signal labels, reviews, training or M4 claims.'
        ],
        'real_cases_generated': 0, 'label_policy_adopted': False,
        'strict_pit': False, 'live_trading': False, 'production_promoted': False,
        'database_connections': 0, 'new_capture': False, 'M3_complete': False,
    }
    OUT.mkdir()
    output = OUT / 'index.json'
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    receipt = {'verdict': 'PASS_structural_index_only', 'index_path': str(output),
               'index_sha256': sha(output), 'producer_sha256': sha(Path(__file__)),
               'verified_input_count': len(verified), 'instruments': 52,
               'stocks': 50, 'benchmarks': 2, 'known_cash_events': 9,
               'suspension_keys': 298, 'research_keys': 36193,
               'real_cases_generated': 0, 'strict_pit': False,
               'source_pins_unchanged_after_read': True}
    (OUT / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n',
                                      encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
