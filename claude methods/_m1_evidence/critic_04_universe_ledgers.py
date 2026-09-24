import sqlite3
TL=r"D:/codex-A股交易/trading_local.sqlite3"; MH=r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    c=sqlite3.connect(f"file:{p}?mode=ro",uri=True); c.execute("PRAGMA query_only=1"); return c
tl=ro(TL); mh=ro(MH)
def show(t,cur):
    print("\n###",t); print(" | ".join(d[0] for d in cur.description))
    for r in cur.fetchall(): print(" | ".join("" if v is None else str(v) for v in r))
print("universe_snapshots cols:", [r[1] for r in mh.execute("PRAGMA table_info(universe_snapshots)")])
print("universe_members cols:", [r[1] for r in mh.execute("PRAGMA table_info(universe_members)")])
show("snapshots", mh.execute("SELECT * FROM universe_snapshots ORDER BY snapshot_date"))
show("members per snapshot", mh.execute("""SELECT s.snapshot_date, s.id, COUNT(*) members
 FROM universe_members m JOIN universe_snapshots s ON s.id=m.snapshot_id GROUP BY 1,2 ORDER BY 1"""))
# survivorship: symbols present in an earlier snapshot but absent later
rows=list(mh.execute("""SELECT s.snapshot_date, m.symbol FROM universe_members m JOIN universe_snapshots s ON s.id=m.snapshot_id"""))
from collections import defaultdict
byd=defaultdict(set)
for d,s in rows: byd[d].add(s)
ds=sorted(byd)
print("\n### consecutive snapshot diffs (removals = observed delistings)")
for a,b in zip(ds,ds[1:]):
    rem=byd[a]-byd[b]; add=byd[b]-byd[a]
    print(f"{a} -> {b}: n_a={len(byd[a])} n_b={len(byd[b])} removed={len(rem)} {sorted(rem)[:8]} added={len(add)}")
print("\n=== forecast_evaluations ===")
print("cols:", [r[1] for r in tl.execute("PRAGMA table_info(forecast_evaluations)")])
show("status/asof", tl.execute("SELECT status, COUNT(*) n, MIN(as_of), MAX(as_of) FROM forecast_evaluations GROUP BY 1"))
print("\n=== ledgers not inventoried in the report ===")
for t in ("learning_backtests","learning_reports","agent_learning_samples","agent_learning_outcomes",
          "agent_calibration_proposals","agent_sandbox_experiments","simulation_fills","historical_backtest_trades",
          "full_market_feature_state","candidate_scores","symbol_fundamental_snapshot","capital_flow_snapshots",
          "dataset2_staging_records","main_force_phase_replays"):
    try: print(f"  {t:36s} {tl.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")
    except Exception as e: print(f"  {t:36s} ERR {e}")
