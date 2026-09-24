from pathlib import Path
base=Path(__file__).with_name('probe_risk_03.py').read_text('utf-8')
exec(compile(base[:base.index('E,L=eng();d=decision(E)')],'<Codex independent risk fixture>','exec'))
E,L=eng();d=decision(E);iid=d['entries'][0]['intent_id'];buy=E.execute(iid,C,evid(qty=1000))
c2=replace(C,decision_session=sessions[2],decided_at='2024-03-20T16:00:00+08:00')
t='2024-03-20T15:00:00+08:00'
stop=E.decide('D-stop',c2,marks=(r.Mark(S,'9',t,t,'syn:close',True),))
sid=stop['exits'][0]['intent_id'];tx='2024-03-21T09:30:00+08:00'
ev=r.AttemptEvidence('A-sell',tx,sessions[3],'open_auction',replace(req.tradability,session=sessions[3],observed_at=tx,available_at=tx,limit_up_price='50',limit_down_price='1'),replace(req.price,price='8.90',observed_at=tx,available_at=tx),replace(req.capacity,capacity_id='C-sell',observed_at=tx,available_at=tx))
sell=E.execute(sid,c2,ev)
c3=replace(C,decision_session=sessions[3],decided_at='2024-03-21T16:00:00+08:00')
cool=decision(E,'D-cool',c3)
b1=r.BenchmarkObservation('SYN_INDEX','100','2024-03-18T15:00:00+08:00','2024-03-18T15:00:00+08:00','syn:bench',True)
b2=replace(b1,level='98',observed_at='2024-03-21T15:00:00+08:00',available_at='2024-03-21T15:00:00+08:00')
perf=E.performance(c3,start_session=sessions[0],initial_cash='10000',benchmark=(b1,b2))
s=L.snapshot()
passed=(s['cash']=='9548.14' and s['realized_pnl_total']=='-451.86' and not s['positions'] and stop['exits'][0]['reason']=='stop_loss' and cool['entries'][0]['reason']=='cooldown_active' and perf['complete'])
receipt=dict(passed=passed,expected={'cash':'9548.14','realized_pnl':'-451.86','position':0,'buy_cost':'4005.04','sell_proceeds':'3553.18'},buy=buy,stop=stop,sell=sell,cooldown=cool,performance=perf,snapshot=s,reconcile=L.reconcile(),source_hashes=sources,guard_denials=denials)
(OUT/'independent_roundtrip.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':passed,'cash':s['cash'],'pnl':s['realized_pnl_total'],'performance':perf},indent=2))
assert passed
