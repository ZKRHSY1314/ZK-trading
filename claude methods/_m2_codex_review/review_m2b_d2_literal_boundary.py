"""Bounded F8 regression review; example command lines are DATA, never executed.

Uses the real normalizer/classifier/preflight. No HTTP or database opens, no capture,
service operations, changes to evidence, or modification of prior reviewer scripts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import review_m2b_d1d2 as prior


CASES = [
    ('python_literal_basic', 'python.exe',
     '''python.exe -c "print('-m uvicorn app.main:app')"''', 'PASS'),
    ('python_literal_launch_text', 'python.exe',
     '''python.exe -c "print('uvicorn.run(app.main:app)')"''', 'PASS'),
    ('python_print_then_actual_launch', 'python.exe',
     '''python.exe -c "print('starting'); from uvicorn import run; run('app.main:app')"''', 'FAIL'),
    ('powershell_literal_listing', 'powershell.exe',
     '''powershell.exe -Command "Get-Item 'scripts/run_stack.ps1'"''', 'PASS'),
    ('powershell_listing_then_worker', 'powershell.exe',
     '''powershell.exe -Command "Get-Item .; python.exe scripts/control_plane_loop.py"''', 'FAIL'),
    ('powershell_listing_with_executed_argument', 'powershell.exe',
     '''powershell.exe -Command "Get-Item $(python.exe scripts/control_plane_loop.py)"''', 'FAIL'),
    ('python_direct_api', 'python.exe',
     '''python.exe -c "import uvicorn; uvicorn.run('app.main:app')"''', 'FAIL'),
    ('powershell_direct_launcher', 'powershell.exe',
     '''powershell.exe -Command "& 'D:\\codex-A股交易\\scripts\\run_stack.ps1'"''', 'FAIL'),
]


def main():
    before = {str(p): prior.tree(p) for p in (prior.ORIGINAL, prior.REVISION, prior.RECEIPTS)}
    db_before = prior.db_metadata()
    results = []
    with prior.cap.no_remote_connections('offline F8 literal-boundary acceptance review'), \
            prior.cap.db_guard('no database opens in literal-boundary review'):
        quiet = {'ProcessId': 4, 'Name': 'System', 'CommandLine': None}
        for label, name, command, expected in CASES:
            raw = [quiet, {'ProcessId': 999993, 'Name': name, 'CommandLine': command}]
            records = prior.cap._normalize_inventory(json.dumps(raw))
            verdict, reason = prior.cap.classify_process(records[1])
            gate = prior.f8(records)
            results.append({'case': label, 'expected_F8': expected,
                            'actual_F8': gate.status, 'pass': gate.status == expected,
                            'classification': verdict, 'reason': reason,
                            'synthetic_command_never_executed': command})
    assert before == {str(p): prior.tree(p) for p in (prior.ORIGINAL, prior.REVISION, prior.RECEIPTS)}
    assert db_before == prior.db_metadata()
    failed = [r for r in results if not r['pass']]
    print(json.dumps({'checks': len(results), 'passed': len(results) - len(failed),
                      'failed': len(failed), 'results': results,
                      'capture_source_sha256': prior.digest(prior.SMOKE / 'smoke_capture.py'),
                      'evidence_and_db_metadata_unchanged': True}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
