from pathlib import Path
import sys, json, hashlib, importlib.util
from dataclasses import replace
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent/'qualification_review_01'
assert OUT.is_dir() and not (OUT/'independent_proposal_probes_02.json').exists()
denials=[]
def guard(event,args):
    deny=event.startswith(('sqlite3.','socket.','subprocess.')) or event in {'os.system','os.exec','os.posix_spawn','os.remove','os.rename','os.rmdir','os.mkdir'}
    if event=='open':
        p,mode,flags=args
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (1|2|64|512|1024)):
            deny=not isinstance(p,(str,bytes)) or not Path(p).resolve().is_relative_to(OUT.resolve())
    if deny: denials.append(event); raise RuntimeError('Guard denied '+event)
sys.addaudithook(guard)
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec); sys.modules[name]=mod; spec.loader.exec_module(mod); return mod
sources={}
for n in ['execution','portfolio','risk']:
    pth=ROOT/f'backend/app/research/m4_{n}.py'; sources[pth.relative_to(ROOT).as_posix()]=hashlib.sha256(pth.read_bytes()).hexdigest()
m=load('proposal_kernel',ROOT/'backend/app/research/m4_execution.py')
p=load('proposal_ledger',ROOT/'backend/app/research/m4_portfolio.py')
r=load('proposal_risk',ROOT/'backend/app/research/m4_risk.py')
fixture=(Path(__file__).resolve().parent/'probe_m4_working_01.py').read_text('utf-8')
exec(compile(fixture[fixture.index("S = 'SYN_CODEX_01'"):fixture.index('cases = []')],'<existing Codex synthetic fixture>','exec'))
def result(request):
    rec=m.execute(request).to_dict(); return {'status':rec['status'],'reasons':rec['reasons'],'fill':rec.get('fill'),'evidence':rec.get('evidence')}
control=result(req)
# Exact proposed dependency: closing limit state is injected at opening, despite identical opening data.
late_close_10=result(replace(req,tradability=replace(req.tradability,limit_state='none',source_ref='ASSUMED:future-close=10')))
late_close_11=result(replace(req,tradability=replace(req.tradability,limit_state='limit_up',source_ref='ASSUMED:future-close=11')))
# Exact proposed capacity quantity equals order quantity, but participation remains 0.10.
cap100=result(replace(req,capacity=replace(req.capacity,quantity=100,kind='predeclared_assumption',assumption_ref='ASSUMPTION:full_fill_capacity_not_market_evidence',basis='hypothetical_full_fill'),assumptions=replace(req.assumptions,max_participation_rate='0.10')))
cap400=result(replace(req,order=replace(req.order,quantity=400),capacity=replace(req.capacity,quantity=400,kind='predeclared_assumption',assumption_ref='ASSUMPTION:full_fill_capacity_not_market_evidence',basis='hypothetical_full_fill'),assumptions=replace(req.assumptions,max_participation_rate='0.10')))
def risk_attempt(available_at):
    ledger=p.PortfolioLedger(m,ledger_id='SYN-Q-L',account_ref='SYN-Q-A',initial_cash='10000')
    policy=r.RiskPolicy('SYN-Q-P','hypothetical_fixture','0.5','0.5','0','0.05',None,5,2,0,'0.02',1,('stop_loss','max_holding'),entry_phase='open_auction')
    engine=r.PolicyEngine(kernel=m,ledger_module=p,ledger=ledger,policy=policy,universe=(r.UniverseMember(S,'stock','syn_main','syn:listing'),),benchmark_symbol='SYN_INDEX',engine_id='SYN-Q-E')
    context=r.DecisionContext(sessions[0],'2024-03-18T16:00:00+08:00',req.calendar,req.fee_schedule,req.assumptions)
    stamp='2024-03-18T15:00:00+08:00'
    dec=engine.decide('D1',context,marks=(r.Mark(S,'10',stamp,stamp,'ASSUMED:mark',True),),signals=(r.Signal('SIG',S,'buy',stamp,stamp,'ASSUMED:signal',True),))
    iid=dec['entries'][0]['intent_id']
    ev=r.AttemptEvidence('A1',T,sessions[1],'open_auction',req.tradability,replace(req.price,field='open',available_at=available_at,kind='predeclared_assumption',assumption_ref='ASSUMPTION:daily_bar_open_equals_0930_auction_print'),req.capacity)
    out=engine.execute(iid,context,ev)
    return {'result':out,'positions':ledger.positions()}
captured=risk_attempt('2026-09-09T17:12:13.572989+00:00')
assumed_open=risk_attempt(T)
receipt={'at_utc':datetime.now(timezone.utc).isoformat(),'synthetic_only':True,'source_hashes':sources,'control':control,
    'future_close_dependency':{'same_open_different_future_close':[late_close_10,late_close_11],'outcome_changes':late_close_10['status']!=late_close_11['status']},
    'capacity_full_fill_mismatch':{'order100':cap100,'order400':cap400},
    'risk_availability_mapping':{'capture_preserved_in_available_at':captured,'assumed_open_available_at_control':assumed_open},
    'guard_denials':denials,'sqlite_connections':0,'live_trading_enabled':False,'review_only':True}
(OUT/'independent_proposal_probes_02.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'control':control['status'],'future_close_outcomes':[late_close_10['status'],late_close_11['status']],'capacity100':cap100,'capacity400':cap400,'risk_capture_status':captured['result']['status'],'risk_capture_reasons':captured['result'].get('reasons'),'risk_assumed_open_status':assumed_open['result']['status'],'guard_denials':denials},ensure_ascii=False))

