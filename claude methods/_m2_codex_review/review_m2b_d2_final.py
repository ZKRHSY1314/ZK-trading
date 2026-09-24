"""Version-aware, offline final D2 review. No example program is executed.

The capture-entry tests inject only synthetic process records and a retained frozen
reference. They must refuse before any HTTP or capture output directory is created.
No production database is opened; every existing evidence directory is read-only.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import review_m2b_d1d2 as prior
import review_m2b_d2_literal_boundary as boundary

CURRENT = prior.SMOKE / 'revision_20260908T021722Z_d2_literal'


def main():
    checks = []

    def check(name, actual, expected=True):
        checks.append({'name': name, 'actual': actual, 'expected': expected,
                       'pass': actual == expected})

    directories = (prior.ORIGINAL, prior.REVISION, prior.RECEIPTS, CURRENT)
    before = {str(p): prior.tree(p) for p in directories}
    db_before = prior.db_metadata()
    prov = json.loads((CURRENT / 'PROVENANCE.json').read_text('utf-8'))
    pins = prov['producer_implementation']
    check('current revision pins match its actual producer',
          {p: prior.digest(prior.SMOKE / p) for p in pins}, pins)
    for name, expected in {
        'PROVENANCE.json': '9270c1f545b8dd0c59f6586d3a29a8fa5b3060caebb85a07076d4a03018005fd',
        'checks.json': '78819944b7c850ce181fbffd2e26ef86ba4aad4fda53c3fa775ab321a424d3a0',
    }.items():
        check('previous revision retains prior review pin: ' + name,
              prior.digest(prior.REVISION / name), expected)
    for rel in ('raw/01_sh600011_klc_kl.js.bin', 'raw/03_sh000300_klc_kl.js.bin',
                'capture_manifest.json', 'reference/reference_extract.json'):
        check('new revision retained input: ' + rel,
              prior.digest(CURRENT / rel), prior.digest(prior.ORIGINAL / rel))

    with prior.cap.no_remote_connections('offline final D2 review'), \
            prior.cap.db_guard('no database opens in final D2 review'):
        replayed = prior.chk.replay(CURRENT)
        check('new revision matches stored replay', replayed['matches_stored'])
        check('new revision deterministic hash', replayed['deterministic_sha256'],
              prov['revised_deterministic_sha256'])
        check('new revision remains capability FAIL',
              replayed['deterministic']['verdicts']['capability'], 'FAIL')

        # Narrow shape/bounds checks; acceptance is scoped to known, visible targets.
        programs = [
            ('py literal container', True, "print({'target': ['app.main:app', 1, None]})", False),
            ('py multiple inert expressions', True, "print('uvicorn'); repr('run_stack.ps1')", False),
            ('py nested call', True, "print(boot('app.main:app'))", True),
            ('py executable keyword argument', True, "print('app.main:app', file=get_stream())", True),
            ('py interpolation', True, '''print(f'{boot("app.main:app")}')''', True),
            ('py name rebinding', True, "print=boot; print('app.main:app')", True),
            ('py comprehension unproven', True, "print([x for x in ['app.main:app']])", True),
            ('py AST node bound', True, "print(['app.main:app'," + ','.join(['1'] * 405) + '])', True),
            ('py text bound', True, "# uvicorn " + 'x' * 4096, True),
            ('ps simple quoted path', False, "Get-Item 'D:/project files/scripts/run_stack.ps1'", False),
            ('ps pipeline', False, "Get-Content run_stack.ps1 | Invoke-Expression", True),
            ('ps variable', False, "Get-Item $path #run_stack.ps1", True),
            ('ps redirection', False, "Get-Content run_stack.ps1 > output.txt", True),
            ('ps newline', False, "Get-Item run_stack.ps1\npython scripts/control_plane_loop.py", True),
        ]
        for name, python, program, must_block in programs:
            verdict, _ = prior.cap._inline_verdict(program, python=python)
            check(name, verdict != 'other', must_block)

        frozen_reference = json.loads(
            (CURRENT / 'reference' / 'reference_extract.json').read_text('utf-8'))
        for label, name, command, _expected in boundary.CASES:
            if label not in ('python_print_then_actual_launch',
                             'powershell_listing_then_worker',
                             'powershell_listing_with_executed_argument'):
                continue
            with tempfile.TemporaryDirectory(prefix='codex_f8_review_') as temp:
                root = Path(temp)
                attempted_http = []
                records = prior.cap._normalize_inventory(json.dumps([
                    {'ProcessId': 4, 'Name': 'System', 'CommandLine': None},
                    {'ProcessId': 999994, 'Name': name, 'CommandLine': command},
                ]))

                class NeverTransport:
                    def __init__(self, *args, **kwargs):
                        pass

                    def __call__(self, url, **kwargs):
                        attempted_http.append(url)
                        raise AssertionError('HTTP forbidden during F8 refusal test')

                with patch.object(prior.cap, 'TMP_ROOT', root / 'tmp'), \
                        prior.requests.Session() as session:
                    run = prior.cap.SmokeRun('20990103T000000Z', evidence_root=root / 'evidence')
                    try:
                        run.capture(session=session, requests_module=prior.requests,
                                    process_lister=lambda: records,
                                    transport_factory=NeverTransport,
                                    reference_reader=lambda: frozen_reference,
                                    supervise_jobs=False)
                    except prior.cap.PreflightError as exc:
                        refused_by_f8 = 'F8' in str(exc)
                    else:
                        refused_by_f8 = False
                check('capture entry refuses ' + label, refused_by_f8)
                check('no HTTP or capture trees for ' + label,
                      not attempted_http and not (root / 'tmp').exists()
                      and not (root / 'evidence').exists())

    check('all existing evidence directories unchanged', before,
          {str(p): prior.tree(p) for p in directories})
    check('production database metadata unchanged', db_before, prior.db_metadata())
    failed = [r for r in checks if not r['pass']]
    print(json.dumps({'checks': len(checks), 'passed': len(checks) - len(failed),
                      'failures': failed,
                      'replayed_hash': replayed['deterministic_sha256'],
                      'producer_pins': pins,
                      'existing_evidence_hashes': before,
                      'production_metadata': db_before}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
