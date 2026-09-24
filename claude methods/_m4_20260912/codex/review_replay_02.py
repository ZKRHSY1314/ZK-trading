"""Codex independent M4-03B acceptance: byte verification and exported evidence only; no SQLite."""
import pathlib, json, hashlib, importlib.util, sys, gzip, shutil
ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / 'claude methods/_m4_20260912/claude_03b'
OUT = ROOT / 'claude methods/_m4_20260912/codex/replay_review_02'
OUT.mkdir(exist_ok=False)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,v): (OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
manifest=json.loads((SRC/'artifact_manifest.json').read_text(encoding='utf-8'))
dump('manifest_snapshot.json',manifest)
checks={}
for group in ('written','consumed'):
 checks[group]={}
 for rel,meta in manifest[group].items():
  p=ROOT/rel
  checks[group][rel]={'actual':sha(p),'expected':meta['sha256'],'matches':sha(p)==meta['sha256']}
  if group=='written':
   q=OUT/'delivery_snapshot'/p.relative_to(SRC);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
dump('hashes.json',checks)
v=load('codex_verify_03b',SRC/'verify_baseline.py').verify('codex_review_01')
dump('preservation.json',v)
print(json.dumps({'manifest_sha256':sha(SRC/'artifact_manifest.json'),'groups':{g:{'total':len(d),'matches':sum(x['matches'] for x in d.values())}for g,d in checks.items()},'baseline_ok':v['ok'],'production_preserved':v['baseline']['production_file_positions']['unchanged'],'problems':v['problems']},ensure_ascii=False))
run=ROOT/manifest['run']['run_dir']
for b in sorted((run/'branches').iterdir()):
 with gzip.open(b/'research_records.jsonl.gz','rt',encoding='utf-8') as f: recs=[json.loads(s) for s in f]
 with gzip.open(b/'ledger_records.jsonl.gz','rt',encoding='utf-8') as f: led=[json.loads(s) for s in f]
 summary=json.loads((b/'summary.json').read_text(encoding='utf-8'))
 dump(b.name+'_structure.json',{'first_decision':recs[0],'first_attempt':next((r for r in recs if r['kind']=='attempt'),None),'performance_wrapper':recs[-1],'first_ledger':led[0]if led else None,'ledger_snapshot_keys':list(summary['ledger_snapshot']),'ledger_reconcile_keys':list(summary['ledger_reconcile'])})
 print(b.name,len(recs),len(led),summary['performance']['cash'],summary['performance'].get('equity'))
