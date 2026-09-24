import sqlite3, sys, time
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
SQL = ("SELECT trade_date, COUNT(*) n FROM daily_bar_cache "
       "WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "
       "AND trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND quality_status='ready' "
       "GROUP BY trade_date ORDER BY trade_date")
print("### G1 SQL:", SQL)
t=time.time()
rows = c.execute(SQL).fetchall()
print(f"distinct trade_dates with ready bars in window: {len(rows)}   [{time.time()-t:.1f}s]")
print("first 5:", rows[:5]); print("last 5:", rows[-5:])
dense = [d for d,n in rows if n>=3000]
print("trade_dates with >=3000 ready bars:", len(dense), "range:", dense[0] if dense else None, "..", dense[-1] if dense else None)
thin = [(d,n) for d,n in rows if n<3000]
print("thin dates (<3000 bars):", len(thin))
for d,n in thin[:40]: print("   ", d, n)
if len(thin)>40: print("   ...")
# per-year
from collections import Counter
yr = Counter(d[:4] for d,_ in rows); yrd = Counter(d[:4] for d in dense)
print("\ntrade_dates per calendar year (all / dense>=3000):")
for y in sorted(yr): print("   ", y, yr[y], yrd.get(y,0))
# monthly dense counts for split design
mo = Counter(d[:7] for d in dense)
print("\ndense trade-day count per month:")
for m in sorted(mo): print("   ", m, mo[m])
print("\n### G2 index/benchmark symbols present")
SQL2=("SELECT symbol, COUNT(*) n, MIN(trade_date), MAX(trade_date), source FROM daily_bar_cache "
      "WHERE symbol LIKE 'sh%' OR symbol LIKE 'sz%' OR symbol LIKE '%INDEX%' OR symbol IN ('SH000001','SZ399001','SH000300') GROUP BY symbol ORDER BY n DESC LIMIT 20")
print("SQL:", SQL2)
for r in c.execute(SQL2): print("   ", tuple(r))
c.close()
