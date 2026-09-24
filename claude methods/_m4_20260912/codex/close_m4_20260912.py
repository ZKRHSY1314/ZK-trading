"""Freeze accepted development replay and close bounded M4 engineering work with unmet research gates."""
import pathlib,json,hashlib,datetime
ROOT=pathlib.Path(__file__).resolve().parents[3]
M4=ROOT/'claude methods/_m4_20260912'
SRC=M4/'claude_03b';REVIEW=M4/'codex/replay_review_02'
FINAL=M4/'codex/final_acceptance_01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def pin(p):return {'sha256':sha(p),'bytes':p.stat().st_size}
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
manifest=read(SRC/'artifact_manifest.json')
assert sha(SRC/'artifact_manifest.json')=='3d557dd4edf805730d99a57e847fbf4450d031b169ac8a543a749fdb03cfff1f'
for group in ('written','consumed'):
 for rel,meta in manifest[group].items():assert sha(ROOT/rel)==meta['sha256'],rel
for name in ('independent_checks.json','export_repair_checks.json'):
 d=read(REVIEW/name);assert d['passed']==d['total'] and all(c['pass']for c in d['checks'])
tests=read(REVIEW/'delivered_tests.json');assert tests['successful']and tests['tests']==17 and not tests['sqlite_connections']
pres=read(REVIEW/'preservation.json');assert pres['ok']and pres['baseline']['production_file_positions']['unchanged']==16
for name,meta in pres['freezes'].items():
 assert sha(M4/name)==meta['sha256']
 for rel,item in read(M4/name)['pins'].items():assert sha(ROOT/rel)==item['sha256'],rel
for rel,meta in pres['candidate_databases'].items():
 p=ROOT/rel;assert sha(p)==meta['sha256']and p.stat().st_size==meta['bytes']and p.stat().st_mtime_ns==meta['mtime_ns']
 assert not any(pathlib.Path(str(p)+x).exists()for x in ('-wal','-shm','-journal'))
paths=[ROOT/p for p in manifest['written']]
paths += [SRC/'artifact_manifest.json',ROOT/'claude methods/M4_03B_CODEX_ACCEPTANCE_20260912.md',M4/'codex/M4_03B_REVIEW_01.md']
paths += [REVIEW/n for n in ('manifest_snapshot.json','hashes.json','preservation.json','delivered_tests.json','independent_checks.json','export_repair_checks.json')]
paths += [M4/'codex'/n for n in ('review_replay_02.py','probe_replay_02.py','verify_export_repair_02.py')]
freeze={'schema':'m4.development_replay_freeze.v1','created_at_utc':now,'verdict':'technically_validated_assumed_development_replay_with_export_revision_02','M4_03B_technical_complete':True,'M4_complete':False,'strict_pit':False,'training_eligible':False,'review_only':True,'live_trading_enabled':False,'M5_started':False,'delivery_manifest_sha256':sha(SRC/'artifact_manifest.json'),'historical_run_id':'829d42809e978c04','export_revision_id':'829d42809e978c04-rev02','original_historical_read_connections':2,'revision_and_Codex_SQL_connections':0,'tests':{'delivered_synthetic':17,'Codex_independent':26,'Codex_export_invariants':30,'all_pass':True},'previous_freezes':{n:{'sha256':v['sha256'],'pins':v['pins_total']}for n,v in pres['freezes'].items()},'pins':{p.relative_to(ROOT).as_posix():pin(p)for p in paths}}
assert not (M4/'development_replay_freeze.json').exists();dump(M4/'development_replay_freeze.json',freeze)
FINAL.mkdir(exist_ok=False)
report=ROOT/'claude methods/M4_FINAL_ACCEPTANCE_20260912.md'
requirements=[
 {'id':'M4-R1','requirement':'decision_timestamp_availability','engineering_evidence':'validated_causal_mapping_and_future_refusals','historical_status':'unmet_actual_historical_availability'},
 {'id':'M4-R2','requirement':'next_legal_execution_point','engineering_evidence':'validated_injected_calendar_T1_and_monotone_global_clock','historical_status':'conditional_on_model_calendar_and_timing'},
 {'id':'M4-R3','requirement':'execution_constraints_fees_liquidity_rejections','engineering_evidence':'validated_explicit_contract_and_ledger_arithmetic','historical_status':'unmet_sourced_ST_bands_fees_phase_capacity'},
 {'id':'M4-R4','requirement':'deterministic_risk_exit_cooldown','engineering_evidence':'validated_synthetic_and_fixed_assumed_replay','historical_status':'conditional_replay_not_strategy_validation'},
 {'id':'M4-R5','requirement':'benchmark_delisting_no_survivorship_leakage','engineering_evidence':'validated_synthetic_benchmark_and_unknown_terminal_handling','historical_status':'unmet_survivor_pool_and_incomplete_actions_delisting'},
 {'id':'M4-R6','requirement':'nonzero_simple_baseline_on_fixture_and_eligible_history','engineering_evidence':'validated_nonzero_fixture_and_assumed_history','historical_status':'unmet_eligible_historical_nonzero_baseline'}]
dump(FINAL/'requirements.json',{'source':'claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md','requirements':requirements,'original_acceptance_all_met':False})
completion={'schema':'m4.technical_closure.v1','closed_at_utc':now,'status':'technically_closed_evidence_target_not_met','M4_technical_complete':True,'M4_complete':False,'research_target_met':False,'complete_semantics':'Bounded engineering implementation, independent acceptance, documented corrections and requirement reconciliation finished. Original historical-evidence acceptance remains unmet.','all_required_bounded_checks_passed':True,'M4_03B_delivery':'delivery_02','M4_03B_checks':freeze['tests'],'M3_complete':False,'M3_dual_positive_episodes':0,'M3_target':50,'M3_disputed_episodes':32,'strict_pit':False,'training_eligible':False,'review_only':True,'live_trading_enabled':False,'M5_started':False,'production_sqlite_connections':0,'Codex_SQL_connections_during_M4_03B_acceptance':0,'original_Claude_historical_connections':2,'Claude_revision_SQL_connections':0,'holdout_price_rows_read':0,'production_service_integration':False,'user_accepted':False,'report':report.relative_to(ROOT).as_posix(),'report_sha256':sha(report),'requirements_receipt_sha256':sha(FINAL/'requirements.json'),'freezes':{n:pin(M4/n)for n in ['execution_freeze.json','portfolio_freeze.json','risk_freeze.json','historical_qualification_freeze.json','development_replay_freeze.json']},'baseline':{'tracked_preserved':316,'historical_immutable_preserved':42,'production_file_positions_preserved':16},'automation_exit_authorized_after_this_receipt':True,'next_step':'No M5 or training. A new bounded evidence-qualification task requires user direction; no automatic data reads or assumption changes.'}
dump(FINAL/'completion.json',completion)
# Verify durable closure and all newly frozen evidence before requesting automation pause.
assert sha(report)==read(FINAL/'completion.json')['report_sha256']
for rel,item in freeze['pins'].items():assert sha(ROOT/rel)==item['sha256'],rel
dump(FINAL/'closure_verification.json',{'at_utc':now,'report_verified':True,'requirements_count':6,'freeze_pins_verified':len(freeze['pins']),'completion_sha256':sha(FINAL/'completion.json'),'M4_complete':False,'technical_complete':True,'sqlite_connections':0})
s=read(M4/'coordination_state.json')
s['current_task'].update({'status':'validated','completion_observed':True,'latest_delivery_completion_observed':True,'runtime_ui_running_observed':False,'unresolved_issue_categories':0,'technical_complete':True,'acceptance_file':'claude methods/M4_03B_CODEX_ACCEPTANCE_20260912.md','latest_delivery_manifest_sha256':sha(SRC/'artifact_manifest.json')})
s.update({'status':completion['status'],'M4_complete':False,'M4_technical_complete':True,'updated_at_utc':now,'final_acceptance_file':completion['report'],'final_completion_receipt':(FINAL/'completion.json').relative_to(ROOT).as_posix(),'next_action':'Bounded M4 engineering technically closed; original historical evidence target unmet. Final report/receipt/five freezes verified. Pause existing patrol as authorized, then await user direction; do not start M5/training or read more data.','next_inspection_due_utc':None})
s['last_inspection']={'at_utc':now,'state':'M4_technical_closure_verified','completion_observed':True,'M4_complete':False,'M4_technical_complete':True,'checks':'17 synthetic +26 independent +30 export invariant checks passed; durable final report/receipt verified.','automation_status':'pause_pending'}
dump(M4/'coordination_state.json',s)
plan=M4/'PLAN.md';text=plan.read_text(encoding='utf-8');lines=text.splitlines();lines[2]='状态：M4-01、M4-02A、M4-02B、M4-03A、M4-03B全部完成限定工程技术验收，五份冻结已保存。原始M4研究验收仍因历史可用性、幸存者偏差与合格历史非零基线证据不足而未达标；M4_technical_complete=true，M4_complete=false。最终报告与机器回执已验证，按既定结束条件暂停巡检；不启动M5/训练。';plan.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'status':completion['status'],'M4_complete':False,'freeze_pins':len(freeze['pins']),'completion_sha256':sha(FINAL/'completion.json'),'report_sha256':sha(report),'next':'pause existing automation after durable receipt'},ensure_ascii=False))
