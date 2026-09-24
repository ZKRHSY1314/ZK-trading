from pathlib import Path
import hashlib, json
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'claude methods/_m4_20260912'
def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
def read(p): return json.loads(p.read_text('utf-8'))
def write(p, value): p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
now = datetime.now(timezone.utc).isoformat()
freeze_path = BASE/'risk_freeze.json'
assert not freeze_path.exists(), 'Refuse to overwrite freeze'
manifest_path = BASE/'claude_02b/artifact_manifest.json'
assert sha(manifest_path) == '9687d18fe2ace63e934286e8ad917903b42ab4083e789996478e6cb43371c5be'
manifest = read(manifest_path)
for rel, pin in manifest['written'].items():
    assert sha(ROOT/rel) == pin['sha256'], rel
review = BASE/'codex/risk_review_03'
assert read(review/'delivery_verification.json')['all_preserved']
assert read(review/'delivery_suite_receipt.json')['successful']
assert read(review/'independent_roundtrip.json')['passed']
acceptance = ROOT/'claude methods/M4_02B_CODEX_ACCEPTANCE_20260912.md'
paths = {ROOT/rel for rel in manifest['written']}
paths.update([manifest_path, acceptance, BASE/'execution_freeze.json', BASE/'portfolio_freeze.json'])
paths.update(p for p in review.rglob('*') if p.is_file())
paths.update(BASE/'codex'/n for n in ['probe_risk_03.py', 'probe_risk_additional_03.py', 'probe_risk_roundtrip_03.py', 'run_risk_delivery_03.py', 'verify_risk_delivery_03.py'])
freeze = dict(schema='m4.risk_freeze.v1', created_at_utc=now, verdict='technically_validated_for_synthetic_risk',
    M4_02B_technical_complete=True, M4_complete=False, review_only=True, live_trading_enabled=False,
    training_eligible=False, strict_pit=False, M3_complete=False,
    source_sha256=manifest['code']['backend/app/research/m4_risk.py']['sha256'],
    policy_hash=manifest['execution_policy']['risk_policy_hash'],
    tests=dict(isolated_unittest=36, independent=12, all_pass=True),
    pins={p.relative_to(ROOT).as_posix(): dict(sha256=sha(p), bytes=p.stat().st_size) for p in sorted(paths)})
write(freeze_path, freeze)
task_path = ROOT/'claude methods/M4_03A_HISTORICAL_QUALIFICATION_CLAUDE_TASK_20260912.md'
state_path = BASE/'coordination_state.json'
state = read(state_path)
old = state['current_task']
assert old['id'] == 'M4-02B-RISK-EXIT-20260912'
old.update(status='validated', completion_observed=True, runtime_ui_running_observed=False,
    latest_delivery_completion_observed=True, latest_delivery_manifest_sha256=sha(manifest_path),
    unresolved_issue_categories=0, technical_complete=True,
    final_source_sha256=freeze['source_sha256'], acceptance_file=acceptance.relative_to(ROOT).as_posix(),
    freeze_file=freeze_path.relative_to(ROOT).as_posix(), freeze_sha256=sha(freeze_path))
state['task_history'].append(old)
state['reviews'].append(dict(id='M4-02B-FINAL', verdict='technically_validated',
    acceptance=acceptance.relative_to(ROOT).as_posix(), freeze=freeze_path.relative_to(ROOT).as_posix(),
    freeze_sha256=sha(freeze_path), tests=36, independent_checks=12))
state['current_task'] = dict(id='M4-03A-HISTORICAL-QUALIFICATION-20260912', status='prepared_not_submitted',
    owner='Claude existing Fable 5.1 project advice (fork)', instruction_file=task_path.relative_to(ROOT).as_posix(),
    instruction_sha256=sha(task_path), write_scope=['claude methods/_m4_20260912/claude_03a/'],
    submitted=False, execution_observed=False, completion_observed=False)
state['updated_at_utc'] = now
state['next_action'] = 'Send prepared M4-03A once after verifying empty Claude composer and no in-flight work. Static qualification only; no SQLite or historical trades. Keep ACTIVE15-minute patrol.'
state['last_inspection'] = dict(at_utc=now, state='M4_02B_validated_M4_03A_prepared',
    automation_status='ACTIVE', native_evidence='Fresh native screenshot shows delivery03 final with Stopping here, 36 tests, no M4-03/M5. UIA lags the visible final; composer visibly empty.')
write(state_path, state)
plan_path = BASE/'PLAN.md'
plan = plan_path.read_text('utf-8')
plan = plan.replace('M4-01、M4-02A 已完成技术验收与冻结，当前推进 M4-02B 风险、退出、基准及退市处理的纯合成小步。',
    'M4-01、M4-02A、M4-02B 已完成技术验收与冻结（M4-02B：36项测试、12项独立检查通过），当前准备派发 M4-03A 历史数据资格静态审查；本小步不连接SQLite、不运行历史成交。')
plan_path.write_text(plan, encoding='utf-8')
print(json.dumps(dict(freeze_sha256=sha(freeze_path), freeze_pins=len(freeze['pins']), task_sha256=sha(task_path), prepared=True), ensure_ascii=False))
