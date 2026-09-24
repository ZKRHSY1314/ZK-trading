import sqlite3, collections
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON"); c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
q = lambda s,*a: c.execute(s,a).fetchall()
STOCK = """ ((symbol GLOB 'SH60[0-9][0-9][0-9][0-9]' OR symbol GLOB 'SH68[89][0-9][0-9][0-9]')
 OR (symbol GLOB 'SZ00[0-9][0-9][0-9][0-9]' OR symbol GLOB 'SZ30[0-9][0-9][0-9][0-9]')
 OR (symbol GLOB 'BJ4[0-9][0-9][0-9][0-9][0-9]' OR symbol GLOB 'BJ8[0-9][0-9][0-9][0-9][0-9]'
     OR symbol GLOB 'BJ9[0-9][0-9][0-9][0-9][0-9]')) """

print("=== N1. WHOLE-TABLE created_at distribution by month (stocks only) ===")
s = f"SELECT substr(created_at,1,7) m, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bar_cache WHERE {STOCK} GROUP BY 1 ORDER BY 1"
print(s)
for r in q(s): print("   ", r)

print("\n=== N2. is created_at rewritten on upsert? created_at vs updated_at ===")
s = f"""SELECT SUM(CASE WHEN created_at=updated_at THEN 1 ELSE 0 END) same,
               SUM(CASE WHEN created_at<>updated_at THEN 1 ELSE 0 END) diff, COUNT(*) tot
        FROM daily_bar_cache WHERE {STOCK} AND trade_date<='2024-06-21'"""
print(s); print("   ramp rows:", q(s)[0])
s = f"""SELECT SUM(CASE WHEN created_at=updated_at THEN 1 ELSE 0 END) same,
               SUM(CASE WHEN created_at<>updated_at THEN 1 ELSE 0 END) diff, COUNT(*) tot
        FROM daily_bar_cache WHERE {STOCK}"""
print("   all stock rows:", q(s)[0])

print("\n=== N3. per-symbol FIRST trade_date distribution (is history depth symbol-specific?) ===")
s = f"""SELECT first_d, COUNT(*) nsym FROM
        (SELECT symbol, MIN(trade_date) first_d FROM daily_bar_cache WHERE {STOCK} GROUP BY symbol)
        GROUP BY 1 ORDER BY 1 LIMIT 20"""
print(s)
for r in q(s): print("   ", r)
s2 = f"""SELECT COUNT(*) FROM (SELECT symbol, MIN(trade_date) f FROM daily_bar_cache WHERE {STOCK} GROUP BY symbol) WHERE f='2024-06-24'"""
print(s2); print("   symbols whose history starts exactly 2024-06-24:", q(s2)[0][0])

print("\n=== N4. do the RAMP symbols also have the deep history, or only the late ones? ===")
s = f"""SELECT (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE {STOCK} AND trade_date<='2024-06-21') ramp_syms,
               (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE {STOCK}) all_syms"""
print(s); print("   ", q(s)[0])

print("\n=== N5. created_at ORDERING inside the backfill: does created_at track trade_date or symbol? ===")
s = f"""SELECT symbol, MIN(trade_date), MAX(trade_date), COUNT(*), MIN(created_at), MAX(created_at)
        FROM daily_bar_cache WHERE {STOCK} AND trade_date<='2024-04-19' GROUP BY symbol ORDER BY MIN(trade_date) LIMIT 12"""
print(s)
for r in q(s): print("   ", r)

print("\n=== N6. FULL-MARKET adequacy of the 536 'good' sessions vs listed count that day ===")
s = f"""SELECT d.trade_date, COUNT(DISTINCT d.symbol) have,
        (SELECT COUNT(*) FROM mh.instruments i WHERE i.list_date IS NOT NULL AND i.list_date<=d.trade_date
           AND (i.delist_date IS NULL OR i.delist_date>d.trade_date)) listed
        FROM daily_bar_cache d WHERE {STOCK.replace('symbol','d.symbol')} AND d.trade_date IN
        ('2024-06-24','2024-09-11','2025-01-02','2025-06-02','2026-01-05','2026-09-03')
        GROUP BY 1 ORDER BY 1"""
print(s)
for r in q(s): print("   ", r, " shortfall:", r[2]-r[1] if r[2] else None)

print("\n=== N7. market_history cross-check with MY classifier (their 2024-09-11 / 474 claim) ===")
s = f"""SELECT trade_date, COUNT(DISTINCT symbol) n FROM mh.daily_bars
        WHERE {STOCK} AND trade_date>='2023-09-04' AND trade_date<='2026-09-04' GROUP BY 1 ORDER BY 1"""
print(s)
rr = q(s)
print("   mh stock-bearing sessions in window:", len(rr), " first:", rr[0], " last:", rr[-1])
f5 = [d for d,n in rr if n>=5000]
print("   mh first session >=5000 stocks:", f5[0] if f5 else None, " count of such sessions:", len(f5))
