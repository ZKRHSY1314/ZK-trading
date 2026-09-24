import sqlite3, sys, json
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op=ro(OP)
print("### Q16 run created_at vs benchmark ingest date")
q="SELECT id, created_at, completed_at, substr(benchmark_json,1,60) FROM historical_backtest_runs ORDER BY id"
print("SQL:", q)
for r in op.execute(q): print("   ", r)
print("   benchmark first ingest into cache:")
q2="SELECT symbol, MIN(created_at), MAX(created_at), MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001') GROUP BY symbol"
print("SQL:", q2)
for r in op.execute(q2): print("   ", r)

print("\n### Q17 full metrics_json of run 39 and run 1")
for rid in (1, 39):
    m = op.execute("SELECT metrics_json FROM historical_backtest_runs WHERE id=?", (rid,)).fetchone()[0]
    print(f"  run {rid} metrics:")
    print("   ", json.dumps(json.loads(m), ensure_ascii=False, indent=2))

print("\n### Q18 config_json of run 39 (and distinct configs)")
c = op.execute("SELECT config_json FROM historical_backtest_runs WHERE id=39").fetchone()[0]
print(json.dumps(json.loads(c), ensure_ascii=False, indent=2)[:4000])
q="SELECT COUNT(DISTINCT config_json) FROM historical_backtest_runs"
print("SQL:", q, "->", op.execute(q).fetchone()[0])

print("\n### Q19 aggregate: any run with non-flat equity or nonzero positions?")
q="""SELECT COUNT(*) FROM historical_backtest_runs r WHERE EXISTS (
  SELECT 1 FROM historical_backtest_daily_equity e WHERE e.run_id=r.id AND (e.total_equity <> r.initial_cash OR e.positions_value <> 0))"""
print("SQL:", q, "->", op.execute(q).fetchone()[0])
q="SELECT COUNT(*), MIN(total_equity), MAX(total_equity), MIN(positions_value), MAX(positions_value), MIN(cash), MAX(cash) FROM historical_backtest_daily_equity"
print("SQL:", q, "->", op.execute(q).fetchone())
q="SELECT COUNT(DISTINCT run_id) FROM historical_backtest_daily_equity"
print("SQL:", q, "->", op.execute(q).fetchone()[0])
op.close()
