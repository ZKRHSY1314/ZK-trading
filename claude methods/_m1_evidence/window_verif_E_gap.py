import sqlite3
TL = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
con = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
con.execute("PRAGMA query_only=ON")
con.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
c = con.cursor()

print("=== look for any trading-calendar table in either DB ===")
for db in ("main", "mh"):
    for r in c.execute(f"SELECT name FROM {db}.sqlite_master WHERE type='table' AND (name LIKE '%calendar%' OR name LIKE '%session%' OR name LIKE '%trading_day%')"):
        print(f"  {db}.{r[0]}")
print()
print("=== ANY row anywhere in window before 2024-04-09? ===")
print("  daily_bar_cache:", c.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date>='2023-09-04' AND trade_date<'2024-04-09' AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'").fetchone()[0])
print("  mh.daily_bars  :", c.execute("SELECT COUNT(*) FROM mh.daily_bars WHERE trade_date>='2023-09-04' AND trade_date<'2024-04-09'").fetchone()[0])
print()
print("=== the ONE index series SH000001 = an independent trading calendar proxy ===")
r = c.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bar_cache WHERE symbol='SH000001'").fetchone()
print("  SH000001 (上证指数) bars:", r)
print("  -> even the index series does not predate 2024-04-09; no calendar evidence exists on disk for 2023-09-04..2024-04-08")
print()
print("=== GAP TEST: does the ramp = suspension artifact of a fixed bar budget? ===")
print("  For ramp symbols: bars_before_2024-06-24  vs  sessions_MISSING after 2024-06-24")
MAIN = c.execute("""SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache
  WHERE trade_date>='2024-06-24' AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'""").fetchone()[0]
print(f"  full-market sessions on/after 2024-06-24 = {MAIN}")
rows = c.execute("""SELECT symbol,
    SUM(CASE WHEN trade_date<'2024-06-24' THEN 1 ELSE 0 END) early,
    SUM(CASE WHEN trade_date>='2024-06-24' THEN 1 ELSE 0 END) late
  FROM daily_bar_cache
  WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
    AND LENGTH(symbol)=8 AND SUBSTR(symbol,1,2) IN ('SH','SZ','BJ')
    AND symbol NOT IN ('SH000001','SH000300')
  GROUP BY 1 HAVING early>0""").fetchall()
import statistics
diffs = [ (MAIN - late) - early for _, early, late in rows ]
inside = sum(1 for d in diffs if -3 <= d <= 3)
print(f"  ramp symbols n={len(rows)}; (missing_late - early) median={statistics.median(diffs)}, "
      f"within +/-3 of zero: {inside}/{len(rows)} = {100*inside/len(rows):.1f}%")
print("  -> a value near 0 means each early bar is EXACTLY compensated by a missing recent bar:")
print("     a fixed per-symbol bar BUDGET, not symbols being added to a watchlist over time.")
print()
print("=== total-bar-budget check: every symbol got the same depth ===")
for r in c.execute("""SELECT n, COUNT(*) FROM (
   SELECT symbol, COUNT(*) n FROM daily_bar_cache
   WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
     AND LENGTH(symbol)=8 AND SUBSTR(symbol,1,2) IN ('SH','SZ','BJ')
     AND symbol NOT IN ('SH000001','SH000300') GROUP BY 1)
   GROUP BY 1 ORDER BY 2 DESC LIMIT 6"""):
    print("   bars_per_symbol =", r[0], " n_symbols =", r[1])
tot = c.execute("""SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   AND LENGTH(symbol)=8 AND SUBSTR(symbol,1,2) IN ('SH','SZ','BJ') AND symbol NOT IN ('SH000001','SH000300')""").fetchone()[0]
print("  stock rows total:", tot, " / 5560 symbols =", round(tot/5560,1), "bars each on average")
con.close()
