import sqlite3, json, collections
OP = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
c.row_factory = sqlite3.Row

print("### Q19 WHEN were the SH000300 benchmark bars written? (dates the backfill)")
for r in c.execute("""
SELECT MIN(created_at) first_created, MAX(created_at) last_created,
       MIN(updated_at) first_updated, MAX(updated_at) last_updated, COUNT(*) n
FROM daily_bar_cache WHERE symbol='SH000300'"""):
    print("  ", dict(r))
print("  rows by created_at date:")
for r in c.execute("SELECT substr(created_at,1,10) d, COUNT(*) n, MIN(trade_date) tf, MAX(trade_date) tl FROM daily_bar_cache WHERE symbol='SH000300' GROUP BY 1 ORDER BY 1"):
    print("    ", tuple(r))

print("\n### Q20 Bars for SH000300 that EXISTED at the time runs 1-37 executed (created_at <= run completed_at)")
q20 = """
SELECT r.id, r.start_date, r.end_date, r.created_at AS run_created,
  (SELECT COUNT(*) FROM daily_bar_cache d
    WHERE d.symbol='SH000300' AND d.quality_status='ready'
      AND d.trade_date>=r.start_date AND d.trade_date<=r.end_date
      AND d.created_at <= r.created_at) AS bars_available_then,
  (SELECT COUNT(*) FROM daily_bar_cache d
    WHERE d.symbol='SH000300' AND d.quality_status='ready'
      AND d.trade_date>=r.start_date AND d.trade_date<=r.end_date) AS bars_available_now,
  json_extract(r.benchmark_json,'$.status') AS stored_status
FROM historical_backtest_runs r WHERE r.id IN (1,8,13,19,36,37,38,39) ORDER BY r.id
"""
for r in c.execute(q20):
    print("  run=%2d %s..%s created=%s  bars_THEN=%3d bars_NOW=%3d stored=%s" %
          (r["id"],r["start_date"],r["end_date"],r["run_created"],r["bars_available_then"],r["bars_available_now"],r["stored_status"]))

print("\n### Q21 learning_backtests - is ANY of the 76 non-empty?")
for r in c.execute("""
SELECT COUNT(*) total,
       SUM(CASE WHEN sample_count>0 THEN 1 ELSE 0 END) with_samples,
       MAX(sample_count) max_samples,
       SUM(CASE WHEN win_rate<>0 OR avg_return<>0 OR max_drawdown<>0 THEN 1 ELSE 0 END) nonzero_metrics,
       COUNT(DISTINCT strategy_name) strategies
FROM learning_backtests"""):
    print("  ", dict(r))

print("\n### Q22 offhour_research_runs.backtest_json - do the 91 runs carry trades/equity the 39-run denominator excludes?")
keys = collections.Counter()
tradecounts = collections.Counter()
persisted = collections.Counter()
for r in c.execute("SELECT id, backtest_json FROM offhour_research_runs WHERE backtest_json NOT IN ('{}','')"):
    j = json.loads(r["backtest_json"])
    for k in j: keys[k]+=1
    m = j.get("metrics") or {}
    tradecounts[(m.get("trade_count"), m.get("closed_trade_count"), m.get("rejected_by_risk_count") is not None)] += 1
    bb = j.get("backtest_budget") or {}
    persisted[bb.get("persisted_historical_backtest")] += 1
print("  top-level keys across 91:", dict(keys.most_common(14)))
print("  (trade_count, closed_trade_count, has_risk_ctr) ->", dict(tradecounts))
print("  persisted_historical_backtest ->", dict(persisted))

row = c.execute("SELECT backtest_json FROM offhour_research_runs WHERE backtest_json NOT IN ('{}','') ORDER BY id DESC LIMIT 1").fetchone()
j = json.loads(row["backtest_json"])
print("\n  latest offhour backtest_json metrics:", json.dumps(j.get("metrics"), ensure_ascii=False)[:700])
print("  trades key:", type(j.get("trades")), len(j.get("trades") or []))
print("  daily_equity key:", type(j.get("daily_equity")), len(j.get("daily_equity") or []))
bh = j.get("benchmark_history")
print("  benchmark_history:", type(bh), len(bh) if hasattr(bh,'__len__') else bh)
c.close()
