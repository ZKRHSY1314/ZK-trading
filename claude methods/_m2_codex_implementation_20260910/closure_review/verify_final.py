"""Codex closing audit; frozen Claude scripts replay into a new output directory.

No collector, staging writer, production SQLite connection or network operation.
Claude's scripts and outputs are never overwritten. This is reproduction of Claude's
independent methods, not a claim of another independent implementation.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
PHASE = HERE.parent
CM = PHASE.parent
REVIEW = CM / '_m2_ths_v2_claude_review_20260910'
RUN_ID = 'ths_v2_20260910_041710_97ef9c09'
RUN = PHASE / 'staging_runs' / RUN_ID / f'run_{RUN_ID}'
OUT = HERE / 'reproduced'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def pins_check(pins, base):
    records = {}
    for name, pin in pins.items():
        path = Path(name)
        if not path.is_absolute():
            path = base / path
        expected = pin['sha256'] if isinstance(pin, dict) else pin
        actual = sha(path)
        size = path.stat().st_size
        assert actual == expected, f'pin changed: {path}'
        if isinstance(pin, dict) and 'bytes' in pin:
            assert size == pin['bytes'], f'size changed: {path}'
        records[str(path)] = dict(sha256=actual, bytes=size)
    return records


def verify_inputs():
    delivery_path = PHASE / 'v2_delivery_manifest.json'
    assert sha(delivery_path) == 'eca6bea3c47ef0d37573f4b20d10d6ffe7956738a98118b7298e703142f7154e'
    delivery = read(delivery_path)
    review_path = REVIEW / 'review_manifest.json'
    review = read(review_path)
    report = review['report']
    assert report['sha256'] == '63620379262de943448e96847922b2da1ac4ceed54d5abac22d723aaf78ad520'
    groups = {
        'delivery_artifacts': pins_check(delivery['artifacts'], PHASE),
        'transitive_evidence': pins_check(delivery['transitive_evidence_pins'], PHASE),
        'claude_inputs': pins_check(review['inputs'], CM),
        'claude_outputs': pins_check(review['outputs'], REVIEW),
        'claude_report': pins_check({report['path']: report}, CM),
        'capture_accounting_inputs': pins_check(read(PHASE / 'v2_capture_accounting.json')['input_pins'], PHASE),
    }
    assert len(groups['delivery_artifacts']) == 31
    assert len(groups['transitive_evidence']) == 479
    return dict(groups=groups, review_manifest_sha256=sha(review_path),
                delivery_manifest_sha256=sha(delivery_path),
                capture_accounting_sha256=sha(PHASE / 'v2_capture_accounting.json'))


def main():
    before = verify_inputs()
    OUT.mkdir(exist_ok=False)
    allowed_uris = {'file:' + quote((RUN / name).as_posix(), safe='/:') + '?mode=ro'
                    for name in ('trading.sqlite3', 'history.sqlite3')}
    connections = []

    def audit(event, args):
        if event.startswith('socket.') or event in ('subprocess.Popen', 'os.system', 'os.startfile', 'os.posix_spawn', 'os.spawn'):
            raise PermissionError('closing audit denies network and processes')
        if event == 'sqlite3.connect':
            if args[0] not in allowed_uris:
                raise PermissionError('only exact candidate mode=ro URIs are allowed')
            connections.append(args[0])
        if event == 'open':
            path, mode, flags = args
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing and (not isinstance(path, (str, bytes, os.PathLike)) or not Path(path).resolve().is_relative_to(OUT)):
                raise PermissionError('closing audit output must stay inside new directory')

    sys.addaudithook(audit)
    reproduced = {}
    for name in ('r03_expected_keys', 'r05_raw_replay', 'r06_basis_unit_controls'):
        spec = importlib.util.spec_from_file_location('codex_closing_' + name, REVIEW / (name + '.py'))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        # Inputs were resolved at module initialization. HERE is used only for output.
        mod.HERE = OUT
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = mod.main()
        (OUT / (name + '.stdout.txt')).write_text(stream.getvalue(), encoding='utf-8')
        actual = read(OUT / (name + '.json'))
        original = read(REVIEW / (name + '.json'))
        assert code == 0 and not actual['problems'], name
        assert actual == original, f'reproduction differs from frozen Claude output: {name}'
        reproduced[name] = dict(exit_code=code, exact_json_reproduction=True,
                                sha256=sha(OUT / (name + '.json')))
        print(name + ': PASS; exact JSON reproduction')
    after = verify_inputs()
    assert after == before, 'frozen artifacts changed during closing replay'
    result = dict(schema='m2.codex_closing_reproduction.v1',
                  checked_at_utc=datetime.now(timezone.utc).isoformat(), passed=True,
                  run_id=RUN_ID, producer_sha256=sha(__file__), input_checks=after,
                  reproduced=reproduced, candidate_readonly_connections=connections,
                  production_sqlite_connections=0, network_requests=0,
                  dataset_writes=0, live_trading=False,
                  method='Reproduce the frozen Claude implementations; compare complete JSON outputs and all frozen pins before/after.')
    (OUT / 'closing_audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': True, 'pin_groups': {k: len(v) for k, v in after['groups'].items()},
                      'readonly_connections': len(connections)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
