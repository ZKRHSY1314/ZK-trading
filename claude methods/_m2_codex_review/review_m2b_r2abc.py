"""Read-only R2-ABC review. Exit 1 denotes a failed acceptance expectation.

No capture, database opens, service changes, or retained-evidence writes.
"""
import json
import sys

from review_m2b_d1d2 import SMOKE, cap, chk, dec, db_metadata, digest, pandas, tree


def main():
    results = []

    def check(name, expected, actual):
        results.append(dict(name=name, expected=expected, actual=actual,
                            passed=actual == expected))

    revision = SMOKE / 'revision_20260908T082833Z_r2abc'
    parent = SMOKE / 'evidence_20260908T082833Z'
    retained = [p for p in SMOKE.iterdir() if p.is_dir() and p.name.startswith(
        ('evidence_', 'revision_', 'receipts_', 'frozen_impl_'))]
    before = {p.name: tree(p) for p in retained}
    db_before = db_metadata()
    provenance = json.loads((revision / 'PROVENANCE.json').read_text('utf-8'))
    pins = provenance['producer_implementation']
    check('current implementation matches revision producer pins', pins,
          {p: digest(SMOKE / p) for p in pins})
    for relative, sha in provenance['input_hashes'].items():
        check('parent input pin: ' + relative, sha, digest(parent / relative))
        check('revision input pin: ' + relative, sha, digest(revision / relative))
    check('original run-2 checks unchanged from previous review',
          'f7c9444b90c0c86ed3f1c5f7f0783ba785425672759440c30448466a8bdbc932',
          digest(parent / 'checks.json'))
    check('original run-1 checks unchanged from previous review',
          '87d8b16278b5dff7e22dc8df3da2a3957ecf10ff46cd100a97a1f2e1b07bc104',
          digest(SMOKE / 'evidence_20260908T021722Z' / 'checks.json'))

    with cap.no_remote_connections('Codex read-only R2ABC review'), \
            cap.db_guard('Codex R2ABC review forbids database opens'):
        replay = chk.replay(revision)
        check('independent offline replay equals stored checks', True,
              replay['matches_stored'])
        check('independent deterministic hash',
              provenance['revised_offline_result']['deterministic_sha256'],
              replay['deterministic_sha256'])
        d = replay['deterministic']
        check('capability remains FAIL', 'FAIL', d['verdicts']['capability'])
        failures = [(c['id'], c['symbol']) for c in d['checks']
                    if c['status'] == 'FAIL']
        check('only retained classification-version disagreements fail',
              [('EV6', 'sh600011'), ('EV6', 'bj920000')], failures)
        for c in d['checks']:
            if c['id'] in ('D1', 'D5', 'R1'):
                check(c['id'] + ' real retained input ' + c['symbol'], 'PASS',
                      c['status'])

        for symbol, filename, count, zeros in (
            ('sh600011', '02_sh600011_getAmountBySymbol.bin', 26, 0),
            ('bj920000', '05_bj920000_getAmountBySymbol.bin', 42, 2),
        ):
            parsed = dec.parse_outstanding_share(
                (parent / 'raw' / filename).read_bytes(), None,
                expected_symbol=symbol, instrument_class='stock')
            check(symbol + ' real auxiliary rows and explicit zeros',
                  (count, zeros), (len(parsed), sum(not r['usable'] for r in parsed)))

        body = (b'var KKE_ShareAmount_sh600011 = ('
                b'[{"date":"2020-01-01","amount":100},'
                b'{"date":"2020-01-03","amount":0},'
                b'{"date":"2020-01-05","amount":200}]);')
        rows = dec.parse_outstanding_share(body, None, expected_symbol='sh600011')
        check('positive-zero-positive: explicit zero invalidates denominator',
              None, dec.outstanding_share_as_of(rows, '2020-01-03'))
        check('positive-zero-positive: intervening day stays unknown',
              None, dec.outstanding_share_as_of(rows, '2020-01-04'))
        check('positive-zero-positive: later positive restores validity',
              200.0, dec.outstanding_share_as_of(rows, '2020-01-05')[
                  'outstanding_share_wan'])
        quality = dec.share_series_quality(rows, ('2020-01-04', '2020-01-05'))
        check('coverage cannot bridge an explicit invalid observation', False,
              quality['covers_window_start'])
        check('installed pandas ffill retains explicit zero', [100.0, 0.0, 0.0, 200.0],
              pandas.Series([100.0, 0.0, None, 200.0]).ffill().tolist())

        # A claimed date in metadata is not evidence of an actual returned date.
        forged = dict(rows=1, first_date='2023-01-03', last_date=None, dates=[])
        check('R1 must reject positive row metadata with no actual dates', 'FAIL',
              chk._replay_verdict(forged, [], False, None)[0])

    check('all retained trees unchanged during review', before,
          {p.name: tree(p) for p in retained})
    check('production database size and mtime unchanged during review', db_before,
          db_metadata())
    for result in results:
        if result['passed']:
            print('[PASS] ' + result['name'])
        else:
            print('[FAIL] ' + json.dumps(result, ensure_ascii=False))
    print(json.dumps(dict(total=len(results), passed=sum(r['passed'] for r in results),
                          failed=sum(not r['passed'] for r in results),
                          retained_directories=len(retained),
                          replay_sha256=replay['deterministic_sha256'],
                          real_replay=[c for c in d['checks'] if c['id'] == 'R1']),
                     ensure_ascii=False, indent=2))
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
