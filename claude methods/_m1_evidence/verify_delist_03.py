# -*- coding: utf-8 -*-
"""Part 3: is there a delisting timeline in the OPERATIONAL store the auditor never looked at?
READ-ONLY."""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"
tl = sqlite3.connect("file:%s?mode=ro" % TL, uri=True)
tl.execute("ATTACH DATABASE ? AS mh", ("file:%s?mode=ro" % MH,))

def show(t, con, sql, p=()):
    print("\n" + "=" * 78); print(t); print("SQL: " + " ".join(sql.split()))
    cur = con.execute(sql, p); cols=[d[0] for d in cur.description]; rows=cur.fetchall()
    print("  " + " | ".join(cols))
    for r in rows: print("  " + " | ".join("NULL" if v is None else str(v) for v in r))
    print("  (%d row(s))" % len(rows)); return rows

print("#"*78)
print("H. OPERATIONAL STORE: symbols whose trading STOPS mid-window (the delisting population)")
print("#"*78)

show("H1. daily_bar_cache: distribution of each symbol's LAST bar, by year -- how many stopped in 23/24/25?", tl, """
WITH last_seen AS (
  SELECT symbol, MAX(trade_date) AS last_bar, COUNT(*) AS n
  FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? GROUP BY symbol
)
SELECT substr(last_bar,1,7) AS last_bar_month, COUNT(*) AS symbols
FROM last_seen WHERE last_bar < '2026-08-01' GROUP BY last_bar_month ORDER BY last_bar_month
""", (W0, W1))

show("H2. daily_bar_cache symbols in window that have NO market_history.instruments row\n"
     "    (delisted names surviving only in the operational store?)", tl, """
SELECT COUNT(DISTINCT c.symbol) AS cache_symbols_not_catalogued
FROM daily_bar_cache AS c LEFT JOIN mh.instruments AS i ON i.symbol = c.symbol
WHERE c.trade_date BETWEEN ? AND ? AND i.symbol IS NULL
""", (W0, W1))

show("H3. list them (if any) with their trading span", tl, """
SELECT c.symbol, MIN(c.trade_date) AS first_bar, MAX(c.trade_date) AS last_bar, COUNT(*) AS n
FROM daily_bar_cache AS c LEFT JOIN mh.instruments AS i ON i.symbol = c.symbol
WHERE c.trade_date BETWEEN ? AND ? AND i.symbol IS NULL
GROUP BY c.symbol ORDER BY last_bar LIMIT 40
""", (W0, W1))

print("\n"+"#"*78)
print("I. THE DEEPER PROBLEM: does ANY store contain a stock that stopped trading in 2023/2024/2025?")
print("#"*78)

show("I1. market_history.daily_bars, NO window filter: last-bar year histogram", tl, """
WITH last_seen AS (SELECT symbol, MAX(trade_date) AS last_bar FROM mh.daily_bars GROUP BY symbol)
SELECT substr(last_bar,1,4) AS last_bar_year, COUNT(*) AS symbols FROM last_seen
GROUP BY last_bar_year ORDER BY last_bar_year
""")

show("I2. trading_local.daily_bar_cache, NO window filter: last-bar year histogram", tl, """
WITH last_seen AS (SELECT symbol, MAX(trade_date) AS last_bar FROM daily_bar_cache GROUP BY symbol)
SELECT substr(last_bar,1,4) AS last_bar_year, COUNT(*) AS symbols FROM last_seen
GROUP BY last_bar_year ORDER BY last_bar_year
""")

print("\n"+"#"*78)
print("J. Does updated_at actually discriminate? (the UPDATE has an AND status='active' guard,\n"
     "   so it fires only on the active->inactive TRANSITION and then freezes)")
print("#"*78)

show("J1. inactive rows: updated_at vs last traded bar -- gap in days", tl, """
SELECT i.symbol, i.name, substr(i.updated_at,1,10) AS marked_inactive_on,
       MAX(b.trade_date) AS last_bar,
       CAST(julianday(substr(i.updated_at,1,10)) - julianday(MAX(b.trade_date)) AS INT) AS days_after_last_bar
FROM mh.instruments AS i LEFT JOIN mh.daily_bars AS b ON b.symbol = i.symbol
WHERE i.status <> 'active'
GROUP BY i.symbol, i.name, i.updated_at ORDER BY last_bar
""")

tl.close()
