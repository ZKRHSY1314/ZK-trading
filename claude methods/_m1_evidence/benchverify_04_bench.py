import sqlite3, json
OP=r"D:/codex-A股交易/trading_local.sqlite3"
c=sqlite3.connect(f"file:{OP}?mode=ro", uri=True); c.row_factory=sqlite3.Row
q=lambda s,p=(): c.execute(s,p).fetchall()

print("### I. which runs resolved the benchmark, and their windows/created_at")
for r in q("""SELECT id,start_date,end_date,created_at,completed_at,
                     json_extract(benchmark_json,'$.status') st
              FROM historical_backtest_runs ORDER BY id"""):
    if r["st"]=="ready": print("  READY ", dict(r))
print("  (all others: insufficient_benchmark_data)")
print()

print("### J. Does SH000300 exist in daily_bar_cache at all? (exact engine predicate)")
for sym in ("SH000300","sh000300","000300","000300.SH","SHSE.000300"):
    row=q("SELECT COUNT(*) n, MIN(trade_date) d0, MAX(trade_date) d1 FROM daily_bar_cache WHERE symbol=?",(sym,))[0]
    rdy=q("SELECT COUNT(*) n, MIN(trade_date) d0, MAX(trade_date) d1 FROM daily_bar_cache WHERE symbol=? AND quality_status='ready'",(sym,))[0]
    print(f"  {sym:14s} all={row['n']:6d} [{row['d0']},{row['d1']}]   quality_ready={rdy['n']:6d} [{rdy['d0']},{rdy['d1']}]")
print()

print("### K. quality_status census for SH000300")
for r in q("SELECT quality_status, COUNT(*) n, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE symbol IN ('SH000300','sh000300') GROUP BY quality_status"):
    print("  ", tuple(r))
print()

print("### L. Replay the engine's exact benchmark query per run window")
for r in q("SELECT id,start_date,end_date FROM historical_backtest_runs ORDER BY id"):
    n=q("""SELECT COUNT(*) FROM daily_bar_cache
           WHERE symbol IN ('SH000300','sh000300') AND quality_status='ready'
             AND trade_date>=? AND trade_date<=?""",(r["start_date"],r["end_date"]))[0][0]
    nn=q("""SELECT COUNT(*) FROM daily_bar_cache
           WHERE symbol IN ('SH000300','sh000300') AND quality_status='ready'
             AND trade_date>=? AND trade_date<=? AND close IS NOT NULL""",(r["start_date"],r["end_date"]))[0][0]
    if r["id"] in (1,8,13,19,39) or n>=2:
        print(f"  run {r['id']:>2} [{r['start_date']}..{r['end_date']}] rows_ready={n} with_close={nn}")
print()

print("### M. ANY index-like symbols in daily_bar_cache?")
for r in q("""SELECT symbol, COUNT(*) n, MIN(trade_date) d0, MAX(trade_date) d1
              FROM daily_bar_cache
              WHERE symbol LIKE 'SH000%' OR symbol LIKE 'SZ399%' OR symbol LIKE '%000300%'
              GROUP BY symbol ORDER BY n DESC LIMIT 25"""):
    print("  ", tuple(r))
