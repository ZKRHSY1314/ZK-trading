import sqlite3,time
c=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True); c.execute("PRAGMA query_only=1")
t0=time.time()
print("=== decisive test: volume discontinuity ACROSS source-switch boundaries INSIDE daily_bar_cache ===")
q="""
WITH x AS (
  SELECT symbol, trade_date, volume*1.0 v, source,
         LAG(volume*1.0) OVER w pv, LAG(source) OVER w ps
  FROM daily_bar_cache
  WHERE length(trade_date)=10 AND quality_status='ready' AND adjustment_mode='qfq' AND volume>0
  WINDOW w AS (PARTITION BY symbol ORDER BY trade_date)
)
SELECT CASE WHEN source<>ps THEN 'BOUNDARY' ELSE 'non-boundary' END grp,
       COUNT(*) pairs,
       SUM(CASE WHEN v/pv BETWEEN 20 AND 500 THEN 1 ELSE 0 END) up20_500x,
       SUM(CASE WHEN pv/v BETWEEN 20 AND 500 THEN 1 ELSE 0 END) down20_500x,
       SUM(CASE WHEN v/pv BETWEEN 60 AND 200 THEN 1 ELSE 0 END) up_near100x,
       SUM(CASE WHEN pv/v BETWEEN 60 AND 200 THEN 1 ELSE 0 END) down_near100x
FROM x WHERE pv IS NOT NULL AND pv>0 GROUP BY 1"""
for r in c.execute(q): print("  ", r)
print("elapsed %.1fs"%(time.time()-t0))
print("\n  examples of near-100x volume jumps at a source boundary (if any):")
q2="""
WITH x AS (SELECT symbol, trade_date, volume*1.0 v, source, LAG(volume*1.0) OVER w pv, LAG(source) OVER w ps,
                  LAG(trade_date) OVER w pd
           FROM daily_bar_cache WHERE length(trade_date)=10 AND quality_status='ready' AND adjustment_mode='qfq' AND volume>0
           WINDOW w AS (PARTITION BY symbol ORDER BY trade_date))
SELECT symbol, pd, trade_date, ps, source, pv, v, ROUND(v/pv,1) ratio FROM x
WHERE pv>0 AND source<>ps AND (v/pv BETWEEN 60 AND 200 OR pv/v BETWEEN 60 AND 200) LIMIT 10"""
for r in c.execute(q2): print("   ", r)
