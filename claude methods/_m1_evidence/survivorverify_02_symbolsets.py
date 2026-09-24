import sqlite3
mh=sqlite3.connect("file:D:/codex-A股交易/market_history.sqlite3?mode=ro",uri=True)
tl=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
q=lambda c,s,p=(): c.execute(s,p).fetchall()

print("### F. index contamination check by symbol pattern in instruments")
print(q(mh,"""SELECT CASE
  WHEN substr(symbol,1,2)='SH' AND substr(symbol,3,3)='000' THEN 'SH000xxx(index-like)'
  WHEN substr(symbol,1,2)='SZ' AND substr(symbol,3,3)='399' THEN 'SZ399xxx(index-like)'
  ELSE 'other' END k, COUNT(*) FROM instruments GROUP BY 1"""))

print()
print("### G. market_history.daily_bars: symbols present in BARS but ABSENT from instruments")
print("   distinct bar symbols:",q(mh,"SELECT COUNT(DISTINCT symbol) FROM daily_bars"))
print("   bar symbols NOT in instruments:",q(mh,"SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM daily_bars WHERE symbol NOT IN (SELECT symbol FROM instruments))"))
print("   instruments with NO bars at all:",q(mh,"SELECT COUNT(*) FROM instruments WHERE symbol NOT IN (SELECT DISTINCT symbol FROM daily_bars)"))

print()
print("### H. THE KEY TEST — trading_local.daily_bar_cache symbols vs the 2026 catalog")
tl.execute("ATTACH DATABASE 'file:D:/codex-A股交易/market_history.sqlite3?mode=ro' AS mh")
print("   distinct cache symbols:",q(tl,"SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache"))
print("   cache symbol format sample:",q(tl,"SELECT symbol FROM daily_bar_cache LIMIT 5"))
print("   cache symbols NOT in mh.instruments (raw):",
  q(tl,"SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM daily_bar_cache WHERE symbol NOT IN (SELECT symbol FROM mh.instruments))"))

print()
print("### I. IMPLICIT DELISTING EVIDENCE: last bar date per symbol, market_history.daily_bars")
print("   max trade_date overall:",q(mh,"SELECT MAX(trade_date) FROM daily_bars"))
rows=q(mh,"""WITH last AS (SELECT symbol, MAX(trade_date) mx FROM daily_bars GROUP BY symbol)
SELECT CASE
  WHEN mx>='2026-08-01' THEN 'A. still trading (>=2026-08)'
  WHEN mx>='2026-06-01' THEN 'B. stops 2026-06/07'
  WHEN mx>='2025-01-01' THEN 'C. stops 2025..2026-05'
  WHEN mx>='2023-09-04' THEN 'D. stops inside window before 2025'
  ELSE 'E. last bar BEFORE window start' END bucket, COUNT(*) n, MIN(mx), MAX(mx)
FROM last GROUP BY 1 ORDER BY 1""")
for r in rows: print("   ",r)

print()
print("### J. same for trading_local.daily_bar_cache (the store the BACKTEST actually reads)")
print("   max trade_date overall:",q(tl,"SELECT MAX(trade_date) FROM daily_bar_cache"))
rows=q(tl,"""WITH last AS (SELECT symbol, MAX(trade_date) mx FROM daily_bar_cache GROUP BY symbol)
SELECT CASE
  WHEN mx>='2026-08-01' THEN 'A. still trading (>=2026-08)'
  WHEN mx>='2026-06-01' THEN 'B. stops 2026-06/07'
  WHEN mx>='2025-01-01' THEN 'C. stops 2025..2026-05'
  WHEN mx>='2023-09-04' THEN 'D. stops inside window before 2025'
  ELSE 'E. last bar BEFORE window start' END bucket, COUNT(*) n, MIN(mx), MAX(mx)
FROM last GROUP BY 1 ORDER BY 1""")
for r in rows: print("   ",r)
