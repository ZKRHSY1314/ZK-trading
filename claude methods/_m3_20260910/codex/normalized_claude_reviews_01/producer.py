"""Validate and copy actually authored Claude reviews after Codex manual review.

Requires a manifest-bound Codex judgment receipt and observed task completion.
No verdict is derived from labels, control admissibility or diagnostic support.
"""
import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CLAUDE = HERE.parent / 'claude_03'
BUNDLE = HERE / 'case_review_bundle_01'


def read(path):
    return json.loads(path.read_bytes().decode('utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def instant(value):
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    return parsed


def main():
    manual_path = Path(sys.argv[1]).resolve(strict=True)
    manual_sha = sys.argv[2]
    out = Path(sys.argv[3]).resolve()
    assert manual_path.is_relative_to(HERE) and sha(manual_path) == manual_sha
    assert out.parent == HERE and not out.exists()
    manual = read(manual_path)
    for key in ('actual_execution_observed', 'completion_observed', 'individual_reviews_verified', 'effective_corrections_verified'):
        assert manual[key] is True
    manifest_path = CLAUDE / 'artifact_manifest.json'
    assert sha(manifest_path) == manual['manifest_sha256']
    manifest = read(manifest_path)
    assert manifest['status'] == 'ready_for_review' and manifest['task_id'] == 'M3-03-CASE-REVIEW-20260910'
    for group in ('written', 'sources_read'):
        for rel, pin in manifest[group].items():
            path = ((CLAUDE if group == 'written' else ROOT) / rel).resolve(strict=True)
            assert path.is_relative_to(CLAUDE if group == 'written' else ROOT), rel
            assert sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'], rel
    assert sha(ROOT / 'backend/app/research/m3_labels.py') == 'e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393'
    assert sha(BUNDLE / 'manifest.json') == 'fa234fded7e448f1d8313ee26f43f1e81902e9294426faf1dc2164747ac887fc'
    for rel, pin in read(BUNDLE / 'manifest.json')['written'].items():
        assert sha(BUNDLE / rel) == pin['sha256']
    out.mkdir()
    denied = []

    def audit(event, args):
        bad = event == 'sqlite3.connect' or event.startswith('socket.') or event in {'subprocess.Popen', 'os.system', 'os.startfile'}
        if event == 'open':
            path, mode, flags = args
            writing = isinstance(mode, str) and any(c in mode for c in 'wax+') or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
            if writing and not (isinstance(path, (str, os.PathLike)) and Path(path).resolve().is_relative_to(out)):
                bad = True
        if bad:
            denied.append(event)
            raise PermissionError(event)

    sys.addaudithook(audit)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / 'backend'))
    from app.research import m3_labels as labels

    execution_path = CLAUDE / 'execution/execution_receipt.json'
    execution = read(execution_path)
    reviewer = execution['reviewer_id']
    assert execution['reviewer_kind'] == 'agent' and reviewer != 'codex-primary-01a086db-m3-03'
    start, end = instant(execution['started_at_utc']), instant(execution['finished_at_utc'])
    episodes, controls, diagnostics, admissible = {}, {}, {}, {}
    index = read(BUNDLE / 'index.json')
    source_pins = {}
    for item in index['cases']:
        case_id = item['case_id']
        path = CLAUDE / 'reviews' / (case_id + '.json')
        review = read(path)
        packet = read(BUNDLE / item['path'])
        binding = review['input_bindings']
        representative = packet['representative_record']
        for key, value in review['frozen_labels_at_representative'].items():
            assert value == (representative['labels'][key] if key in representative['labels'] else representative[key]), (case_id, key)
        assert review['reviewer_id'] == reviewer and review['reviewer_kind'] == 'agent'
        assert review['case_id'] == case_id and review['symbol'] == item['symbol']
        assert review['representative_date'] == item['decision_date']
        assert binding['case_file_sha256'] == item['sha256']
        for key in ('case_record_hash', 'case_prefix_hash', 'cutoff_packet_hash'):
            assert binding[key] == item['record_hash' if key == 'case_record_hash' else key]
        assert binding['case_episode_id'] == item['episode_id']
        assert binding['policy_hash'] == labels.POLICY_HASH
        assert review['execution_id'] == execution['execution_id'] and review['session_id'] == execution['session_id']
        assert start <= instant(review['reviewed_at']) <= end
        assert all(instant(t) <= instant(review['reviewed_at']) for t in review['evidence_inspected_at'])
        assert sha(CLAUDE / review['authored_note_path']) == review['authored_note_sha256']
        raw = review['raw_review']
        assert raw['verdict'] == review['verdict'] and raw['reviewed_at'] == review['reviewed_at']
        assert raw['case_record_hash'] == item['record_hash'] and raw['case_prefix_hash'] == item['case_prefix_hash']
        assert raw['reviewer_id'] == reviewer and raw['reviewer_kind'] == 'agent' and raw['synthetic'] is False
        arguments = {k: v for k, v in raw.items() if k != 'entry_hash'}
        arguments['evidence_refs'] = tuple(arguments['evidence_refs'])
        assert labels.ReviewRecord(**arguments).validated() == raw
        episodes[case_id] = copy.deepcopy(raw)
        assert isinstance(review['control_set_admissible'], bool)
        admissible[case_id] = review['control_set_admissible']
        originals = {r['symbol']: r for r in packet['control_records']}
        assert len(review['control_reviews']) == len(originals) == item['control_count']
        assert {x['symbol'] for x in review['control_reviews']} == set(originals)
        for control in review['control_reviews']:
            record = originals[control['symbol']]
            assert control['control_record_hash'] == record['record_hash']
            assert control['control_episode_id'] == record['episode_id']
            assert control['decision_date'] == item['decision_date']
            assert control['frozen_selection_reasons'] == record['labels']['selection']['reasons']
            assert control['frozen_phase'] == record['labels']['phase']['label']
            assert control['frozen_selection'] == record['labels']['selection']['label']
            assert control['frozen_liquidity_band'] == record['labels']['liquidity']['band']
            assert control['frozen_regime'] == record['labels']['regime']['regime']
            assert control['amount_20_mean_cny'] == record['features']['amount_20_mean_cny']
            assert control['bars_available'] == record['features']['bars_available']
            assert control['suspensions_in_window'] == record['session_view']['suspensions_in_window']
            assert control['cutoff'] == record['cutoff'] and control['current_state'] == record['current_state']
            assert isinstance(control['reviewer_admissible'], bool)
            assert all(control['same_policy_eligibility'].values())
            for key in ('reviewer_assessment', 'reviewer_non_candidate_reason', 'reviewer_uncertainty'):
                assert isinstance(control[key], str) and control[key].strip()
            controls[case_id + '/' + control['symbol']] = {
                'case_id': case_id, 'case_record_hash': record['record_hash'], 'reviewer_id': reviewer, 'reviewer_kind': 'agent',
                'reviewed_at': review['reviewed_at'], 'reviewed_at_semantics': 'parent case review sealing time',
                'execution_ref': review['execution_ref'], 'source_review_path': str(path.relative_to(ROOT)), 'source_review_sha256': sha(path),
                'original_control_review': copy.deepcopy(control), 'raw_verdict_generated': False}
        source_pins[str(path.relative_to(ROOT))] = sha(path)
    for i in range(1, 9):
        case_id = f'D{i:03}'
        path = CLAUDE / 'diagnostics' / (case_id + '.json')
        review = read(path)
        packet = read(BUNDLE / 'diagnostics' / (case_id + '.json'))
        for key, value in review['frozen_labels'].items():
            assert value == (packet['record']['labels'][key] if key in packet['record']['labels'] else packet['record'][key]), (case_id, key)
        assert review['input_bindings']['record_hash'] == packet['record']['record_hash']
        assert review['input_bindings']['diagnostic_file_sha256'] == sha(BUNDLE / 'diagnostics' / (case_id + '.json'))
        assert review['reviewer_id'] == reviewer and review['reviewer_kind'] == 'agent'
        assert review['counts_as_positive_episode'] is False and review['excluded_from_positive_counts'] is True
        assert review['execution_id'] == execution['execution_id']
        assert start <= instant(review['reviewed_at']) <= end
        assert sha(CLAUDE / review['authored_note_path']) == review['authored_note_sha256']
        diagnostics[case_id] = {'case_record_hash': packet['record']['record_hash'], 'original_diagnostic_review': copy.deepcopy(review), 'counts_as_positive_episode': False}
        source_pins[str(path.relative_to(ROOT))] = sha(path)
    assert len(episodes) == 32 and len(controls) == 127 and len(diagnostics) == 8
    result = {'schema': 'm3.codex.claude_review_normalization.v1', 'accepted': True,
              'actual_execution_observed': True, 'completion_observed': True, 'individual_reviews_verified': True,
              'reviewer_id': reviewer, 'reviewer_kind': 'agent', 'episode_reviews': episodes, 'control_reviews': controls,
              'diagnostic_reviews': diagnostics, 'control_set_admissible': admissible,
              'manual_judgment_receipt': {'path': str(manual_path.relative_to(ROOT)), 'sha256': manual_sha},
              'delivery_manifest_sha256': sha(manifest_path), 'execution_receipt_sha256': sha(execution_path),
              'source_review_files': source_pins, 'review_judgments_generated': 0,
              'control_admissibility_not_converted_to_verdict': True, 'sqlite_connections': 0, 'network_requests': 0, 'denied_events': denied,
              'normalized_at_utc': datetime.now(timezone.utc).isoformat(), 'producer_sha256': sha(Path(__file__))}
    assert all(sha(ROOT / rel) == digest for rel, digest in source_pins.items())
    assert sha(manifest_path) == manual['manifest_sha256']
    (out / 'normalized.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'producer.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'passed': True, 'episode_reviews': 32, 'control_assessments': 127, 'diagnostics': 8,
                      'normalized_sha256': sha(out / 'normalized.json'), 'denied_events': denied}, ensure_ascii=False))


if __name__ == '__main__':
    main()
