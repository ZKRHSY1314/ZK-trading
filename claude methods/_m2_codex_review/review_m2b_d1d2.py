"""Independent offline acceptance checks for the 2026-09-08 D1/D2 revision.

Never captures HTTP, opens SQLite, starts/stops services, or edits retained evidence.
Synthetic process records are strings only; none of the example launches is executed.
Exit 1 means an acceptance expectation failed, not that this driver crashed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / 'claude methods' / '_m2_smoke'
ORIGINAL = SMOKE / 'evidence_20260908T021722Z'
REVISION = SMOKE / 'revision_20260908T021722Z_d1d2'
RECEIPTS = SMOKE / 'receipts_20260908T021722Z'
sys.path.insert(0, str(SMOKE))
import requests
import pandas  # imported before the connection guard
from akshare.stock import cons
from akshare.stock import stock_zh_a_sina
from akshare.index import index_stock_zh
import smoke_capture as cap
import smoke_checks as chk
import sina_klc_decoder as dec


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(path):
    return {p.relative_to(path).as_posix(): digest(p)
            for p in sorted(path.rglob('*')) if p.is_file()}


def db_metadata():
    return {p.name: {'size': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns}
            for p in (cap.TRADING_DB, cap.MARKET_DB, cap.MARKET_WAL) if p.exists()}


def f8(items):
    checks, _ = cap.preflight(
        out_root=cap.TMP_ROOT / 'm2b_smoke_20990102T000000Z',
        evidence_dir=cap.EVIDENCE_ROOT / 'evidence_20990102T000000Z',
        process_lister=lambda: items, requests_module=requests,
        probe_reference=False)
    return next(c for c in checks if c.id == 'F8')


def main():
    results = []

    def check(name, expected, actual):
        results.append({'name': name, 'expected': expected, 'actual': actual,
                        'pass': actual == expected})

    original_before, revised_before = tree(ORIGINAL), tree(REVISION)
    receipts_before = tree(RECEIPTS)
    db_before = db_metadata()
    original_pins = {
        'raw/01_sh600011_klc_kl.js.bin': 'adc5a39131ba32df3bdc53cbc47bcc842f9ed2c31c8e60cfe8173f2d387a2d02',
        'raw/03_sh000300_klc_kl.js.bin': 'ef2180be45a1c1bb33f99772a55b410eb3923524d9b8fe268d549584a6e28647',
        'capture_manifest.json': '09a3442a284dca4d1ea533f43a23a345ab16c3616cc27f4fa00c65e5be65ce6c',
        'checks.json': '87d8b16278b5dff7e22dc8df3da2a3957ecf10ff46cd100a97a1f2e1b07bc104',
        'reference/reference_extract.json': 'ea021004a7b387fccfacd5bfec55b327cb90333811b8a4e27c6ef1390ec036b2',
    }
    check('original evidence retains previous review pins', original_pins,
          {p: original_before[p] for p in original_pins})
    provenance = json.loads((REVISION / 'PROVENANCE.json').read_text('utf-8'))
    pins = provenance['implementation_that_produced_this_revision']
    check('revision implementation matches declared pins', pins,
          {p: digest(SMOKE / p) for p in pins})
    for rel in ('raw/01_sh600011_klc_kl.js.bin', 'raw/03_sh000300_klc_kl.js.bin',
                'capture_manifest.json', 'reference/reference_extract.json'):
        check('revision is byte-identical input: ' + rel, original_before[rel],
              revised_before[rel])

    receipt_inventory = json.loads((RECEIPTS / 'RECEIPTS.json').read_text('utf-8'))
    for entry in receipt_inventory['files']:
        target, source = RECEIPTS / entry['file'], Path(entry['source'])
        check('receipt copy: ' + entry['file'], entry['sha256'], digest(target))
        check('receipt original source: ' + entry['file'], entry['sha256'],
              digest(source) if source.exists() else 'unavailable')
        check('receipt preserved mtime: ' + entry['file'], entry['source_mtime_ns'],
              target.stat().st_mtime_ns)

    with cap.no_remote_connections('Codex offline D1/D2 review'), \
            cap.db_guard('Codex review forbids all database opens'):
        decoded = []
        for job, filename, branch, count in (
            ('sh600011', '01_sh600011_klc_kl.js.bin', 'O', 5935),
            ('sh000300', '03_sh000300_klc_kl.js.bin', 'D', 5987),
        ):
            body = (ORIGINAL / 'raw' / filename).read_bytes()
            rows = dec.decode_klc(body, None, routine=cons.hk_js_decode)
            dates = [r['date'] for r in rows['rows']]
            check('D1 real decode: ' + job, (branch, count, True),
                  (rows['branch'], rows['row_count'], dates == sorted(set(dates))))
            decoded.append({'job': job, 'rows': count, 'first': dates[0], 'last': dates[-1]})
        base = 'var KLC="K2xx";'
        for trailer in (' alert(1)', ' /*ok*/ var other="x";', ' /*open', ' //comment',
                        ' /*ok*/foo', '/*' + 'x' * 8200 + '*/', '/*ok*/' * 9):
            try:
                dec.extract_payload(base + trailer)
                actual = 'accepted'
            except dec.DecodeError:
                actual = 'refused'
            check('D1 bad trailer ' + repr(trailer[:35]), 'refused', actual)

        replayed = chk.replay(REVISION)
        check('revised offline replay matches stored', True, replayed['matches_stored'])
        check('revised deterministic hash', provenance['revised_deterministic_sha256'],
              replayed['deterministic_sha256'])
        check('revised capability remains FAIL', 'FAIL',
              replayed['deterministic']['verdicts']['capability'])

        for label, completed in (
            ('nonzero', SimpleNamespace(returncode=1, stdout=b'[]')),
            ('blank stdout', SimpleNamespace(returncode=0, stdout=b'  ')),
            ('invalid UTF8', SimpleNamespace(returncode=0, stdout=b'\xff')),
        ):
            try:
                cap._decode_inventory(completed)
                actual = 'accepted'
            except cap.InventoryUnavailable:
                actual = 'refused'
            check('D2 decoder ' + label, 'refused', actual)
        with patch.object(cap.subprocess, 'run', side_effect=subprocess.TimeoutExpired('inventory', 1)):
            try:
                cap._run_inventory_command(['inventory-not-executed'], 1)
                actual = 'accepted'
            except cap.InventoryUnavailable:
                actual = 'refused'
            check('D2 inventory timeout', 'refused', actual)

        quiet = [{'pid': 4, 'name': 'System', 'cmdline': '', 'cmdline_available': False}]
        check('D2 empty inventory', 'FAIL', f8([]).status)
        check('D2 irrelevant protected OS image', 'PASS', f8(quiet).status)
        cases = [
            ('actual run_stack API', 'python.exe',
             'python.exe -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port 8000', 'FAIL'),
            ('absolute control worker', 'python.exe',
             r'python.exe -X utf8 "D:\codex-A股交易\backend\scripts\control_plane_loop.py"', 'FAIL'),
            ('backend-relative control worker', 'python.exe',
             r'python.exe -X utf8 scripts\control_plane_loop.py --profile full', 'FAIL'),
            ('backend-relative history worker', 'python.exe',
             r'python.exe -X utf8 scripts\market_history_refresh_loop.py', 'FAIL'),
            ('inline executing API', 'python.exe',
             'python.exe -c "import uvicorn; uvicorn.run(\'app.main:app\', host=\'127.0.0.1\', port=8000)"', 'FAIL'),
            ('inline executing stack launcher', 'powershell.exe',
             "powershell.exe -NoProfile -Command \"& 'D:\\codex-A股交易\\scripts\\run_stack.ps1'\"", 'FAIL'),
            ('merely quoting API in print', 'python.exe',
             'python.exe -c "print(\'-m uvicorn app.main:app\')"', 'PASS'),
            ('merely listing stack script', 'powershell.exe',
             'powershell.exe -Command "Get-Item scripts/run_stack.ps1"', 'PASS'),
        ]
        for label, name, command, expected in cases:
            record = {'pid': 999991, 'name': name, 'cmdline': command, 'cmdline_available': True}
            check('D2 F8 ' + label, expected, f8(quiet + [record]).status)
        for label, record in (
            ('null command on python', {'ProcessId': 999991, 'Name': 'python.exe', 'CommandLine': None}),
            ('empty command on python', {'ProcessId': 999991, 'Name': 'python.exe', 'CommandLine': ''}),
            ('whitespace command on python', {'ProcessId': 999991, 'Name': 'python.exe', 'CommandLine': '  '}),
            ('missing name and null command', {'ProcessId': 999991, 'CommandLine': None}),
        ):
            try:
                items = cap._normalize_inventory(json.dumps([record]))
                actual = f8(quiet + items).status
            except cap.InventoryUnavailable:
                actual = 'FAIL'
            check('D2 F8 normalized ' + label, 'FAIL', actual)

        # Read only current machine inventory; do not print unrelated command lines.
        try:
            inventory = cap.default_process_lister(timeout=30)
            live_check = f8(inventory)
            present = {'process_count': len(inventory), 'F8': live_check.status,
                       'stack_matches': len(live_check.data.get('stack_matches', [])),
                       'unreadable_relevant': len(live_check.data.get('unreadable_relevant', []))}
        except cap.InventoryUnavailable as exc:
            present = {'inventory_unavailable': type(exc).__name__}

    check('original evidence unchanged by review', original_before, tree(ORIGINAL))
    check('revised evidence unchanged by review', revised_before, tree(REVISION))
    check('receipts unchanged by review', receipts_before, tree(RECEIPTS))
    check('production DB metadata unchanged by review', db_before, db_metadata())
    failed = [r for r in results if not r['pass']]
    print(json.dumps({'checks': len(results), 'passed': len(results) - len(failed),
                      'failures': failed, 'decoded': decoded,
                      'revised_hash': replayed['deterministic_sha256'],
                      'current_inventory_not_historical_proof': present,
                      'production_metadata': db_before}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
