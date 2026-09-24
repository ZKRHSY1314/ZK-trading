import sqlite3, datetime
TL = "D:/codex-A股交易/trading_local.sqlite3"
MH = "D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl, mh = ro(TL), ro(MH)
W0, W1 = '2023-09-04', '2026-09-04'

print("### 1. BENCHMARK SERIES — raw facts, no calendar involved")
for r in tl.execute("""
  SELECT symbol, COUNT(*) rows_all, COUNT(DISTINCT trade_date) distinct_days,
         MIN(trade_date) first_day, MAX(trade_date) last_day,
         SUM(CASE WHEN trade_date BETWEEN ? AND ? THEN 1 ELSE 0 END) rows_in_window,
         SUM(CASE WHEN trade_date < ? THEN 1 ELSE 0 END) rows_before_window,
         SUM(CASE WHEN trade_date > ? THEN 1 ELSE 0 END) rows_after_window,
         SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) null_close,
         COUNT(DISTINCT quality_status) qs
  FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001')
  GROUP BY symbol""", (W0,W1,W0,W1)):
    print("   ", r)

print("\n   quality_status / source / adjustment_mode of benchmark rows:")
for r in tl.execute("""SELECT symbol, source, quality_status, adjustment_mode, volume_unit, COUNT(*)
                       FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001')
                       GROUP BY 1,2,3,4,5"""):
    print("   ", r)

print("\n   Do the two benchmarks share an identical date set?")
r = tl.execute("""SELECT
   (SELECT COUNT(*) FROM (SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000300'
                          EXCEPT SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000001')),
   (SELECT COUNT(*) FROM (SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000001'
                          EXCEPT SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000300'))""").fetchone()
print("   300-only days, 001-only days:", r)

print("\n### 2. BEFORE 2024-06-19: ANY benchmark row anywhere, any table, any symbol shape?")
print("   daily_bar_cache SH000300/SH000001 rows < 2024-06-19:",
   tl.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001') AND trade_date < '2024-06-19'").fetchone()[0])
print("   market_history.daily_bars any index-shaped symbol:",
   mh.execute("SELECT COUNT(*) FROM daily_bars WHERE symbol LIKE 'SH000%' OR symbol LIKE 'SZ399%' OR symbol LIKE '%INDEX%'").fetchone()[0])
print("   global_market_bars any CN index:",
   tl.execute("SELECT COUNT(*) FROM global_market_bars WHERE symbol LIKE '%000300%' OR symbol LIKE '%HS300%' OR asset_class LIKE '%index%'").fetchone()[0])

print("\n### 3. MY OWN session calendar — sensitivity to breadth threshold (stocks only, indices+6-digit dupes excluded)")
base = """FROM daily_bar_cache
          WHERE symbol GLOB '[SB][HZJ][0-9][0-9][0-9][0-9][0-9][0-9]'
            AND symbol NOT IN ('SH000300','SH000001')
            AND close IS NOT NULL"""
for thr in (1, 50, 100, 500, 1000, 2000, 3000, 4000):
    q = f"""WITH cal AS (SELECT trade_date {base} GROUP BY trade_date HAVING COUNT(DISTINCT symbol) >= {thr})
            SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM cal WHERE trade_date BETWEEN ? AND ?"""
    print(f"   >= {thr:5d} distinct stocks/day -> {tl.execute(q,(W0,W1)).fetchone()}")

print("\n### 4. CROSS-DB calendar from market_history.daily_bars (independent store)")
for thr in (1, 100, 1000, 3000):
    q = f"""WITH cal AS (SELECT trade_date FROM daily_bars WHERE close IS NOT NULL
                         GROUP BY trade_date HAVING COUNT(DISTINCT symbol) >= {thr})
            SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM cal WHERE trade_date BETWEEN ? AND ?"""
    print(f"   >= {thr:5d} -> {mh.execute(q,(W0,W1)).fetchone()}")

print("\n### 5. Daily breadth around the alleged 2024-06-07 onset")
for r in tl.execute(f"""SELECT trade_date, COUNT(DISTINCT symbol) n {base}
                        AND trade_date BETWEEN '2024-05-27' AND '2024-06-28'
                        GROUP BY trade_date ORDER BY trade_date"""):
    print("   ", r)

print("\n### 6. Earliest stock data at all in each store (warm-up region)")
print("   daily_bar_cache MIN(trade_date) stocks:", tl.execute(f"SELECT MIN(trade_date), MAX(trade_date) {base}").fetchone())
print("   market_history MIN/MAX:", mh.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_bars").fetchone())

print("\n### 7. Weekday arithmetic check 2023-09-04..2026-09-04")
d0 = datetime.date(2023,9,4); d1 = datetime.date(2026,9,4)
wd = sum(1 for i in range((d1-d0).days+1) if (d0+datetime.timedelta(days=i)).weekday() < 5)
print("   inclusive calendar days:", (d1-d0).days+1, " weekdays(Mon-Fri):", wd)
