import sqlite3, json, collections
OP = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
c.row_factory = sqlite3.Row

print("### Q9 per-run risk-rejection counters via json_extract (NOT zero)")
q9 = """
SELECT id,
       json_extract(metrics_json,'$.rejected_by_risk_count')     AS rejected_by_risk,
       json_extract(metrics_json,'$.rejected_execution_count')   AS rejected_exec,
       json_extract(metrics_json,'$.skipped_due_to_data_count')  AS skipped_data,
       json_extract(metrics_json,'$.blocked_by_regime_count')    AS blocked_regime,
       json_extract(metrics_json,'$.trade_count')                AS trades,
       json_extract(benchmark_json,'$.status')                   AS bench_status,
       start_date, end_date
FROM historical_backtest_runs ORDER BY id
"""
rows=c.execute(q9).fetchall()
for r in rows:
    print("  run=%2d  rejected_by_risk=%5s  rejected_exec=%s  skipped_data=%s  blocked_regime=%s  trades=%s  bench=%s  %s..%s"
          % (r["id"],r["rejected_by_risk"],r["rejected_exec"],r["skipped_data"],r["blocked_regime"],r["trades"],r["bench_status"],r["start_date"],r["end_date"]))

agg = c.execute("""
SELECT COUNT(*) runs,
       SUM(json_extract(metrics_json,'$.rejected_by_risk_count')) total_risk_rejections,
       MIN(json_extract(metrics_json,'$.rejected_by_risk_count')) min_rr,
       MAX(json_extract(metrics_json,'$.rejected_by_risk_count')) max_rr,
       COUNT(DISTINCT json_extract(metrics_json,'$.rejected_by_risk_count')) distinct_rr,
       SUM(CASE WHEN json_extract(metrics_json,'$.rejected_by_risk_count')>0 THEN 1 ELSE 0 END) runs_with_signals
FROM historical_backtest_runs
""").fetchone()
print("\n  AGGREGATE:", dict(agg))

print("\n### Q10 config_json distinct shapes")
cc = collections.Counter()
for r in c.execute("SELECT id, config_json FROM historical_backtest_runs ORDER BY id"):
    cfg = json.loads(r["config_json"])
    cc[json.dumps(cfg, sort_keys=True, ensure_ascii=False)] += 1
for k,v in cc.most_common():
    print(f"  n={v}: {k[:600]}")

print("\n### Q11 does the benchmark index SH000300 exist in daily_bar_cache?")
for sym in ("SH000300","000300","sh000300","SH000001","SZ399001","SH000905","SH000016"):
    r = c.execute("SELECT COUNT(*) n, MIN(trade_date) f, MAX(trade_date) l FROM daily_bar_cache WHERE symbol=?", (sym,)).fetchone()
    print(f"  symbol={sym:10s} rows={r['n']:6d} range={r['f']}..{r['l']}")
print("  -- any symbol starting with SH000 / 000 index-like:")
for r in c.execute("SELECT symbol, COUNT(*) n, MIN(trade_date) f, MAX(trade_date) l FROM daily_bar_cache WHERE symbol LIKE 'SH000%' GROUP BY symbol ORDER BY n DESC LIMIT 15"):
    print("   ", tuple(r))

print("\n### Q12 benchmark window coverage: bars for SH000300 inside each run window")
for r in c.execute("""
SELECT r.id, r.start_date, r.end_date,
 (SELECT COUNT(*) FROM daily_bar_cache d WHERE d.symbol=r.benchmark_symbol AND d.trade_date>=r.start_date AND d.trade_date<=r.end_date) AS bench_bars,
 (SELECT COUNT(*) FROM historical_backtest_daily_equity e WHERE e.run_id=r.id) AS eq_rows,
 json_extract(r.benchmark_json,'$.status') AS bstat
FROM historical_backtest_runs r ORDER BY r.id"""):
    print("  run=%2d %s..%s bench_bars=%d eq_rows=%d status=%s" % tuple(r))
c.close()
