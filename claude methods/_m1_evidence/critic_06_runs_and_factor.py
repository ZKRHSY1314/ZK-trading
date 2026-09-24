import sqlite3, time, statistics
def ro(p):
    c=sqlite3.connect(f"file:{p}?mode=ro",uri=True); c.execute("PRAGMA query_only=1"); return c
tl=ro(r"D:/codex-A股交易/trading_local.sqlite3")
print("=== 39 backtest runs: requested windows vs available data (report never checks this) ===")
for r in tl.execute("SELECT start_date, end_date, COUNT(*) n, MIN(created_at), MAX(created_at) FROM historical_backtest_runs GROUP BY 1,2 ORDER BY n DESC"):
    print("  ", r)
print("  runs whose start_date precedes the earliest bar 2024-04-09:",
      tl.execute("SELECT COUNT(*) FROM historical_backtest_runs WHERE start_date < '2024-04-09'").fetchone()[0])
print("  runs whose start_date precedes the dense start 2024-06-24:",
      tl.execute("SELECT COUNT(*) FROM historical_backtest_runs WHERE start_date < '2024-06-24'").fetchone()[0])

print("\n=== OFFLINE ADJUSTMENT-FACTOR RECOVERY (report S6.1/U11 claim no factor is recoverable) ===")
print("implied raw VWAP = amount / (volume*100); ratio = implied_vwap / qfq_close  ~= raw/qfq factor")
t0=time.time()
q = """
SELECT substr(trade_date,1,4) yr, COUNT(*) n,
       SUM(CASE WHEN r BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END) near1,
       SUM(CASE WHEN r > 1.02 THEN 1 ELSE 0 END) gt,
       SUM(CASE WHEN r < 0.98 THEN 1 ELSE 0 END) lt,
       ROUND(MIN(r),4), ROUND(MAX(r),4), ROUND(AVG(r),4)
FROM (SELECT trade_date, amount/(volume*100.0)/close AS r
      FROM daily_bar_cache
      WHERE length(trade_date)=10 AND quality_status='ready' AND adjustment_mode='qfq'
        AND amount IS NOT NULL AND amount>0 AND volume>0 AND close>0
        AND low>0 AND high>0)
GROUP BY 1 ORDER BY 1"""
print("yr | n | ratio_in[0.98,1.02] | >1.02 | <0.98 | min | max | avg")
for r in tl.execute(q): print("  ", r)
print("elapsed %.1fs" % (time.time()-t0))

print("\n  sanity: implied VWAP must lie within [low,high] when prices and amount share a scale")
r = tl.execute("""
SELECT COUNT(*) n,
       SUM(CASE WHEN v BETWEEN low AND high THEN 1 ELSE 0 END) inside,
       SUM(CASE WHEN v < low THEN 1 ELSE 0 END) below,
       SUM(CASE WHEN v > high THEN 1 ELSE 0 END) above
FROM (SELECT amount/(volume*100.0) v, low, high FROM daily_bar_cache
      WHERE length(trade_date)=10 AND quality_status='ready' AND adjustment_mode='qfq'
        AND amount>0 AND volume>0 AND low>0)""").fetchone()
print("   ", r)

print("\n=== per-symbol factor drift = an offline corporate-action detector ===")
r = tl.execute("""
WITH f AS (SELECT symbol, trade_date, amount/(volume*100.0)/close AS r FROM daily_bar_cache
           WHERE length(trade_date)=10 AND quality_status='ready' AND adjustment_mode='qfq'
             AND amount>0 AND volume>0 AND close>0),
     g AS (SELECT symbol, COUNT(*) n, MIN(r) mn, MAX(r) mx FROM f GROUP BY symbol HAVING n>=100)
SELECT COUNT(*) syms, SUM(mx/mn > 1.05) drift_gt5pct, SUM(mx/mn > 1.5) drift_gt50pct, SUM(mx/mn > 2.0) drift_gt2x
FROM g""").fetchone()
print("   symbols with >=100 priced rows:", r)
