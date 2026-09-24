import sqlite3, json, collections
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON")
c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
q = lambda s,*a: c.execute(s,a).fetchall()

print("=== A. trade_date FORMAT CENSUS in daily_bar_cache (whole table, no window) ===")
sql_a = """SELECT length(trade_date) L,
                  SUM(CASE WHEN trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN 1 ELSE 0 END) glob_ok,
                  COUNT(*) n, MIN(trade_date), MAX(trade_date), typeof(trade_date) t
           FROM daily_bar_cache GROUP BY L, t ORDER BY n DESC"""
print(sql_a)
for r in q(sql_a): print(" ", r)

print("\n=== B. FULL date span of daily_bar_cache (any symbol) ===")
sql_b = "SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date), COUNT(*) FROM daily_bar_cache"
print(sql_b); print(" ", q(sql_b)[0])

print("\n=== C. distinct sessions in RESEARCH WINDOW, ALL symbols (no stock filter) ===")
sql_c = """SELECT COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date), COUNT(*)
           FROM daily_bar_cache
           WHERE trade_date >= '2023-09-04' AND trade_date <= '2026-09-04'"""
print(sql_c); print(" ", q(sql_c)[0])

print("\n=== D. sessions in window BEFORE 2024-04-09 and what symbols carry them ===")
sql_d = """SELECT trade_date, COUNT(DISTINCT symbol) nsym, COUNT(*) nrow
           FROM daily_bar_cache
           WHERE trade_date >= '2023-09-04' AND trade_date < '2024-04-09'
           GROUP BY 1 ORDER BY 1 LIMIT 25"""
print(sql_d)
for r in q(sql_d): print(" ", r)
sql_d2 = """SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache
            WHERE trade_date >= '2023-09-04' AND trade_date < '2024-04-09'"""
print(sql_d2); print("  pre-ramp sessions in window:", q(sql_d2)[0])

print("\n=== E. instruments asset_type / exchange census (is 'stock' the only stock label?) ===")
sql_e = "SELECT asset_type, exchange, COUNT(*) FROM mh.instruments GROUP BY 1,2 ORDER BY 3 DESC"
print(sql_e)
for r in q(sql_e): print(" ", r)

print("\n=== F. symbol FORMAT compatibility between the two DBs (join loss test) ===")
sql_f1 = "SELECT symbol FROM daily_bar_cache LIMIT 5"
print(" dbc sample:", [r[0] for r in q(sql_f1)])
sql_f2 = "SELECT symbol FROM mh.instruments LIMIT 5"
print(" instruments sample:", [r[0] for r in q(sql_f2)])
sql_f3 = """SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM daily_bar_cache) d
            LEFT JOIN mh.instruments i ON i.symbol=d.symbol WHERE i.symbol IS NULL"""
print(sql_f3); print("  dbc symbols NOT in instruments:", q(sql_f3)[0][0])
sql_f4 = "SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache"
print("  dbc distinct symbols total:", q(sql_f4)[0][0])
