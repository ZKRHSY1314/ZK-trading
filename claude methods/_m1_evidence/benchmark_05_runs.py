import sqlite3, sys, json
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op=ro(OP)

print("### Q13 anomalous trade_date values in daily_bar_cache")
q="SELECT trade_date, COUNT(*), COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE length(trade_date)<>10 OR trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY trade_date ORDER BY 2 DESC LIMIT 20"
print("SQL:", q)
for r in op.execute(q): print("   ", r)

print("\n### Q14 historical_backtest_runs overview")
q="SELECT status, COUNT(*) FROM historical_backtest_runs GROUP BY status"
print("SQL:", q)
for r in op.execute(q): print("   ", r)
q="SELECT benchmark_symbol, COUNT(*) FROM historical_backtest_runs GROUP BY benchmark_symbol"
print("SQL:", q)
for r in op.execute(q): print("   ", r)
q="SELECT data_source, COUNT(*) FROM historical_backtest_runs GROUP BY data_source"
print("SQL:", q)
for r in op.execute(q): print("   ", r)
q="SELECT benchmark_json, COUNT(*) FROM historical_backtest_runs GROUP BY benchmark_json ORDER BY 2 DESC LIMIT 10"
print("SQL:", q)
for r in op.execute(q): print("   ", (r[0][:300], r[1]))

print("\n### Q15 per-run detail")
q="""SELECT r.id, r.status, r.data_source, r.start_date, r.end_date, r.benchmark_symbol,
 r.initial_cash, r.final_cash, r.created_at, r.completed_at,
 length(r.config_json) clen, length(r.metrics_json) mlen, r.metrics_json, r.benchmark_json, r.execution_warnings_json,
 (SELECT COUNT(*) FROM historical_backtest_daily_equity e WHERE e.run_id=r.id) eq_rows,
 (SELECT MIN(trade_date) FROM historical_backtest_daily_equity e WHERE e.run_id=r.id) eq_d0,
 (SELECT MAX(trade_date) FROM historical_backtest_daily_equity e WHERE e.run_id=r.id) eq_d1,
 (SELECT COUNT(DISTINCT total_equity) FROM historical_backtest_daily_equity e WHERE e.run_id=r.id) distinct_equity,
 (SELECT MIN(total_equity) FROM historical_backtest_daily_equity e WHERE e.run_id=r.id) min_eq,
 (SELECT MAX(total_equity) FROM historical_backtest_daily_equity e WHERE e.run_id=r.id) max_eq,
 (SELECT MAX(ABS(positions_value)) FROM historical_backtest_daily_equity e WHERE e.run_id=r.id) max_pos,
 (SELECT COUNT(*) FROM historical_backtest_trades t WHERE t.run_id=r.id) trades
FROM historical_backtest_runs r ORDER BY r.id"""
print("SQL:", q.replace("\n"," "))
cols=None
for r in op.execute(q):
    (rid,status,ds,sd,ed,bs,ic,fc,ca,cp,clen,mlen,mj,bj,ew,eqn,eq0,eq1,deq,mineq,maxeq,maxpos,ntr)=r
    print(f"  run {rid:3d} status={status:12s} src={ds:22s} {sd}..{ed} bench={bs} cash={ic}->{fc} eq_rows={eqn} eq_span={eq0}..{eq1} distinct_eq={deq} eq[{mineq},{maxeq}] max|pos|={maxpos} trades={ntr}")
    print(f"        metrics={mj[:400]}")
    print(f"        benchmark_json={bj[:250]}  warnings={ew[:400]}")
op.close()
