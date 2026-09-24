"""Read-only review evidence; stdlib only, no application imports or network."""
import ast
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DB = ROOT / 'trading_local.sqlite3'

def fingerprint():
    result = {}
    for path in (DB, Path(str(DB) + '-wal')):
        if path.exists():
            with path.open('rb') as f:
                digest = hashlib.file_digest(f, 'sha256').hexdigest()
            st = path.stat()
            result[path.name] = dict(size=st.st_size, mtime_ns=st.st_mtime_ns, sha256=digest)
    return result

evidence = {'at_utc': datetime.now(timezone.utc).isoformat(), 'before': fingerprint()}
con = sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True)
con.row_factory = sqlite3.Row
con.execute('PRAGMA query_only=ON')
def query(sql):
    return [dict(row) for row in con.execute(sql)]
try:
    evidence['query_only'] = con.execute('PRAGMA query_only').fetchone()[0]
    evidence['recent_bars'] = query("SELECT trade_date,COUNT(*) rows,COUNT(DISTINCT symbol) symbols FROM daily_bar_cache WHERE trade_date BETWEEN '2026-09-01' AND '2026-09-13' GROUP BY trade_date ORDER BY trade_date")
    evidence['invalid_dates'] = query("SELECT symbol,trade_date,source,quality_status FROM daily_bar_cache WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' LIMIT 20")
    evidence['sources'] = query("SELECT source,COUNT(*) rows,SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) null_amount,SUM(CASE WHEN amount IS NULL OR amount<=0 THEN 1 ELSE 0 END) missing_or_nonpositive_amount FROM daily_bar_cache GROUP BY source")
    evidence['fundamental_schema'] = query('PRAGMA table_info(symbol_fundamental_snapshot)')
    evidence['fundamental_dates'] = query('SELECT as_of,COUNT(*) rows,MIN(available_at) first_available,MAX(available_at) last_available FROM symbol_fundamental_snapshot GROUP BY as_of ORDER BY as_of DESC LIMIT 5')
    evidence['raw_stock_forecasts'] = query("SELECT d.horizon_days,COUNT(*) n,COUNT(DISTINCT d.decision_id) snapshots,COUNT(DISTINCT substr(d.decision_cutoff,1,10)) cutoff_dates FROM forecast_decisions d JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject AND o.horizon_days=d.horizon_days WHERE d.scope='stock' AND o.status='matured' GROUP BY d.horizon_days")
    evidence['latest_evaluations'] = query("SELECT as_of,horizon_days,status,sample_count,fold_count,coverage,spearman_rank_ic,canonical_policy_version FROM forecast_evaluations WHERE scope='stock' ORDER BY id DESC LIMIT 10")
    tree = ast.parse((ROOT/'backend/app/forecasting/canonical.py').read_text(encoding='utf-8-sig'))
    template = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_CANONICAL_CTE_TEMPLATE' for t in n.targets))
    cte = template.format(required_horizon_list='1, 3, 5, 10, 20',required_horizon_count=5,confirmed='confirmed',inferred='inferred')
    evidence['canonical_stock_snapshots'] = query('WITH '+cte+" SELECT selection_kind,COUNT(*) snapshots FROM canonical WHERE scope='stock' GROUP BY selection_kind")
    evidence['canonical_stock_matured'] = query('WITH '+cte+" SELECT cs.selection_kind,d.horizon_days,COUNT(*) n,COUNT(DISTINCT d.decision_id) snapshots,COUNT(DISTINCT substr(d.decision_cutoff,1,10)) cutoff_dates FROM canonical cs JOIN forecast_decisions d ON d.decision_id=cs.decision_id AND d.scope=cs.scope AND d.data_version=cs.data_version JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject AND o.horizon_days=d.horizon_days WHERE d.scope='stock' AND o.status='matured' GROUP BY cs.selection_kind,d.horizon_days")
finally:
    con.close()
evidence['after'] = fingerprint()
evidence['database_bytes_unchanged'] = evidence['before']==evidence['after']

# Exercise the exact valuation method, without importing the application.
tree = ast.parse((ROOT/'backend/app/backtest/engine.py').read_text(encoding='utf-8-sig'))
method = next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_positions_value')
method.returns = None
for arg in method.args.args:
    arg.annotation = None
namespace = {}
exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])), '<review_extracted_positions_value>', 'exec'), namespace)
class Ledger:
    lots = {'SYN_HOLDING': []}
    def quantity(self, symbol): return 100
    def average_cost(self, symbol): return 10
class Frame:
    index = ['SYN_DATE']
    def __init__(self, close): self.loc = {'SYN_DATE': {'close': close}}
evidence['future_close_valuation_probe'] = []
for close in (10,20):
    value = namespace['_positions_value'](None,Ledger(),{'SYN_HOLDING':Frame(close)},'SYN_DATE')
    evidence['future_close_valuation_probe'].append(dict(only_changed_future_close=close,holding_value=value,cash=10000,allocation_cap=0.2,open_allocation=min(10000,(10000+value)*0.2)))

child = r'''
import importlib.util,io,json,sys,types,unittest
from pathlib import Path
root=Path(sys.argv[1])
if sys.argv[2]=='preexisting_app': sys.modules['app']=types.ModuleType('app')
cases=[('test_m4_portfolio.py','TestPolicyAndIsolation','test_module_is_stdlib_only_without_side_effects'),('test_m4_risk.py','TestImmutabilityAndDeterminism','test_module_is_stdlib_only_and_frozen_modules_are_the_pinned_bytes')]
suite=unittest.TestSuite()
for filename,cls,method in cases:
    spec=importlib.util.spec_from_file_location('review_'+filename[:-3],root/'backend/tests'/filename)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    suite.addTest(getattr(module,cls)(method))
stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
print(json.dumps(dict(run=result.testsRun,failures=len(result.failures),errors=len(result.errors),details=stream.getvalue())))
'''
evidence['isolation_checks'] = {}
for mode in ('clean','preexisting_app'):
    result = subprocess.run([sys.executable,'-B','-X','utf8','-c',child,str(ROOT),mode],capture_output=True,text=True,encoding='utf-8',timeout=60)
    evidence['isolation_checks'][mode] = {'exit_code':result.returncode,'result':json.loads(result.stdout) if result.stdout else result.stderr}
(OUT/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(evidence,ensure_ascii=False,indent=2))
