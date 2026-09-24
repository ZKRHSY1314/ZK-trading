"""Codex isolated delivery replay plus independent checks. Writes only acceptance_review_01."""
from pathlib import Path
import sys, json, hashlib, importlib.util, io, unittest
from dataclasses import replace
from decimal import Decimal
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent/'acceptance_review_01'
OUT.mkdir(exist_ok=True)
denials=[]
def guard(event,args):
    deny=event.startswith(('sqlite3.','socket.','subprocess.')) or event in {'os.system','os.exec','os.posix_spawn','os.remove','os.rename','os.rmdir','os.mkdir'}
    if event=='open':
        p,mode,flags=args
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (1|2|64|512|1024)):
            deny=not isinstance(p,(str,bytes)) or not Path(p).resolve().is_relative_to(OUT.resolve())
    if deny:
        denials.append(event)
        raise RuntimeError('Codex guard denied '+event)
sys.addaudithook(guard)
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module
started=datetime.now(timezone.utc).isoformat()
paths=[ROOT/'backend/app/research/m4_execution.py', ROOT/'backend/tests/test_m4_execution.py']
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
test=load('codex_m4_delivery_tests',paths[1])
suite=unittest.defaultTestLoader.loadTestsFromModule(test)
stream=io.StringIO()
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(OUT/'unittest_stdout.txt').write_text(stream.getvalue(),encoding='utf-8')
m=test.m
# The independent original fixture, not Claude's helpers or expected-value generators.
probe=(Path(__file__).resolve().parent/'probe_m4_working_01.py').read_text('utf-8')
exec(compile(probe[probe.index("S = 'SYN_CODEX_01'"):probe.index('cases = []')],'<Codex original synthetic fixture>','exec'))
checks=[]
def check(name,r,expected,predicate):
    try:
        actual=m.execute(r).to_dict()
        checks.append(dict(name=name,expected=expected,passed=bool(predicate(actual)),actual=actual))
    except Exception as ex:
        checks.append(dict(name=name,expected=expected,passed=False,exception=type(ex).__name__,detail=str(ex)))
cashlow=replace(req,account=replace(req.account,available_cash='1005.00'))
check('all_in_cash_before_fill',cashlow,'Reject and no ledger when cash short by 0.01',lambda r:r['status']=='rejected' and r['ledger_entry'] is None)
sell=replace(req,decision=replace(req.decision,side='sell'),order=replace(req.order,side='sell',limit_price='11.00'),price=replace(req.price,price='11.00'),account=replace(req.account,inventory=(m.InventoryLot(100,sessions[0]),)))
check('sell_hand_fees',sell,'Sell 100x11: commission5 transfer0.01 stamp0.55 -> +1094.44',lambda r:r['ledger_entry']['cash_delta']=='1094.44')
check('same_session_t1_reject',replace(sell,account=replace(sell.account,inventory=(m.InventoryLot(100,sessions[1]),))),'T+1 disallows same-session acquired shares',lambda r:r['status']=='rejected' and r['ledger_entry'] is None)
check('raw_share_capacity',replace(req,order=replace(req.order,quantity=300),capacity=replace(req.capacity,quantity=250)),'250-share capacity with 100 increments -> 200 filled',lambda r:r['fill']['filled_quantity']==200)
cny=replace(req,capacity=replace(req.capacity,unit='CNY',quantity='10000.00'))
ref=m.execute(cny).to_dict()
check('cny_capacity_integer_identity',replace(cny,capacity=replace(cny.capacity,quantity=10000)),'CNY capacity money int and decimal string bind identical result',lambda r:r==ref)
check('benchmark_no_fill',replace(req,instrument=replace(req.instrument,role='benchmark')),'Benchmark cannot execute',lambda r:r['status']=='rejected' and r['ledger_entry'] is None)
fee=replace(req.fee_schedule,min_commission='0',buy_commission_rate='0',sell_commission_rate='0',transfer_fee_rate='0',sell_stamp_duty_rate='0')
buyone=replace(req,fee_schedule=fee,order=replace(req.order,quantity=100))
check('future_price_not_available',replace(buyone,price=replace(req.price,available_at='2024-03-19T15:05:00+08:00')),'No contemporaneous opening fill using unavailable price',lambda r:r['status']=='rejected')
after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
receipt=dict(started_at_utc=started,finished_at_utc=datetime.now(timezone.utc).isoformat(),command=sys.orig_argv,source_hashes=before,source_unchanged=before==after,tests={'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'pass':result.wasSuccessful()},additional_checks=checks,guard_denials=denials,app_imported=any(n=='app' or n.startswith('app.') for n in sys.modules),conftest_imported=any('conftest' in n for n in sys.modules),synthetic_only=True,review_only=True,live_trading_enabled=False,training_eligible=False)
(OUT/'delivery_and_boundaries.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'tests':receipt['tests'],'checks':[{'name':c['name'],'passed':c['passed']} for c in checks],'unchanged':before==after,'guard_denials':denials},indent=2))
sys.exit(0 if result.wasSuccessful() and all(c['passed'] for c in checks) and before==after and not denials else 1)
