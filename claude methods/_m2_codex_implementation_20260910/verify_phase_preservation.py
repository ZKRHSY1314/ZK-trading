"""Read bytes only; compare old evidence, production files and tracked baseline."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATIC = ROOT/'claude methods/_m2_codex_review/tonghuasun_static_20260909'
ALLOWED_CHANGES = {
    'backend/app/data/tonghuasun_provider.py': 'e0cd1e00c21ba9f8ee7bd5ea0605312bff7a187ee82163b5996678f76542c74b',
    'backend/tests/test_tonghuasun_provider.py': 'dc698ea3a1678c0a63acba761847f16a0da2325345a524deb9c2084e813bf757',
}

def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()

def review():
    baseline_path = HERE/'baseline/production_files_before.json'
    baseline = json.loads(baseline_path.read_bytes())
    production = {}
    for name, old in baseline['files'].items():
        path = Path(name)
        if old.get('exists') is False:
            production[name] = {'passed': not path.exists(), 'expected': 'absent'}
        elif not path.is_file():
            production[name] = {'passed': False, 'reason': 'missing'}
        else:
            before = path.stat()
            actual = sha(path)
            after = path.stat()
            passed = (before.st_size == after.st_size == old['size'] and
                before.st_mtime_ns == after.st_mtime_ns == old['mtime_ns'] and actual == old['sha256'])
            production[name] = {'passed': passed, 'sha256': actual,
                'size': after.st_size, 'mtime_ns': after.st_mtime_ns}
    archives = {}
    for name in ['artifact_manifest.json', 'probe_delivery_manifest.json',
                 'resume_20260910/resume_delivery_manifest.json']:
        path = STATIC/name
        pins = json.loads(path.read_bytes())['artifacts']
        matches = {}
        for artifact_name, pin in pins.items():
            artifact = Path(artifact_name)
            if not artifact.is_absolute():
                artifact = path.parent/artifact
            matches[artifact_name] = artifact.is_file() and sha(artifact) == pin
        archives[str(path)] = {'manifest_sha256': sha(path), 'checked': len(matches),
            'passed': all(matches.values()), 'mismatches': [name for name, ok in matches.items() if not ok]}
    tracked_path = HERE/'baseline/tracked_full_names_sha256.json'
    tracked_pins = json.loads(tracked_path.read_bytes())
    unexpected = []
    changed = []
    for name, old in tracked_pins.items():
        actual = sha(ROOT/name) if (ROOT/name).is_file() else None
        if actual != old:
            changed.append(name)
        if actual != ALLOWED_CHANGES.get(name, old):
            unexpected.append(name)
    original = (HERE/'baseline/test_tonghuasun_provider.py').read_text(encoding='utf-8')
    expected = original.replace('    assert payload["codes"] == ["600000.SH"]',
        '    assert "codes" not in payload').replace('        "code": "600000",\n', '')
    test_delta_ok = expected == (ROOT/'backend/tests/test_tonghuasun_provider.py').read_text(encoding='utf-8')
    tracked = {'checked': len(tracked_pins), 'changed': changed, 'unexpected': unexpected,
        'test_has_only_expected_two_assertion_changes': test_delta_ok,
        'passed': not unexpected and test_delta_ok}
    capture_manifest = HERE/'qualification_capture/producer_pins.json'
    capture_pins = json.loads(capture_manifest.read_bytes())
    capture = {'manifest_sha256': sha(capture_manifest), 'checked': len(capture_pins),
        'passed': all(Path(name).is_file() and sha(name) == pin for name, pin in capture_pins.items())}
    return {'schema': 'm2.ths.preservation.v1', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'method': 'read bytes only; no SQLite or network', 'production_files': production,
        'old_delivery_manifests': archives, 'tracked_files': tracked, 'qualification_producers': capture,
        'passed': all(row['passed'] for row in production.values()) and
            all(row['passed'] for row in archives.values()) and tracked['passed'] and capture['passed'],
        'production_sqlite_connections': 0, 'market_requests': 0,
        'inputs': {str(baseline_path): sha(baseline_path), str(tracked_path): sha(tracked_path)},
        'producer_sha256': sha(__file__)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    destination = Path(args.out).resolve()
    if not destination.is_relative_to(HERE.resolve()) or destination.exists():
        raise SystemExit('new output inside current phase required')
    result = review()
    with destination.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, ensure_ascii=True)
    print(json.dumps({'passed': result['passed'], 'tracked': result['tracked_files'],
        'production_files': len(result['production_files']), 'old_evidence': [
            row['checked'] for row in result['old_delivery_manifests'].values()],
        'artifact': str(destination)}, ensure_ascii=True))
    raise SystemExit(0 if result['passed'] else 1)
