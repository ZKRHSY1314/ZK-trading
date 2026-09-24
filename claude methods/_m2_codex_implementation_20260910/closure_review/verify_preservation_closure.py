"""Account for explicitly authorized coordination updates without rewriting old FAIL.

Only the coordination file may differ inside the old 13-artifact static manifest.
Its original bytes must still match the pinned pre-resumption backup. The original
preservation checker and every non-coordination artifact retain their original rules.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PHASE = HERE.parent
sys.path.insert(0, str(PHASE))
import verify_preservation_v2 as v2


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    output = Path(sys.argv[1]).resolve()
    expected_current = sys.argv[2]
    assert output.parent == HERE and not output.exists(), 'fresh closing receipt required'
    coordination = PHASE.parent / '_m2_codex_review/m2_claude_coordination_state.json'
    baseline_copy = PHASE / 'claude_resume_coordination_before.json'
    old_manifest = PHASE.parent / '_m2_codex_review/tonghuasun_static_20260909/artifact_manifest.json'
    old_pin = json.loads(old_manifest.read_bytes())['artifacts'][str(coordination)]
    assert sha(baseline_copy) == old_pin == 'cdd8902edff8edc11f12fc86bc081ebc943914b1a416ede8a07936b84aecab8f'
    before = json.loads(baseline_copy.read_bytes())
    current = json.loads(coordination.read_bytes())
    assert sha(coordination) == expected_current, 'coordination changed before audit'
    allowed = {'authorization', 'automation', 'codex_claude_resumption_history',
               'codex_supplemental_evidence', 'codex_takeover', 'coordination_speedup',
               'current_task', 'last_ui_observation', 'latest_review', 'next_action',
               'next_claude_inspection_due_utc', 'prohibitions', 'state_limits',
               'updated_at_utc', 'task_history', 'review_history', 'm2_closure'}
    changed = sorted(k for k in set(before) | set(current) if before.get(k) != current.get(k))
    assert set(changed) <= allowed, 'unrelated coordination fields changed'
    for name in ('task_history', 'review_history'):
        assert current[name][:len(before[name])] == before[name], 'history rewritten'
    assert current['current_task']['id'] == 'M2-THS-V2-INDEPENDENT-REVIEW-20260910'
    assert current['state_limits']['live_trading'] is False
    assert current['state_limits']['production_promoted'] is False
    check = v2.review()
    base = check['original_checker']
    assert all(v['passed'] for v in base['production_files'].values())
    for path, item in base['old_delivery_manifests'].items():
        if Path(path) == old_manifest:
            assert item['mismatches'] == [str(coordination)] and item['checked'] == 13
        else:
            assert item['passed']
    assert base['tracked_files']['unexpected'] == ['.gitignore']
    assert base['tracked_files']['test_has_only_expected_two_assertion_changes']
    assert check['ignore_delta']['exact_append_verified']
    assert base['qualification_producers']['passed']
    assert sha(coordination) == expected_current, 'coordination changed during audit'
    result = dict(schema='m2.closure_preservation.v1', checked_at_utc=datetime.now(timezone.utc).isoformat(),
                  passed=True, original_v2_checker=check, original_fail_preserved=True,
                  coordination_delta=dict(path=str(coordination), before_sha256=old_pin,
                      preserved_before_copy=str(baseline_copy), current_sha256=expected_current,
                      changed_top_level_fields=changed,
                      authority='Actual user request: write acceptance, resume Claude delegation, patrol every 15 minutes until M2 complete. This file is the authorized coordination write scope.'),
                  producer_sha256=sha(__file__), production_sqlite_connections=0,
                  network_requests=0, dataset_writes=0, live_trading=False)
    with output.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({'passed': True, 'production_positions': len(base['production_files']),
                      'tracked_files': base['tracked_files']['checked'], 'authorized_coordination_delta': True}))


if __name__ == '__main__':
    main()
