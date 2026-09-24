import sqlite3
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON"); c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
q = lambda s,*a: c.execute(s,a).fetchall()

# MY OWN classifier: A-share common stock by exchange-prefixed code pattern.
# SH stocks = 60x/688/689 ; SZ = 00x/30x ; BJ = 43x/83x/87x/88x/920.
# This EXCLUDES SH000001/SH000300 (indices) by construction, and excludes bare6 dupes.
STOCK = """ (
   (symbol GLOB 'SH60[0-9][0-9][0-9][0-9]' OR symbol GLOB 'SH68[89][0-9][0-9][0-9]')
OR (symbol GLOB 'SZ00[0-9][0-9][0-9][0-9]' OR symbol GLOB 'SZ30[0-9][0-9][0-9][0-9]')
OR (symbol GLOB 'BJ4[0-9][0-9][0-9][0-9][0-9]' OR symbol GLOB 'BJ8[0-9][0-9][0-9][0-9][0-9]'
    OR symbol GLOB 'BJ9[0-9][0-9][0-9][0-9][0-9]')
 ) """
W = " trade_date >= '2023-09-04' AND trade_date <= '2026-09-04' "

print("=== M1. my classifier vs their instruments-join: distinct stock symbols in window ===")
s1 = f"SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE {STOCK} AND {W}"
s2 = f"""SELECT COUNT(DISTINCT d.symbol) FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
         WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ') AND {W.replace('trade_date','d.trade_date')}"""
print(" mine :", s1); print("   ->", q(s1)[0][0])
print(" theirs:", s2); print("   ->", q(s2)[0][0])

print("\n=== M2. per-session distinct STOCK count (MY classifier). Buckets. ===")
sqlm = f"""SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bar_cache
           WHERE {STOCK} AND {W} GROUP BY 1 ORDER BY 1"""
print(sqlm)
rows = q(sqlm)
print("  sessions with >=1 stock:", len(rows))
import collections
b = collections.Counter()
for d,n in rows:
    if n < 100: b['<100'] += 1
    elif n < 1000: b['100-999'] += 1
    elif n < 3000: b['1000-2999'] += 1
    elif n < 5000: b['3000-4999'] += 1
    else: b['>=5000'] += 1
for k in ['<100','100-999','1000-2999','3000-4999','>=5000']:
    print(f"   {k:10s} {b[k]}")
print("  first 14 sessions:", rows[:14])
print("  last  5 sessions:", rows[-5:])
first5k = next(d for d,n in rows if n>=5000)
print("  first session with >=5000 stocks:", first5k)
print("  max per-session stock count:", max(n for _,n in rows))
print("  median of the >=5000 group:", sorted(n for _,n in rows if n>=5000)[ (b['>=5000'])//2 ])

print("\n=== M3. does ANY session in window have 0 stocks (index-only day)? ===")
s3 = f"""SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE {W}"""
print(s3); print("   all-symbol sessions:", q(s3)[0][0], " | stock-bearing sessions:", len(rows))

print("\n=== M4. ramp sub-window recount, MY classifier, explicit bounds ===")
s4 = f"""SELECT COUNT(*) rows_, COUNT(DISTINCT symbol) syms, COUNT(DISTINCT trade_date) sess
         FROM daily_bar_cache WHERE {STOCK} AND trade_date >= '2024-04-09' AND trade_date <= '2024-06-21'"""
print(s4); print("   ", q(s4)[0])

print("\n=== M5. final-day partiality: last 6 sessions ===")
for d,n in rows[-6:]:
    print("   ", d, n)

print("\n=== M6. MECHANISM TEST - accretion vs backfill: created_at vs trade_date ===")
s6 = f"""SELECT trade_date, COUNT(*) n, MIN(created_at), MAX(created_at)
         FROM daily_bar_cache WHERE {STOCK} AND trade_date <= '2024-06-21' GROUP BY 1 ORDER BY 1 LIMIT 12"""
print(s6)
for r in q(s6): print("   ", r)
s6b = f"""SELECT substr(created_at,1,7) m, COUNT(*) n, MIN(trade_date), MAX(trade_date)
          FROM daily_bar_cache WHERE {STOCK} AND trade_date <= '2024-06-21' GROUP BY 1 ORDER BY 1"""
print(s6b)
for r in q(s6b): print("   ", r)
