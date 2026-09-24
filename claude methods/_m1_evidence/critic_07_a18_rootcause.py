import sqlite3, time
c=sqlite3.connect(f"file:D:/codex-A股交易/market_history.sqlite3?mode=ro",uri=True)
c.execute("PRAGMA query_only=1")
c.execute("ATTACH DATABASE 'file:D:/codex-A股交易/trading_local.sqlite3?mode=ro' AS tl")
print("attached dbs:", list(c.execute("PRAGMA database_list")))
t0=time.time()
print("\n=== A18 ROOT CAUSE: which provider produced the 100x rows? (report blames 'tencent系' without measuring) ===")
q="""SELECT b.provider, c2.source, COUNT(*) n, MIN(b.trade_date), MAX(b.trade_date), COUNT(DISTINCT b.symbol) syms
FROM daily_bars b JOIN tl.daily_bar_cache c2 ON c2.symbol=b.symbol AND c2.trade_date=b.trade_date
WHERE c2.volume>0 AND b.volume>0 AND b.volume/c2.volume BETWEEN 99 AND 101
GROUP BY 1,2 ORDER BY n DESC"""
for r in c.execute(q): print("  ", r)
print("elapsed %.1fs"%(time.time()-t0))

print("\n=== inverse direction: rows where mh.volume is 1/100 of cache (would mean CACHE is the wrong one) ===")
for r in c.execute("""SELECT b.provider, c2.source, COUNT(*) n FROM daily_bars b
 JOIN tl.daily_bar_cache c2 ON c2.symbol=b.symbol AND c2.trade_date=b.trade_date
 WHERE c2.volume>0 AND b.volume>0 AND c2.volume/b.volume BETWEEN 99 AND 101 GROUP BY 1,2 ORDER BY n DESC"""):
    print("  ", r)

print("\n=== which store's volume is right? implied VWAP from cache.amount must sit near [low,high] ===")
r=c.execute("""SELECT
  COUNT(*) n,
  SUM(CASE WHEN c2.amount/(c2.volume*100.0) BETWEEN c2.low*0.5 AND c2.high*3 THEN 1 ELSE 0 END) cache_vol_plausible,
  SUM(CASE WHEN c2.amount/(b.volume*100.0) BETWEEN c2.low*0.5 AND c2.high*3 THEN 1 ELSE 0 END) mh_vol_plausible
FROM daily_bars b JOIN tl.daily_bar_cache c2 ON c2.symbol=b.symbol AND c2.trade_date=b.trade_date
WHERE c2.volume>0 AND b.volume>0 AND b.volume/c2.volume BETWEEN 99 AND 101 AND c2.amount>0 AND c2.low>0""").fetchone()
print("   (n, cache_volume_plausible, mh_volume_plausible) =", r)

print("\n=== does the 100x band understate the problem? full ratio histogram ===")
for r in c.execute("""SELECT CASE
   WHEN vr < 0.011 THEN 'a <1/90'
   WHEN vr < 0.9 THEN 'b 0.011-0.9'
   WHEN vr <= 1.1 THEN 'c ~1'
   WHEN vr < 90 THEN 'd 1.1-90'
   WHEN vr <= 110 THEN 'e ~100'
   ELSE 'f >110' END band, COUNT(*), COUNT(DISTINCT sym)
FROM (SELECT b.volume/c2.volume vr, b.symbol sym FROM daily_bars b
      JOIN tl.daily_bar_cache c2 ON c2.symbol=b.symbol AND c2.trade_date=b.trade_date
      WHERE c2.volume>0 AND b.volume>0) GROUP BY 1 ORDER BY 1"""):
    print("  ", r)
print("elapsed %.1fs"%(time.time()-t0))
