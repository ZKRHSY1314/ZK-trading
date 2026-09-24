"""Independent synthetic adversarial review of a byte-pinned working draft; no app imports."""
from pathlib import Path
import ast
import sys
import json
import hashlib
import importlib.util
from dataclasses import replace
from datetime import datetime, timezone
from decimal import localcontext, ROUND_DOWN

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / 'acceptance_review_01'
OUT.mkdir(exist_ok=True)
SOURCE = ROOT / 'backend/app/research/m4_execution.py'
raw = SOURCE.read_bytes()
sha = hashlib.sha256(raw).hexdigest()
snapshot = OUT / 'm4_execution_snapshot.py'
if snapshot.exists() and snapshot.read_bytes() != raw:
    raise RuntimeError('Refusing to overwrite a different reviewed source snapshot')
snapshot.write_bytes(raw)
allowed_imports = {'__future__', 'hashlib', 'json', 'dataclasses', 'datetime', 'decimal', 'typing'}
for node in ast.walk(ast.parse(raw)):
    names = [a.name for a in node.names] if isinstance(node, ast.Import) else ([node.module] if isinstance(node, ast.ImportFrom) else [])
    assert all(n in allowed_imports for n in names), names
denied = []
def guard(event, args):
    block = event.startswith(('sqlite3.', 'socket.', 'subprocess.')) or event in {'os.system','os.exec','os.posix_spawn','os.remove','os.rename','os.rmdir','os.mkdir'}
    if event == 'open':
        path, mode, flags = args
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (1|2|64|512|1024))
        if writing:
            block = not isinstance(path, (str,bytes)) or not Path(path).resolve().is_relative_to(OUT.resolve())
    if block:
        denied.append(event)
        raise RuntimeError('Guard denied ' + event)
sys.addaudithook(guard)
spec = importlib.util.spec_from_file_location('m4_independent_pinned', snapshot)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
S = 'SYN_CODEX_01'
T = '2024-03-19T09:30:00+08:00'
sessions = ('2024-03-18','2024-03-19','2024-03-20','2024-03-21')
req = m.ExecutionRequest(
    decision=m.Decision('D','SYN_CODEX_01','buy',sessions[0],'2024-03-18T16:00:00+08:00',(m.InputAvailability('prior_close','2024-03-18T15:05:00+08:00','syn:prior_close'),),'syn:rule'),
    order=m.Order('O','D',S,'buy',100,'10.00','2024-03-19T09:00:00+08:00',T,1,'open_auction'),
    instrument=m.Instrument(S,'stock','syn_main','syn:listing','syn:calendar',True),
    calendar=m.SessionCalendar(sessions,'+08:00','09:30','15:00','syn:calendar','2024-01-01T00:00:00+08:00',True),
    tradability=m.TradabilityEvidence(S,sessions[1],'tradable','none','band','11.00','9.00','not_st','seasoned',T,T,'syn:tradable',True),
    price=m.PriceObservation(S,'10.00','open_auction_print',T,T,'syn:price','contemporaneous',True),
    capacity=m.LiquidityCapacity(S,'C',1000,'share','auction_matched_quantity',T,T,'syn:capacity','contemporaneous',True),
    account=m.AccountState('SYN_CODEX_ACCOUNT','10000.00',(),'2024-03-19T09:00:00+08:00',True),
    fee_schedule=m.FeeSchedule('HYPOTHETICAL_CODEX','1','hypothetical_fixture','syn:fees','2024-01-01',None,('syn_main',),'0.0003','0.0003','5.00','0.00001','0.0005'),
    assumptions=m.ExecutionAssumptions('HYPOTHETICAL_CODEX','hypothetical_fixture','syn:policy','0','1','0.01',m.LotPolicy('syn:lot',100,100,100,'whole_odd_remainder_only',1000000),m.SettlementPolicy('syn:T+1',1)),
    attempt=m.ExecutionAttempt('A',T,sessions[1],'open_auction'),
)
cases = []
def check(name, request, expectation, pred):
    try:
        result=m.execute(request).to_dict()
        passed=bool(pred(result))
        cases.append(dict(name=name, expected=expectation, expectation_met=passed, result=result))
    except Exception as exc:
        cases.append(dict(name=name, expected=expectation, expectation_met=False, exception_type=type(exc).__name__,exception=str(exc)))
check('hand_buy',req,'100 shares; cash delta -1005.01',lambda r:r['fill']['filled_quantity']==100 and r['ledger_entry']['cash_delta']=='-1005.01')
check('future_calendar',replace(req,calendar=replace(req.calendar,available_at='2025-01-01T00:00:00+08:00')),'Reject calendar unavailable at decision',lambda r:r['status']=='rejected')
sell = replace(req,decision=replace(req.decision,side='sell'),order=replace(req.order,side='sell',quantity=50),account=replace(req.account,inventory=(m.InventoryLot(50,sessions[0]),)),capacity=replace(req.capacity,quantity=50))
check('whole_odd_50_exact_capacity',sell,'All 50 settled odd shares fit raw capacity; fill 50',lambda r:r['fill']['filled_quantity']==50)
sell199=replace(sell,order=replace(sell.order,quantity=199),account=replace(sell.account,inventory=(m.InventoryLot(199,sessions[0]),)),capacity=replace(sell.capacity,quantity=199))
check('whole_odd_199_exact_capacity',sell199,'All 199 settled shares fit raw capacity; fill 199',lambda r:r['fill']['filled_quantity']==199)
T10='2024-03-19T10:00:00+08:00'
cont=replace(req,order=replace(req.order,quantity=200,execution_phase='continuous'),attempt=replace(req.attempt,phase='continuous',executed_at=T10),price=replace(req.price,observed_at=T10,available_at=T10,field='last_trade'),capacity=replace(req.capacity,quantity=100,observed_at=T10,available_at=T10,basis='available_at_attempt'))
check('partial_continuous_before_expiry',cont,'Partial 100 at 10:00, expires 15:00; remainder stays live',lambda r:r['status']=='partially_filled' and r['order_live_after_attempt'])
check('unfilled_continuous_before_expiry',replace(cont,capacity=replace(cont.capacity,quantity=0)),'Unfilled 10:00, expires 15:00; order stays live',lambda r:r['status']=='unfilled' and r['order_live_after_attempt'])
reference=m.execute(req).to_dict()
with localcontext() as ctx:
    ctx.prec=6
    ctx.rounding=ROUND_DOWN
    check('ambient_decimal_precision',req,'Same valid input, result and hash independent of caller Decimal context',lambda r:r==reference)
check('integer_numeric_spelling',replace(req,price=replace(req.price,price=10)),'Money 10 integer and 10.00 string yield identical identity/result',lambda r:r==reference)
check('future_settlement_suffix',replace(req,calendar=replace(req.calendar,sessions=(sessions[0],sessions[1],'2024-03-22','2024-03-25'))),'Input identity must bind actual consumed next settlement session if output changes',lambda r:r['identities']['input_hash']!=reference['identities']['input_hash'] or r==reference)
receipt=dict(schema='m4.codex.working_review.v1',observed_at_utc=datetime.now(timezone.utc).isoformat(),source=str(SOURCE),source_sha256=sha,snapshot=str(snapshot),working_draft_not_final_acceptance=True,synthetic_only=True,review_only=True,live_trading_enabled=False,training_eligible=False,guard_denials=denied,source_unchanged_during_probe=SOURCE.read_bytes()==raw,cases=cases)
(OUT/'results.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(source_sha256=sha,checks=[{'name':c['name'],'expectation_met':c['expectation_met'],'status':c.get('result',{}).get('status'),'exception':c.get('exception_type')} for c in cases],guard_denials=denied),ensure_ascii=False,indent=2))
