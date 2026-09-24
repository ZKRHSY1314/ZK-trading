import sqlite3
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{HIST}?mode=ro", uri=True); c.execute("PRAGMA query_only=ON")
c.execute(f"ATTACH DATABASE 'file:{CACHE}?mode=ro' AS cache")

print("=== A. which field diverges? (full-store, no sampling) ===")
SQL_A = """
SELECT
 COUNT(*)                                                              AS matched_pairs,
 SUM(h.provider   IS NOT k.source)                                     AS provider_differs,
 SUM(h.volume_unit IS NOT k.volume_unit)                               AS volume_unit_differs,
 SUM(h.close      IS NOT k.close)                                      AS close_differs,
 SUM(h.open IS NOT k.open OR h.high IS NOT k.high
     OR h.low IS NOT k.low OR h.close IS NOT k.close)                  AS any_ohlc_differs,
 SUM(h.volume     IS NOT k.volume)                                     AS volume_differs,
 SUM(h.amount     IS NOT k.amount)                                     AS amount_differs,
 SUM(h.open IS k.open AND h.high IS k.high AND h.low IS k.low
     AND h.close IS k.close AND h.volume IS k.volume
     AND h.amount IS k.amount AND h.provider IS k.source
     AND h.volume_unit IS k.volume_unit)                               AS fully_identical
FROM main.daily_bars h
JOIN cache.daily_bar_cache k ON k.symbol=h.symbol AND k.trade_date=h.trade_date
"""
cols = [d[0] for d in c.execute(SQL_A).description] if False else None
cur = c.execute(SQL_A); names=[d[0] for d in cur.description]; vals=cur.fetchone()
for n,v in zip(names, vals): print(f"   {n:24s} = {v:,}")

print("\n=== B. provider(hist) x source(cache) crosstab, top 15 ===")
for r in c.execute("""
SELECT h.provider AS hist_provider, k.source AS cache_source, COUNT(*) AS n
FROM main.daily_bars h
JOIN cache.daily_bar_cache k ON k.symbol=h.symbol AND k.trade_date=h.trade_date
GROUP BY 1,2 ORDER BY 3 DESC LIMIT 15"""):
    print(f"   {str(r[0])[:46]:46s} | {str(r[1])[:46]:46s} | {r[2]:,}")

print("\n=== C. distinct providers on each side ===")
print(" hist.daily_bars.provider:")
for r in c.execute("SELECT provider, COUNT(*) FROM main.daily_bars GROUP BY 1 ORDER BY 2 DESC"):
    print(f"    {str(r[0])[:60]:60s} {r[1]:,}")
print(" cache.daily_bar_cache.source:")
for r in c.execute("SELECT source, COUNT(*) FROM cache.daily_bar_cache GROUP BY 1 ORDER BY 2 DESC"):
    print(f"    {str(r[0])[:60]:60s} {r[1]:,}")

print("\n=== D. side-by-side examples where OHLC differs ===")
for r in c.execute("""
SELECT h.symbol,h.trade_date,h.close,k.close,h.volume,k.volume,h.amount,k.amount,
       h.provider,k.source,h.updated_at,k.updated_at
FROM main.daily_bars h
JOIN cache.daily_bar_cache k ON k.symbol=h.symbol AND k.trade_date=h.trade_date
WHERE h.close IS NOT k.close LIMIT 8"""):
    print(f"   {r[0]} {r[1]} close h={r[2]} k={r[3]} | vol h={r[4]} k={r[5]} | amt h={r[6]} k={r[7]}")
    print(f"        prov h={r[8]} k={r[9]}  upd h={r[10]} k={r[11]}")
