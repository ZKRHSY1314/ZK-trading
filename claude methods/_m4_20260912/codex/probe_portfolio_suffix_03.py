from pathlib import Path
base=Path(__file__).with_name('probe_portfolio_calendar_03.py').read_text('utf-8')
exec(compile(base[:base.index('for name, calendar')],'<Codex independent calendar fixture>','exec'))
T11='2024-03-19T11:00:00+08:00'
valid=replace(late,attempt=replace(late.attempt,executed_at=T11),price=replace(late.price,observed_at=T11,available_at=T11),capacity=replace(late.capacity,observed_at=T11,available_at=T11))
for name,cal in [('unchanged',req.calendar),('append_unused_session',replace(req.calendar,sessions=sessions+('2024-03-22',))),('alter_unused_suffix',replace(req.calendar,sessions=sessions[:3]+('2024-03-25',)))]:
    L=ledger(); first=L.apply(event(L,1,cont)); prefix=L.records
    r=L.apply(event(L,2,replace(valid,calendar=cal)))
    s=L.snapshot()
    add(name,'Within-window retry fills; cash7989.98,200shares; prior record preserved',r['status']=='applied' and s['cash']=='7989.98' and s['positions'][S]==200 and L.records[:1]==prefix,record=r,snapshot=s)
receipt=dict(cases=cases,source_hashes=sources,guard_denials=denials,synthetic_only=True)
(OUT/'suffix_results.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{'name':c['name'],'passed':c['passed']} for c in cases]))
assert all(c['passed'] for c in cases)
