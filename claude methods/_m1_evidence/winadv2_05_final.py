import sqlite3
TL = r"D:/codex-A股交易/trading_local.sqlite3"; MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON"); c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
q = lambda s,*a: c.execute(s,a).fetchall()
STOCK = """ ((symbol GLOB 'SH60[0-9][0-9][0-9][0-9]' OR symbol GLOB 'SH68[89][0-9][0-9][0-9]')
 OR (symbol GLOB 'SZ00[0-9][0-9][0-9][0-9]' OR symbol GLOB 'SZ30[0-9][0-9][0-9][0-9]')
 OR (symbol GLOB 'BJ4[0-9][0-9][0-9][0-9][0-9]' OR symbol GLOB 'BJ8[0-9][0-9][0-9][0-9][0-9]'
     OR symbol GLOB 'BJ9[0-9][0-9][0-9][0-9][0-9]')) """

print("=== P1. coverage ratio vs contemporaneous LISTED universe, all 587 sessions ===")
sql = f"""
WITH have AS (SELECT trade_date d, COUNT(DISTINCT symbol) h FROM daily_bar_cache
              WHERE {STOCK} AND trade_date>='2023-09-04' AND trade_date<='2026-09-04' GROUP BY 1),
     lst AS (SELECT h.d, h.h, (SELECT COUNT(*) FROM mh.instruments i
              WHERE i.list_date IS NOT NULL AND i.list_date<=h.d
                AND (i.delist_date IS NULL OR i.delist_date>h.d)) L FROM have h)
SELECT d, h, L, ROUND(100.0*h/L,2) pct FROM lst ORDER BY d"""
print(sql)
rows = q(sql)
import collections
b = collections.Counter()
for d,h,L,p in rows:
    if p is None: b['nolist']+=1
    elif p>=99.5: b['>=99.5%']+=1
    elif p>=99: b['99-99.5%']+=1
    elif p>=95: b['95-99%']+=1
    elif p>=50: b['50-95%']+=1
    else: b['<50%']+=1
for k in ['>=99.5%','99-99.5%','95-99%','50-95%','<50%','nolist']: print(f"   {k:10s} {b[k]}")
ge = [r for r in rows if r[3] and r[3]>=99.0]
print("   sessions >=99% of listed universe:", len(ge), " first:", ge[0][0] if ge else None)
ge5 = [r for r in rows if r[1]>=5000]
print("   sessions with >=5000 stocks (their rule):", len(ge5), " first:", ge5[0][0])
print("   of those, how many are <99% of listed:", sum(1 for r in ge5 if r[3] and r[3]<99.0))
print("   worst 8 of the >=5000 group by pct:", sorted(ge5,key=lambda r:r[3])[:8])

print("\n=== P2. backfill fingerprint: created_at spread of the ENTIRE ramp ===")
sql2 = f"""SELECT MIN(created_at), MAX(created_at), COUNT(*), COUNT(DISTINCT substr(created_at,1,10))
           FROM daily_bar_cache WHERE {STOCK} AND trade_date>='2024-04-09' AND trade_date<='2024-06-21'"""
print(sql2); print("   ", q(sql2)[0])
sql3 = f"""SELECT COUNT(*) FROM daily_bar_cache WHERE {STOCK} AND created_at < '2026-01-01'"""
print(sql3); print("   stock rows created before 2026:", q(sql3)[0][0])

print("\n=== P3. history-depth cliff: symbols by first bar date, bucketed ===")
sql4 = f"""SELECT CASE WHEN f<'2024-06-24' THEN 'pre-2024-06-24 (ramp)'
                       WHEN f='2024-06-24' THEN 'exactly 2024-06-24 (bulk load)'
                       ELSE 'after 2024-06-24 (later add/IPO)' END g, COUNT(*) nsym
           FROM (SELECT symbol, MIN(trade_date) f FROM daily_bar_cache WHERE {STOCK} GROUP BY symbol)
           GROUP BY 1 ORDER BY 2 DESC"""
print(sql4)
for r in q(sql4): print("   ", r)
