import sqlite3
c=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True); c.execute("PRAGMA query_only=1")
print("=== scope of the 股/手 contamination INSIDE daily_bar_cache (the store the backtest prices from) ===")
q="""
WITH x AS (SELECT symbol, trade_date, volume*1.0 v, source, LAG(volume*1.0) OVER w pv, LAG(source) OVER w ps
           FROM daily_bar_cache WHERE length(trade_date)=10 AND quality_status='ready' AND adjustment_mode='qfq' AND volume>0
           WINDOW w AS (PARTITION BY symbol ORDER BY trade_date)),
 b AS (SELECT DISTINCT symbol FROM x WHERE pv>0 AND source<>ps AND pv/v BETWEEN 20 AND 500)
SELECT (SELECT COUNT(*) FROM b) affected_symbols,
       (SELECT COUNT(*) FROM daily_bar_cache d JOIN b ON b.symbol=d.symbol
         WHERE d.source='tencent.fqkline.qfq' AND length(d.trade_date)=10) tencent_rows_on_those_symbols,
       (SELECT COUNT(*) FROM daily_bar_cache d JOIN b ON b.symbol=d.symbol
         WHERE d.source='tencent.fqkline.qfq' AND d.amount IS NULL AND length(d.trade_date)=10) tencent_rows_amount_null,
       (SELECT COUNT(*) FROM daily_bar_cache d JOIN b ON b.symbol=d.symbol
         WHERE d.source='tencent.fqkline.qfq' AND d.quality_status='ready' AND length(d.trade_date)=10) tencent_ready_rows
"""
print("  ", list(c.execute(q))[0])
print("\n  ALL tencent rows in cache (upper bound on the 股-unit population):",
  c.execute("SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE source='tencent.fqkline.qfq' AND length(trade_date)=10 AND quality_status='ready'").fetchone())
print("\n  these rows are EXACTLY the rows that fall into execution.py's volume-based liquidity proxy:")
print("   tencent ready rows with amount IS NULL:",
  c.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE source='tencent.fqkline.qfq' AND amount IS NULL AND quality_status='ready' AND length(trade_date)=10").fetchone())
print("\n  cross-check: do those same symbols show a matching PRICE jump (i.e. is it a re-fetch, not a unit change)?")
q2="""
WITH x AS (SELECT symbol, trade_date, volume*1.0 v, close*1.0 cl, source, LAG(volume*1.0) OVER w pv,
                  LAG(close*1.0) OVER w pc, LAG(source) OVER w ps
           FROM daily_bar_cache WHERE length(trade_date)=10 AND quality_status='ready' AND adjustment_mode='qfq' AND volume>0 AND close>0
           WINDOW w AS (PARTITION BY symbol ORDER BY trade_date))
SELECT COUNT(*) near100x_vol_drops,
       SUM(CASE WHEN ABS(cl/pc-1)<0.11 THEN 1 ELSE 0 END) with_normal_price_move,
       ROUND(AVG(cl/pc),4) avg_price_ratio
FROM x WHERE pv>0 AND source<>ps AND pv/v BETWEEN 60 AND 200"""
print("  ", list(c.execute(q2))[0])
