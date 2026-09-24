# -*- coding: utf-8 -*-
"""Read-only survivorship audit, part 2: delisting / truncation forensics."""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"


def ro(p):
    return sqlite3.connect("file:%s?mode=ro" % p, uri=True)


mh = ro(MH)
tl = ro(TL)


def show(tag, conn, sql, params=(), limit=None):
    rows = conn.execute(sql, params).fetchall()
    print("\n### %s" % tag)
    print("SQL: %s" % " ".join(sql.split()))
    if params:
        print("PARAMS: %r" % (params,))
    it = rows if limit is None else rows[:limit]
    for r in it:
        print("   ", r)
    if limit is not None and len(rows) > limit:
        print("    ... (%d rows total)" % len(rows))
    return rows


print("=" * 100)
print("SECTION 7  the 5 inactive instruments + the 18 with no list_date")
print("=" * 100)
show("inactive instruments (full rows)", mh,
     "SELECT symbol, name, exchange, asset_type, board, list_date, delist_date, status, provider, fetched_at "
     "FROM instruments WHERE status <> 'active'")
show("instruments with NULL list_date (full rows)", mh,
     "SELECT symbol, name, exchange, asset_type, board, list_date, delist_date, status, provider "
     "FROM instruments WHERE list_date IS NULL")

print("=" * 100)
print("SECTION 8  research-window coverage of the bar stores (context for the universe question)")
print("=" * 100)
show("market_history.daily_bars: rows/symbols inside research window", mh,
     "SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) "
     "FROM daily_bars WHERE trade_date BETWEEN ? AND ?", (W0, W1))
show("market_history.daily_bars: any rows BEFORE 2023-09-04 (warm-up)?", mh,
     "SELECT COUNT(*) FROM daily_bars WHERE trade_date < ?", (W0,))
show("daily_bar_cache: rows/symbols inside research window", tl,
     "SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) "
     "FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?", (W0, W1))
show("daily_bar_cache: any rows BEFORE 2023-09-04 (warm-up)?", tl,
     "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date < ?", (W0,))
show("daily_bar_cache: malformed trade_date values", tl,
     "SELECT trade_date, COUNT(*) FROM daily_bar_cache WHERE length(trade_date) <> 10 GROUP BY trade_date")
show("first 10 distinct trade_dates in daily_bars", mh,
     "SELECT trade_date, COUNT(DISTINCT symbol) FROM daily_bars GROUP BY trade_date ORDER BY trade_date LIMIT 10")
show("first 10 distinct trade_dates in daily_bar_cache", tl,
     "SELECT trade_date, COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE length(trade_date)=10 "
     "GROUP BY trade_date ORDER BY trade_date LIMIT 10")

print("=" * 100)
print("SECTION 9  last-trade-date forensics: delisting vs silent truncation")
print("=" * 100)
STORE_END = "2026-09-03"  # last trade_date present in daily_bars
show("daily_bars: histogram of per-symbol last trade_date (buckets)", mh,
     "WITH last AS (SELECT symbol, MAX(trade_date) AS lt FROM daily_bars GROUP BY symbol) "
     "SELECT CASE WHEN lt >= '2026-09-01' THEN 'A current (>=2026-09-01)' "
     "            WHEN lt >= '2026-08-01' THEN 'B stale 1-4wk' "
     "            WHEN lt >= '2026-06-01' THEN 'C stale 1-3mo' "
     "            WHEN lt >= '2026-01-01' THEN 'D stale 3-9mo' "
     "            WHEN lt >= '2025-01-01' THEN 'E stopped in 2025' "
     "            ELSE 'F stopped 2024' END AS bucket, COUNT(*) "
     "FROM last GROUP BY bucket ORDER BY bucket")
show("daily_bars: symbols whose last trade_date < 2026-08-01 (candidate 'dead' names)", mh,
     "WITH last AS (SELECT symbol, MAX(trade_date) AS lt, MIN(trade_date) AS ft, COUNT(*) n "
     "FROM daily_bars GROUP BY symbol) "
     "SELECT l.symbol, i.name, i.status, i.list_date, i.delist_date, l.ft, l.lt, l.n "
     "FROM last l LEFT JOIN instruments i ON i.symbol=l.symbol "
     "WHERE l.lt < '2026-08-01' ORDER BY l.lt", limit=80)
show("daily_bars: COUNT of symbols last<2026-08-01 split by whether instruments explains it", mh,
     "WITH last AS (SELECT symbol, MAX(trade_date) AS lt FROM daily_bars GROUP BY symbol) "
     "SELECT CASE WHEN i.symbol IS NULL THEN 'not in instruments' "
     "            WHEN i.delist_date IS NOT NULL THEN 'has delist_date' "
     "            WHEN i.status <> 'active' THEN 'status != active' "
     "            ELSE 'UNEXPLAINED (status=active, delist_date NULL)' END AS explanation, COUNT(*) "
     "FROM last l LEFT JOIN instruments i ON i.symbol=l.symbol "
     "WHERE l.lt < '2026-08-01' GROUP BY explanation ORDER BY 2 DESC")

show("daily_bar_cache: same bucket histogram", tl,
     "WITH last AS (SELECT symbol, MAX(trade_date) AS lt FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY symbol) "
     "SELECT CASE WHEN lt >= '2026-09-01' THEN 'A current (>=2026-09-01)' "
     "            WHEN lt >= '2026-08-01' THEN 'B stale 1-4wk' "
     "            WHEN lt >= '2026-06-01' THEN 'C stale 1-3mo' "
     "            WHEN lt >= '2026-01-01' THEN 'D stale 3-9mo' "
     "            WHEN lt >= '2025-01-01' THEN 'E stopped in 2025' "
     "            ELSE 'F stopped 2024' END AS bucket, COUNT(*) "
     "FROM last GROUP BY bucket ORDER BY bucket")
show("daily_bar_cache: symbols last<2026-08-01", tl,
     "WITH last AS (SELECT symbol, MAX(trade_date) AS lt, MIN(trade_date) AS ft, COUNT(*) n "
     "FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY symbol) "
     "SELECT symbol, ft, lt, n FROM last WHERE lt < '2026-08-01' ORDER BY lt", limit=80)

print("=" * 100)
print("SECTION 10  symbols in bar stores NOT in instruments (would be the delisted survivors)")
print("=" * 100)
show("daily_bars symbols missing from instruments", mh,
     "SELECT COUNT(DISTINCT b.symbol) FROM daily_bars b LEFT JOIN instruments i ON i.symbol=b.symbol "
     "WHERE i.symbol IS NULL")
show("instruments symbols with ZERO bars in daily_bars", mh,
     "SELECT COUNT(*) FROM instruments i WHERE NOT EXISTS (SELECT 1 FROM daily_bars b WHERE b.symbol=i.symbol)")
show("list them", mh,
     "SELECT i.symbol, i.name, i.status, i.list_date FROM instruments i "
     "WHERE NOT EXISTS (SELECT 1 FROM daily_bars b WHERE b.symbol=i.symbol)", limit=30)
show("daily_bar_cache symbol prefix shapes (sample)", tl,
     "SELECT substr(symbol,1,2) AS pfx, COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY pfx ORDER BY 2 DESC LIMIT 20")
show("daily_bars symbol prefix shapes", mh,
     "SELECT substr(symbol,1,2) AS pfx, COUNT(DISTINCT symbol) FROM daily_bars GROUP BY pfx ORDER BY 2 DESC LIMIT 20")

print("=" * 100)
print("SECTION 11  ST / name-history evidence?")
print("=" * 100)
show("instruments names containing ST (current names only)", mh,
     "SELECT COUNT(*) FROM instruments WHERE name LIKE '%ST%'")
show("sample ST names", mh,
     "SELECT symbol, name, status, list_date FROM instruments WHERE name LIKE '%ST%' ORDER BY symbol", limit=15)
show("is there any dated name history anywhere in market_history?", mh,
     "SELECT name FROM sqlite_master WHERE type='table'")

print("=" * 100)
print("SECTION 12  trading_local.stock_profiles as an alternative listing source?")
print("=" * 100)
for sql in ["SELECT sql FROM sqlite_master WHERE name='stock_profiles'"]:
    show("stock_profiles schema", tl, sql)
show("stock_profiles counts", tl, "SELECT COUNT(*) FROM stock_profiles")

print("=" * 100)
print("SECTION 13  ingest_runs -- what universe was each ingest driven by?")
print("=" * 100)
show("ingest_runs schema", mh, "SELECT sql FROM sqlite_master WHERE name='ingest_runs'")
show("ingest_runs summary", mh,
     "SELECT COUNT(*), MIN(started_at), MAX(started_at) FROM ingest_runs")
mh.close()
tl.close()
