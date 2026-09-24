"""Record independently completed M3-02 acceptance and prepare one next task."""
import json, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'claude methods/_m3_20260910'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return {'path':str(p.relative_to(ROOT)), 'sha256':sha(p)}
now=datetime.now(timezone.utc)
report=ROOT/'claude methods/M3_02_CODEX_ACCEPTANCE_20260910.md'
assert sha(report)=='4c1fcc2376c93c5ebf233b28b1d2f6608108eadadd8754ca30cb3e79124648dd'
receipt={'schema':'m3.codex_acceptance.v1','task_id':'M3-02-FROZEN-READER-20260910','verdict':'accepted_for_actual_cutoff_case_review','recorded_at_utc':now.isoformat(),'report':pin(report),'completion_observed':True,'completion_evidence':'Actual unobstructed native Claude screenshot and UIA: same selected fork, Message63 ready_for_review, manifest4aa337d9840c970700bad7f2566af7e7a84a486ec8180c1b0295664bc0662962, Idle, Claude finished the response, empty composer and disabled Send. Refreshed at 08:57 UTC. No duplicate dispatch.','evidence':[pin(BASE/'codex'/p) for p in ['reader_chronology_source_review_02/result.json','reader_episode_packet_review_03/result.json','reader_delivery_tests_isolated_01/execution.json','reader_working_boundary_tests_02/execution.json','reader_working_packet_extension_tests_01/execution.json','preservation_m3_02_checkpoint_01.json','reader_delivery_static_validation_01.json']],'delivery_manifest':pin(BASE/'claude_02/artifact_manifest.json'),'actual_case_reviews':0,'M3_complete':False,'review_only':True,'live_trading_enabled':False}
target=BASE/'codex/m3_02_acceptance.json'
assert not target.exists()
target.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
statepath=BASE/'coordination_state.json';s=json.loads(statepath.read_text('utf-8'))
assert s['current_task']['id']=='M3-02-FROZEN-READER-20260910'
old=s['current_task'];old.update(status='reviewed_accepted_for_actual_cutoff_case_review',completion_observed=True,completion_observed_at_utc=now.isoformat(),completion_evidence=receipt['completion_evidence'],acceptance_receipt=pin(target))
s['task_history'].append(old)
s['reviews'].append({'id':'M3-02-CODEX-REVIEW-20260910','verdict':receipt['verdict'],'reviewed_at_utc':now.isoformat(),'report':str(report.relative_to(ROOT)),'report_sha256':sha(report),'receipt':pin(target),'delivery_manifest_sha256':receipt['delivery_manifest']['sha256'],'delivery_tests_passed':20,'additional_methods_passed':8,'source_records_replayed':17554,'all_cutoff_packets_checked':225,'actual_reviews':0})
task=ROOT/'claude methods/M3_03_CASE_REVIEW_CLAUDE_TASK_20260910.md'
s['current_task']={'id':'M3-03-CASE-REVIEW-20260910','status':'prepared_not_submitted','owner':'Claude existing Fable 5.1 project advice (fork)','instruction_file':str(task.relative_to(ROOT)),'instruction_sha256':sha(task),'allowed_write_scope':['claude methods/_m3_20260910/claude_03/'],'allowed_data_scope':'pinned cutoff-only case_review_bundle_01 and accepted policy documentation; no SQLite/network/chronology or later episode audit; no Codex reviews','submitted':False,'execution_observed':False,'completion_observed':False,'input_manifest':pin(BASE/'codex/case_review_bundle_01/manifest.json'),'predecessor_manifest_sha256':receipt['delivery_manifest']['sha256']}
s['updated_at_utc']=now.isoformat();s['next_inspection_due_utc']=(now+timedelta(minutes=15)).isoformat()
s['last_inspection']={'inspected_at_utc':now.isoformat(),'task_id':old['id'],'status':'accepted_complete','evidence':receipt['completion_evidence'],'redispatched':False,'completion_observed':True}
s['next_action']='Submit prepared M3-03 once after verified idle composer; Codex independently reviews fixed individual cases before reading Claude opinions; inspect every15minutes; preserve dissent and honest below50 target limitation.'
statepath.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'task_sha256':sha(task),'acceptance_receipt':pin(target),'status':s['current_task']['status']}))
