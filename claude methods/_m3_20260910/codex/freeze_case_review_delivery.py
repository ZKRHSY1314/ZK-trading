"""Pin the completed M3-03 delivery before independent acceptance.

Copies declared Claude outputs and ordinary consumed source documents only.
Never connects to SQLite, executes delivery code, or manufactures reviews.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DELIVERY = HERE.parent / 'claude_03'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    expected = sys.argv[1]
    output = HERE / sys.argv[2]
    assert output.parent == HERE and not output.exists()
    manifest = DELIVERY / 'artifact_manifest.json'
    assert sha(manifest) == expected
    raw = manifest.read_bytes()
    data = json.loads(raw)
    assert data['task_id'] == 'M3-03-CASE-REVIEW-20260910'
    assert data['status'] == 'ready_for_review'
    state = json.loads((HERE.parent / 'coordination_state.json').read_bytes().decode('utf-8-sig'))
    assert state['current_task']['completion_observed'] is True
    copies = {}
    for kind, entries in [('files', data['written']), ('sources', data['sources_read'])]:
        for rel, pin in entries.items():
            path = ((DELIVERY if kind == 'files' else ROOT) / rel).resolve(strict=True)
            assert path.is_relative_to(ROOT) and not pin.get('missing'), rel
            assert path.suffix.lower() not in {'.sqlite', '.sqlite3', '.db', '.gz'}, rel
            if kind == 'files':
                assert path.is_relative_to(DELIVERY), rel
            blob = path.read_bytes()
            assert hashlib.sha256(blob).hexdigest() == pin['sha256'] and len(blob) == pin['bytes'], rel
            copies[(kind, str(path.relative_to(ROOT)))] = blob
    for rel, pin in data.get('preserved_originals', {}).items():
        path = (DELIVERY / rel).resolve(strict=True)
        assert path.is_relative_to(DELIVERY) and sha(path) == pin, rel
    assert sha(manifest) == expected
    output.mkdir()
    (output / 'artifact_manifest.json').write_bytes(raw)
    for (kind, rel), blob in copies.items():
        destination = output / kind / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(blob)
    for (kind, rel), blob in copies.items():
        assert (ROOT / rel).read_bytes() == blob, ('changed_during_snapshot', kind, rel)
    assert sha(manifest) == expected
    (output / 'coordination_at_snapshot.json').write_bytes((HERE.parent / 'coordination_state.json').read_bytes())
    receipt = {'schema': 'm3.codex.case_review_snapshot.v1', 'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
               'manifest_sha256': expected, 'written': data['written'], 'sources_read': data['sources_read'],
               'preserved_originals': data.get('preserved_originals', {}),
               'copied_output_count': len(data['written']), 'copied_source_count': len(data['sources_read']),
               'actual_completion_observed': True, 'sqlite_connections': 0, 'network_requests': 0,
               'review_judgments_generated': 0, 'accepted': False, 'producer_sha256': sha(Path(__file__))}
    (output / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in receipt.items() if key not in {'written', 'sources_read', 'preserved_originals'}}, ensure_ascii=False))
    print('receipt_sha256', sha(output / 'receipt.json'))


if __name__ == '__main__':
    main()
