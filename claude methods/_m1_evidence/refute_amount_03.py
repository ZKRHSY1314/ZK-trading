import sqlite3
LOC = r"D:/codex-A股交易/trading_local.sqlite3"
HIS = r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{HIS}?mode=ro", uri=True)
con.execute(f"ATTACH DATABASE 'file:{LOC}?mode=ro' AS cache")
def show(t, s):
    print("="*90); print(t); print("-- SQL:", " ".join(s.split()))
    for r in con.execute(s).fetchall(): print("   ", r)

# C1 symbol format distribution -- B7 showed 'BJ920000' vs '000001'
show("C1 hist symbol formats", """
SELECT CASE WHEN symbol GLOB '[A-Z][A-Z]*' THEN 'prefixed' ELSE 'bare' END fmt,
COUNT(DISTINCT symbol) syms, COUNT(*) rows FROM main.daily_bars GROUP BY fmt""")
show("C1b cache symbol formats", """
SELECT CASE WHEN symbol GLOB '[A-Z][A-Z]*' THEN 'prefixed' ELSE 'bare' END fmt,
COUNT(DISTINCT symbol) syms, COUNT(*) rows FROM cache.daily_bar_cache GROUP BY fmt""")

# C2 THE LOSS DENOMINATOR: net regression vs status quo
show("C2 net regression accounting", """
SELECT COUNT(*) hist_rows,
 SUM(CASE WHEN (b.amount IS NULL OR b.amount<=0) AND c.amount>0 THEN 1 ELSE 0 END) net_loss_rows,
 ROUND(100.0*SUM(CASE WHEN (b.amount IS NULL OR b.amount<=0) AND c.amount>0 THEN 1 ELSE 0 END)/COUNT(*),3) pct_net_loss,
 SUM(CASE WHEN (b.amount IS NULL OR b.amount<=0) AND (c.amount IS NULL OR c.amount<=0) THEN 1 ELSE 0 END) already_proxied_today,
 ROUND(100.0*SUM(CASE WHEN (b.amount IS NULL OR b.amount<=0) AND (c.amount IS NULL OR c.amount<=0) THEN 1 ELSE 0 END)/COUNT(*),3) pct_status_quo
FROM main.daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date""")

# C3 distinct securities affected (not just rows)
show("C3 distinct symbols affected", """
SELECT COUNT(DISTINCT b.symbol) syms_with_any_net_loss FROM main.daily_bars b
JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
WHERE (b.amount IS NULL OR b.amount<=0) AND c.amount>0""")
show("C3b symbols wholly amount-less in hist", """
SELECT COUNT(*) FROM (SELECT symbol FROM main.daily_bars GROUP BY symbol
HAVING SUM(amount>0)=0)""")

# C4 IS THE PROXY EVEN AVAILABLE? volume on the NULL-amount hist rows
show("C4 volume availability on amount-less hist rows", """
SELECT COUNT(*) amountless, SUM(volume IS NULL OR volume<=0) also_no_volume,
 SUM(volume>0) has_volume, volume_unit
FROM main.daily_bars WHERE amount IS NULL OR amount<=0 GROUP BY volume_unit""")

# C5 UNIT/SCALE compatibility of amount where BOTH populated (is backfill valid?)
show("C5 amount agreement where both >0", """
SELECT COUNT(*) both_pos,
 SUM(ABS(b.amount-c.amount)/c.amount < 0.01) within_1pct,
 SUM(ABS(b.amount-c.amount)/c.amount >= 0.01) differ_ge_1pct,
 ROUND(AVG(b.amount/c.amount),6) avg_ratio,
 ROUND(MIN(b.amount/c.amount),6) min_ratio, ROUND(MAX(b.amount/c.amount),6) max_ratio
FROM main.daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
WHERE b.amount>0 AND c.amount>0""")

# C6 time profile of the net loss -- is it old history or recent?
show("C6 net loss by year", """
SELECT substr(b.trade_date,1,4) yr, COUNT(*) rows,
 SUM(CASE WHEN (b.amount IS NULL OR b.amount<=0) AND c.amount>0 THEN 1 ELSE 0 END) net_loss,
 ROUND(100.0*SUM(CASE WHEN (b.amount IS NULL OR b.amount<=0) AND c.amount>0 THEN 1 ELSE 0 END)/COUNT(*),2) pct
FROM main.daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
GROUP BY yr ORDER BY yr""")

# C7 actual date range of hist (window claim)
show("C7 hist date range", "SELECT MIN(trade_date), MAX(trade_date) FROM main.daily_bars")
show("C7b cache date range", "SELECT MIN(trade_date), MAX(trade_date) FROM cache.daily_bar_cache")
