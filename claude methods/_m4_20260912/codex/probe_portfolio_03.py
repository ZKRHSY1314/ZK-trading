"""Independent working-draft adversarial cases; all inputs synthetic; no app imports."""
from pathlib import Path
import sys, json, hashlib, importlib.util
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, localcontext, ROUND_DOWN
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent/'portfolio_review_03'
OUT.mkdir(exist_ok=True)
sources={}
for rel in ['backend/app/research/m4_execution.py','backend/app/research/m4_portfolio.py']:
    raw=(ROOT/rel).read_bytes(); sources[rel]=hashlib.sha256(raw).hexdigest()
    dest=OUT/Path(rel).name
    if dest.exists() and dest.read_bytes()!=raw: raise RuntimeError('Refuse to overwrite changed source snapshot')
    dest.write_bytes(raw)
denials=[]
def guard(event,args):
    deny=event.startswith(('sqlite3.','socket.','subprocess.')) or event in {'os.system','os.exec','os.posix_spawn','os.remove','os.rename','os.rmdir','os.mkdir'}
    if event=='open':
        p,mode,flags=args
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (1|2|64|512|1024)):
            deny=not isinstance(p,(str,bytes)) or not Path(p).resolve().is_relative_to(OUT.resolve())
    if deny:
        denials.append(event);raise RuntimeError('Guard denied '+event)
sys.addaudithook(guard)
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec)
    sys.modules[name]=obj;spec.loader.exec_module(obj);return obj
m=load('codex_portfolio_kernel',OUT/'m4_execution.py')
p=load('codex_portfolio_subject',OUT/'m4_portfolio.py')
# Reuse Codex's pre-existing independent synthetic kernel fixture, not Claude test helpers.
old=(Path(__file__).resolve().parent/'probe_m4_working_01.py').read_text('utf-8')
exec(compile(old[old.index("S = 'SYN_CODEX_01'"):old.index('cases = []')],'<Codex synthetic fixture>','exec'))
def ledger(lots=()):
    return p.PortfolioLedger(m,ledger_id='SYN-CODEX-L',account_ref='SYN_CODEX_ACCOUNT',initial_cash='10000.00',initial_lots=lots)
def event(L,seq,r):
    return p.AttemptEvent('E'+str(seq),seq,replace(r,account=L.account_state(r.attempt.executed_at, r.order.symbol)))
def snap(L):return json.loads(json.dumps(L.snapshot()))
def economic(s):return {k:v for k,v in s.items() if k!='records'}
cases=[]
def add(name,expected,passed,**actual):cases.append(dict(name=name,expected=expected,passed=bool(passed),actual=actual))
# 1: Normal round-trip positive control.
L=ledger();buy=L.apply(event(L,1,req))
T2='2024-03-20T09:30:00+08:00'
sell=replace(req,decision=replace(req.decision,decision_id='D-S',side='sell',decision_session=sessions[1],decided_at='2024-03-19T16:00:00+08:00'),order=replace(req.order,order_id='O-S',decision_id='D-S',side='sell',limit_price='11.00',submitted_at='2024-03-20T09:00:00+08:00',eligible_from=T2),price=replace(req.price,price='11.00',observed_at=T2,available_at=T2),tradability=replace(req.tradability,session=sessions[2],observed_at=T2,available_at=T2),capacity=replace(req.capacity,capacity_id='C-S',observed_at=T2,available_at=T2),attempt=replace(req.attempt,attempt_id='A-S',session=sessions[2],executed_at=T2))
r=L.apply(event(L,2,sell)); s=L.snapshot()
add('positive_round_trip','Cash10089.43, PnL89.43, no position',s['cash']=='10089.43' and s['realized_pnl_total']=='89.43' and not s['positions'],record=r,snapshot=s,reconcile=L.reconcile())
# 2: Another symbol's settled shares cannot legalize same-session target shares.
lots=(p.InitialLot(S,100,sessions[1],'1000.00','syn:today-target'),p.InitialLot('SYN_OTHER',100,sessions[0],'1000.00','syn:old-other'))
L=ledger(lots);ss=replace(req,decision=replace(req.decision,side='sell'),order=replace(req.order,side='sell'))
before=snap(L);r=L.apply(event(L,1,ss));after=snap(L)
add('cross_symbol_t1','Target same-session shares remain unsold despite other settled symbol',r['status']!='applied' and after['positions'].get(S)==100 and after['cash']==before['cash'],record=r,before=before,after=after)
# 3: No target shares; kernel's wrongly pooled inventory must not cause partial commits.
L=ledger((p.InitialLot('SYN_OTHER',100,sessions[0],'1000.00','syn:old-other'),))
before=snap(L);e=event(L,1,ss);r=L.apply(e);after=snap(L);replay=L.apply(e)
add('rejection_atomicity','Rejected sale preserves all execution state and does not consume id/capacity',r['status']!='applied' and economic(before)==economic(after) and replay['status']!='skipped_duplicate',record=r,before=before,after=after,replay=replay)
# 4: Returned views must not alias internal audit/provenance state.
L=ledger();r=L.apply(event(L,1,req));before=snap(L)
r['state_after']['cash']='999999.00'
snapview=L.snapshot();snapview['capacity']['C']['evidence']['source_ref']='syn:mutated-via-view'
after=snap(L)
add('detached_read_views','Mutating returned record/snapshot cannot change stored history/evidence',L.records[0]['state_after']['cash']!='999999.00' and economic(before)==economic(after),record_history_cash=L.records[0]['state_after']['cash'],before=before,after=after)
# 5: Same order id cannot silently move its original expiry through a new attempt.
L=ledger();T10='2024-03-19T10:00:00+08:00'
cont=replace(req,order=replace(req.order,quantity=200,execution_phase='continuous'),attempt=replace(req.attempt,executed_at=T10,phase='continuous'),price=replace(req.price,observed_at=T10,available_at=T10),capacity=replace(req.capacity,quantity=100,observed_at=T10,available_at=T10))
first=L.apply(event(L,1,cont));Tnext='2024-03-20T10:00:00+08:00'
later=replace(cont,decision=replace(cont.decision,decision_session=sessions[1],decided_at='2024-03-19T16:00:00+08:00'),order=replace(cont.order,quantity=100,submitted_at='2024-03-20T09:00:00+08:00',eligible_from='2024-03-20T09:30:00+08:00'),attempt=replace(cont.attempt,attempt_id='A-later',session=sessions[2],executed_at=Tnext),price=replace(cont.price,observed_at=Tnext,available_at=Tnext),capacity=replace(cont.capacity,capacity_id='C-later',observed_at=Tnext,available_at=Tnext),tradability=replace(cont.tradability,session=sessions[2],observed_at=T2,available_at=T2))
r=L.apply(event(L,2,later))
add('same_order_rewrites_expiry','Expired original order must not refill by replacing decision/eligible terms',first['status']=='applied' and r['status']!='applied',first=first,later=r,snapshot=L.snapshot())
receipt=dict(schema='m4.codex.portfolio_adversarial.v1',observed_at_utc=datetime.now(timezone.utc).isoformat(),source_hashes=sources,source_unchanged=all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h for f,h in sources.items()),cases=cases,guard_denials=denials,synthetic_only=True,review_only=True,live_trading_enabled=False,training_eligible=False)
(OUT/'results.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checks':[{'name':c['name'],'passed':c['passed']} for c in cases],'source_hashes':sources,'source_unchanged':receipt['source_unchanged'],'guard_denials':denials},indent=2))
