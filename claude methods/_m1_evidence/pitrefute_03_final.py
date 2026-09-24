import sqlite3
con = sqlite3.connect(r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro", uri=True)
q=lambda s: con.execute(s).fetchall()
print("--- 1. HEADLINE, my own SQL (date()+CAST, not substr) ---")
print(q("""
SELECT SUM(CASE WHEN CAST(julianday(date(created_at))-julianday(date(trade_date)) AS INTEGER)<=3
                THEN 1 ELSE 0 END) AS near_live,
       SUM(CASE WHEN CAST(julianday(date(created_at))-julianday(date(trade_date)) AS INTEGER)>3
                THEN 1 ELSE 0 END) AS backfilled,
       COUNT(*) AS denom,
       ROUND(100.0*SUM(CASE WHEN CAST(julianday(date(created_at))-julianday(date(trade_date)) AS INTEGER)>3
                THEN 1 ELSE 0 END)/COUNT(*),4) AS pct_backfilled
FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'"""))

print("\n--- 2. BULK-LOAD CONCENTRATION (kills the 'latency distribution' reading) ---")
print(q("""SELECT date(created_at) d, COUNT(*) n,
           ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM daily_bar_cache),2) pct
    FROM daily_bar_cache GROUP BY d ORDER BY n DESC LIMIT 3"""))

print("\n--- 3. SESSION-LEVEL denominator (the sharper metric) ---")
print(q("""SELECT COUNT(DISTINCT trade_date) sessions_held,
   COUNT(DISTINCT CASE WHEN julianday(date(created_at))-julianday(date(trade_date))<=3
                       THEN trade_date END) sessions_with_any_near_live
   FROM daily_bar_cache
   WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
     AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'"""))

print("\n--- 4. THE MISLEADING UNIT: distinct symbols (do NOT use this denominator) ---")
print(q("""SELECT COUNT(DISTINCT symbol) all_syms,
   COUNT(DISTINCT CASE WHEN date(created_at)=trade_date THEN symbol END) syms_with_a_sameday_row
   FROM daily_bar_cache"""))

print("\n--- 5. SANITY: no NULLs, no negative lag, no dup keys, no index symbols ---")
print("null created_at:", q("SELECT COUNT(*) FROM daily_bar_cache WHERE created_at IS NULL")[0][0],
      "| negative lag:", q("SELECT COUNT(*) FROM daily_bar_cache WHERE date(created_at)<trade_date AND trade_date GLOB '[0-9]*'")[0][0],
      "| dup(sym,date):", q("SELECT COUNT(*) FROM (SELECT symbol,trade_date FROM daily_bar_cache GROUP BY 1,2 HAVING COUNT(*)>1)")[0][0])
con.close()
