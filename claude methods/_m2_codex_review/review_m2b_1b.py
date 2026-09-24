"""Read-only independent review of retained M2b-1b evidence, 2026-09-08.

No live capture, production database open, service operation or source edit. Actual
process inventory is read only. Raw vendor JS is never evaluated: only the pinned
decoder routine receives an extracted string. Diagnostic decoding is not acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / 'claude methods' / '_m2_smoke'
EVIDENCE = SMOKE / 'evidence_20260908T021722Z'
sys.path.insert(0, str(SMOKE))
import requests
import pandas
from akshare.stock import cons
from akshare.stock import stock_zh_a_sina
from akshare.index import index_stock_zh
import smoke_capture as cap
import smoke_checks as chk
import sina_klc_decoder as dec


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_tree():
    return {p.relative_to(EVIDENCE).as_posix(): digest(p)
            for p in sorted(EVIDENCE.rglob('*')) if p.is_file()}


def f8(items):
    checks, _ = cap.preflight(out_root=cap.TMP_ROOT / 'm2b_smoke_20990101T000000Z',
                             evidence_dir=cap.EVIDENCE_ROOT / 'evidence_20990101T000000Z',
                             process_lister=lambda: items, requests_module=requests,
                             probe_reference=False)
    return next(c.status for c in checks if c.id == 'F8')


def main():
    before = evidence_tree()
    manifest = json.loads((EVIDENCE / 'capture_manifest.json').read_text('utf-8'))
    stored = json.loads((EVIDENCE / 'checks.json').read_text('utf-8'))
    results = {'run_id': manifest['run_id']}
    with cap.no_remote_connections('offline independent review'), \
            cap.db_guard('no database opens in independent review'), \
            patch.object(requests.Session, 'request', side_effect=AssertionError('no HTTP')):
        replayed = chk.replay(EVIDENCE)
        assert replayed['matches_stored'] is True
        assert replayed['deterministic'] == stored['deterministic']
        assert replayed['deterministic']['verdicts']['capability'] == 'FAIL'
        results['replay'] = {'matches_stored': True,
                             'deterministic_sha256': replayed['deterministic_sha256'],
                             'capability': 'FAIL'}
        attempts = manifest['attempts']
        assert [a['request_index'] for a in attempts] == [1, 3]
        assert [a['status'] for a in attempts] == [200, 200]
        assert all(a['attempt_no'] == 1 for a in attempts)
        gap = attempts[1]['started_at_monotonic'] - attempts[0]['started_at_monotonic']
        assert gap >= 1.5
        assert manifest['run_status'] == 'aborted'
        results['wire'] = {'planned': 5, 'issued': 2, 'retries': 0,
                           'gap_sec': gap, 'capture_sec': manifest['deadline']['elapsed_sec'],
                           'inventory_size_recorded': manifest['environment']['process_inventory_size']}

        diagnostic = []
        for record in manifest['requests']:
            if record.get('raw_file') is None:
                continue
            path = EVIDENCE / 'raw' / record['raw_file']
            assert digest(path) == record['body_sha256']
            body = path.read_bytes()
            assert len(body) == record['bytes']
            try:
                dec.decode_klc(body, record['encoding'], routine=cons.hk_js_decode)
            except dec.DecodeError as exc:
                assert 'single quoted' in str(exc)
            else:
                raise AssertionError('the frozen decoder unexpectedly accepted the original body')
            text = dec.bytes_to_text(body, record['encoding'])
            match = re.fullmatch(r'\s*(var\s+(\w+)="([^"]*)";)\s*(/\*.*?\*/)\s*', text, re.S)
            assert match, 'observed body is not exactly assignment plus block comment'
            assert match.group(3) == text.split('=')[1].split(';')[0].replace('"', '')
            # Diagnostic-only: discard the matched non-executable comment IN MEMORY.
            # Original bytes, stored verdict, and implementation remain unchanged.
            decoded = dec.decode_klc(match.group(1).encode('utf-8'), 'utf-8', routine=cons.hk_js_decode)
            dates = [r['date'] for r in decoded['rows']]
            assert dates == sorted(set(dates))
            diagnostic.append({'job': record['job'], 'bytes': len(body), 'raw_sha256': digest(path),
                               'branch': decoded['branch'], 'rows': len(dates),
                               'first_date': dates[0], 'last_date': dates[-1],
                               'after_research_end': sum(d > cap.RESEARCH_END for d in dates),
                               'trailer_chars_including_delimiters': len(match.group(4)),
                               'amount_present_rows': sum('amount' in r for r in decoded['rows']),
                               'unique_dates': len(set(dates)),
                               'interpretation': 'diagnostic only; not a semantic gate result'})
        results['decoder_diagnosis'] = diagnostic

        # F8 must not accept missing inventory or the actual repository API launch form.
        results['f8_missing_inventory_status'] = f8([])
        api_command = 'python.exe -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port 8000'
        results['f8_repository_api_command_status'] = f8([{'pid': 424242, 'cmdline': api_command}])
        assert results['f8_missing_inventory_status'] == 'PASS'
        assert results['f8_repository_api_command_status'] == 'PASS'
        with patch.object(cap.subprocess, 'run', return_value=SimpleNamespace(
                returncode=1, stdout='', stderr='synthetic inventory failure')):
            missing = cap.default_process_lister()
        assert missing == []
        results['failed_process_command_returns_empty_list'] = True

        # Reproduce the encoding issue without emitting any process command lines.
        errors = []
        with patch.object(threading, 'excepthook', side_effect=lambda args: errors.append(args.exc_type.__name__)):
            current_broken = cap.default_process_lister()
        results['current_default_inventory'] = {'count': len(current_broken), 'reader_errors': errors}

        # Independent present-time inventory: producer explicitly emits UTF-8, parent
        # captures bytes and decodes strictly. No lossy replacement and no raw log output.
        command = ('[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); '
                   'Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine '
                   '| ConvertTo-Json -Compress')
        good = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
                              capture_output=True, timeout=60, check=False)
        assert good.returncode == 0 and good.stdout
        inventory = json.loads(good.stdout.decode('utf-8-sig', errors='strict'))
        assert isinstance(inventory, list) and len(inventory) > 0
        names = [p.get('Name', '') for p in inventory]
        results['current_explicit_utf8_inventory_count'] = len(inventory)
        results['current_inventory_includes_powershell'] = any('powershell' in n.lower() for n in names)

    assert evidence_tree() == before
    results['retained_evidence_unchanged'] = True
    results['production_metadata'] = {name: {'bytes': (ROOT / name).stat().st_size,
                                            'mtime_ns': (ROOT / name).stat().st_mtime_ns}
                                      for name in ('trading_local.sqlite3', 'market_history.sqlite3',
                                                   'market_history.sqlite3-wal')}
    print(json.dumps(results, indent=2))
    return results


if __name__ == '__main__':
    main()
