"""Assemble two externally evidenced reviewer ledgers after delivery acceptance.

Requires a separately verified Claude normalization receipt. Does not author or
resolve reviews, change labels, choose controls, read SQLite or inspect outcomes.
Full accepted chronology is consumed solely to recompute counting/dependence.
"""
import copy,gzip,hashlib,json,os,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
RUN=ROOT/'claude methods/_m3_20260910/claude_02/runs/dev_run_02'
BUNDLE=HERE/'case_review_bundle_01';OWN=HERE/'individual_review_bound_01'
LABEL=ROOT/'backend/app/research/m3_labels.py';META=HERE/'metadata_index_01/index.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text('utf-8'))
def put(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def pin(p):return {'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size}
def main():
 normalized=Path(sys.argv[1]).resolve(strict=True);expected_sha=sys.argv[2];out=Path(sys.argv[3]).resolve()
 assert normalized.is_relative_to(HERE) and sha(normalized)==expected_sha
 assert out.parent==HERE and not out.exists();out.mkdir()
 denied=[]
 def audit(event,args):
  bad=event=='sqlite3.connect' or event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.startfile','os.exec','os.spawn','os.posix_spawn','os.link','os.symlink'}
  if event=='open':
   p,mode,flags=args;writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
   if writing and not (isinstance(p,(str,os.PathLike)) and Path(p).resolve().is_relative_to(out)):bad=True
  if event in {'os.mkdir','os.remove','os.rmdir'} and not Path(args[0]).resolve().is_relative_to(out):bad=True
  if event=='os.rename' and not all(Path(p).resolve().is_relative_to(out) for p in args[:2]):bad=True
  if bad:denied.append(event);raise PermissionError(event)
 sys.addaudithook(audit);sys.dont_write_bytecode=True
 assert sha(LABEL)=='e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393'
 assert sha(META)=='14f1bad7d393b4e15bf73111a9d96a78c8b156784f9ccbb084d6b606d3a152e9'
 sys.path.insert(0,str(ROOT/'backend'));from app.research import m3_labels as m
 n=read(normalized)
 assert n['accepted'] and n['actual_execution_observed'] and n['completion_observed'] and n['individual_reviews_verified']
 assert len(n['episode_reviews'])==32 and len(n['diagnostic_reviews'])==8 and len(n['control_reviews'])==127
 assert n['reviewer_kind']=='agent' and n['reviewer_id']!='codex-primary-01a086db-m3-03'
 ownmanifest=OWN/'manifest.json';assert sha(ownmanifest)=='82ffd165f955220228560a23e2f6b147d8f5c5fb6b1b437323762b04d3c6d6ba'
 for rel,v in read(ownmanifest)['written'].items():assert sha(OWN/rel)==v['sha256']
 bundlemanifest=BUNDLE/'manifest.json';assert sha(bundlemanifest)=='fa234fded7e448f1d8313ee26f43f1e81902e9294426faf1dc2164747ac887fc'
 for rel,v in read(bundlemanifest)['written'].items():assert sha(BUNDLE/rel)==v['sha256']
 replay=read(HERE/'reader_chronology_source_review_02/result.json');assert replay['passed'] and replay['records_replayed']==17554
 assert sha(HERE/'reader_chronology_source_review_02/result.json')=='a0a0e3013ba3f796385fd2a886d4ce4bf0e737edf376b3072ad015ccda7ca4a1'
 source_manifest=ROOT/'claude methods/_m3_20260910/claude_02/artifact_manifest.json';assert sha(source_manifest)=='4aa337d9840c970700bad7f2566af7e7a84a486ec8180c1b0295664bc0662962'
 index=read(RUN/'chronology_index.json');inv=read(RUN/'inventory.json');meta=read(META);c=inv['calendar']
 calendar=m.SessionCalendar(tuple(x for x in meta['calendar']['sessions'] if c['first']<=x<=c['last']),c['source_ref'],c['available_at'],synthetic=False);assert calendar.record()==c
 records={};envelopes={};inputpins={}
 for symbol,info in index['files'].items():
  p=RUN/'chronology'/(symbol+'.jsonl.gz');assert sha(p)==info['sha256_gzip']==replay['input_files'][str(p)]
  inputpins[str(p)]=sha(p);rows=[json.loads(line) for line in gzip.decompress(p.read_bytes()).decode('utf-8').splitlines()];envelopes[symbol]=rows
  for e in rows:
   r=e['record'];assert not r['review_ledger']['entries'];k=(r['episode_id'],r['record_hash']);assert k not in records;records[k]=r
 def append(raw):
  args={k:v for k,v in raw.items() if k!='entry_hash'};args['evidence_refs']=tuple(args['evidence_refs']);review=m.ReviewRecord(**args)
  assert review.validated()==raw
  key=(raw['case_episode_id'],raw['case_record_hash']);old=records[key];new=m.attach_review(old,review)
  assert m.record_hash(new)==old['record_hash'];records[key]=new
 comparison=[];matches=[];control_collection=[]
 for i in range(1,33):
  cid=f'C{i:03}';d=read(BUNDLE/'cases'/(cid+'.json'));ours=read(OWN/'reviews'/(cid+'.json'));theirs=n['episode_reviews'][cid]
  assert theirs['case_record_hash']==ours['raw_review']['case_record_hash'] and theirs['case_prefix_hash']==ours['case_prefix_hash']
  append(ours['raw_review']);append(theirs)
  for cr in ours['control_reviews']:
   other=n['control_reviews'][cid+'/'+cr['symbol']]
   assert other['case_record_hash']==cr['record_hash'] and isinstance(other['original_control_review']['reviewer_admissible'],bool)
   # Claude authored admissibility/contrast assessments, not a raw control
   # verdict. Preserve these verbatim alongside Codex's actual assessment;
   # do not manufacture a ReviewRecord verdict from an admissibility flag.
   control_collection.append({'case_id':cid,'symbol':cr['symbol'],'case_record_hash':cr['record_hash'],'codex_review':cr,'claude_review':other,'review_collection_separate_from_episode_ledger':True})
  assert isinstance(n['control_set_admissible'][cid],bool) and ours['control_set_admissible'] is True
  if not n['control_set_admissible'][cid]:assert theirs['verdict']!='positive'
  matches.append(d['cutoff_packet']['match'])
  comparison.append({'case_id':cid,'symbol':d['representative_record']['symbol'],'date':d['representative_record']['cutoff']['decision_date'],'codex_verdict':ours['verdict'],'claude_verdict':theirs['verdict'],'agreement':ours['verdict']==theirs['verdict'],'dual_positive':ours['verdict']==theirs['verdict']=='positive','original_reviews_preserved':True,'resolution':'unchanged original judgments; disagreements excluded from positive consensus','control_count':len(d['control_records']),'control_set_admissible_codex':ours['control_set_admissible'],'control_set_admissible_claude':n['control_set_admissible'][cid]})
 diagnostics=[]
 for i in range(1,9):
  cid=f'D{i:03}';ours=read(OWN/'diagnostics'/(cid+'.json'));theirs=n['diagnostic_reviews'][cid]
  assert theirs['case_record_hash']==ours['core_hash']
  # Diagnostics assess a named semantic behavior rather than accumulation
  # episode admission. Preserve both actual reviews in a separate collection;
  # never translate 'diagnostic supported' into a positive episode ledger.
  diagnostics.append({'case_id':cid,'case_record_hash':ours['core_hash'],'codex_review':ours,'claude_review':theirs,'counts_as_positive_episode':False})
 counts=m.library_counts(list(records.values()),matches,calendar)
 expected=sum(x['dual_positive'] for x in comparison);assert counts['qualified_reviewed_positive_episodes']==expected
 assert not counts['target']['met'] and expected<=31 and not counts['target']['training_eligible']
 for symbol,rows in envelopes.items():
  for e in rows:
   old=e['record'];e['record']=records[(old['episode_id'],old['record_hash'])]
  plain=''.join(json.dumps(e,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n' for e in rows).encode('utf-8')
  p=out/'chronology'/(symbol+'.jsonl.gz');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(gzip.compress(plain,mtime=0))
 put(out/'library_counts.json',counts);put(out/'review_comparison.json',comparison);put(out/'matches.json',matches);put(out/'diagnostic_reviews.json',diagnostics);put(out/'control_reviews.json',control_collection)
 for cid in [f'C{i:03}' for i in range(1,33)]+[f'D{i:03}' for i in range(1,9)]:
  d=read(BUNDLE/('cases' if cid[0]=='C' else 'diagnostics')/(cid+'.json'));r=d['representative_record'] if cid[0]=='C' else d['record']
  put(out/'reviewed_representatives'/(cid+'.json'),records[(r['episode_id'],r['record_hash'])])
 for p,digest in inputpins.items():assert sha(Path(p))==digest
 receipt={'passed':True,'at_utc':datetime.now(timezone.utc).isoformat(),'normalized_claude_reviews':pin(normalized),'codex_review_manifest':pin(ownmanifest),'source_delivery_manifest':pin(source_manifest),'all_core_hashes_unchanged':True,'chronology_records':len(records),'actual_agent_reviewers':2,'episode_reviews_per_agent':32,'control_reviews_per_agent':127,'diagnostics_per_agent':8,'dual_positive':expected,'dissent_case_ids':[x['case_id'] for x in comparison if not x['agreement']],'count_target_met':False,'training_eligible':False,'strict_pit':False,'review_only':True,'live_trading_enabled':False,'denied_events':denied,'sqlite_connections':0,'network_requests':0,'input_files':inputpins,'M3_complete':False}
 put(out/'execution.json',receipt);(out/'producer.py').write_bytes(Path(__file__).read_bytes())
 put(out/'manifest.json',{'written':{str(p.relative_to(out)):pin(p) for p in sorted(out.rglob('*')) if p.is_file()},'sources':[pin(normalized),pin(ownmanifest),pin(bundlemanifest),pin(LABEL),pin(META),pin(source_manifest)]})
 print(json.dumps({k:v for k,v in receipt.items() if k!='input_files'},ensure_ascii=False));print('manifest_sha256',sha(out/'manifest.json'))
if __name__=='__main__':main()
