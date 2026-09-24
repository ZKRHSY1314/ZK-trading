import sqlite3
LOC = r"D:/codex-A股交易/trading_local.sqlite3"
HIS = r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{HIS}?mode=ro", uri=True)
con.execute(f"ATTACH DATABASE 'file:{LOC}?mode=ro' AS cache")
def show(t, s):
    print("="*90); print(t); print("-- SQL:", " ".join(s.split()))
    for r in con.execute(s).fetchall(): print("   ", r)

# B1 join fan-out check: is (symbol,trade_date) unique in hist? (PK includes adj_mode)
show("B1 hist duplicate (symbol,trade_date)", """
SELECT COUNT(*) FROM (SELECT symbol,trade_date FROM main.daily_bars
GROUP BY symbol,trade_date HAVING COUNT(*)>1)""")

# B2 INDEX contamination: are index symbols inflating either side?
show("B2 hist rows by instrument exchange x amount-null", """
SELECT i.exchange, COUNT(*) rows, SUM(b.amount IS NULL) amt_null
FROM main.daily_bars b JOIN main.instruments i USING(symbol)
GROUP BY i.exchange ORDER BY rows DESC""")

# B3 STOCKS ONLY (exclude INDEX/OTHER), full store
show("B3 hist STOCK-only null rate", """
SELECT COUNT(*) rows, SUM(b.amount IS NULL OR b.amount<=0) unusable,
 ROUND(100.0*SUM(b.amount IS NULL OR b.amount<=0)/COUNT(*),3) pct
FROM main.daily_bars b JOIN main.instruments i USING(symbol)
WHERE i.exchange IN ('SH','SZ','BJ')""")

# B4 RESEARCH WINDOW 2023-09-04..2026-09-04, stocks only, both stores
show("B4 window hist stocks", """
SELECT COUNT(*) rows, SUM(b.amount IS NULL OR b.amount<=0) unusable,
 ROUND(100.0*SUM(b.amount IS NULL OR b.amount<=0)/COUNT(*),3) pct
FROM main.daily_bars b JOIN main.instruments i USING(symbol)
WHERE i.exchange IN ('SH','SZ','BJ') AND b.trade_date BETWEEN '2023-09-04' AND '2026-09-04'""")
show("B4b window cache (all symbols)", """
SELECT COUNT(*) rows, SUM(amount IS NULL OR amount<=0) unusable,
 ROUND(100.0*SUM(amount IS NULL OR amount<=0)/COUNT(*),3) pct
FROM cache.daily_bar_cache
WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'""")

# B5 THE REAL QUESTION: after a symbol/date backfill from cache, what is TRULY lost?
show("B5 full outer picture (hist rows only)", """
SELECT
 COUNT(*) hist_rows,
 SUM(CASE WHEN c.symbol IS NULL THEN 1 ELSE 0 END) hist_only_no_cache_row,
 SUM(CASE WHEN (b.amount IS NULL OR b.amount<=0) AND c.amount>0 THEN 1 ELSE 0 END) recoverable,
 SUM(CASE WHEN (b.amount IS NULL OR b.amount<=0) AND (c.amount IS NULL OR c.amount<=0) THEN 1 ELSE 0 END) unusable_in_both,
 SUM(CASE WHEN b.amount>0 AND (c.amount IS NULL OR c.amount<=0) THEN 1 ELSE 0 END) hist_better_than_cache
FROM main.daily_bars b LEFT JOIN cache.daily_bar_cache c
  ON c.symbol=b.symbol AND c.trade_date=b.trade_date""")

# B6 does the CACHE have rows hist lacks, and vice versa (coverage direction)
show("B6 cache-only rows", """
SELECT COUNT(*) FROM cache.daily_bar_cache c
LEFT JOIN main.daily_bars b ON b.symbol=c.symbol AND b.trade_date=c.trade_date
WHERE b.symbol IS NULL""")

# B7 symbol-format mismatch risk between stores (would fake a 0 in 'hist better')
show("B7 symbol format samples", """
SELECT 'hist' src, symbol FROM main.daily_bars LIMIT 3""")
show("B7b", "SELECT 'cache' src, symbol FROM cache.daily_bar_cache LIMIT 3")
show("B7c distinct symbols overlap", """
SELECT (SELECT COUNT(DISTINCT symbol) FROM main.daily_bars) hist_syms,
       (SELECT COUNT(DISTINCT symbol) FROM cache.daily_bar_cache) cache_syms,
       (SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM main.daily_bars
         INTERSECT SELECT DISTINCT symbol FROM cache.daily_bar_cache)) shared""")
