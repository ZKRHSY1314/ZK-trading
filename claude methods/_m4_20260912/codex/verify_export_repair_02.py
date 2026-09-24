"""Codex: verify repair against delivery01 snapshots, no SQL or historical replay."""
import pathlib,json,gzip,copy,hashlib,importlib.util,sys
ROOT=pathlib.Path(__file__).resolve().parents[3]
SRC=ROOT/'claude methods/_m4_20260912/claude_03b'
OUT=ROOT/'claude methods/_m4_20260912/codex/replay_review_02'
ORIG=ROOT/'claude methods/_m4_20260912/codex/replay_review_01/delivery_snapshot/runs/829d42809e978c04'
REV=SRC/'runs/829d42809e978c04-rev02'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def can(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def read(p):
 with gzip.open(p,'rt',encoding='utf-8')as f:return[json.loads(x)for x in f]
g=load('m4_03b_guard',SRC/'guard.py');g.ALLOWED_WRITE_ROOT=OUT.resolve();g.install()
repair=load('codex_repair_02',SRC/'repair_export_revision_02.py')
checks=[]
def ck(n,ok,**d):checks.append({'name':n,'pass':bool(ok),**d})
oldfiles=[p for p in ORIG.rglob('*')if p.is_file()]
ck('original_run_unchanged_against_Codex_delivery01_snapshot',all(sha(p)==sha(SRC/'runs/829d42809e978c04'/p.relative_to(ORIG))for p in oldfiles),files=len(oldfiles))
for b in sorted((ORIG/'branches').iterdir()):
 old=read(b/'research_records.jsonl.gz');new=read(REV/'branches'/b.name/'research_records.jsonl.gz')
 ck(b.name+':every_nested_engine_record_unchanged',len(old)==len(new)and all(can(x['engine_record'])==can(y['engine_record'])for x,y in zip(old,new)),records=len(old))
 ck(b.name+':only_performance_wrapper_changed',[i for i,(x,y)in enumerate(zip(old,new))if can(x)!=can(y)]==[len(old)-1]and old[-1]['kind']=='performance')
 ck(b.name+':ledger_file_byte_identical',sha(b/'ledger_records.jsonl.gz')==sha(REV/'branches'/b.name/'ledger_records.jsonl.gz'))
 a,deriv=repair.repair_records(copy.deepcopy(old),b.name);c,_=repair.repair_records(copy.deepcopy(old),b.name)
 ck(b.name+':export_transform_twice_equals_delivery',can(a)==can(c)==can(new))
 first=next(r for r in old if r['kind']=='decision'and r['session']=='2023-09-04')
 last=next(r for r in old if r['kind']=='decision'and r['session']=='2025-03-31')
 provenance_ok=True
 for d,role in [(first,'benchmark_start_level'),(last,'benchmark_end_level')]:
  source=next(p for p in d['raw_provenance']if p.get('role')=='benchmark_level')
  target=next(p for p in new[-1]['raw_provenance']if p.get('role')==role)
  provenance_ok &= {k:v for k,v in source.items()if k!='role'}=={k:v for k,v in target.items()if k!='role'}
 ck(b.name+':endpoint_source_exactly_matches_original_decisions',provenance_ok)
 for typ in ('missing','conflicting'):
  bad=copy.deepcopy(old);d=next(r for r in bad if r['kind']=='decision'and r['session']=='2023-09-04')
  if typ=='missing':d['raw_provenance']=[p for p in d['raw_provenance']if p.get('role')!='benchmark_level']
  else:
   ep=copy.deepcopy(next(p for p in d['raw_provenance']if p.get('role')=='benchmark_level'));ep['point_index']+=1;d['raw_provenance'].append(ep)
  try:repair.repair_records(bad,b.name);rejected=False
  except repair.RepairFailure:rejected=True
  ck(b.name+':'+typ+'_source_fails_closed',rejected)
ck('zero_SQL_connections_and_unexpected_guard_denials',not g.CONNECTIONS and not g.DENIAL_LOG)
(OUT/'export_repair_checks.json').write_text(json.dumps({'checks':checks,'passed':sum(c['pass']for c in checks),'total':len(checks)},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({'passed':sum(c['pass']for c in checks),'total':len(checks),'failed':[c for c in checks if not c['pass']]}))
