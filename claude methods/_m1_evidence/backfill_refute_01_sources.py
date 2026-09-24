import sqlite3, os
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"

def ro(p):
    c = sqlite3.connect(f"file:{p.replace(chr(92),'/')}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c

op = ro(OP)

def q(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()

def show(title, sql, conn=op, params=()):
    print("\n" + "="*100)
    print(title)
    print("-- SQL:", " ".join(sql.split()))
    try:
        rows = q(conn, sql, params)
    except Exception as e:
        print("   ERROR:", e); return []
    if not rows:
        print("   (no rows)"); return []
    cols = rows[0].keys()
    print("   " + " | ".join(f"{c}" for c in cols))
    for r in rows[:60]:
        print("   " + " | ".join(str(r[c]) for c in cols))
    if len(rows) > 60:
        print(f"   ... {len(rows)-60} more")
    return rows

print("#"*100)
print("# INDEPENDENT CHECK 1: daily_bar_cache source composition (my own aggregation)")
print("#"*100)

show("1a. Rows AND distinct symbols AND date extent per source (NOT just row counts)",
"""
SELECT source,
       COUNT(*)                        AS rows_total,
       COUNT(DISTINCT symbol)          AS distinct_symbols,
       MIN(trade_date)                 AS first_bar,
       MAX(trade_date)                 AS last_bar,
       MIN(updated_at)                 AS first_written,
       MAX(updated_at)                 AS last_written
FROM daily_bar_cache
GROUP BY source
ORDER BY rows_total DESC
""")

show("1b. Grand total (verify their 2,891,617 denominator)",
"SELECT COUNT(*) AS rows_total, COUNT(DISTINCT symbol) AS distinct_symbols FROM daily_bar_cache")

print("\n" + "#"*100)
print("# INDEPENDENT CHECK 2: are the 123 akshare.stock_zh_a_hist symbols STOCKS or INDICES?")
print("#"*100)

show("2a. Symbol shape of the eastmoney-backed source (prefix histogram)",
"""
SELECT substr(symbol,1,3) AS prefix3, COUNT(DISTINCT symbol) AS syms, COUNT(*) AS rows
FROM daily_bar_cache
WHERE source='akshare.stock_zh_a_hist'
GROUP BY prefix3 ORDER BY syms DESC
""")

show("2b. Sample symbols from that source",
"""
SELECT DISTINCT symbol FROM daily_bar_cache
WHERE source='akshare.stock_zh_a_hist' ORDER BY symbol LIMIT 30
""")

print("\n" + "#"*100)
print("# INDEPENDENT CHECK 3: EXCLUSIVITY - is this source the SOLE holder of any symbol/date?")
print("#   (the real question: would losing eastmoney lose data, or is it fully redundant?)")
print("#"*100)

show("3a. Of the (symbol,trade_date) keys written by akshare.stock_zh_a_hist, how many symbols\n"
     "    have ANY coverage from another source at all?",
"""
SELECT COUNT(*) AS symbols_from_eastmoney,
       SUM(CASE WHEN other_rows>0 THEN 1 ELSE 0 END) AS also_covered_by_other_source,
       SUM(CASE WHEN other_rows=0 THEN 1 ELSE 0 END) AS eastmoney_only_symbols
FROM (
  SELECT e.symbol,
         (SELECT COUNT(*) FROM daily_bar_cache o
           WHERE o.symbol=e.symbol AND o.source<>'akshare.stock_zh_a_hist') AS other_rows
  FROM (SELECT DISTINCT symbol FROM daily_bar_cache WHERE source='akshare.stock_zh_a_hist') e
)
""")

print("\n" + "#"*100)
print("# INDEPENDENT CHECK 4: capital_flow_ingestion_runs - MY OWN slice, not theirs")
print("#"*100)

show("4a. Full schema of capital_flow_ingestion_runs",
"SELECT sql FROM sqlite_master WHERE name='capital_flow_ingestion_runs'")

show("4b. Every run, chronologically, with scope + source + counts (no GROUP BY hiding anything)",
"""
SELECT id, scope, source, status, error_type,
       requested_count, accepted_count, rejected_count,
       started_at, finished_at
FROM capital_flow_ingestion_runs
ORDER BY started_at
""")

print("\n" + "#"*100)
print("# INDEPENDENT CHECK 5: did the capital-flow pipeline actually produce data despite runs?")
print("#"*100)

show("5a. capital-flow related tables",
"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%capital%' OR name LIKE '%flow%'")

op.close()
