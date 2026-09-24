from pathlib import Path
import hashlib,json
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3]; BASE=ROOT/'claude methods/_m4_20260912'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text('utf-8-sig'))
def write(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
now=datetime.now(timezone.utc).isoformat(); mp=BASE/'claude_03a/artifact_manifest.json'; mf=read(mp)
assert sha(mp)=='5166dec377d61f86d20b87dae264bd8c037e3a629dd2204c10a52747d6640df1'
review=BASE/'codex/qualification_review_02'
assert read(review/'verification.json')['all_preserved'] and read(review/'evidence/validation_receipt.json')['passed'] and read(review/'independent_mapping_checks_verified.json')['all_pass']
freeze_path=BASE/'historical_qualification_freeze.json'; assert not freeze_path.exists()
paths={ROOT/rel for rel in mf['written']}
for rel,pin in mf['written'].items(): assert sha(ROOT/rel)==pin['sha256'],rel
acceptance=ROOT/'claude methods/M4_03A_CODEX_ACCEPTANCE_20260912.md'
paths.update([mp,acceptance,BASE/'execution_freeze.json',BASE/'portfolio_freeze.json',BASE/'risk_freeze.json'])
paths.update(p for p in review.rglob('*') if p.is_file())
paths.update(BASE/'codex'/n for n in ['review_qualification_02.py','probe_qualification_mapping_02.py','probe_qualification_mapping_final.py','probe_qualification_mapping_verified.py'])
freeze=dict(schema='m4.historical_qualification_freeze.v1',created_at_utc=now,verdict='technically_validated_static_qualification_and_assumed_replay_contract',
    M4_03A_technical_complete=True,M4_complete=False,review_only=True,live_trading_enabled=False,strict_pit=False,training_eligible=False,M3_complete=False,
    qualification_sha256=sha(BASE/'claude_03a/qualification.json'),mapping_sha256=sha(BASE/'claude_03a/proposal_mapping.py'),
    proposal_sha256=sha(BASE/'claude_03a/NEXT_READ_PROPOSAL.md'),
    validation=dict(pins=24,requirements=12,anchors=65,kernel_cases=9,classifier_cases=5,mapping_chain_cases=10,codex_independent_cases=6,all_pass=True),
    pins={p.relative_to(ROOT).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(paths)})
write(freeze_path,freeze)
sp=BASE/'coordination_state.json'; state=read(sp); old=state['current_task']; assert old['id']=='M4-03A-HISTORICAL-QUALIFICATION-20260912'
old.update(status='validated',completion_observed=True,runtime_ui_running_observed=False,unresolved_issue_categories=0,technical_complete=True,
    latest_delivery_completion_observed=True,latest_delivery_manifest_sha256=sha(mp),acceptance_file=acceptance.relative_to(ROOT).as_posix(),freeze_file=freeze_path.relative_to(ROOT).as_posix(),freeze_sha256=sha(freeze_path))
state['task_history'].append(old)
state['reviews'].append(dict(id='M4-03A-FINAL',verdict='technically_validated',acceptance=acceptance.relative_to(ROOT).as_posix(),freeze=freeze_path.relative_to(ROOT).as_posix(),freeze_sha256=sha(freeze_path),validation=freeze['validation']))
task=ROOT/'claude methods/M4_03B_DEVELOPMENT_REPLAY_CLAUDE_TASK_20260912.md'
state['current_task']=dict(id='M4-03B-DEVELOPMENT-REPLAY-20260912',status='prepared_not_submitted',owner='Claude existing Fable 5.1 project advice (fork)',instruction_file=task.relative_to(ROOT).as_posix(),instruction_sha256=sha(task),write_scope=['claude methods/_m4_20260912/claude_03b/'],submitted=False,execution_observed=False,completion_observed=False)
state['updated_at_utc']=now; state['next_action']='Send prepared M4-03B once after confirming empty composer/no in-flight work. Exactly two immutable candidate reads, fixed development assumed replay, no holdout price access or M5. Keep ACTIVE15-minute patrol.'
write(sp,state)
plan=BASE/'PLAN.md'; text=plan.read_text('utf-8-sig')
text=text.replace('当前Claude正在修订 M4-03A 的历史重放方案（资格矩阵已复验，方案有未来收盘依赖、时间映射和容量数学三项问题）；本小步不连接SQLite、不运行历史成交。','M4-03A已技术验收并冻结（三项方案问题已修复），当前准备派发M4-03B：对两份固定候选库做只读开发区间假设重放；不使用留出期价格，不宣称真实历史执行通过。')
plan.write_text(text,encoding='utf-8')
print(json.dumps({'freeze_sha256':sha(freeze_path),'freeze_pins':len(freeze['pins']),'task_sha256':sha(task),'status':'prepared_not_submitted'}))
