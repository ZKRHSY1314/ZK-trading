# -*- coding: utf-8 -*-
"""Part 2: can the delisting timeline be recovered some OTHER way?
If yes -> the finding is overstated. READ-ONLY."""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"
mh = sqlite3.connect("file:%s?mode=ro" % MH, uri=True)
tl = sqlite3.connect("file:%s?mode=ro" % TL, uri=True)

def show(t, con, sql, p=()):
    print("\n" + "=" * 78); print(t); print("SQL: " + " ".join(sql.split()))
    cur = con.execute(sql, p); cols=[d[0] for d in cur.description]; rows=cur.fetchall()
    print("  " + " | ".join(cols))
    for r in rows: print("  " + " | ".join("NULL" if v is None else str(v) for v in r))
    print("  (%d row(s))" % len(rows)); return rows

print("#"*78); print("D. WHEN WAS THE CATALOG BORN? (delistings before that leave NO ROW AT ALL)"); print("#"*78)

show("D1. instruments.created_at histogram -- catalog age vs the 3y research window", mh, """
SELECT substr(created_at,1,10) AS created_day, COUNT(*) AS n,
       MIN(provider) AS a_provider, COUNT(DISTINCT provider) AS providers
FROM instruments GROUP BY created_day ORDER BY created_day
""")

show("D2. distinct catalog refresh timestamps (resolution of any updated_at-based timeline)", mh, """
SELECT substr(fetched_at,1,10) AS fetched_day, COUNT(*) AS rows_stamped,
       COUNT(DISTINCT fetched_at) AS distinct_ts
FROM instruments GROUP BY fetched_day ORDER BY fetched_day
""")

print("\n"+"#"*78); print("E. RECOVERABILITY: does the last traded bar date place delistings on a timeline?"); print("#"*78)

show("E1. the 5 inactive names: first/last bar in market_history.daily_bars vs updated_at", mh, """
SELECT i.symbol, i.name, i.status, i.updated_at,
       MIN(b.trade_date) AS first_bar, MAX(b.trade_date) AS last_bar, COUNT(*) AS bar_rows
FROM instruments AS i LEFT JOIN daily_bars AS b ON b.symbol = i.symbol
WHERE i.status <> 'active' GROUP BY i.symbol, i.name, i.status, i.updated_at ORDER BY i.symbol
""")

show("E2. same 5 names against the OPERATIONAL store trading_local.daily_bar_cache (the store the backtest actually reads)", tl, """
SELECT symbol, MIN(trade_date) AS first_bar, MAX(trade_date) AS last_bar, COUNT(*) AS bar_rows
FROM daily_bar_cache
WHERE symbol IN ('BJ920305','SH605081','SZ000004','SZ002808','SZ002898')
GROUP BY symbol ORDER BY symbol
""")

print("\n"+"#"*78); print("F. IS 5 THE REAL DELISTING COUNT? symbols that stop trading inside the window"); print("#"*78)

show("F1. market_history: stocks whose LAST bar is inside the window but well before window end\n"
     "    (i.e. stopped trading = delist OR long suspension OR ingest truncation) -- by status", mh, """
WITH last_seen AS (
  SELECT symbol, MAX(trade_date) AS last_bar, MIN(trade_date) AS first_bar, COUNT(*) AS n
  FROM daily_bars WHERE trade_date BETWEEN ? AND ? GROUP BY symbol
)
SELECT COALESCE(i.status,'<not in instruments>') AS status,
       COUNT(*) AS symbols_stopped_early,
       MIN(l.last_bar) AS earliest_last_bar, MAX(l.last_bar) AS latest_last_bar
FROM last_seen AS l LEFT JOIN instruments AS i ON i.symbol = l.symbol
WHERE l.last_bar < '2026-08-01'
GROUP BY status ORDER BY symbols_stopped_early DESC
""", (W0, W1))

show("F2. symbols WITH bars in the window but NO instruments row at all\n"
     "    (a delisting that predates the catalog is invisible even as status='inactive')", mh, """
SELECT COUNT(DISTINCT b.symbol) AS traded_but_uncatalogued
FROM daily_bars AS b LEFT JOIN instruments AS i ON i.symbol = b.symbol
WHERE b.trade_date BETWEEN ? AND ? AND i.symbol IS NULL
""", (W0, W1))

show("F3. same question for the OPERATIONAL store (daily_bar_cache symbols not in the research catalog)", tl, """
SELECT COUNT(DISTINCT symbol) AS distinct_symbols_in_cache_window
FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?
""", (W0, W1))

print("\n"+"#"*78); print("G. CROSS-DB CONFLATION CHECK: does trading_local carry delisting info the auditor missed?"); print("#"*78)

show("G1. any table in trading_local with a delist/status-ish column", tl, """
SELECT m.name AS tbl, p.name AS col
FROM sqlite_master AS m JOIN pragma_table_info(m.name) AS p
WHERE m.type='table' AND (p.name LIKE '%delist%' OR p.name LIKE '%list_date%'
      OR p.name LIKE '%suspend%' OR p.name LIKE '%halt%')
ORDER BY tbl, col
""")

show("G2. any table in market_history with a delist/suspend-ish column", mh, """
SELECT m.name AS tbl, p.name AS col
FROM sqlite_master AS m JOIN pragma_table_info(m.name) AS p
WHERE m.type='table' AND (p.name LIKE '%delist%' OR p.name LIKE '%suspend%' OR p.name LIKE '%halt%')
ORDER BY tbl, col
""")

show("G3. universe_snapshots -- could membership diffs date a delisting instead?", mh, """
SELECT id, universe_name, snapshot_date, provider, member_count, substr(fetched_at,1,19) AS fetched_at
FROM universe_snapshots ORDER BY snapshot_date, id
""")

mh.close(); tl.close()
