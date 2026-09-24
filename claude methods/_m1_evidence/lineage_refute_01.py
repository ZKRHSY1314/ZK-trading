import sqlite3, json
OP = r"D:/codex-A股交易/trading_local.sqlite3"
RH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True); c.row_factory = sqlite3.Row; return c
op, rh = ro(OP), ro(RH)

def show(title, conn, sql, params=()):
    print("\n### " + title); print("SQL: " + " ".join(sql.split()))
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception as e:
        print("  ERROR:", e); return []
    for r in rows[:40]: print("   ", dict(r))
    if len(rows) > 40: print(f"    ... {len(rows)} rows total")
    return rows

# --- A. Is daily_bar_cache a TABLE or a VIEW? Could it proxy market_history? ---
show("A1 objects named daily_bar_cache / daily_bars in trading_local", op,
 "SELECT name,type,sql FROM sqlite_master WHERE name IN ('daily_bar_cache','daily_bars')")
show("A2 objects named daily_bar_cache / daily_bars in market_history", rh,
 "SELECT name,type FROM sqlite_master WHERE name IN ('daily_bar_cache','daily_bars')")
show("A3 any VIEW at all in trading_local", op,
 "SELECT name FROM sqlite_master WHERE type='view'")

# --- B. The denominator the claimant asserts: what the engine WHERE clause admits ---
show("B1 total rows vs engine-admissible rows (quality_status='ready' exact match)", op, """
SELECT COUNT(*) AS all_rows,
       SUM(CASE WHEN quality_status='ready' THEN 1 ELSE 0 END) AS ready_rows,
       COUNT(DISTINCT symbol) AS all_symbols
FROM daily_bar_cache""")
show("B2 distinct symbols admitted by the engine clause", op,
 "SELECT COUNT(DISTINCT symbol) AS ready_symbols FROM daily_bar_cache WHERE quality_status='ready'")
show("B3 quality_status value distribution (is 'ready' the only value?)", op,
 "SELECT COALESCE(quality_status,'<NULL>') AS qs, COUNT(*) n, COUNT(DISTINCT symbol) syms FROM daily_bar_cache GROUP BY 1 ORDER BY n DESC")
# engine also drops any row with a NULL OHLC (df.dropna(subset=PRICE_COLUMNS))
show("B4 rows engine ACTUALLY keeps: ready AND all four OHLC non-null", op, """
SELECT COUNT(*) AS kept_rows, COUNT(DISTINCT symbol) AS kept_symbols
FROM daily_bar_cache
WHERE quality_status='ready'
  AND open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL""")
show("B5 case-variant symbols: engine expands to {sym,UPPER,lower}. Any lowercase symbols present?", op, """
SELECT SUM(CASE WHEN symbol <> UPPER(symbol) THEN 1 ELSE 0 END) AS non_upper_rows,
       SUM(CASE WHEN symbol <> UPPER(symbol) THEN 0 ELSE 1 END) AS upper_rows
FROM daily_bar_cache""")

# --- C. Are those 5,566 symbols STOCKS? indices must not be counted as stocks ---
show("C1 symbol shape breakdown of engine-admissible symbols", op, """
SELECT CASE
   WHEN symbol LIKE 'sh%' OR symbol LIKE 'sz%' OR symbol LIKE 'bj%' THEN 'prefixed_'||substr(symbol,1,2)
   WHEN symbol GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]' THEN 'bare6_'||substr(symbol,1,1)
   ELSE 'other' END AS shape,
   COUNT(DISTINCT symbol) AS syms, COUNT(*) AS rows_
FROM daily_bar_cache WHERE quality_status='ready' GROUP BY 1 ORDER BY syms DESC""")
op.close(); rh.close()
