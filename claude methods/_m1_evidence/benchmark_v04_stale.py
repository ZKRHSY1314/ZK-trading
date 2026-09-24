import sqlite3, json
OP = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
c.row_factory = sqlite3.Row

print("### Q13 do ANY runs carry the current engine's signal_* metrics keys?")
q13 = """
SELECT
 SUM(CASE WHEN json_extract(metrics_json,'$.signal_evaluated_bars') IS NOT NULL THEN 1 ELSE 0 END) has_signal_evaluated_bars,
 SUM(CASE WHEN json_extract(metrics_json,'$.signal_unknown_ratio')  IS NOT NULL THEN 1 ELSE 0 END) has_signal_unknown_ratio,
 SUM(CASE WHEN json_extract(metrics_json,'$.signal_missing_inputs') IS NOT NULL THEN 1 ELSE 0 END) has_signal_missing_inputs,
 SUM(CASE WHEN json_extract(metrics_json,'$.rejected_by_risk_count') IS NOT NULL THEN 1 ELSE 0 END) has_rejected_by_risk,
 COUNT(*) total_runs
FROM historical_backtest_runs
"""
print("  ", dict(c.execute(q13).fetchone()))

print("\n### Q14 run timestamps (when were these produced?)")
for r in c.execute("SELECT MIN(created_at) first_run, MAX(created_at) last_run, MIN(completed_at) fc, MAX(completed_at) lc FROM historical_backtest_runs"):
    print("  ", dict(r))
for r in c.execute("SELECT id, created_at, completed_at, json_extract(benchmark_json,'$.status') bs FROM historical_backtest_runs WHERE id IN (36,37,38,39) ORDER BY id"):
    print("  ", tuple(r))

print("\n### Q15 THE benchmark filter: engine requires quality_status='ready'. What is SH000300's actual quality_status?")
for r in c.execute("SELECT symbol, quality_status, COUNT(*) n, MIN(trade_date) f, MAX(trade_date) l FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001') GROUP BY symbol, quality_status ORDER BY symbol, n DESC"):
    print("  ", tuple(r))

print("\n### Q16 replicate engine._benchmark's EXACT query for run 19's window (reported insufficient) and run 38's (reported ready)")
q16 = """
SELECT COUNT(*) AS rows_matching_engine_filter
FROM daily_bar_cache
WHERE symbol IN ('SH000300','sh000300')
  AND quality_status = 'ready'
  AND trade_date >= ? AND trade_date <= ?
"""
for rid, s, e in [(19,'2025-10-15','2026-06-12'), (38,'2025-10-15','2026-06-12'), (39,'2025-10-15','2026-06-29'), (1,'2025-10-12','2026-06-09')]:
    n = c.execute(q16, (s,e)).fetchone()[0]
    tot = c.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE symbol='SH000300' AND trade_date>=? AND trade_date<=?", (s,e)).fetchone()[0]
    print(f"  run={rid:2d} {s}..{e}: engine-filter rows={n:4d}  (all quality_status rows={tot:4d})")

print("\n### Q17 sanity: is the index counted as a stock anywhere? distinct symbols in daily_bar_cache")
r=c.execute("SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache").fetchone()[0]
print("  distinct symbols in daily_bar_cache =", r)

print("\n### Q18 alternative backtest evidence stores")
for t,cols in [("learning_backtests","strategy_name, sample_count, win_rate, avg_return, max_drawdown"),
               ("strategy_performance_snapshots","*")]:
    try:
        n=c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"\n  {t}: rows={n}")
        for r in c.execute(f"SELECT {cols} FROM {t} LIMIT 4"):
            print("    ", tuple(r)[:8])
    except Exception as ex:
        print("   ERR", ex)
n=c.execute("SELECT COUNT(*) FROM offhour_research_runs WHERE backtest_json NOT IN ('{}','')").fetchone()[0]
print(f"\n  offhour_research_runs with non-empty backtest_json = {n} / 91")
for r in c.execute("SELECT id, substr(backtest_json,1,400) FROM offhour_research_runs WHERE backtest_json NOT IN ('{}','') ORDER BY id DESC LIMIT 3"):
    print("    run",r[0],":",r[1][:400])
c.close()
