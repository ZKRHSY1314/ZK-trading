"""Pin a complete Claude M3-01 delivery before independent execution.

Reads ordinary source/doc bytes only. Does not import the implementation, open
SQLite, or modify Claude's files. The frozen review snapshot cannot be reused.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PHASE = HERE.parent
ROOT = PHASE.parents[1]
DELIVERY = PHASE / 'claude_01'
MANIFEST = DELIVERY / 'artifact_manifest.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    expected = sys.argv[1]
    raw = MANIFEST.read_bytes()
    assert sha(raw) == expected, 'manifest differs from observed delivery'
    manifest = json.loads(raw)
    assert manifest['task_id'] == 'M3-01-LABEL-SPEC-20260910'
    assert manifest['status'] == 'ready_for_review'
    written = manifest['written']
    assert all(key in written for key in (
        'backend/app/research/m3_labels.py', 'backend/tests/test_m3_labels.py',
        'claude methods/_m3_20260910/claude_01/DELIVERY.md',
        'claude methods/_m3_20260910/claude_01/LABEL_POLICY.md',
        'claude methods/_m3_20260910/claude_01/LABEL_POLICY.json',
        'claude methods/_m3_20260910/claude_01/test_output.txt'))
    blobs = {}
    pins = {}
    for rel, entry in written.items():
        path = (ROOT / rel).resolve(strict=True)
        allowed = path in {ROOT / 'backend/app/research/m3_labels.py', ROOT / 'backend/tests/test_m3_labels.py'} or path.is_relative_to(DELIVERY)
        assert allowed and path.is_relative_to(ROOT), f'out-of-scope delivery file {rel}'
        content = path.read_bytes()
        assert sha(content) == entry['sha256'] and len(content) == entry['bytes'], rel
        blobs[rel] = content
        pins[rel] = dict(sha256=sha(content), bytes=len(content))
    source_pins = {}
    for rel, entry in manifest['sources_read'].items():
        assert not entry.get('missing'), f'missing declared source {rel}'
        path = (ROOT / rel).resolve(strict=True)
        assert path.is_relative_to(ROOT) and path.suffix.lower() not in {'.db', '.sqlite', '.sqlite3', '.bin'}, rel
        content = path.read_bytes()
        assert sha(content) == entry['sha256'] and len(content) == entry['bytes'], rel
        source_pins[rel] = dict(sha256=sha(content), bytes=len(content))
    assert sha(MANIFEST.read_bytes()) == expected, 'manifest changed during snapshot'
    for rel, pin in pins.items():
        assert sha((ROOT / rel).read_bytes()) == pin['sha256'], 'source changed during snapshot: ' + rel
    output = HERE / 'review_01_input'
    assert not output.exists(), 'review input already frozen'
    output.mkdir()
    (output / 'artifact_manifest.json').write_bytes(raw)
    for rel, content in blobs.items():
        dest = output / 'files' / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    # Mutable coordinator state is a historical input, not a forever-current pin.
    (output / 'coordination_at_delivery.json').write_bytes((PHASE / 'coordination_state.json').read_bytes())
    receipt = dict(schema='m3.codex.delivery_pin.v1', frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        manifest_sha256=expected, written=pins, sources_read=source_pins,
        status='complete_delivery_pinned_not_yet_validated', sqlite_connections=0,
        real_cases_read=0, producer_sha256=sha(Path(__file__).read_bytes()))
    (output / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(manifest_sha256=expected, written=len(pins), sources=len(source_pins),
                         snapshot=str(output), checked=True), ensure_ascii=False))


if __name__ == '__main__':
    main()
