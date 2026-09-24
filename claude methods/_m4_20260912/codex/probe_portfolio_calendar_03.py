"""Independent calendar-binding regression, synthetic only, same read/write guard as review 02."""
from pathlib import Path
base = Path(__file__).with_name('probe_portfolio_03.py').read_text('utf-8')
exec(compile(base[:base.index('# 1: Normal round-trip')], '<Codex isolated fixture>', 'exec'))
T10='2024-03-19T10:00:00+08:00'
cont=replace(req,order=replace(req.order,quantity=200,execution_phase='continuous'),attempt=replace(req.attempt,executed_at=T10,phase='continuous'),price=replace(req.price,field='last_trade',observed_at=T10,available_at=T10),capacity=replace(req.capacity,quantity=100,basis='available_at_attempt',observed_at=T10,available_at=T10))
Tlate='2024-03-19T15:30:00+08:00'
late=replace(cont,order=replace(cont.order,quantity=100),attempt=replace(cont.attempt,attempt_id='A-late',executed_at=Tlate),price=replace(cont.price,observed_at=Tlate,available_at=Tlate),capacity=replace(cont.capacity,capacity_id='C-late',observed_at=Tlate,available_at=Tlate))
for name, calendar in [('original_calendar',cont.calendar),('same_source_extended_close',replace(cont.calendar,close_time='16:00'))]:
    L=ledger()
    first=L.apply(event(L,1,cont))
    before=snap(L)
    r=L.apply(event(L,2,replace(late,calendar=calendar)))
    after=snap(L)
    add(name,'Original 15:00 expiry cannot be extended on same order id; no second fill',first['status']=='applied' and r['status']!='applied' and economic(before)==economic(after),first=first,later=r,before=before,after=after)
receipt=dict(source_hashes=sources,cases=cases,guard_denials=denials,synthetic_only=True,source_unchanged=all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h for f,h in sources.items()))
(OUT/'calendar_binding_results.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([dict(name=c['name'],passed=c['passed'],status=c['actual']['later']['status'],reasons=c['actual']['later']['reasons']) for c in cases],indent=2))
