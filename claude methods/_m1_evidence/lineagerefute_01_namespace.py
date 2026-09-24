import sqlite3
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{HIST}?mode=ro", uri=True); c.execute("PRAGMA query_only=ON")
c.execute(f"ATTACH DATABASE 'file:{CACHE}?mode=ro' AS cache")
q = lambda s: c.execute(s).fetchall()

print("=== A. symbol-namespace census ===")
SQL_A = """
SELECT CASE
         WHEN symbol GLOB '[A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9]' THEN 'prefixed(XX999999)'
         WHEN symbol GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'           THEN 'bare(999999)'
         ELSE 'other'
       END AS ns,
       COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms
FROM cache.daily_bar_cache GROUP BY 1 ORDER BY 2 DESC"""
print("cache.daily_bar_cache:")
for r in q(SQL_A): print("   ", r)
print("main.daily_bars:")
for r in q(SQL_A.replace("cache.daily_bar_cache","main.daily_bars")): print("   ", r)

print("\n=== B. 'other' namespace examples in cache ===")
for r in q("""SELECT symbol, COUNT(*) FROM cache.daily_bar_cache
              WHERE symbol NOT GLOB '[A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9]'
                AND symbol NOT GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'
              GROUP BY 1 ORDER BY 2 DESC LIMIT 15"""): print("   ", r)

print("\n=== C. do bare cache symbols shadow a prefixed twin? ===")
SQL_C = """
WITH bare AS (
  SELECT symbol, trade_date FROM cache.daily_bar_cache
  WHERE symbol GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'
)
SELECT
  (SELECT COUNT(*) FROM bare) AS bare_rows,
  (SELECT COUNT(DISTINCT symbol) FROM bare) AS bare_syms,
  (SELECT COUNT(*) FROM bare b
     WHERE EXISTS (SELECT 1 FROM cache.daily_bar_cache c2
                   WHERE c2.symbol IN ('SH'||b.symbol,'SZ'||b.symbol,'BJ'||b.symbol)
                     AND c2.trade_date=b.trade_date)) AS bare_rows_with_prefixed_twin_in_cache,
  (SELECT COUNT(*) FROM bare b
     WHERE EXISTS (SELECT 1 FROM main.daily_bars h
                   WHERE h.symbol IN ('SH'||b.symbol,'SZ'||b.symbol,'BJ'||b.symbol)
                     AND h.trade_date=b.trade_date)) AS bare_rows_present_in_hist_under_prefix
"""
print("   ", q(SQL_C)[0])
print("    cols: bare_rows, bare_syms, twin_in_cache, present_in_hist_under_prefix")
