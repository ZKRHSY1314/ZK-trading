import sqlite3, sys
from datetime import date, timedelta
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
TL = r"D:/codex-A股交易/trading_local.sqlite3"; MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl, mh = ro(TL), ro(MH); a, b = tl.cursor(), mh.cursor()
GL = "trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"

print("### 12. VERIFY their month sub-numbers exactly")
for m in ('2024-04','2024-05','2024-06'):
    r = a.execute(f"SELECT COUNT(*), COUNT(DISTINCT symbol), COUNT(DISTINCT trade_date) FROM daily_bar_cache "
                  f"WHERE {GL} AND substr(trade_date,1,7)=?", (m,)).fetchone()
    print(f"   cache {m}: rows={r[0]} distinct_symbols={r[1]} sessions={r[2]}")

print()
print("### 13. EXACT SIZE OF THE HOLE (they said '~9.5 months no data at all')")
r = a.execute(f"SELECT COUNT(*) FROM daily_bar_cache WHERE {GL} AND trade_date BETWEEN '2023-09-04' AND '2024-06-23'").fetchone()[0]
print(f"   cache rows in 2023-09-04..2024-06-23: {r}   <- NOT zero, so 'no data at all' is imprecise for the tail")
r2 = a.execute(f"SELECT COUNT(*) FROM daily_bar_cache WHERE {GL} AND trade_date BETWEEN '2023-09-04' AND '2024-04-08'").fetchone()[0]
print(f"   cache rows in 2023-09-04..2024-04-08 (TRUE empty region): {r2}")
print("   -> true zero-data span = 2023-09-04..2024-04-08 = 218 calendar days ~ 7.2 months")
print("   -> negligible-data span = 2024-04-09..2024-06-21 (<1000 stocks/session)")

print()
print("### 14. SESSION-LEVEL WINDOW COVERAGE (weekday proxy for expected A-share sessions)")
d0, d1 = date(2023,9,4), date(2026,9,4)
wk = sum(1 for i in range((d1-d0).days+1) if (d0+timedelta(days=i)).weekday() < 5)
have = a.execute(f"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE {GL} "
                 f"AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'").fetchone()[0]
usable = a.execute(f"SELECT COUNT(*) FROM (SELECT trade_date FROM daily_bar_cache WHERE {GL} "
                   f"AND trade_date BETWEEN '2023-09-04' AND '2026-09-04' GROUP BY trade_date "
                   f"HAVING COUNT(DISTINCT symbol)>=1000)").fetchone()[0]
print(f"   weekdays in window (upper bound on sessions, incl. holidays): {wk}")
print(f"   distinct trade_dates present in cache within window: {have}")
print(f"   sessions with >=1000 distinct symbols (usable breadth):  {usable}")
print(f"   usable/weekday ratio: {usable/wk:.1%}  (holiday-adjusted true sessions ~730, ratio ~{usable/730:.1%})")

print()
print("### 15. CROSS-STORE: does market_history hold ANY date the cache lacks (or vice versa)?")
cd = set(x[0] for x in a.execute(f"SELECT DISTINCT trade_date FROM daily_bar_cache WHERE {GL}"))
md = set(x[0] for x in b.execute(f"SELECT DISTINCT trade_date FROM daily_bars WHERE {GL}"))
print(f"   cache sessions={len(cd)} mh sessions={len(md)}")
print(f"   in mh but NOT in cache: {sorted(md-cd)}")
print(f"   in cache but NOT in mh: {sorted(cd-md)}")
print(f"   UNION of both stores = {len(cd|md)} sessions -- still far short of ~730")
tl.close(); mh.close()
