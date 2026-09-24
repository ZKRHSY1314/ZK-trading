"""Independent working-draft adversarial cases; all inputs synthetic; no app imports."""
from pathlib import Path
import sys, json, hashlib, importlib.util
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, localcontext, ROUND_DOWN
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent/'risk_review_03'
OUT.mkdir(exist_ok=True)
sources={}
for rel in ['backend/app/research/m4_execution.py','backend/app/research/m4_portfolio.py','backend/app/research/m4_risk.py']:
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

r=load('codex_risk_subject',OUT/'m4_risk.py')
POL=r.RiskPolicy('SYN-CODEX-P','hypothetical_fixture','0.5','0.5','0','0.05',None,5,2,0,'0.5',1,('stop_loss','max_holding'),entry_phase='continuous')
C=r.DecisionContext(sessions[0],'2024-03-18T16:00:00+08:00',req.calendar,req.fee_schedule,req.assumptions)
def eng():
    L=ledger()
    E=r.PolicyEngine(kernel=m,ledger_module=p,ledger=L,policy=POL,universe=(r.UniverseMember(S,'stock','syn_main','syn:listing'),),benchmark_symbol='SYN_INDEX',engine_id='SYN-CODEX-RISK')
    return E,L
def decision(E,did='D1',c=C):
    t=c.decision_session+'T15:00:00+08:00'
    return E.decide(did,c,marks=(r.Mark(S,'10.00',t,t,'syn:mark',True),),signals=(r.Signal(did+'-sig',S,'buy',t,t,'syn:signal',True),))
def evid(aid='A1',price='10',qty=100,time='2024-03-19T10:00:00+08:00'):
    return r.AttemptEvidence(aid,time,sessions[1],'continuous',replace(req.tradability,limit_up_price='50',limit_down_price='1'),replace(req.price,price=price,field='last_trade',observed_at=time,available_at=time),replace(req.capacity,capacity_id=aid,quantity=qty,basis='available_at_attempt',observed_at=time,available_at=time))
E,L=eng();d=decision(E);iid=d['entries'][0]['intent_id'];x=E.execute(iid,C,evid(qty=1000));s=L.snapshot()
add('positive_sized_entry','400shares, cash5994.96',s['positions'].get(S)==400 and s['cash']=='5994.96',decision=d,attempt=x,snapshot=s)
# Partial fills must debit the SAME reserved budget, not reuse all 5000 for the remainder.
E,L=eng();d=decision(E);iid=d['entries'][0]['intent_id'];x1=E.execute(iid,C,evid());x2=E.execute(iid,C,evid('A2','14',1000,'2024-03-19T11:00:00+08:00'));s=L.snapshot();spent=Decimal('10000')-Decimal(s['cash'])
add('cumulative_intent_budget','All partial fills total cost <= original reserved5000',spent<=Decimal('5000'),spent=str(spent),first=x1,second=x2,snapshot=s,reservations=E.reservations())
# Unavailable/mismatched execution evidence cannot cancel and release a valid intent before kernel validation.
E,L=eng();d=decision(E);iid=d['entries'][0]['intent_id'];before=E.intents();ev=evid(price='100');ev=replace(ev,price=replace(ev.price,observed_at='2024-03-20T10:00:00+08:00',available_at='2024-03-20T10:00:00+08:00'))
x=E.execute(iid,C,ev)
add('future_price_cancels_intent','Future execution price rejected before any intent/reservation change',E.intents()==before and E.reservations()['reserved_cash']=='5000.00',attempt=x,before=before,after=E.intents(),reservations=E.reservations())
# First fill must preserve decision-time calendar expiry too, not bind only on first ledger execution.
E,L=eng();d=decision(E);iid=d['entries'][0]['intent_id'];changed=replace(C,calendar=replace(C.calendar,close_time='16:00'))
x=E.execute(iid,changed,evid(time='2024-03-19T15:30:00+08:00'))
add('decision_calendar_rewritten_before_first_fill','Intent expires original15:00; changed execution context must not fill15:30',not L.positions(),attempt=x,snapshot=L.snapshot())
# Current ledger state must not leak backward into decisions older than an applied execution.
E,L=eng();d=decision(E);iid=d['entries'][0]['intent_id'];x=E.execute(iid,C,evid());back=decision(E,'D-back')
add('decision_before_last_fill','Backdated decision after a fill refused instead of consuming future holdings',back.get('status')=='refused',decision=back,snapshot=L.snapshot())
receipt=dict(schema='m4.codex.risk_review.v1',at_utc=datetime.now(timezone.utc).isoformat(),source_hashes=sources,source_unchanged=all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h for f,h in sources.items()),cases=cases,guard_denials=denials,synthetic_only=True,review_only=True,live_trading_enabled=False)
(OUT/'results.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checks':[{'name':c['name'],'passed':c['passed']} for c in cases],'source_hashes':sources,'source_unchanged':receipt['source_unchanged'],'guard_denials':denials},indent=2))
