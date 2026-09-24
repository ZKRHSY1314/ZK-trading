# -*- coding: utf-8 -*-
import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
mh, tl = ro(MH), ro(TL)
def show(title, c, s, *a):
    print("\n### " + title); print("SQL: " + " ".join(s.split()))
    for r in c.execute(s, a).fetchall(): print("   ", r)

print("="*78); print("C. Does the PRICE PANEL contain names absent from the survivor master?")
show("C1 market_history.daily_bars: distinct symbols in window", mh,
 "SELECT COUNT(DISTINCT symbol) FROM daily_bars WHERE trade_date>=? AND trade_date<=?", W0, W1)
show("C2 trading_local.daily_bar_cache: distinct symbols in window", tl,
 "SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date>=? AND trade_date<=?", W0, W1)
show("C3 last market-wide trade_date in each store (defines 'still alive')", mh,
 "SELECT MAX(trade_date) FROM daily_bars")
show("C3b same for cache", tl, "SELECT MAX(trade_date) FROM daily_bar_cache")

# Symbols present in bars but NOT in the instruments survivor master
mh.execute("CREATE TEMP TABLE _dummy(x)")  # temp only, DB is read-only
print("\n--- C4: bars-symbols MINUS instruments-symbols (market_history, same DB, direct join)")
sql = ("SELECT COUNT(*) FROM (SELECT DISTINCT b.symbol FROM daily_bars b "
       "LEFT JOIN instruments i ON i.symbol=b.symbol WHERE i.symbol IS NULL)")
print("SQL:", sql); print("   ", mh.execute(sql).fetchone())

print("\n--- C5: per-symbol LAST bar date -> who stopped trading mid-window?")
sql = ("SELECT last_d, COUNT(*) FROM (SELECT symbol, MAX(trade_date) AS last_d FROM daily_bars "
       "WHERE trade_date<=? GROUP BY symbol) GROUP BY last_d ORDER BY last_d")
rows = mh.execute(sql, (W1,)).fetchall()
print("SQL:", " ".join(sql.split()))
tot = sum(n for _, n in rows)
print(f"   total symbols with any bar <= {W1}: {tot}")
print("   symbols whose LAST bar is in each year:")
from collections import Counter
byyear = Counter()
for d, n in rows: byyear[d[:4]] += n
for y in sorted(byyear): print(f"      last-bar-year {y}: {byyear[y]} symbols")
print("   the 25 latest distinct last-bar dates (tail = alive names):")
for d, n in rows[-25:]: print(f"      {d}: {n}")

print("\n--- C6: same for trading_local.daily_bar_cache")
rows2 = tl.execute(sql.replace("daily_bars","daily_bar_cache"), (W1,)).fetchall()
byyear2 = Counter()
for d, n in rows2: byyear2[d[:4]] += n
print(f"   total symbols: {sum(n for _,n in rows2)}")
for y in sorted(byyear2): print(f"      last-bar-year {y}: {byyear2[y]} symbols")
print("   25 latest distinct last-bar dates:")
for d, n in rows2[-25:]: print(f"      {d}: {n}")
