import sqlite3
tl=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
mh=sqlite3.connect("file:D:/codex-A股交易/market_history.sqlite3?mode=ro",uri=True)
q=lambda c,s,p=(): c.execute(s,p).fetchall()

print("### Q. daily_bar_cache (backtest source): does it span the window, and does ANY stock die mid-window?")
print("   MIN/MAX trade_date (valid 10-char only):",
  q(tl,"SELECT MIN(trade_date),MAX(trade_date) FROM daily_bar_cache WHERE length(trade_date)=10 AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"))
print("   rows with INVALID trade_date:",
  q(tl,"SELECT COUNT(*) FROM daily_bar_cache WHERE NOT (length(trade_date)=10 AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')"))

print()
print("   -- STOCKS ONLY (exclude the 2 index symbols SH000001/SH000300 + 4 bare dupes), valid dates, window-clipped")
STK = """FROM daily_bar_cache b
 WHERE b.symbol GLOB '[A-Z][A-Z][0-9]*'
   AND b.symbol NOT IN ('SH000001','SH000300')
   AND length(b.trade_date)=10
   AND b.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   AND b.trade_date BETWEEN '2023-09-04' AND '2026-09-04'"""
print("   distinct stock symbols in window:",q(tl,f"SELECT COUNT(DISTINCT symbol) {STK}"))
rows=q(tl,f"""WITH last AS (SELECT symbol,MIN(trade_date) mn,MAX(trade_date) mx,COUNT(*) n {STK} GROUP BY symbol)
SELECT CASE
  WHEN mx>='2026-08-01' THEN 'A. alive at window end'
  WHEN mx>='2026-06-01' THEN 'B. last bar 2026-06/07 (removed AFTER store went live)'
  WHEN mx>='2025-01-01' THEN 'C. last bar 2025..2026-05 (would be a true mid-window death)'
  ELSE 'D. last bar <=2024 (true mid-window death)' END bucket,
COUNT(*) n_symbols FROM last GROUP BY 1 ORDER BY 1""")
for r in rows: print("   ",r)

print()
print("### R. How far back does the backtest store actually go, per symbol?")
rows=q(tl,f"""WITH f AS (SELECT symbol,MIN(trade_date) mn {STK} GROUP BY symbol)
SELECT CASE WHEN mn<='2023-09-05' THEN 'reaches window start'
            WHEN mn<'2024-04-09' THEN '2023-09..2024-04'
            WHEN mn<'2025-01-01' THEN '2024-04..2024-12'
            ELSE '2025 or later' END b, COUNT(*) FROM f GROUP BY 1 ORDER BY 1""")
for r in rows: print("   ",r)

print()
print("### S. EXHAUSTIVE: any non-null delist_date anywhere in either DB?")
for tag,c in (("market_history",mh),("trading_local",tl)):
    for (n,) in q(c,"SELECT name FROM sqlite_master WHERE type='table'"):
        cols=[r[1] for r in q(c,f'PRAGMA table_info("{n}")')]
        for col in cols:
            if 'delist' in col.lower():
                v=q(c,f'SELECT COUNT(*), SUM(CASE WHEN "{col}" IS NOT NULL AND trim("{col}")<>\'\' THEN 1 ELSE 0 END) FROM "{n}"')
                print(f"   {tag}.{n}.{col}: total={v[0][0]} non_empty={v[0][1]}")

print()
print("### T. instruments distinct fetched_at days (is the catalog a single 2026 vintage?)")
print(q(mh,"SELECT substr(fetched_at,1,10) d, COUNT(*) FROM instruments GROUP BY 1 ORDER BY 1"))
