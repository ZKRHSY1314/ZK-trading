# -*- coding: utf-8 -*-
"""Read-only survivorship audit, part 6: available_at semantics + breadth ramp."""
import sqlite3, sys, io
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
print("SECTION 24  available_at: real point-in-time, or just ingest time?")
print("=" * 100)
show("available_at vs trade_date lag distribution (sample of dates)", mh,
     "SELECT trade_date, MIN(available_at), MAX(available_at), COUNT(*) FROM daily_bars "
     "WHERE trade_date IN ('2024-07-01','2025-01-02','2025-07-01','2026-01-05','2026-09-03') "
     "GROUP BY trade_date ORDER BY trade_date")
show("how many bars have available_at EARLIER than trade_date (impossible / lookahead)", mh,
     "SELECT COUNT(*) FROM daily_bars WHERE substr(available_at,1,10) < trade_date")
show("how many bars have available_at more than 30 days after trade_date (bulk backfill signature)", mh,
     "SELECT COUNT(*) FROM daily_bars WHERE julianday(substr(available_at,1,10)) - julianday(trade_date) > 30")
show("total bars", mh, "SELECT COUNT(*) FROM daily_bars")
show("available_at distribution by day (top 10)", mh,
     "SELECT substr(available_at,1,10) d, COUNT(*) FROM daily_bars GROUP BY d ORDER BY 2 DESC LIMIT 10")

print("=" * 100)
print("SECTION 25  breadth ramp: distinct symbols with a bar, by month")
print("=" * 100)
show("daily_bars monthly breadth (max symbols on any date in month)", mh,
     "WITH per_date AS (SELECT trade_date, COUNT(DISTINCT symbol) c FROM daily_bars GROUP BY trade_date) "
     "SELECT substr(trade_date,1,7) mon, MIN(c), MAX(c), COUNT(*) AS trading_dates FROM per_date "
     "GROUP BY mon ORDER BY mon")

print("=" * 100)
print("SECTION 26  research-window denominators (measured, not assumed)")
print("=" * 100)
show("distinct trade dates in daily_bars, by calendar year", mh,
     "SELECT substr(trade_date,1,4) y, COUNT(DISTINCT trade_date) FROM daily_bars GROUP BY y ORDER BY y")
show("distinct trade dates in window 2023-09-04..2024-04-08 (the missing head)", mh,
     "SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2024-04-08'")
show("same for daily_bar_cache", tl,
     "SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2024-04-08'")

print("=" * 100)
print("SECTION 27  index rows inside daily_bar_cache (must not be counted as stocks)")
print("=" * 100)
show("index-sourced symbols in daily_bar_cache", tl,
     "SELECT DISTINCT symbol, source, MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bar_cache "
     "WHERE source='akshare.stock_zh_index_daily' GROUP BY symbol, source")
show("daily_bar_cache symbols that are NOT SH/SZ/BJ prefixed", tl,
     "SELECT symbol, COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache "
     "WHERE substr(symbol,1,2) NOT IN ('SH','SZ','BJ') GROUP BY symbol")
mh.close()
tl.close()
