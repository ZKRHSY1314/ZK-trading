import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c = ro(OP); c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")

print("=== I. Which load batches contribute the 52,358 '<=3d live' rows? ===")
q="""SELECT substr(created_at,1,10) cdate, COUNT(*) n_le3, COUNT(DISTINCT trade_date) tdays,
       MIN(trade_date) mn, MAX(trade_date) mx
FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'
  AND julianday(substr(created_at,1,10))-julianday(trade_date) <= 3
GROUP BY 1 ORDER BY 1"""
print("SQL:", q)
for r in c.execute(q): print("  ", r)

print("\n=== J. UTC-vs-local skew check: created_at is SQLite CURRENT_TIMESTAMP (UTC), updated_at is datetime.now() (local) ===")
q2="""SELECT MIN(created_at), MAX(created_at), MIN(updated_at), MAX(updated_at),
   SUM(CASE WHEN substr(created_at,12,2) >= '16' THEN 1 ELSE 0 END) inserted_after_16h_utc, COUNT(*)
FROM daily_bar_cache"""
print("SQL:", q2); print("  ", list(c.execute(q2))[0])
print("  -> rows stamped >=16:00 UTC would fall on the NEXT local (UTC+8) day; a UTC created_at can only")
print("     UNDERSTATE lag vs local calendar, so it cannot manufacture the 98.19%.")

print("\n=== K. Is market_history.available_at a real point-in-time field, or just the scrape clock? ===")
q3="""SELECT SUM(available_at = fetched_at) equal_rows, COUNT(*) total FROM mh.daily_bars"""
print("SQL:", q3); print("  ", list(c.execute(q3))[0])
q4="""SELECT COUNT(*) FROM mh.daily_bars WHERE substr(available_at,1,10) < trade_date"""
print("SQL:", q4); print("  available_at BEFORE its own trade_date (impossible):", list(c.execute(q4))[0][0])
q5="""SELECT CASE WHEN substr(available_at,1,10)=trade_date THEN 'same_day'
   WHEN julianday(substr(available_at,1,10))-julianday(trade_date)<=3 THEN '1to3d'
   ELSE 'backfilled_gt3d' END k, COUNT(*) n
FROM mh.daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' GROUP BY 1"""
print("SQL:", q5)
tot=0; rows=[]
for k,n in c.execute(q5): rows.append((k,n)); tot+=n
for k,n in rows: print(f"   {k:18s} {n:>9,}  {100*n/tot:6.2f}%")

print("\n=== L. HEADLINE RESTATED FROM MY OWN QUERY (single self-contained SQL) ===")
q6="""SELECT COUNT(*) AS window_rows,
  SUM(CASE WHEN julianday(substr(created_at,1,10)) - julianday(trade_date) > 3 THEN 1 ELSE 0 END) AS backfilled_gt3d,
  ROUND(100.0*SUM(CASE WHEN julianday(substr(created_at,1,10)) - julianday(trade_date) > 3 THEN 1 ELSE 0 END)/COUNT(*), 2) AS pct_backfilled,
  COUNT(DISTINCT symbol) AS symbols, MIN(trade_date) AS first_bar, MAX(trade_date) AS last_bar
FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'"""
print("SQL:", q6)
print("  ", list(c.execute(q6))[0])
print("\n=== M. Window coverage gap: research window starts 2023-09-04 but first bar is? ===")
q7="""SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date < '2024-04-09'"""
print("SQL:", q7); print("  rows in 2023-09-04..2024-04-08 :", list(c.execute(q7))[0][0])
c.close()
