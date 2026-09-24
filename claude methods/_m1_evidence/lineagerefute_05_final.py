import sqlite3
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{HIST}?mode=ro", uri=True); c.execute("PRAGMA query_only=ON")
c.execute(f"ATTACH DATABASE 'file:{CACHE}?mode=ro' AS cache")
def show(t,sql):
    cur=c.execute(sql); names=[d[0] for d in cur.description]
    print(f"\n=== {t} ===")
    for row in cur.fetchall(): print("   "+" | ".join(f"{n}={v}" for n,v in zip(names,row)))

show("G. are the 102,711 ready+qfq missing rows the OLDEST per symbol? (truncation test)", """
WITH miss AS (
  SELECT c.symbol, c.trade_date FROM cache.daily_bar_cache c
  WHERE c.quality_status='ready' AND c.adjustment_mode='qfq' AND c.trade_date<>'ERROR'
    AND NOT EXISTS(SELECT 1 FROM main.daily_bars b WHERE b.symbol=c.symbol AND b.trade_date=c.trade_date)
),
kept AS (SELECT symbol, MIN(trade_date) AS first_kept FROM main.daily_bars GROUP BY 1)
SELECT COUNT(*) AS missing_ready_qfq,
       SUM(CASE WHEN m.trade_date < k.first_kept THEN 1 ELSE 0 END) AS older_than_earliest_kept_bar,
       SUM(CASE WHEN k.first_kept IS NULL THEN 1 ELSE 0 END)        AS symbol_absent_from_hist_entirely,
       COUNT(DISTINCT m.symbol) AS symbols_affected
FROM miss m LEFT JOIN kept k ON k.symbol=m.symbol
""")

show("H. bars-per-symbol cap signature in market_history", """
SELECT bars_per_symbol, COUNT(*) AS symbols FROM (
  SELECT symbol, COUNT(*) AS bars_per_symbol FROM main.daily_bars GROUP BY 1
) GROUP BY 1 ORDER BY 2 DESC LIMIT 6
""")

show("I. distinct securities, not rows (stocks only, INDEX excluded)", """
SELECT
 (SELECT COUNT(DISTINCT b.symbol) FROM main.daily_bars b
    JOIN main.instruments i ON i.symbol=b.symbol WHERE i.exchange<>'INDEX')      AS hist_stocks,
 (SELECT COUNT(DISTINCT c.symbol) FROM cache.daily_bar_cache c
    JOIN main.instruments i ON i.symbol=c.symbol WHERE i.exchange<>'INDEX')      AS cache_stocks,
 (SELECT COUNT(DISTINCT c.symbol) FROM cache.daily_bar_cache c
    JOIN main.instruments i ON i.symbol=c.symbol WHERE i.exchange<>'INDEX'
    AND NOT EXISTS(SELECT 1 FROM main.daily_bars b WHERE b.symbol=c.symbol))     AS stocks_in_cache_absent_from_hist
""")

show("J. VALUE-level independence: what survives ONLY in market_history", """
SELECT
 (SELECT COUNT(*) FROM main.daily_bars) AS hist_rows,
 (SELECT COUNT(*) FROM main.daily_bars h JOIN cache.daily_bar_cache k
    ON k.symbol=h.symbol AND k.trade_date=h.trade_date
  WHERE NOT (h.open IS k.open AND h.high IS k.high AND h.low IS k.low AND h.close IS k.close
             AND h.volume IS k.volume AND h.amount IS k.amount AND h.provider IS k.source))
   AS rows_disagreeing_with_cache,
 (SELECT COUNT(*) FROM main.daily_bars WHERE provider='tencent.newfqkline.qfq')
   AS rows_whose_provider_purged_from_cache
""")
