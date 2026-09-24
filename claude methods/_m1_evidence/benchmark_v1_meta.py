import sqlite3, json
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
op = sqlite3.connect(f"file:{OP}?mode=ro", uri=True); op.row_factory = sqlite3.Row
mh = sqlite3.connect(f"file:{MH}?mode=ro", uri=True); mh.row_factory = sqlite3.Row

print("=== SQL A: historical_backtest_runs schema ===")
print(op.execute("SELECT sql FROM sqlite_master WHERE name='historical_backtest_runs'").fetchone()[0])

print("\n=== SQL B: fundamentals snapshot census ===")
q = """SELECT COUNT(*) n, COUNT(DISTINCT symbol) syms, COUNT(DISTINCT as_of) asofs,
 MIN(as_of) mn, MAX(as_of) mx, MIN(available_at) mina, MAX(available_at) maxa,
 SUM(CASE WHEN total_share_billion IS NULL THEN 1 ELSE 0 END) null_share,
 SUM(CASE WHEN book_value_per_share IS NULL THEN 1 ELSE 0 END) null_bvps,
 COUNT(DISTINCT source) srcs FROM symbol_fundamental_snapshot"""
print(q); print(dict(op.execute(q).fetchone()))

print("\n=== SQL C: all runs, window + stored metrics ===")
q = """SELECT id,start_date,end_date,status,
 json_extract(metrics_json,'$.signal_evaluated_bars') ev,
 json_extract(metrics_json,'$.rejected_by_risk_count') rej,
 json_extract(metrics_json,'$.entry_signal_count') sig,
 json_extract(metrics_json,'$.total_trades') tt
 FROM historical_backtest_runs ORDER BY id"""
try:
    for r in op.execute(q).fetchall(): print(dict(r))
except Exception as e:
    print("ERR", e)
    print([d[0] for d in op.execute("SELECT * FROM historical_backtest_runs LIMIT 1").description])
