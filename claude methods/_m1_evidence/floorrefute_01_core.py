# -*- coding: utf-8 -*-
import sqlite3
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
def show(c, sql, title, args=()):
    print("-"*88); print(title); print("SQL:", " ".join(sql.split()))
    try:
        cur = c.execute(sql, args)
        hdr = [d[0] for d in cur.description]
        rows = cur.fetchall()
        print("  " + " | ".join(hdr))
        for r in rows[:60]:
            print("  " + " | ".join("NULL" if v is None else str(v) for v in r))
        if len(rows) > 60: print(f"  ... {len(rows)-60} more")
    except Exception as e:
        print("  ERROR:", e)

tl = ro(TL); mh = ro(MH)

print("#"*88); print("# TRAP 1: storage-class census. MIN() sorts INTEGER/REAL BEFORE TEXT in SQLite.")
print("# If any trade_date is stored numerically, a GLOB-filtered MIN() would silently hide it.")
show(tl, """
SELECT typeof(trade_date) AS storage_class, COUNT(*) AS n,
       MIN(CAST(trade_date AS TEXT)) AS lo_text, MAX(CAST(trade_date AS TEXT)) AS hi_text
FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC
""", "T1a trading_local.daily_bar_cache typeof(trade_date)")
show(mh, """
SELECT typeof(trade_date) AS storage_class, COUNT(*) AS n,
       MIN(CAST(trade_date AS TEXT)) AS lo_text, MAX(CAST(trade_date AS TEXT)) AS hi_text
FROM daily_bars GROUP BY 1 ORDER BY 2 DESC
""", "T1b market_history.daily_bars typeof(trade_date)")

print()
print("#"*88); print("# TRAP 2: the 1 row that fails their GLOB. What is it? Could it be an old date in another format?")
show(tl, """
SELECT symbol, quote(trade_date) AS raw_trade_date, typeof(trade_date) AS st,
       length(trade_date) AS len, source, quality_status, created_at, updated_at
FROM daily_bar_cache
WHERE trade_date IS NULL
   OR trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
""", "T2 non-ISO trade_date rows in daily_bar_cache")

print()
print("#"*88); print("# TRAP 3: NO window filter, NO string comparison. Integer year histogram via substr+CAST.")
print("# This cannot be fooled by lexicographic ordering or by a wrong window boundary.")
show(tl, """
SELECT CAST(substr(CAST(trade_date AS TEXT),1,4) AS INTEGER) AS yr,
       COUNT(*) AS rows_all, COUNT(DISTINCT symbol) AS distinct_symbols,
       MIN(CAST(trade_date AS TEXT)) AS first_td, MAX(CAST(trade_date AS TEXT)) AS last_td,
       COUNT(DISTINCT CAST(trade_date AS TEXT)) AS sessions
FROM daily_bar_cache GROUP BY 1 ORDER BY 1
""", "T3a trading_local.daily_bar_cache: every row bucketed by integer year")
show(mh, """
SELECT CAST(substr(CAST(trade_date AS TEXT),1,4) AS INTEGER) AS yr,
       COUNT(*) AS rows_all, COUNT(DISTINCT symbol) AS distinct_symbols,
       MIN(CAST(trade_date AS TEXT)) AS first_td, MAX(CAST(trade_date AS TEXT)) AS last_td,
       COUNT(DISTINCT CAST(trade_date AS TEXT)) AS sessions
FROM daily_bars GROUP BY 1 ORDER BY 1
""", "T3b market_history.daily_bars: every row bucketed by integer year")

print()
print("#"*88); print("# TRAP 4: month histogram around the alleged floor, integer-keyed. Off-by-one would show here.")
show(tl, """
SELECT CAST(substr(CAST(trade_date AS TEXT),1,4)||substr(CAST(trade_date AS TEXT),6,2) AS INTEGER) AS ym,
       COUNT(*) AS rows_all, COUNT(DISTINCT symbol) AS syms,
       MIN(CAST(trade_date AS TEXT)) AS lo, MAX(CAST(trade_date AS TEXT)) AS hi
FROM daily_bar_cache
WHERE CAST(substr(CAST(trade_date AS TEXT),1,4) AS INTEGER) <= 2024
GROUP BY 1 ORDER BY 1
""", "T4a daily_bar_cache monthly buckets <=2024")
show(mh, """
SELECT CAST(substr(CAST(trade_date AS TEXT),1,4)||substr(CAST(trade_date AS TEXT),6,2) AS INTEGER) AS ym,
       COUNT(*) AS rows_all, COUNT(DISTINCT symbol) AS syms,
       MIN(CAST(trade_date AS TEXT)) AS lo, MAX(CAST(trade_date AS TEXT)) AS hi
FROM daily_bars
WHERE CAST(substr(CAST(trade_date AS TEXT),1,4) AS INTEGER) <= 2024
GROUP BY 1 ORDER BY 1
""", "T4b daily_bars monthly buckets <=2024")

print()
print("#"*88); print("# TRAP 5: per-adjustment_mode floor in market_history (a single global MIN could mask a mode)")
show(mh, """
SELECT adjustment_mode, COUNT(*) AS n, COUNT(DISTINCT symbol) AS syms,
       MIN(CAST(trade_date AS TEXT)) AS lo, MAX(CAST(trade_date AS TEXT)) AS hi
FROM daily_bars GROUP BY 1 ORDER BY 1
""", "T5 daily_bars by adjustment_mode")
show(tl, """
SELECT adjustment_mode, COUNT(*) AS n, MIN(CAST(trade_date AS TEXT)) AS lo, MAX(CAST(trade_date AS TEXT)) AS hi
FROM daily_bar_cache GROUP BY 1 ORDER BY 1
""", "T5b daily_bar_cache by adjustment_mode")
show(tl, """
SELECT source, quality_status, COUNT(*) AS n,
       MIN(CAST(trade_date AS TEXT)) AS lo, MAX(CAST(trade_date AS TEXT)) AS hi
FROM daily_bar_cache GROUP BY 1,2 ORDER BY 3 DESC
""", "T5c daily_bar_cache by source+quality_status (a subset could reach back further)")

tl.close(); mh.close()
