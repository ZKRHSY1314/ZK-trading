import sqlite3
c=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True); c.execute("PRAGMA query_only=1")
print("=== Is the PRICING store itself unit-contaminated? (report only tested market_history) ===")
print("For symbols carrying both a tencent (amount NULL) and a sina (amount present) vintage in daily_bar_cache,")
print("compare per-symbol mean volume per source. A ~100x ratio would mean the backtest store has the same bug.")
q="""
WITH s AS (SELECT symbol, source, AVG(volume*1.0) av, COUNT(*) n FROM daily_bar_cache
           WHERE length(trade_date)=10 AND quality_status='ready' AND volume>0
             AND source IN ('tencent.fqkline.qfq','akshare.stock_zh_a_daily') GROUP BY 1,2),
     t AS (SELECT symbol, MAX(CASE WHEN source='tencent.fqkline.qfq' THEN av END) tv,
                  MAX(CASE WHEN source='akshare.stock_zh_a_daily' THEN av END) sv,
                  MAX(CASE WHEN source='tencent.fqkline.qfq' THEN n END) tn
           FROM s GROUP BY 1)
SELECT CASE WHEN tv/sv < 0.5 THEN 'a <0.5x' WHEN tv/sv <= 2 THEN 'b 0.5-2x'
            WHEN tv/sv < 20 THEN 'c 2-20x' WHEN tv/sv <= 200 THEN 'd 20-200x' ELSE 'e >200x' END band,
       COUNT(*) syms, SUM(tn) tencent_rows
FROM t WHERE tv IS NOT NULL AND sv IS NOT NULL AND sv>0 GROUP BY 1 ORDER BY 1"""
for r in c.execute(q): print("  ", r)
print("\n  tencent-sourced cache rows with NO amount anywhere (U10 blind spot):",
      c.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE source='tencent.fqkline.qfq' AND amount IS NULL AND length(trade_date)=10").fetchone())
print("\n=== stale-vintage exposure of the PRICING store by year (report gives only a 2-month split) ===")
for r in c.execute("""SELECT substr(trade_date,1,4) yr, COUNT(*) rows, SUM(amount IS NULL) amt_null,
       ROUND(100.0*SUM(amount IS NULL)/COUNT(*),2) pct_null, COUNT(DISTINCT source) srcs
FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY 1"""): print("  ", r)
print("\n=== per-symbol source mixing inside the pricing store (splice exposure, cache side) ===")
for r in c.execute("""SELECT nsrc, COUNT(*) syms FROM (SELECT symbol, COUNT(DISTINCT source) nsrc FROM daily_bar_cache
 WHERE length(trade_date)=10 AND quality_status='ready' GROUP BY 1) GROUP BY 1 ORDER BY 1"""): print("  ", r)
