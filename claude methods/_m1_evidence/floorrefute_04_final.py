# -*- coding: utf-8 -*-
import sqlite3
TL=r"D:/codex-A股交易/trading_local.sqlite3"; MH=r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl=ro(TL); mh=ro(MH)
def show(c,sql,t):
    print("-"*88); print(t); print("SQL:"," ".join(sql.split()))
    cur=c.execute(sql); print("  "+" | ".join(d[0] for d in cur.description))
    for r in cur.fetchall()[:30]: print("  "+" | ".join("NULL" if v is None else str(v) for v in r))

show(tl, """
SELECT COUNT(*) AS valid_sessions_in_window,
       MIN(td) AS first_session, MAX(td) AS last_session
FROM (SELECT DISTINCT CAST(trade_date AS TEXT) AS td FROM daily_bar_cache
      WHERE CAST(replace(CAST(trade_date AS TEXT),'-','') AS INTEGER) BETWEEN 20230904 AND 20260904)
""", "F1 valid distinct sessions inside the mandated window (daily_bar_cache)")

show(tl, """
SELECT td, syms FROM (
  SELECT CAST(trade_date AS TEXT) AS td, COUNT(DISTINCT symbol) AS syms
  FROM daily_bar_cache
  WHERE CAST(replace(CAST(trade_date AS TEXT),'-','') AS INTEGER) BETWEEN 20240409 AND 20240701
  GROUP BY 1) ORDER BY td LIMIT 30
""", "F2 breadth per session at the alleged floor: when does the panel actually become full-market?")

show(tl, """
SELECT MIN(td) AS first_session_with_ge_4000_symbols FROM (
  SELECT CAST(trade_date AS TEXT) AS td, COUNT(DISTINCT symbol) AS syms
  FROM daily_bar_cache GROUP BY 1 HAVING COUNT(DISTINCT symbol) >= 4000)
""", "F3 effective FULL-MARKET floor (first session with >=4000 distinct symbols)")

show(tl, """
SELECT COUNT(DISTINCT symbol) AS symbols_with_any_bar_before_2024_06_01
FROM daily_bar_cache
WHERE CAST(replace(CAST(trade_date AS TEXT),'-','') AS INTEGER) BETWEEN 20240409 AND 20240531
""", "F4 how many securities exist at all in the first ~7 weeks above the floor")

show(mh, """
SELECT MIN(td) AS first_session_with_ge_4000_symbols FROM (
  SELECT trade_date AS td FROM daily_bars GROUP BY 1 HAVING COUNT(DISTINCT symbol) >= 4000)
""", "F5 same effective full-market floor in market_history.daily_bars")

show(tl, """
SELECT (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache) AS symbols_cache,
       (SELECT COUNT(*) FROM (SELECT DISTINCT CAST(trade_date AS TEXT) td FROM daily_bar_cache
                              WHERE CAST(trade_date AS TEXT) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')) AS valid_sessions_total
""", "F6 totals")
tl.close(); mh.close()
