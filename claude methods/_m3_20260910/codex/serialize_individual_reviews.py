"""Bind already authored agent judgments; no case verdict selection or replay."""
import json,hashlib,sys,shutil
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=Path(__file__).resolve().parent
INPUT=BASE/'case_review_bundle_01';NOTES=BASE/'individual_review_01';OUT=BASE/'individual_review_bound_01'
assert not OUT.exists();OUT.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text('utf-8'))
def put(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def pin(p):return {'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size}
module=ROOT/'backend/app/research/m3_labels.py'
assert sha(module)=='e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393'
sys.path.insert(0,str(ROOT/'backend'))
from app.research import m3_labels as m
manifest=read(INPUT/'manifest.json');assert sha(INPUT/'manifest.json')=='fa234fded7e448f1d8313ee26f43f1e81902e9294426faf1dc2164747ac887fc'
for rel,v in manifest['written'].items():assert sha(INPUT/rel)==v['sha256']
authors={};author_sources={}
for p in sorted(NOTES.glob('authored_*.json')):
 for cid,v in read(p).items():
  assert cid not in authors;authors[cid]=v;author_sources[cid]=p
assert set(authors)=={f'C{i:03}' for i in range(1,33)}|{f'D{i:03}' for i in range(1,9)}
events=[json.loads(s) for s in (NOTES/'display_events.jsonl').read_text('utf-8').splitlines()];display={e['case_id']:e for e in events}
assert len(display)==40
execution={'schema':'m3.actual_agent_review_execution.v1','reviewer_id':'codex-primary-01a086db-m3-03','reviewer_kind':'agent','task_id':'01a086db-3c02-7a21-bf22-26e4f73e24b0','recorded_at_utc':datetime.now(timezone.utc).isoformat(),'method':pin(NOTES/'REVIEW_METHOD.md'),'display_events':pin(NOTES/'display_events.jsonl'),'independence':'Own judgments authored after input display, before opening Claude03 opinions; same evidence does not imply independent statistical ground truth.','input_bundle_manifest':pin(INPUT/'manifest.json'),'case_executions':{},'other_reviewer_opinions_read':False,'verdicts_generated_by_serializer':False}
for cid in sorted(authors):
 p=author_sources[cid];t=datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat();assert datetime.fromisoformat(t)>=datetime.fromisoformat(display[cid]['at_utc'])
 execution['case_executions'][cid]={'authored_judgment':pin(p),'authored_persisted_at_utc':t,'input_display':display[cid],'input':pin(INPUT/('cases' if cid[0]=='C' else 'diagnostics')/(cid+'.json')),'evidence_extraction':pin(NOTES/(cid+'_evidence.json'))}
put(OUT/'execution.json',execution)
checks=[];count=Counter();control_uses=0
for cid,note in sorted(authors.items()):
 rel=('cases' if cid[0]=='C' else 'diagnostics')+'/'+cid+'.json';d=read(INPUT/rel);r=d['representative_record'] if cid[0]=='C' else d['record'];m.verify_record(r)
 ex=execution['case_executions'][cid];proof=d['cutoff_packet']['prefix_proof'] if cid[0]=='C' else None
 assert note['verdict'] in m.VERDICTS and len(note['support'])>100 and len(note['counter'])>100
 refs=[str((INPUT/rel).relative_to(ROOT))+' sha256='+sha(INPUT/rel),str(author_sources[cid].relative_to(ROOT))+' sha256='+sha(author_sources[cid]),str((NOTES/'REVIEW_METHOD.md').relative_to(ROOT))+' sha256='+sha(NOTES/'REVIEW_METHOD.md')]
 er=str((OUT/'execution.json').relative_to(ROOT))+' sha256='+sha(OUT/'execution.json')+'#'+cid
 rv=m.ReviewRecord(reviewer_id=execution['reviewer_id'],reviewer_kind='agent',reviewed_at=ex['authored_persisted_at_utc'],verdict=note['verdict'],evidence_refs=tuple(refs),execution_ref=er,case_episode_id=r['episode_id'],case_record_hash=r['record_hash'],case_policy_hash=r['policy_hash'],case_prefix_hash=proof['prefix_hash'] if proof else None,synthetic=False,notes=note['support']+' Counterevidence: '+note['counter'])
 bound=m.attach_review(r,rv)
 item={'schema':'m3.actual_individual_review.v1','case_id':cid,'input':pin(INPUT/rel),'core_hash':r['record_hash'],'policy_hash':r['policy_hash'],'case_prefix_hash':proof['prefix_hash'] if proof else None,'cutoff_packet_hash':d['cutoff_packet']['cutoff_packet_hash'] if proof else None,'reviewer_id':execution['reviewer_id'],'reviewer_kind':'agent','reviewed_at':rv.reviewed_at,'verdict':note['verdict'],'supporting_evidence':note['support'],'contradicting_evidence':note['counter'],'execution_ref':er,'raw_review':rv.validated(),'control_reviews':[],'control_set_admissible':True if proof else None,'counts_as_episode':bool(proof),'review_only':True,'strict_pit':False,'training_eligible':False,'live_trading_enabled':False}
 if proof:
  assert proof['member_record_hashes']==[x['record_hash'] for x in d['prefix_records']]
  assert set(note['controls'])=={c['symbol'] for c in d['control_records']}
  for c in d['control_records']:
   m.verify_record(c);assert c['current_state']=='observed' and c['cutoff']==r['cutoff'] and c['labels']['selection']['label']=='non_candidate'
   assert c['labels']['liquidity']['band']==r['labels']['liquidity']['band'] and c['labels']['regime']['regime']==r['labels']['regime']['regime']
   assert c['policy_hash']==r['policy_hash'] and c['role']=='stock' and not c['synthetic'] and c['universe']['in_frozen_universe']
   assert len(note['controls'][c['symbol']])>50
   cr=m.ReviewRecord(reviewer_id=execution['reviewer_id'],reviewer_kind='agent',reviewed_at=rv.reviewed_at,verdict='negative',evidence_refs=tuple(refs),execution_ref=er+'/control/'+c['symbol'],case_episode_id=c['episode_id'],case_record_hash=c['record_hash'],case_policy_hash=c['policy_hash'],synthetic=False,notes=note['controls'][c['symbol']]+' Negative denotes corroborated non-candidate selection, not forecasted loss. Common retrospective/adjustment/ST/coverage and coarse matching limitations apply per REVIEW_METHOD.md.')
   item['control_reviews'].append({'symbol':c['symbol'],'decision_date':c['cutoff']['decision_date'],'record_hash':c['record_hash'],'formal_match_admissible':True,'assessment':note['controls'][c['symbol']],'raw_review':cr.validated()})
   m.attach_review(c,cr);control_uses+=1
  count[note['verdict']]+=1
 else:item['diagnostic_supported']=note['diagnostic_supported']
 put(OUT/('reviews' if proof else 'diagnostics')/(cid+'.json'),item)
 put(OUT/'single_review_cores'/(cid+'.json'),bound)
 checks.append({'case_id':cid,'input_preserved':sha(INPUT/rel)==manifest['written'][rel]['sha256'],'core_unchanged':m.record_hash(bound)==r['record_hash'],'entry_hash':rv.validated()['entry_hash'],'agent_judgment_authored_before_serialization':True})
assert control_uses==127 and count=={'positive':31,'ambiguous':1}
receipt={'passed':True,'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'episode_reviews':32,'diagnostic_reviews':8,'individual_control_reviews':127,'episode_verdicts':dict(count),'actual_reviewer_executions':1,'dual_reviewed_positive_episodes':0,'source_manifest':pin(INPUT/'manifest.json'),'execution_receipt':pin(OUT/'execution.json'),'checks':checks,'no_sqlite_or_network_used':True,'M3_complete':False}
put(OUT/'validation.json',receipt)
shutil.copyfile(__file__,OUT/'serializer.py')
for p in sorted(NOTES.glob('authored_*.json')):shutil.copyfile(p,OUT/p.name)
shutil.copyfile(NOTES/'REVIEW_METHOD.md',OUT/'REVIEW_METHOD.md')
put(OUT/'manifest.json',{'written':{str(p.relative_to(OUT)):pin(p) for p in sorted(OUT.rglob('*')) if p.is_file()},'sources':[pin(module),pin(INPUT/'manifest.json'),pin(BASE/'m3_03_dispatch_receipt.json')],'actual_review':True,'reviewer_kind':'agent','live_trading_enabled':False})
print(json.dumps({k:v for k,v in receipt.items() if k!='checks'}));print('manifest_sha256',sha(OUT/'manifest.json'))
