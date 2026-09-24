"""Close only M2 coordination after validated artifacts and actual heartbeat pause."""
from datetime import datetime, timezone
import copy
import hashlib
import json
from pathlib import Path
import sys
import tomllib

import verify_final
import verify_preservation_closure

HERE = Path(__file__).resolve().parent
PHASE = HERE.parent
CM = PHASE.parent
COORD = CM / '_m2_codex_review/m2_claude_coordination_state.json'
AUTOMATION = Path(r'C:\Users\Administrator\.codex\automations\claude\automation.toml')
REPORT = CM / 'M2_FINAL_ACCEPTANCE_20260910.md'


def read(path):
    return json.loads(Path(path).read_bytes())


def pin(path):
    return dict(sha256=verify_final.sha(path), bytes=Path(path).stat().st_size)


def dump_new(path, data):
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    assert not (HERE / 'completion.json').exists()
    assert read(HERE / 'reproduced/closing_audit.json')['passed']
    assert read(HERE / 'preservation_before_closure.json')['passed']
    inputs = verify_final.verify_inputs()
    automation = tomllib.loads(AUTOMATION.read_text(encoding='utf-8'))
    assert automation['id'] == 'claude' and automation['status'] == 'PAUSED'
    assert automation['rrule'] == 'RRULE:FREQ=MINUTELY;INTERVAL=15'
    assert automation['target_thread_id'] == '01a086db-3c02-7a21-bf22-26e4f73e24b0'
    before = COORD.read_bytes()
    assert hashlib.sha256(before).hexdigest() == '5defcc6c1ba0664c6b1d11b995079a5e4ace6267e8c07b6485ad15937c06c900'
    with (HERE / 'coordination_before_closure.json').open('xb') as f:
        f.write(before)
    state = json.loads(before)
    now = datetime.now(timezone.utc).isoformat()
    previous_review = copy.deepcopy(state['latest_review'])
    state['review_history'].append(previous_review)
    state['last_ui_observation'] = dict(recorded_at_utc=now, window_id=264394,
        status='artifact_delivery_verified_ui_idle_unverified', task_id=state['current_task']['id'],
        evidence='Read-only UI state still displayed the earlier Running / 5m 0s tool text. Refresh and one recovery attempt returned GetCursorPos failed: access denied (0x80070005). No second dispatch, Stop action or client shutdown. Final report and review manifest exist, match pins, and their complete computational outputs reproduce.',
        completion_observed=False, previous=state['last_ui_observation'])
    state['current_task'].update(status='technically_validated_complete', artifact_delivery_observed=True,
        artifact_delivery_reviewed_at_utc=now, ui_completion_observed=False, completion_observed=True,
        completion_evidence_type='stable_report_manifest_and_full_offline_reproduction_not_UI_idle',
        final_report=str(CM / 'M2_TONGHUASUN_V2_CLAUDE_INDEPENDENT_REVIEW_20260910.md'),
        final_report_sha256='63620379262de943448e96847922b2da1ac4ceed54d5abac22d723aaf78ad520',
        codex_final_acceptance=str(REPORT), codex_final_acceptance_sha256=pin(REPORT)['sha256'])
    state['task_history'].append(copy.deepcopy(state['current_task']))
    state['latest_review'] = dict(report=str(REPORT), report_sha256=pin(REPORT)['sha256'],
        verdict='M2_technically_validated_in_approved_52_security_staging_scope', at_utc=now,
        independent_reviewer='Claude actual existing fork delivery',
        codex_reproduction=str(HERE / 'reproduced/closing_audit.json'),
        all_three_reproductions_exact=True, final_user_acceptance='not_asserted',
        documentation_corrections='Names NULL versus raw bytes; AI PDF readings and literal flag; conditional BJ scope inference; cross-market SSE limits; 2 rejected attempts; absolute reproduction paths.')
    state['state_limits'].update(tonghuasun_long_history='actual_52_security_v2_staging_independently_reviewed_and_reproduced',
        v2_dataset_state='validated', M2_complete=True, M2_scope='approved_50_stocks_and_2_benchmarks_staging_only',
        full_market_complete=False, M3_started=False, production_promoted=False,
        live_trading=False, strict_pit=False)
    state['automation'].update(status='PAUSED', updated_at=automation['updated_at'],
        status_evidence='automation_update returned PAUSED; actual TOML re-read and id, status, 15-minute interval and current-thread target verified',
        configuration_sha256=pin(AUTOMATION)['sha256'])
    state['codex_takeover']['claude_dispatch_enabled'] = False
    state['codex_takeover']['claude_completion_ui_verified'] = False
    state['next_action'] = 'M2 technical staging delivery is complete. No further M2 dispatch. Existing heartbeat is PAUSED. Preserve frozen evidence; await a separately authorized M3 or production-promotion task. Do not reinterpret legacy FAIL or the old pre-review manifest state as current closure status.'
    state['next_claude_inspection_due_utc'] = None
    state['updated_at_utc'] = now
    state['m2_closure'] = dict(status='validated', technical_work_complete=True,
        user_acceptance_not_asserted=True, at_utc=now, report=str(REPORT), report_sha256=pin(REPORT)['sha256'],
        run_id=verify_final.RUN_ID, independent_review_verdict='PASS_with_documentation_corrections_recorded',
        runtime_ui_idle_verified=False, automation_status='PAUSED', next_stage_started=False)
    temporary = COORD.with_name('m2_claude_coordination_state.closure.tmp')
    dump_new(temporary, state)
    assert COORD.read_bytes() == before, 'coordination changed concurrently'
    temporary.replace(COORD)
    coord_after = pin(COORD)
    sys.argv = [str(HERE / 'verify_preservation_closure.py'), str(HERE / 'preservation_after_closure.json'), coord_after['sha256']]
    verify_preservation_closure.main()
    assert verify_final.verify_inputs() == inputs
    final_files = [REPORT, HERE / 'verify_final.py', HERE / 'verify_preservation_closure.py', Path(__file__),
        HERE / 'reproduced/closing_audit.json', HERE / 'preservation_before_closure.json',
        HERE / 'preservation_after_closure.json', HERE / 'coordination_before_closure.json',
        PHASE / 'preservation_final_m2.json', PHASE / 'v2_capture_accounting.json',
        CM / '_m2_ths_v2_claude_review_20260910/review_manifest.json',
        CM / 'M2_TONGHUASUN_V2_CLAUDE_INDEPENDENT_REVIEW_20260910.md']
    final_files.extend(sorted((HERE / 'reproduced').glob('r*')))
    completion = dict(schema='m2.final_closure.v1', completed_at_utc=datetime.now(timezone.utc).isoformat(),
        status='validated', M2_complete=True, scope='user_approved_52_security_staging_corpus',
        run_id=verify_final.RUN_ID, price_rows_per_store=45685, suspension_rows_per_store=298,
        coverage_keys_per_store=45983, unknown_missing_keys=0, duplicate_business_keys=0,
        field_comparisons_both_stores=548220, differences=0, independent_review='actual_Claude_PASS',
        full_reproduction_exact=True, frozen_inputs_unchanged=True, production_files_preserved=True,
        final_user_acceptance='not_asserted', live_trading=False, production_promoted=False,
        strict_pit=False, full_market_complete=False, M3_started=False,
        listing_depth_shortfalls=14, source_scope='one reviewed BJ block-total interpretation; direct official daily total not retained; limited to staging',
        immutable_artifacts={str(p): pin(p) for p in final_files},
        frozen_delivery_manifest_sha256=inputs['delivery_manifest_sha256'],
        coordination_snapshot=dict(path=str(COORD), **coord_after),
        automation=dict(id='claude', status='PAUSED', interval_minutes=15,
            target_thread_id=automation['target_thread_id'], actual_toml_sha256=pin(AUTOMATION)['sha256']),
        operational_note='Claude final artifact delivery verified; stale UI Running label could not be refreshed due desktop access denied. No claim of UI Idle, no repeat dispatch, no application shutdown.',
        production_sqlite_connections=0, network_requests=0, dataset_writes=0)
    dump_new(HERE / 'completion.json', completion)
    print(json.dumps({'M2_complete': True, 'status': 'validated', 'report': str(REPORT),
                      'automation': 'PAUSED', 'completion_sha256': pin(HERE / 'completion.json')['sha256']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
