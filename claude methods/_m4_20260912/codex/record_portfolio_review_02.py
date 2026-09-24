from pathlib import Path
import json, hashlib
from datetime import datetime, timezone, timedelta
BASE=Path(__file__).resolve().parent.parent
path=BASE/'coordination_state.json'
state=json.loads(path.read_text('utf-8'))
now=datetime.now(timezone.utc)
review='claude methods/_m4_20260912/codex/M4_02A_REVIEW_02.md'
h=hashlib.sha256((BASE/'codex/M4_02A_REVIEW_02.md').read_bytes()).hexdigest()
task=state['current_task']
task.update(status='revision_feedback_sent',completion_observed=False,latest_delivery_completion_observed=True,latest_delivery_manifest_sha256='ebc18c1f147008876f3cce801693dfca426b2f05422d825e7d7e57fd69d9fdca',revision=2,review_file=review,review_sha256=h,unresolved_issue_categories=1,correction_execution_observed=False,feedback_received=False)
state['reviews'].append(dict(id='M4-02A-REVIEW-02',verdict='changes_required',source_sha256='fd832b0e41e8ff5c284b2c08213e6bb525b6dc69158ac66fa358d3b347e9658d',delivered_tests_replayed=38,original_independent_checks_passed=5,additional_checks=2,additional_failures=1,review_file=review,review_sha256=h))
state['last_inspection']=dict(task_id=task['id'],at_utc=now.isoformat(),state='feedback_sent_execution_pending',submitted_once=True,feedback_sent_at_utc=now.isoformat(),review_sha256=h,automation_status='ACTIVE',native_evidence='Correct ZK-trading / Fable 5.1 project advice (fork), delivery_02 final verified; empty composer, sent same-task feedback exactly once; message bubble plus Sending observed. Do not resend.')
state['updated_at_utc']=now.isoformat()
state['next_inspection_due_utc']=(now+timedelta(minutes=15)).isoformat()
state['next_action']='Verify review_02 feedback receipt/execution without resend; accept corrected M4-02A only after independent original five checks, calendar mutation/suffix checks, isolated suite and preservation verification. One remaining calendar-binding P1; do not start M4-02B yet. Existing 15-minute patrol remains ACTIVE.'
path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(BASE/'codex/portfolio_review_02/feedback_dispatch_receipt.json').write_text(json.dumps(state['last_inspection'],ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(state['last_inspection'],ensure_ascii=False,indent=2))
