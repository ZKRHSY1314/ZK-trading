from pathlib import Path
base=Path(__file__).with_name('probe_risk_02.py').read_text('utf-8')
exec(compile(base[:base.index('E,L=eng();d=decision(E)')],'<Codex independent risk fixture>','exec'))
OTHER='SYN_OTHER'
def other_engine():
    L=ledger((p.InitialLot(OTHER,1000,sessions[0],'1000','syn:other-lot'),))
    E=r.PolicyEngine(kernel=m,ledger_module=p,ledger=L,policy=POL,universe=(r.UniverseMember(S,'stock','syn_main','syn:S'),r.UniverseMember(OTHER,'stock','syn_main','syn:other')),benchmark_symbol='SYN_INDEX',engine_id='SYN-CODEX-OTHER')
    t='2024-03-18T15:00:00+08:00'
    d=E.decide('D1',C,marks=(r.Mark(S,'10',t,t,'syn:S',True),r.Mark(OTHER,'1',t,t,'syn:other',True)),signals=(r.Signal('sig',S,'buy',t,t,'syn:signal',True),))
    return E,L,d['entries'][0]['intent_id']
old=r.Mark(OTHER,'1','2024-03-19T09:00:00+08:00','2024-03-19T09:00:00+08:00','syn:other',True)
latest=replace(old,price='20',observed_at='2024-03-19T09:45:00+08:00',available_at='2024-03-19T09:45:00+08:00')
for name,marks in [('latest_only',(latest,)),('old_plus_latest',(old,latest)),('latest_plus_old',(latest,old)),('conflicting_same_time',(latest,replace(latest,price='1'))),('conflicting_same_time_reversed',(replace(latest,price='1'),latest))]:
    E,L,iid=other_engine();x=E.execute(iid,C,evid(qty=1000),marks=marks)
    add(name,'No buy: latest OTHER value20000 exceeds 50% gross cap; conflicts refused',L.positions().get(S,0)==0 and (not name.startswith('conflicting') or x['status']=='refused'),attempt=x,snapshot=L.snapshot())
E,L=eng();d=decision(E);iid=d['entries'][0]['intent_id']
x1=E.execute(iid,C,evid(time='2024-03-19T11:00:00+08:00'))
before=E.intents();res=E.reservations()
ev=evid('A-earlier','100',1000,'2024-03-19T10:00:00+08:00');ev=replace(ev,tradability=replace(ev.tradability,limit_up_price='200'))
x=E.execute(iid,C,ev)
add('backdated_attempt_cancels','Attempt preceding applied11:00 state refused without cancel/reservation change',x['status']=='refused' and E.intents()==before and E.reservations()==res,first=x1,attempt=x,before=before,after=E.intents(),reservations=E.reservations())
receipt=dict(source_hashes=sources,cases=cases,guard_denials=denials,synthetic_only=True)
(OUT/'additional_results.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{'name':c['name'],'passed':c['passed'],'status':c['actual']['attempt']['status'],'recheck':c['actual']['attempt'].get('outcome',{}).get('recheck')} for c in cases],indent=2))
