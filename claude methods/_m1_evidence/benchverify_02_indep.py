import sqlite3, json, collections
OP=r"D:/codex-A股交易/trading_local.sqlite3"
c=sqlite3.connect(f"file:{OP}?mode=ro", uri=True); c.row_factory=sqlite3.Row
q=lambda s,p=(): c.execute(s,p).fetchall()

print("### A. Run status / denominator (is '39 of 39' the right denominator?)")
for r in q("SELECT status, COUNT(*) n, COUNT(DISTINCT data_source) ds, MIN(id), MAX(id) FROM historical_backtest_runs GROUP BY status"):
    print(dict(r))
print()
print("### A2. runs WITHOUT any equity row")
print(q("SELECT COUNT(*) FROM historical_backtest_runs r WHERE NOT EXISTS(SELECT 1 FROM historical_backtest_daily_equity e WHERE e.run_id=r.id)")[0][0])
print("### A3. equity rows whose run_id has no parent run (orphans)")
print(q("SELECT COUNT(*) FROM historical_backtest_daily_equity e WHERE NOT EXISTS(SELECT 1 FROM historical_backtest_runs r WHERE r.id=e.run_id)")[0][0])
print()

print("### B. DISTINCT value census (not MIN/MAX) -- my own independent formulation")
for col in ("cash","positions_value","total_equity"):
    rows=q(f"SELECT {col} v, COUNT(*) n FROM historical_backtest_daily_equity GROUP BY {col} ORDER BY n DESC LIMIT 10")
    print(f"  {col}: distinct={q(f'SELECT COUNT(DISTINCT {col}) FROM historical_backtest_daily_equity')[0][0]}  top={[ (r['v'],r['n']) for r in rows]}")
print()

print("### C. WITHIN-run variance (the real test: does ANY run's curve move at all?)")
rows=q("""SELECT run_id, COUNT(*) n, COUNT(DISTINCT total_equity) dq, COUNT(DISTINCT cash) dc,
                 COUNT(DISTINCT positions_value) dp, MIN(trade_date) d0, MAX(trade_date) d1
          FROM historical_backtest_daily_equity GROUP BY run_id ORDER BY run_id""")
moving=[r['run_id'] for r in rows if r['dq']>1 or r['dp']>1 or r['dc']>1]
print(f"  runs with equity rows: {len(rows)}; runs where ANY of the 3 columns takes >1 distinct value: {len(moving)} -> {moving}")
print(f"  total equity rows summed per-run: {sum(r['n'] for r in rows)}")
print()

print("### D. Per-run initial_cash vs its own equity values (join, not a global constant)")
rows=q("""SELECT r.id, r.status, r.initial_cash, r.final_cash, r.start_date, r.end_date, r.data_source,
                 r.benchmark_symbol,
                 COUNT(e.id) n, MIN(e.total_equity) mn, MAX(e.total_equity) mx,
                 MIN(e.trade_date) d0, MAX(e.trade_date) d1
          FROM historical_backtest_runs r LEFT JOIN historical_backtest_daily_equity e ON e.run_id=r.id
          GROUP BY r.id ORDER BY r.id""")
print(f"  {'id':>3} {'status':10} {'init':>9} {'final':>9} {'n':>4} {'minEq':>10} {'maxEq':>10} {'cfg_start':>10} {'cfg_end':>10} {'eq_d0':>10} {'eq_d1':>10} src bench")
for r in rows:
    print(f"  {r['id']:>3} {str(r['status']):10} {str(r['initial_cash']):>9} {str(r['final_cash']):>9} {r['n']:>4} {str(r['mn']):>10} {str(r['mx']):>10} {str(r['start_date']):>10} {str(r['end_date']):>10} {str(r['d0']):>10} {str(r['d1']):>10} {r['data_source']} {r['benchmark_symbol']}")
