# -*- coding: utf-8 -*-
"""Read-only survivorship audit, part 7: breadth thresholds + the Dec-2025 truncation cohort."""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MH = r"D:/codex-A股交易/market_history.sqlite3"


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


mh = sqlite3.connect("file:%s?mode=ro" % MH, uri=True)

print("=" * 100)
print("SECTION 28  exact date the store first reaches broad breadth")
print("=" * 100)
show("first trade_date with >=4000 distinct symbols", mh,
     "SELECT MIN(trade_date) FROM (SELECT trade_date FROM daily_bars GROUP BY trade_date "
     "HAVING COUNT(DISTINCT symbol) >= 4000)")
show("first trade_date with >=5000 distinct symbols", mh,
     "SELECT MIN(trade_date) FROM (SELECT trade_date FROM daily_bars GROUP BY trade_date "
     "HAVING COUNT(DISTINCT symbol) >= 5000)")
show("first trade_date with >=5400 distinct symbols", mh,
     "SELECT MIN(trade_date) FROM (SELECT trade_date FROM daily_bars GROUP BY trade_date "
     "HAVING COUNT(DISTINCT symbol) >= 5400)")
show("June 2024 daily breadth (the ramp)", mh,
     "SELECT trade_date, COUNT(DISTINCT symbol) FROM daily_bars WHERE trade_date BETWEEN '2024-06-01' AND '2024-07-05' "
     "GROUP BY trade_date ORDER BY trade_date")
show("Dec 2025 daily breadth (the second wave)", mh,
     "SELECT trade_date, COUNT(DISTINCT symbol) FROM daily_bars WHERE trade_date BETWEEN '2025-11-25' AND '2025-12-20' "
     "GROUP BY trade_date ORDER BY trade_date")

print("=" * 100)
print("SECTION 29  the 2025-12 cohort: 340 symbols whose history starts in Dec 2025")
print("=" * 100)
show("cohort size + how many were listed long before", mh,
     "WITH f AS (SELECT symbol, MIN(trade_date) ft, COUNT(*) n FROM daily_bars GROUP BY symbol) "
     "SELECT COUNT(*) AS cohort, SUM(i.list_date < '2024-06-24') AS listed_before_store_broad, "
     "SUM(i.list_date IS NULL) AS no_list_date "
     "FROM f JOIN instruments i ON i.symbol=f.symbol WHERE substr(f.ft,1,7)='2025-12'")
show("cohort exchange breakdown", mh,
     "WITH f AS (SELECT symbol, MIN(trade_date) ft FROM daily_bars GROUP BY symbol) "
     "SELECT i.exchange, i.board, COUNT(*) FROM f JOIN instruments i ON i.symbol=f.symbol "
     "WHERE substr(f.ft,1,7)='2025-12' GROUP BY i.exchange, i.board ORDER BY 3 DESC")
show("cohort sample", mh,
     "WITH f AS (SELECT symbol, MIN(trade_date) ft, COUNT(*) n FROM daily_bars GROUP BY symbol) "
     "SELECT f.symbol, i.name, i.exchange, i.list_date, f.ft, f.n FROM f JOIN instruments i ON i.symbol=f.symbol "
     "WHERE substr(f.ft,1,7)='2025-12' ORDER BY i.list_date", limit=15)

print("=" * 100)
print("SECTION 30  BJ (Beijing exchange) coverage -- the whole board arrived late")
print("=" * 100)
show("BJ symbols: first bar date histogram", mh,
     "WITH f AS (SELECT symbol, MIN(trade_date) ft FROM daily_bars WHERE symbol LIKE 'BJ%' GROUP BY symbol) "
     "SELECT substr(ft,1,7) mon, COUNT(*) FROM f GROUP BY mon ORDER BY mon")
show("SH/SZ symbols: first bar date histogram", mh,
     "WITH f AS (SELECT symbol, MIN(trade_date) ft FROM daily_bars WHERE symbol LIKE 'SH%' OR symbol LIKE 'SZ%' "
     "GROUP BY symbol) SELECT substr(ft,1,7) mon, COUNT(*) FROM f GROUP BY mon ORDER BY mon", limit=40)
mh.close()
