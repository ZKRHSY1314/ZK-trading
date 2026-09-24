from pathlib import Path
import sys,json,hashlib,importlib.util
from dataclasses import asdict, replace
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[3]; BASE=ROOT/'claude methods/_m4_20260912'; OUT=BASE/'codex/qualification_review_02'
assert not (OUT/'independent_mapping_checks.json').exists()
denials=[]
def guard(event,args):
    deny=event.startswith(('sqlite3.','socket.','subprocess.')) or event in {'os.system','os.exec','os.posix_spawn','os.remove','os.rename','os.rmdir','os.mkdir'}
    if event=='open':
        p,mode,flags=args
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (1|2|64|512|1024)):
            deny=not isinstance(p,(str,bytes)) or not Path(p).resolve().is_relative_to(OUT.resolve())
    if deny: denials.append(event); raise RuntimeError('guard:'+event)
sys.addaudithook(guard)
def load(name,path):
    sp=importlib.util.spec_from_file_location(name,path); obj=importlib.util.module_from_spec(sp);sys.modules[name]=obj;sp.loader.exec_module(obj);return obj
m=load('ind_kernel',ROOT/'backend/app/research/m4_execution.py'); p=load('ind_ledger',ROOT/'backend/app/research/m4_portfolio.py'); r=load('ind_risk',ROOT/'backend/app/research/m4_risk.py'); pm=load('ind_mapping',BASE/'claude_03a/proposal_mapping.py')
S='SYN_CODEX_01'; CAPTURE='2026-09-09T17:12:13.572989+00:00'; sessions=('2024-03-18','2024-03-19','2024-03-20','2024-03-21')
cal=pm.calendar(m,sessions,CAPTURE,'assumed',True,'syn:calendar'); fees=pm.fee_schedule(m); asm=pm.execution_assumptions(m)
policy=r.RiskPolicy('SYN-CODEX-Q','hypothetical_fixture','0.5','0.5','0','0.05',None,5,2,0,'0.02',1,('stop_loss','max_holding'))
def engine():
    L=p.PortfolioLedger(m,ledger_id='SYN-Q-L',account_ref='SYN-Q-A',initial_cash='10000')
    E=r.PolicyEngine(kernel=m,ledger_module=p,ledger=L,policy=policy,universe=(r.UniverseMember(S,'stock','main','syn:listing'),),benchmark_symbol='SYN_INDEX',engine_id='SYN-Q-E'); return E,L
def decision(E,did,day,price,signal=False,variant='assumed'):
    c=pm.decision_context(r,day,cal,fees,asm)
    d=E.decide(did,c,marks=(pm.mark(r,S,day,price,CAPTURE,variant,True),),signals=(pm.signal(r,did+'-sig',S,day,CAPTURE,variant,True),) if signal else ())
    return d,c
def mapping(day,openprice,prev,qty=400,variant='assumed',capacity='full_fill'):
    return pm.attempt_evidence(m,r,pm.OpenAttemptInputs(S,day,openprice,prev,False,CAPTURE,'main',200),'A-'+day,variant,capacity,qty,True)
cases=[]
def add(name,ok,**actual): cases.append(dict(name=name,passed=bool(ok),actual=actual))
E,L=engine(); d,c=decision(E,'D1',sessions[0],'10',True); iid=d['entries'][0]['intent_id']; x=E.execute(iid,c,mapping(sessions[1],'10','10'))
stop,cs=decision(E,'DS',sessions[2],'9.4'); xs=E.execute(stop['exits'][0]['intent_id'],cs,mapping(sessions[3],'9.4','9.4')); cool,_=decision(E,'DC',sessions[3],'9.4',True)
snapshot=L.snapshot()
add('independent_hand_roundtrip',x['outcome']['filled_quantity']==400 and x['outcome']['cash_after']=='5985.92' and snapshot['cash']=='9728.84' and snapshot['realized_pnl_total']=='-271.16' and not L.positions() and L.reconcile()['ok'] and cool['entries'][0]['reason']=='cooldown_active',buy=x,sell=xs,snapshot=snapshot,cooldown=cool)
raw=pm.mark(r,S,sessions[0],'10',CAPTURE,'raw',True); modeled=pm.mark(r,S,sessions[0],'10',CAPTURE,'assumed',True)
add('raw_and_model_time_preserved',raw.available_at==CAPTURE and modeled.available_at==sessions[0]+'T16:00:00+08:00' and CAPTURE in modeled.source_ref and 'ASSUMPTION:' in modeled.source_ref,raw=asdict(raw),modeled=asdict(modeled))
Er,Lr=engine(); dr,cr=decision(Er,'RAW',sessions[0],'10',True,'raw'); add('raw_signal_cannot_create_intent',not Er.intents() and not Lr.records and any(z['code']=='future_evidence' for z in dr['refusals']),record=dr)
for qty in [100,400]:
    ev=mapping(sessions[1],'10','10',qty)
    req=m.ExecutionRequest(m.Decision('D',S,'buy',sessions[0],sessions[0]+'T16:00:00+08:00',(m.InputAvailability('close',sessions[0]+'T16:00:00+08:00','syn:close'),),'syn:rule'),m.Order('O','D',S,'buy',qty,'10.20',sessions[0]+'T16:00:00+08:00',ev.executed_at,1,'open_auction'),m.Instrument(S,'stock','main','syn:listing','syn:calendar',True),cal,ev.tradability,ev.price,ev.capacity,m.AccountState('SYN-A','10000',(),ev.executed_at,True),fees,asm,m.ExecutionAttempt('A',ev.executed_at,sessions[1],'open_auction'))
    rec=m.execute(req).record; add('capacity_'+str(qty),rec['status']=='filled' and rec['fill']['filled_quantity']==qty and rec['evidence']['evidence_grade']=='assumed',record=rec)
base={'open':'10','high':'11','low':'9','close':'10','volume':1000}; changed={**base,'high':'20','low':'1','close':'11','volume':999999}
ev1=mapping(sessions[1],base['open'],'10'); ev2=mapping(sessions[1],changed['open'],'10')
add('future_bar_suffix_cannot_enter_mapping',asdict(ev1)==asdict(ev2) and ev1.tradability.limit_state=='none',mapped=asdict(ev1))
result=dict(cases=cases,all_pass=all(z['passed'] for z in cases),mapping_sha256=hashlib.sha256((BASE/'claude_03a/proposal_mapping.py').read_bytes()).hexdigest(),guard_denials=denials,sqlite_connections=0,synthetic_only=True)
(OUT/'independent_mapping_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'all_pass':result['all_pass'],'cases':[{'name':x['name'],'passed':x['passed']} for x in cases],'guard_denials':denials}))
