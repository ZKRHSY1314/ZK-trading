"""Independently reconcile a sealed two-reviewer library with original inputs.

Does not author reviews, call the label/count implementation, or read SQLite.
Every original record field except review_ledger must remain byte-equivalent as
a JSON value. Expected ledgers come directly from the two sealed deliveries.
"""
import gzip
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ORIGINAL = HERE.parent / 'claude_02/runs/dev_run_02'
BUNDLE = HERE / 'case_review_bundle_01'
OWN = HERE / 'individual_review_bound_01'


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]


def main():
    library = Path(sys.argv[1]).resolve(strict=True)
    expected_manifest = sys.argv[2]
    output = Path(sys.argv[3]).resolve()
    assert library.parent == HERE and output.parent == HERE and not output.exists()
    assert sha(library / 'manifest.json') == expected_manifest
    denied = []

    def audit(event, args):
        bad = event == 'sqlite3.connect' or event.startswith('socket.') or event in {'subprocess.Popen', 'os.system', 'os.startfile'}
        if event == 'open':
            path, mode, flags = args
            writing = isinstance(mode, str) and any(c in mode for c in 'wax+') or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
            if writing and not (isinstance(path, (str, os.PathLike)) and Path(path).resolve() == output):
                bad = True
        if bad:
            denied.append(event)
            raise PermissionError(event)

    sys.addaudithook(audit)
    pins = {}
    for rel, value in read(library / 'manifest.json')['written'].items():
        path = library / rel
        assert sha(path) == value['sha256']
        pins[str(path)] = value['sha256']
    execution = read(library / 'execution.json')
    normalized_path = ROOT / execution['normalized_claude_reviews']['path']
    assert sha(normalized_path) == execution['normalized_claude_reviews']['sha256']
    theirs = read(normalized_path)
    expected = {}
    comparisons = []
    positive_controls = Counter()
    expected_controls = {}
    for item in read(BUNDLE / 'index.json')['cases']:
        case_id = item['case_id']
        packet = read(BUNDLE / item['path'])
        ours = read(OWN / 'reviews' / (case_id + '.json'))
        other = theirs['episode_reviews'][case_id]
        key = (item['episode_id'], item['record_hash'])
        assert key not in expected
        expected[key] = [ours['raw_review'], other]
        dual = ours['verdict'] == other['verdict'] == 'positive'
        comparisons.append((case_id, dual, ours['verdict'] == other['verdict']))
        if dual:
            assert ours['control_set_admissible'] and theirs['control_set_admissible'][case_id]
        for control in ours['control_reviews']:
            raw = control['raw_review']
            control_key = (raw['case_episode_id'], raw['case_record_hash'])
            assert control_key not in expected_controls and control_key not in expected
            expected_controls[control_key] = [case_id, control, theirs['control_reviews'][case_id + '/' + control['symbol']]]
            if dual:
                positive_controls[control_key] += 1
        assert len(packet['control_records']) in (3, 4, 5)
    assert len(expected) == 32 and len(expected_controls) == 127
    original_records = {}
    checked = changed = 0
    for path in sorted((ORIGINAL / 'chronology').glob('*.jsonl.gz')):
        assert sha(path) == execution['input_files'][str(path)]
        old_rows, new_rows = rows(path), rows(library / 'chronology' / path.name)
        assert len(old_rows) == len(new_rows)
        for old, new in zip(old_rows, new_rows):
            a, b = old['record'], new['record']
            key = (a['episode_id'], a['record_hash'])
            assert key not in original_records
            original_records[key] = a
            assert {k: v for k, v in old.items() if k != 'record'} == {k: v for k, v in new.items() if k != 'record'}
            assert {k: v for k, v in a.items() if k != 'review_ledger'} == {k: v for k, v in b.items() if k != 'review_ledger'}
            if key in expected:
                assert b['review_ledger']['entries'] == expected[key]
                assert len({x['reviewer_id'] for x in expected[key]}) == 2
                assert all(x['reviewer_kind'] == 'agent' and not x['synthetic'] for x in expected[key])
                changed += 1
            else:
                assert a == b
            checked += 1
    assert checked == 17554 and changed == 32
    counts = read(library / 'library_counts.json')
    dual_count = sum(x[1] for x in comparisons)
    assert counts['qualified_reviewed_positive_episodes'] == dual_count
    assert counts['unique_controls'] == len(positive_controls)
    assert counts['control_uses'] == sum(positive_controls.values())
    assert counts['control_reuse_max'] == max(positive_controls.values(), default=0)
    assert counts['pending_review'] == 17554 - 32
    assert counts['single_review'] == 0
    assert counts['disputed'] == sum(pair[0]['verdict'] != pair[1]['verdict'] for pair in expected.values())
    assert counts['independently_reviewed'] == 32 - counts['disputed']
    assert not counts['target']['met'] and not counts['target']['training_eligible']
    controls = read(library / 'control_reviews.json')
    assert len(controls) == 127
    for item in controls:
        raw = item['codex_review']['raw_review']
        expected_control = expected_controls.pop((raw['case_episode_id'], raw['case_record_hash']))
        assert [item['case_id'], item['codex_review'], item['claude_review']] == expected_control
        assert item['review_collection_separate_from_episode_ledger'] is True
    assert not expected_controls
    diagnostics = read(library / 'diagnostic_reviews.json')
    assert len(diagnostics) == 8 and all(x['counts_as_positive_episode'] is False for x in diagnostics)
    for item in diagnostics:
        source = read(BUNDLE / 'diagnostics' / (item['case_id'] + '.json'))['record']
        final = read(library / 'reviewed_representatives' / (item['case_id'] + '.json'))
        assert final == source
        assert item['claude_review'] == theirs['diagnostic_reviews'][item['case_id']]
        assert item['codex_review'] == read(OWN / 'diagnostics' / (item['case_id'] + '.json'))
    assert all(sha(Path(path)) == digest for path, digest in pins.items())
    result = {'passed': True, 'at_utc': datetime.now(timezone.utc).isoformat(), 'library_manifest_sha256': expected_manifest,
              'unchanged_original_core_values': checked, 'exact_two_review_ledgers': changed,
              'preserved_pending_core_records': checked - changed, 'dual_positive_cases': dual_count,
              'dissent_case_ids': [x[0] for x in comparisons if not x[2]], 'diagnostics_separately_preserved': 8, 'dual_control_assessments_separately_preserved': 127,
              'expected_qualified_control_uses': sum(positive_controls.values()), 'target_met': False,
              'training_eligible': False, 'sqlite_connections': 0, 'network_requests': 0, 'denied_events': denied,
              'review_judgments_generated': 0, 'producer_sha256': sha(Path(__file__))}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
