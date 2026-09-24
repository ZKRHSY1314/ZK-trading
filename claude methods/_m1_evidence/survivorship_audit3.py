# -*- coding: utf-8 -*-
"""Read-only survivorship audit, part 3: rolling-window fingerprint + manifest inspection."""
import sqlite3, sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"


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
print("SECTION 14  ROLLING-WINDOW FINGERPRINT: is the store 'last N bars of currently listed names'?")
print("=" * 100)
show("daily_bars: bars-per-symbol histogram (bucketed)", mh,
     "WITH c AS (SELECT symbol, COUNT(*) n FROM daily_bars GROUP BY symbol) "
     "SELECT CASE WHEN n<50 THEN '<50' WHEN n<150 THEN '50-149' WHEN n<300 THEN '150-299' "
     "WHEN n<450 THEN '300-449' WHEN n<=520 THEN '450-520' ELSE '>520' END AS bucket, "
     "COUNT(*) AS symbols, MIN(n), MAX(n) FROM c GROUP BY bucket ORDER BY MIN(n)")
show("daily_bars: exact bars-per-symbol top values", mh,
     "WITH c AS (SELECT symbol, COUNT(*) n FROM daily_bars GROUP BY symbol) "
     "SELECT n, COUNT(*) FROM c GROUP BY n ORDER BY COUNT(*) DESC LIMIT 15")
show("daily_bars: histogram of per-symbol FIRST trade_date (monthly)", mh,
     "WITH f AS (SELECT symbol, MIN(trade_date) ft FROM daily_bars GROUP BY symbol) "
     "SELECT substr(ft,1,7) AS mon, COUNT(*) FROM f GROUP BY mon ORDER BY mon")

print("=" * 100)
print("SECTION 15  first bar vs list_date: truncated history that LOOKS like a new listing")
print("=" * 100)
show("classification of every symbol by (list_date vs first bar date)", mh,
     "WITH f AS (SELECT symbol, MIN(trade_date) ft, MAX(trade_date) lt, COUNT(*) n FROM daily_bars GROUP BY symbol) "
     "SELECT CASE WHEN i.list_date IS NULL THEN '0 no list_date (cannot judge)' "
     "            WHEN i.list_date >= '2024-04-09' THEN '1 genuine new listing (list_date after store start)' "
     "            WHEN f.ft <= '2024-04-30' THEN '2 history reaches store start' "
     "            ELSE '3 TRUNCATED: listed long before, but history starts late' END AS cls, "
     "COUNT(*) FROM f JOIN instruments i ON i.symbol=f.symbol GROUP BY cls ORDER BY cls")
show("worst truncation examples (listed pre-2020, but first bar is late)", mh,
     "WITH f AS (SELECT symbol, MIN(trade_date) ft, COUNT(*) n FROM daily_bars GROUP BY symbol) "
     "SELECT f.symbol, i.name, i.list_date, f.ft, f.n FROM f JOIN instruments i ON i.symbol=f.symbol "
     "WHERE i.list_date < '2020-01-01' AND f.ft > '2024-06-01' ORDER BY f.ft DESC", limit=25)
show("count: listed pre-2024-04-09 but first bar after 2024-04-30", mh,
     "WITH f AS (SELECT symbol, MIN(trade_date) ft FROM daily_bars GROUP BY symbol) "
     "SELECT COUNT(*) FROM f JOIN instruments i ON i.symbol=f.symbol "
     "WHERE i.list_date IS NOT NULL AND i.list_date < '2024-04-09' AND f.ft > '2024-04-30'")
show("of those, how many have >=480 bars (i.e. a full rolling window, not a gap)", mh,
     "WITH f AS (SELECT symbol, MIN(trade_date) ft, COUNT(*) n FROM daily_bars GROUP BY symbol) "
     "SELECT COUNT(*) FROM f JOIN instruments i ON i.symbol=f.symbol "
     "WHERE i.list_date IS NOT NULL AND i.list_date < '2024-04-09' AND f.ft > '2024-04-30' AND f.n >= 480")

print("=" * 100)
print("SECTION 16  How many delistings SHOULD there be? (bars present on an early date but not later)")
print("=" * 100)
for d in ("2024-05-06", "2024-09-02", "2025-03-03", "2025-09-01", "2026-03-02"):
    show("symbols with a bar on %s (breadth check)" % d, mh,
         "SELECT COUNT(DISTINCT symbol) FROM daily_bars WHERE trade_date = ?", (d,))
show("symbols traded on 2024-09-02 but NOT on 2026-09-03 (would be delistings)", mh,
     "SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM daily_bars WHERE trade_date='2024-09-02' "
     "EXCEPT SELECT DISTINCT symbol FROM daily_bars WHERE trade_date='2026-09-03')")
show("list them", mh,
     "SELECT b.symbol, i.name, i.status, i.list_date, i.delist_date FROM "
     "(SELECT DISTINCT symbol FROM daily_bars WHERE trade_date='2024-09-02' "
     " EXCEPT SELECT DISTINCT symbol FROM daily_bars WHERE trade_date='2026-09-03') b "
     "LEFT JOIN instruments i ON i.symbol=b.symbol", limit=40)

print("=" * 100)
print("SECTION 17  trading_local universe-ish tables that could carry dated evidence")
print("=" * 100)
for t, dc in [("candidate_scans", None), ("candidate_scan_items", None), ("auto_discovered_candidates", None)]:
    show("%s schema" % t, tl, "SELECT sql FROM sqlite_master WHERE name=?", (t,))
show("forecast_decisions symbol/date span (what universe was actually traded)", tl,
     "SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(decision_date), MAX(decision_date) FROM forecast_decisions"
     if True else "")
mh.close()
tl.close()

print("=" * 100)
print("SECTION 18  universe manifest files on disk (read-only)")
print("=" * 100)
LOGS = r"D:/codex-A股交易/backend/logs"
for fn in ("current_a_share_universe.json", "universe_backfill_checkpoint.json",
           "universe_backfill_probe.json", "universe_backfill_retry_outcome.json"):
    p = os.path.join(LOGS, fn)
    if not os.path.exists(p):
        print("\n--- %s : MISSING" % fn)
        continue
    st = os.stat(p)
    print("\n--- %s  size=%d bytes  mtime=%s" % (fn, st.st_size, __import__('datetime').datetime.fromtimestamp(st.st_mtime).isoformat()))
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:
        print("    parse error: %r" % e)
        continue
    if isinstance(data, dict):
        print("    top-level keys: %s" % sorted(data.keys())[:40])
        for k, v in list(data.items())[:40]:
            if isinstance(v, (str, int, float, bool)) or v is None:
                print("      %s = %r" % (k, v))
            elif isinstance(v, list):
                print("      %s = list(len=%d) first=%r" % (k, len(v), v[0] if v else None))
            elif isinstance(v, dict):
                print("      %s = dict(len=%d) keys=%s" % (k, len(v), sorted(v.keys())[:15]))
    elif isinstance(data, list):
        print("    list(len=%d) first=%r" % (len(data), data[0] if data else None))
