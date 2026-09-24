"""Independent bounded closure review; synthetic fixtures and retained bytes only.

Usage: python -B -X utf8 this_file.py [separately-named-revision-directory]
Does not change implementation, retained evidence, production data, or Git state.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / 'claude methods' / '_m2_smoke'
sys.path.insert(0, str(SMOKE))

# Load the SSL and JS engine dependencies before installing connection guards.
import requests
import pandas
from akshare.stock import cons
import smoke_capture as cap
import smoke_checks as chk
import sina_klc_decoder as dec

RESULTS = []


def expect(name, expected, actual):
    RESULTS.append(dict(name=name, passed=expected == actual,
                        expected=expected, actual=actual))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(path):
    return {str(p.relative_to(path)): digest(p) for p in sorted(path.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def database_metadata():
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns)
            for p in ROOT.glob('*.sqlite3*')}


def parsed(observations):
    payload = [{'date': d, 'amount': value} for d, value in observations]
    body = ('var KKE_ShareAmount_sh600011=(' + json.dumps(payload) + ');').encode()
    return dec.parse_outstanding_share(body, None, expected_symbol='sh600011')


def contracts():
    # Expectations are explicit state sequences, independent of implementation helpers.
    dates = ['2024-01-%02d' % day for day in range(1, 9)]
    cases = [
        ('positive zero positive', [(dates[0], 100), (dates[2], 0), (dates[4], 200)],
         [100, 100, None, None, 200, 200, 200, 200]),
        ('repeated zero', [(dates[0], 100), (dates[2], 0), (dates[3], 0), (dates[5], 200)],
         [100, 100, None, None, None, 200, 200, 200]),
        ('trailing zero', [(dates[0], 100), (dates[3], 0)],
         [100, 100, 100, None, None, None, None, None]),
        ('leading zero', [(dates[1], 0), (dates[4], 200)],
         [None, None, None, None, 200, 200, 200, 200]),
        ('absent observation carries positive', [(dates[1], 100), (dates[5], 200)],
         [None, 100, 100, 100, 100, 200, 200, 200]),
        ('all zero', [(dates[0], 0), (dates[4], 0)], [None] * 8),
        ('empty', [], [None] * 8),
    ]
    for label, observations, wanted in cases:
        rows = parsed(observations) if observations else []
        actual = [dec.outstanding_share_as_of(rows, d) for d in dates]
        expect(label + ' denominator states', wanted,
               [r['outstanding_share_wan'] if r else None for r in actual])
        expect(label + ' window-start coverage', [v is not None for v in wanted],
               [dec.share_series_quality(rows, (d, dates[-1]))['covers_window_start']
                for d in dates])
        zeros = [r for r in rows if r['outstanding_share_wan'] == 0]
        expect(label + ' raw zeros retained with reasons', True,
               len(zeros) == sum(v == 0 for _, v in observations)
               and all(r['usable'] is False and r['unusable_reason'] for r in zeros))

    def info(ds, **changes):
        result = dict(rows=len(ds), first_date=ds[0] if ds else None,
                      last_date=ds[-1] if ds else None, dates=ds)
        result.update(changes)
        return result

    good = ['2023-09-04', '2023-09-05']
    probes = [
        ('actual sequence valid', info(good), [], 'PASS'),
        ('prior metadata-only counterexample', info([], rows=1, first_date='2023-01-03'), [], 'FAIL'),
        ('missing dates', dict(rows=1, first_date=good[0], last_date=good[0]), [], 'FAIL'),
        ('empty dates', info([]), [], 'FAIL'),
        ('row count mismatch', info(good, rows=3), [], 'FAIL'),
        ('first metadata mismatch', info(good, first_date='2023-09-01'), [], 'FAIL'),
        ('last metadata mismatch', info(good, last_date=None), [], 'FAIL'),
        ('duplicate dates', info([good[0], good[0]]), [], 'FAIL'),
        ('unsorted dates', info(list(reversed(good))), [], 'FAIL'),
        ('pre-window stock date', info(['2022-08-23']), [], 'FAIL'),
        ('post-window stock date', info(['2026-09-07']), [], 'FAIL'),
        ('fabricated date', info(good), [good[0]], 'FAIL'),
        ('short legitimate series', info([good[0]]), [], 'PASS'),
    ]
    for label, value, fabricated, wanted in probes:
        expect('R1 ' + label, wanted, chk._replay_verdict(value, fabricated, False, None)[0])
    expect('R1 index full series is a separate contract', 'PASS',
           chk._replay_verdict(info(['2002-01-04', '2026-09-07']), [], False, None,
                               window=None)[0])
    expect('R1 unevaluated auxiliary remains inconclusive', 'INCONCLUSIVE',
           chk._replay_verdict({}, [], True, None)[0])

    # Reuse only fixture plumbing. Explicit expected counts below are reviewer-owned.
    import test_m2_smoke as fixtures
    # U4 consumes the research interval; the replay interval also includes warm-up.
    sessions = [d for d in fixtures.WINDOW if '2023-09-04' <= d <= '2026-09-04']
    for label, observations, before, invalid, aligned in [
        ('repeated zero end-to-end', [(sessions[1], 100), (sessions[3], 0),
                                     (sessions[4], 0), (sessions[6], 200)],
         1, 3, len(sessions) - 4),
        ('trailing zero end-to-end', [(sessions[0], 100), (sessions[3], 0)],
         0, len(sessions) - 3, 3),
        ('positive carry-in end-to-end', [('2019-01-01', 100)], 0, 0, len(sessions)),
    ]:
        with tempfile.TemporaryDirectory(prefix='codex_r2abc_') as scratch:
            scene = fixtures.scenario(scratch, specs={2: {
                'body': fixtures.jsonp_body('sh600011', observations)}})
            result = fixtures.run(scene)
            u4 = next(c for c in result['deterministic']['checks']
                      if c['id'] == 'U4' and c['symbol'] == 'sh600011')
            measured = u4['measured']
            expect(label + ' U4 counts', (before, invalid, before + invalid, aligned),
                   (measured.get('rows_before_the_first_observation'),
                    measured.get('rows_under_an_invalid_observation'),
                    measured['rows_without_applicable_share'], measured['aligned_rows']))
            expect(label + ' U4 remains advisory', 'ADVISORY', u4['status'])
            expect(label + ' all volume rows accounted for', len(sessions),
                   measured['aligned_rows'] + measured['rows_without_applicable_share'])


def revision_review(revision):
    provenance = json.loads((revision / 'PROVENANCE.json').read_text('utf-8'))
    parent = SMOKE / 'evidence_20260908T082833Z'
    expect('new revision is separate from old r2abc', True,
           revision.resolve() != (SMOKE / 'revision_20260908T082833Z_r2abc').resolve())
    pins = provenance['producer_implementation']
    expect('producer pins match exact tested sources', pins,
           {name: digest(SMOKE / name) for name in pins})
    for name, sha in provenance['input_hashes'].items():
        expect('parent input ' + name, sha, digest(parent / name))
        expect('copied input ' + name, sha, digest(revision / name))
    replay = chk.replay(revision)
    expect('replay matches stored bytes-derived result', True, replay['matches_stored'])
    expect('new provenance result hash', provenance['revised_offline_result']['deterministic_sha256'],
           replay['deterministic_sha256'])
    block = replay['deterministic']
    expect('capability is still FAIL', 'FAIL', block['verdicts']['capability'])
    expect('only two EV6 version disagreements fail',
           [('EV6', 'sh600011'), ('EV6', 'bj920000')],
           [(c['id'], c['symbol']) for c in block['checks'] if c['status'] == 'FAIL'])
    for c in block['checks']:
        if c['id'] in ('D1', 'D5', 'R1'):
            expect('retained ' + c['id'] + ' ' + c['symbol'], 'PASS', c['status'])
    print(json.dumps(dict(revision=revision.name,
                          deterministic_sha256=replay['deterministic_sha256'],
                          actual_R1=[c for c in block['checks'] if c['id'] == 'R1']),
                     ensure_ascii=False))


def main():
    retained = [p for p in SMOKE.iterdir() if p.is_dir() and p.name.startswith(
        ('evidence_', 'revision_', 'receipts_', 'frozen_impl_'))]
    before = {p.name: tree(p) for p in retained}
    sources = {p.name: digest(p) for p in SMOKE.glob('*.py')}
    databases = database_metadata()
    with cap.no_remote_connections('Codex independent closure prohibits HTTP'), \
            cap.db_guard('Codex independent closure prohibits all SQLite opens'):
        contracts()
        if len(sys.argv) > 1:
            revision_review(Path(sys.argv[1]))
    expect('source files unchanged during this validation', sources,
           {p.name: digest(p) for p in SMOKE.glob('*.py')})
    expect('all retained trees unchanged during validation', before,
           {p.name: tree(p) for p in retained})
    expect('database file metadata unchanged during validation', databases, database_metadata())
    for item in RESULTS:
        print(json.dumps({k: v for k, v in item.items()
                          if not item['passed'] or k in ('name', 'passed')},
                         ensure_ascii=False))
    print(json.dumps(dict(total=len(RESULTS), passed=sum(r['passed'] for r in RESULTS),
                          failed=sum(not r['passed'] for r in RESULTS)), ensure_ascii=False))
    return 0 if all(r['passed'] for r in RESULTS) else 1


if __name__ == '__main__':
    raise SystemExit(main())
