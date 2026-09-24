"""Display bound evidence for actual agent review; never generate a verdict."""
import json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent
BUNDLE=BASE/'case_review_bundle_01'
OUT=BASE/'individual_review_01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((BUNDLE/'manifest.json').read_text('utf-8'))
assert sha(BUNDLE/'manifest.json')=='fa234fded7e448f1d8313ee26f43f1e81902e9294426faf1dc2164747ac887fc'
def load(rel):
 p=BUNDLE/rel;assert sha(p)==manifest['written'][rel]['sha256'];return json.loads(p.read_text('utf-8'))
def metric(r):
 f=r['features'];l=r['labels'];sv=r['session_view']
 return {'symbol':r['symbol'],'date':r['cutoff']['decision_date'],'core':r['record_hash'],'features':f,'phase':l['phase'],'selection':l['selection'],'entry':l['entry'],'limit':l['limit'],'liquidity':l['liquidity'],'regime':l['regime'],'quality':r['data_quality'],'session_view':sv,'security_context':r['security_context'],'stock_range':[r['provenance']['source_refs'][0],r['input_availability']['max_trade_date_consumed']],'stock_bars':r['input_availability']['rows_consumed'],'benchmark_last':r['benchmark_availability']['max_trade_date_consumed'],'coverage':r['identity']['decision_inputs']['coverage'],'pit':r['pit'],'position_event':l['position_event']}
def compact(r):
 f=r['features'];l=r['labels'];sv=r['session_view'];ctx=r['security_context']
 return {'s':r['symbol'],'d':r['cutoff']['decision_date'],'phase':l['phase']['label'],'select':l['selection'],'position':f['position_250'],'spread':f['ma_spread_20_60'],'r120':f['return_120'],'r20':f['return_20'],'r60':f['return_60'],'vr':f['volume_ratio_20'],'drawdown':f['drawdown_from_lookback_high'],'markup_prior':l['phase']['markup_within_lookback'],'close':f['close'],'ma20':f['ma20'],'cth':f['close_to_high'],'amount_m':f['amount_20_mean_cny']/1e6 if f['amount_20_mean_cny'] is not None else None,'band':l['liquidity']['band'],'regime':l['regime']['regime'],'bars':f['bars_available'],'entry':l['entry']['label'],'entry_reasons':l['entry']['reasons'],'quality':r['data_quality'],'state':r['current_state'],'susp':sv['suspensions_in_window'],'missing':sv['interior_missing_sessions'],'limit':l['limit'],'ca':ctx['corporate_action_status'],'listing':ctx['listing_date'],'bench_r60':l['regime'].get('benchmark_return_60'),'coverage':r['identity']['decision_inputs']['coverage']}
ids=sys.argv[1:]
OUT.mkdir(exist_ok=True)
for cid in ids:
 rel=('cases/' if cid.startswith('C') else 'diagnostics/')+cid+'.json';d=load(rel)
 if cid.startswith('C'):
  full={'case_id':cid,'input_sha256':sha(BUNDLE/rel),'prefix':d['cutoff_packet']['prefix_proof'],'prefix_records':[metric(r) for r in d['prefix_records']],'representative':metric(d['representative_record']),'controls':[metric(r) for r in d['control_records']]}
  view={'case_id':cid,'prefix':[{'d':r['cutoff']['decision_date'],'phase':r['labels']['phase']['label'],'selection':r['labels']['selection']['label'],'pos':r['features']['position_250'],'spread':r['features']['ma_spread_20_60'],'r120':r['features']['return_120'],'quality':r['data_quality']} for r in d['prefix_records']],'representative':compact(d['representative_record']),'controls':[compact(r) for r in d['control_records']]}
 else:
  r=d['record'];full={'case_id':cid,'input_sha256':sha(BUNDLE/rel),'record':metric(r)};view={'case_id':cid,'record':compact(r),'extra':{k:v for k,v in r.items() if k in ['session_view','input_availability','labels']}}
 # Full evidence extraction retains all selected fields; CLI formatting rounds
 # floats for readability only. Original bound cores remain exact and immutable.
 dest=OUT/(cid+'_evidence.json');assert not dest.exists();dest.write_text(json.dumps(full,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def rounded(v):
  if isinstance(v,float):return round(v,6)
  if isinstance(v,dict):return {k:rounded(x) for k,x in v.items()}
  if isinstance(v,list):return [rounded(x) for x in v]
  return v
 print(json.dumps(rounded(view),ensure_ascii=False))
 with (OUT/'display_events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'at_utc':datetime.now(timezone.utc).isoformat(),'case_id':cid,'input_sha256':sha(BUNDLE/rel),'extracted_evidence_sha256':sha(dest),'event':'evidence_displayed_for_agent_review','verdict_generated':False})+'\n')
