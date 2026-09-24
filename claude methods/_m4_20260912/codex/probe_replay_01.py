"""No SQL/network; independent arithmetic, chronology, provenance and synthetic probes."""
import pathlib,json,gzip,hashlib,sys,importlib.util,unittest,io
from decimal import Decimal as D, ROUND_HALF_UP
from collections import defaultdict,Counter,deque
ROOT=pathlib.Path(__file__).resolve().parents[3]
SRC=ROOT/'claude methods/_m4_20260912/claude_03b'
OUT=ROOT/'claude methods/_m4_20260912/codex/replay_review_01'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
def dump(n,v): (OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
g=load('m4_03b_guard',SRC/'guard.py');g.ALLOWED_WRITE_ROOT=OUT.resolve();g.install()
t=load('codex_03b_test',SRC/'test_replay_synthetic.py')
stream=io.StringIO();z=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(t))
dump('delivered_tests.json',{'tests':z.testsRun,'failures':len(z.failures),'errors':len(z.errors),'successful':z.wasSuccessful(),'output':stream.getvalue(),'sqlite_connections':g.CONNECTIONS,'guard_denials':g.DENIAL_LOG})
checks=[]
def check(n,ok,**v): checks.append({'name':n,'pass':bool(ok),**v})
# A no-trade synthetic run with a caller-specified balance has an exactly known return: zero.
S=t.sessions_from((2024,1,2),26)
snap=t.core.synthetic_snapshot(S,{'SYN000001':t.flat_then_cross(S,99)})
r=t.core.Replay(t.MODS,snap,'assumed_full_fill',initial_cash='100000.00',synthetic=True,decision_sessions=(S[0],S[-2])).run()
check('custom_initial_cash_zero_trade_return',D(r['performance']['return'])==0,expected='0',actual=r['performance']['return'],equity=r['performance']['equity'],initial_cash='100000.00')
manifest=json.loads((SRC/'artifact_manifest.json').read_text(encoding='utf-8'))
run=ROOT/manifest['run']['run_dir']
def cent(x): return x.quantize(D('.01'),rounding=ROUND_HALF_UP)
for b in sorted((run/'branches').iterdir()):
 with gzip.open(b/'research_records.jsonl.gz','rt',encoding='utf-8')as f: recs=[json.loads(x)for x in f]
 with gzip.open(b/'ledger_records.jsonl.gz','rt',encoding='utf-8')as f: led=[json.loads(x)for x in f]
 summary=json.loads((b/'summary.json').read_text(encoding='utf-8'))
 cash=D('1000000');positions=Counter();lots=defaultdict(deque);realized=D(0);errors=[];fills=Counter();capacities={}
 for e in led:
  fx=e.get('effects')or{}
  if fx.get('filled_quantity',0):
   q=fx['filled_quantity'];symbol=fx['symbol'];side=fx['side'];price=D(fx['fill_price']);gross=cent(q*price)
   fees=cent(max(D(6),gross*D('.0004')))+cent(gross*D('.00002'))+(cent(gross*D('.0008'))if side=='sell'else D(0))
   if gross!=D(fx['gross_amount'])or fees!=D(fx['fees']['total']):errors.append(['fee',e['event_id']])
   if D(fx['cash_before'])!=cash:errors.append(['cash_before',e['event_id']])
   if side=='buy':
    cash-=gross+fees;positions[symbol]+=q;lots[symbol].append([q,gross+fees,e['identity']['executed_at'][:10]])
   else:
    cash+=gross-fees;positions[symbol]-=q;remaining=q;cost=D(0)
    while remaining:
     lot=lots[symbol][0];take=min(lot[0],remaining)
     part=lot[1]if take==lot[0]else cent(lot[1]*D(take)/D(lot[0]))
     if lot[2]>=e['identity']['executed_at'][:10]:errors.append(['T+1',e['event_id']])
     lot[0]-=take;lot[1]-=part;cost+=part;remaining-=take
     if not lot[0]:lots[symbol].popleft()
    realized+=gross-fees-cost
   if cash!=D(fx['cash_after']):errors.append(['cash_after',e['event_id']])
   fills[side]+=1
   cap=fx.get('capacity')
   if cap:
    cid=cap['capacity_id'];old=capacities.get(cid,{'budget':cap['budget'],'consumed':D(0)})
    if old['budget']!=cap['budget']:errors.append(['capacity_budget_changed',cid])
    old['consumed']+=q;capacities[cid]=old
    if old['consumed']>D(old['budget']):errors.append(['capacity_exceeded',cid])
  state=e.get('state_after')or{}
  if state and (D(state['cash'])!=cash or {s:q for s,q in positions.items()if q}!=state['positions']or D(state['realized_pnl_total'])!=realized):errors.append(['state_after',e['event_id']])
 perf=summary['performance'];marked=sum(D(v['mark'])*v['quantity'] for v in perf.get('positions',{}).values())
 check(b.name+':independent_cash_FIFO_fees_T1_capacity',not errors and cash==D(perf['cash'])and realized==D(perf['realized_pnl_total'])and cash+marked==D(perf['equity']),errors=errors[:10],cash=cash,realized=realized,equity=cash+marked,fills=dict(fills))
 clocks=[];events=[];order_errors=[]
 for r in recs:
  if r['kind']=='performance':continue
  er=r['engine_record'];clocks.append(er['state_summary']['event_clock']);events.append((r['session'],0 if r['kind']=='attempt'else 1,0 if r.get('side')=='sell'else 1,er.get('intent_id','').split(':')[-1],er.get('intent_id','')))
  if r['kind']=='attempt':
   for p in r['raw_provenance']:
    if p['role'] in ('other_held_mark','band_reference_previous_close')and p['trade_date']>=r['session']:order_errors.append(p)
 check(b.name+':global_open_before_close_prior_marks',clocks==sorted(clocks)and events==sorted(events)and not order_errors,records=len(recs))
 st=summary['funnel']['decision_stage'];check(b.name+':mutually_exclusive_funnel',sum(st.get(k,0)for k in ['not_listed','halt_key','missing_unconfirmed_row','price_row'])==50*378 and sum(st.get(k,0)for k in ['new_listing_exclusion','insufficient_history','no_signal','signal'])==st['price_row'])
 check(b.name+':raw_and_assumed_grade',all(r['grade']==('raw'if b.name=='raw'else'assumed')and r['adjustment_uncertainty'] for r in recs))
 pw=recs[-1];keys={(p['symbol'],p['trade_date'])for p in pw['raw_provenance']};expected={('SH000300','2023-09-04'),('SH000300','2025-03-31')}
 check(b.name+':performance_benchmark_structured_provenance',expected<=keys,missing=sorted(expected-keys))
 # Rebuild the published deterministic output hash from exported content, without invoking producer output_hash.
 body={'records':recs,'ledger_records':led,'funnel':summary['funnel'],'performance':perf,'censored':summary['censored'],'ledger_state_hash':summary['ledger_state_hash'],'engine_chain_hash':summary['engine_chain_hash']}
 h=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False,default=str).encode()).hexdigest()
 check(b.name+':export_output_hash',h==summary['output_hash'],actual=h)
check('zero_SQL_connections',not g.CONNECTIONS and not g.DENIAL_LOG)
dump('independent_checks.json',{'checks':checks,'passed':sum(c['pass']for c in checks),'total':len(checks),'sql_connections':0})
print(json.dumps({'tests':z.testsRun,'successful':z.wasSuccessful(),'passed':sum(c['pass']for c in checks),'total':len(checks),'failed':[c for c in checks if not c['pass']]},ensure_ascii=False))
