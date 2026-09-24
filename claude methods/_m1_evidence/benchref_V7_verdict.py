import sqlite3, json
c=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro", uri=True)
print("### T. benchmark_json status across all 39 runs vs their window coverage")
q="""SELECT json_extract(benchmark_json,'$.status') st, COUNT(*) n,
   MIN(start_date), MAX(end_date),
   SUM(CASE WHEN start_date>='2024-06-19' AND end_date<='2026-09-02' THEN 1 ELSE 0 END) fully_inside_bench_life
 FROM historical_backtest_runs GROUP BY st"""
for r in c.execute(q).fetchall(): print("   status=%-28s n=%-3s window=%s..%s fully_inside_benchmark_coverage=%s"%r)
print()
print("### U. For every run, how many benchmark bars EXIST in its window?")
q2="""SELECT r.id, r.start_date, r.end_date, json_extract(r.benchmark_json,'$.status') st,
 (SELECT COUNT(*) FROM daily_bar_cache d WHERE d.symbol='SH000300'
   AND d.trade_date BETWEEN r.start_date AND r.end_date) bench_bars_available
 FROM historical_backtest_runs r ORDER BY r.id"""
rows=c.execute(q2).fetchall()
for r in rows[:6]: print("   ",r)
print("    ...")
for r in rows[-4:]: print("   ",r)
bad=[r for r in rows if r[3]=='insufficient_benchmark_data']
print()
print(f"   runs reporting insufficient_benchmark_data: {len(bad)}/39")
print(f"   ...of those, min benchmark bars actually available in-window: {min(r[4] for r in bad)}")
print(f"   ...of those, max benchmark bars actually available in-window: {max(r[4] for r in bad)}")
print(f"   => every 'insufficient' run had >={min(r[4] for r in bad)} real benchmark bars on disk. Not a coverage gap.")
c.close()
