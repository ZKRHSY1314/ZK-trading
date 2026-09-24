import sqlite3, json
from collections import Counter
def ro(p):
    c=sqlite3.connect(f"file:{p}?mode=ro",uri=True); c.execute("PRAGMA query_only=1"); return c
tl=ro(r"D:/codex-A股交易/trading_local.sqlite3")
print("=== A2 filter fields the report requires: do they EXIST? ===")
cols=[r[1] for r in tl.execute("PRAGMA table_info(forecast_evaluations)")]
print("forecast_evaluations columns:", cols)
for f in ("run_kind","evidence_quality","canonical_policy_version","decision_id","data_version"):
    print(f"   column '{f}' present in table:", f in cols)
keys=Counter(); n=0
for (mj,) in tl.execute("SELECT metrics_json FROM forecast_evaluations WHERE metrics_json IS NOT NULL"):
    try: d=json.loads(mj)
    except Exception: continue
    n+=1; keys.update(d.keys())
print(f"metrics_json parsed rows={n}; top keys:", keys.most_common(25))
for f in ("run_kind","evidence_quality","canonical_policy_version"):
    print(f"   metrics_json key '{f}' occurrences:", keys.get(f,0))
print("\n=== agent_calibration_proposals (report says 10; table has 11) ===")
for r in tl.execute("SELECT proposal_type, status, COUNT(*) FROM agent_calibration_proposals GROUP BY 1,2"):
    print("  ", r)
print("\n=== decisions/outcomes/evaluations linkage columns ===")
print("forecast_decisions cols:", [r[1] for r in tl.execute("PRAGMA table_info(forecast_decisions)")])
print("forecast_outcomes cols:", [r[1] for r in tl.execute("PRAGMA table_info(forecast_outcomes)")])
print("\n=== 39 backtest runs: date ranges actually requested (report never lists them) ===")
cols=[r[1] for r in tl.execute("PRAGMA table_info(historical_backtest_runs)")]
print("cols:", cols)
for r in tl.execute("SELECT id, start_date, end_date, symbols_json IS NULL, data_source, created_at FROM historical_backtest_runs ORDER BY id LIMIT 8"):
    print("  ", r)
print("  distinct windows:", list(tl.execute("SELECT start_date, end_date, COUNT(*) FROM historical_backtest_runs GROUP BY 1,2 ORDER BY 3 DESC LIMIT 10")))
