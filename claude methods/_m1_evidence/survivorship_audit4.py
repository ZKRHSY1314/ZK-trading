# -*- coding: utf-8 -*-
"""Read-only survivorship audit, part 4: manifest files + suspension vs delisting."""
import sqlite3, sys, io, json, os, datetime
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
print("SECTION 17b  the 6 'active' symbols absent on 2026-09-03: suspension or truncation?")
print("=" * 100)
show("their first/last bar + count", mh,
     "SELECT b.symbol, i.name, i.status, i.list_date, MIN(b.trade_date), MAX(b.trade_date), COUNT(*) "
     "FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol "
     "WHERE b.symbol IN ('SH600929','SH688432','SZ002731','SZ002870','SZ301139','SZ301266') "
     "GROUP BY b.symbol, i.name, i.status, i.list_date")
show("gap analysis: symbols with a bar on 2026-08-31 but none on 2026-09-03 (1-day suspensions)", mh,
     "SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM daily_bars WHERE trade_date='2026-08-31' "
     "EXCEPT SELECT DISTINCT symbol FROM daily_bars WHERE trade_date='2026-09-03')")
show("distribution: bars missing per symbol across the 586 store dates, for symbols whose "
     "[first..last] span covers all of 2024-07-01..2026-09-03", mh,
     "WITH span AS (SELECT symbol, MIN(trade_date) ft, MAX(trade_date) lt, COUNT(*) n FROM daily_bars GROUP BY symbol), "
     "dates AS (SELECT COUNT(DISTINCT trade_date) d FROM daily_bars WHERE trade_date BETWEEN '2024-07-01' AND '2026-09-03') "
     "SELECT CASE WHEN (SELECT d FROM dates) - s.n <= 0 THEN '0 missing' "
     "            WHEN (SELECT d FROM dates) - s.n <= 5 THEN '1-5 missing' "
     "            WHEN (SELECT d FROM dates) - s.n <= 20 THEN '6-20 missing' "
     "            WHEN (SELECT d FROM dates) - s.n <= 60 THEN '21-60 missing' "
     "            ELSE '>60 missing' END AS bucket, COUNT(*) "
     "FROM span s WHERE s.ft <= '2024-07-01' AND s.lt >= '2026-09-03' GROUP BY bucket ORDER BY bucket")

print("=" * 100)
print("SECTION 17c  forecast_decisions: what universe did the system actually act on?")
print("=" * 100)
show("forecast_decisions schema", tl, "SELECT sql FROM sqlite_master WHERE name='forecast_decisions'")

print("=" * 100)
print("SECTION 18  universe manifest files on disk (read-only)")
print("=" * 100)
LOGS = r"D:/codex-A股交易/backend/logs"
for fn in ("current_a_share_universe.json", "universe_backfill_checkpoint.json",
           "universe_backfill_probe.json", "universe_backfill_retry_outcome.json",
           "instrument_catalog_refresh_heartbeat.json", "reference_data_heartbeat.json"):
    p = os.path.join(LOGS, fn)
    if not os.path.exists(p):
        print("\n--- %s : MISSING" % fn)
        continue
    st = os.stat(p)
    print("\n--- %s  size=%d  mtime=%s" % (fn, st.st_size, datetime.datetime.fromtimestamp(st.st_mtime).isoformat()))
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:
        print("    parse error: %r" % e)
        continue
    if isinstance(data, dict):
        print("    top-level keys: %s" % sorted(data.keys())[:60])
        for k, v in list(data.items())[:60]:
            if isinstance(v, (str, int, float, bool)) or v is None:
                print("      %s = %r" % (k, v))
            elif isinstance(v, list):
                print("      %s = list(len=%d) first=%r" % (k, len(v), v[0] if v else None))
            elif isinstance(v, dict):
                ks = sorted(v.keys())
                print("      %s = dict(len=%d) keys=%s" % (k, len(v), ks[:12]))
                for kk in ks[:3]:
                    print("          sample %s -> %r" % (kk, v[kk]))
    elif isinstance(data, list):
        print("    list(len=%d) first=%r" % (len(data), data[0] if data else None))
mh.close()
tl.close()
