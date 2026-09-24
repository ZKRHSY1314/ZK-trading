# READ-ONLY reconciliation of trading_local.daily_bar_cache vs market_history.daily_bars
import sqlite3, io, sys, time
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
OUT   = r"D:/codex-A股交易/claude methods/_m1_evidence/lineage_reconcile_output.txt"
W0, W1 = "2023-09-04", "2026-09-04"

buf = io.StringIO()
def P(*a):
    s = " ".join(str(x) for x in a)
    buf.write(s + "\n")
    print(s.encode("ascii", "replace").decode("ascii"))

conn = sqlite3.connect(f"file:{HIST}?mode=ro", uri=True)
conn.execute("PRAGMA query_only=ON")
conn.row_factory = sqlite3.Row
conn.execute(f"ATTACH DATABASE 'file:{CACHE}?mode=ro' AS cache")
P("database_list:", [tuple(r) for r in conn.execute("PRAGMA database_list")])
P("query_only:", conn.execute("PRAGMA query_only").fetchone()[0])

def q(title, sql, params=()):
    t = time.time()
    rows = conn.execute(sql, params).fetchall()
    P("\n### " + title)
    P("SQL: " + " ".join(sql.split()))
    for r in rows[:40]:
        P("   ", dict(r))
    if len(rows) > 40:
        P("    ... (%d rows total)" % len(rows))
    P("    [%.1fs]" % (time.time()-t))
    return rows

# ---------- 1. store shape ----------
q("M1 cache row count + date range (excluding ERROR sentinel)", """
SELECT COUNT(*) AS rows_total,
       SUM(CASE WHEN trade_date='ERROR' THEN 1 ELSE 0 END) AS error_sentinel_rows,
       MIN(CASE WHEN trade_date!='ERROR' THEN trade_date END) AS min_date,
       MAX(CASE WHEN trade_date!='ERROR' THEN trade_date END) AS max_date,
       COUNT(DISTINCT symbol) AS distinct_symbols
FROM cache.daily_bar_cache""")

q("M2 hist daily_bars row count + date range", """
SELECT COUNT(*) AS rows_total, MIN(trade_date) AS min_date, MAX(trade_date) AS max_date,
       COUNT(DISTINCT symbol) AS distinct_symbols
FROM main.daily_bars""")

q("M3 hist daily_bars adjustment_mode row counts", """
SELECT adjustment_mode, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS symbols,
       MIN(trade_date) AS min_date, MAX(trade_date) AS max_date
FROM main.daily_bars GROUP BY adjustment_mode ORDER BY rows DESC""")

q("M4 hist: any (symbol,trade_date) with MORE THAN ONE adjustment_mode", """
SELECT COUNT(*) AS pairs_with_multiple_modes FROM (
  SELECT symbol, trade_date FROM main.daily_bars
  GROUP BY symbol, trade_date HAVING COUNT(DISTINCT adjustment_mode) > 1)""")

q("M5 cache adjustment_mode row counts", """
SELECT COALESCE(adjustment_mode,'<NULL>') AS adjustment_mode, COUNT(*) AS rows,
       COUNT(DISTINCT symbol) AS symbols
FROM cache.daily_bar_cache GROUP BY 1 ORDER BY rows DESC""")

q("M6 cache volume_unit row counts", """
SELECT COALESCE(volume_unit,'<NULL>') AS volume_unit, COUNT(*) AS rows FROM cache.daily_bar_cache GROUP BY 1 ORDER BY rows DESC""")

q("M7 cache quality_status row counts", """
SELECT COALESCE(quality_status,'<NULL>') AS quality_status, COUNT(*) AS rows FROM cache.daily_bar_cache GROUP BY 1 ORDER BY rows DESC""")

q("M8 cache source row counts", """
SELECT COALESCE(source,'<NULL>') AS source, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS symbols
FROM cache.daily_bar_cache GROUP BY 1 ORDER BY rows DESC""")

q("M9 hist provider row counts", """
SELECT provider, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS symbols FROM main.daily_bars GROUP BY 1 ORDER BY rows DESC""")

q("M10 hist volume_unit / quality_status", """
SELECT volume_unit, quality_status, COUNT(*) AS rows FROM main.daily_bars GROUP BY 1,2 ORDER BY rows DESC""")

# ---------- 2. bars per symbol (the 500-bar seeder cap hypothesis) ----------
q("M11 hist bars-per-symbol distribution (qfq)", """
WITH per AS (SELECT symbol, COUNT(*) AS n FROM main.daily_bars WHERE adjustment_mode='qfq' GROUP BY symbol)
SELECT COUNT(*) AS symbols, MIN(n) AS min_bars, MAX(n) AS max_bars,
       AVG(n) AS avg_bars,
       SUM(CASE WHEN n=500 THEN 1 ELSE 0 END) AS symbols_exactly_500,
       SUM(CASE WHEN n>500 THEN 1 ELSE 0 END) AS symbols_gt_500,
       SUM(CASE WHEN n>=730 THEN 1 ELSE 0 END) AS symbols_ge_730
FROM per""")

q("M12 hist bars-per-symbol histogram buckets", """
WITH per AS (SELECT symbol, COUNT(*) AS n FROM main.daily_bars WHERE adjustment_mode='qfq' GROUP BY symbol)
SELECT CASE WHEN n<100 THEN 'a:<100' WHEN n<250 THEN 'b:100-249' WHEN n<400 THEN 'c:250-399'
            WHEN n<500 THEN 'd:400-499' WHEN n=500 THEN 'e:exactly 500'
            WHEN n<=1000 THEN 'f:501-1000' ELSE 'g:>1000' END AS bucket,
       COUNT(*) AS symbols, SUM(n) AS rows
FROM per GROUP BY bucket ORDER BY bucket""")

q("M13 cache bars-per-symbol distribution", """
WITH per AS (SELECT symbol, COUNT(*) AS n FROM cache.daily_bar_cache WHERE trade_date!='ERROR' GROUP BY symbol)
SELECT COUNT(*) AS symbols, MIN(n) AS min_bars, MAX(n) AS max_bars, AVG(n) AS avg_bars,
       SUM(CASE WHEN n>=730 THEN 1 ELSE 0 END) AS symbols_ge_730
FROM per""")

# ---------- 3. research window coverage ----------
q("M14 rows inside research window 2023-09-04..2026-09-04", """
SELECT 'cache.daily_bar_cache' AS store, COUNT(*) AS rows_in_window,
       COUNT(DISTINCT symbol) AS symbols, COUNT(DISTINCT trade_date) AS distinct_trade_dates
FROM cache.daily_bar_cache WHERE trade_date BETWEEN ? AND ?
UNION ALL
SELECT 'market_history.daily_bars(qfq)', COUNT(*), COUNT(DISTINCT symbol), COUNT(DISTINCT trade_date)
FROM main.daily_bars WHERE adjustment_mode='qfq' AND trade_date BETWEEN ? AND ?""", (W0,W1,W0,W1))

q("M15 rows BEFORE window (warm-up region), separate measurement", """
SELECT 'cache.daily_bar_cache' AS store, COUNT(*) AS rows_before_window, COUNT(DISTINCT symbol) AS symbols
FROM cache.daily_bar_cache WHERE trade_date!='ERROR' AND trade_date < ?
UNION ALL
SELECT 'market_history.daily_bars', COUNT(*), COUNT(DISTINCT symbol)
FROM main.daily_bars WHERE trade_date < ?""", (W0,W0))

q("M16 hist: earliest trade_date per store-year (qfq)", """
SELECT substr(trade_date,1,4) AS yr, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS symbols
FROM main.daily_bars WHERE adjustment_mode='qfq' GROUP BY yr ORDER BY yr""")

q("M17 cache: rows per year", """
SELECT substr(trade_date,1,4) AS yr, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS symbols
FROM cache.daily_bar_cache WHERE trade_date!='ERROR' GROUP BY yr ORDER BY yr""")

conn.close()
open(OUT,"w",encoding="utf-8").write(buf.getvalue())
print("\nWROTE", OUT)
