import sqlite3, re, collections
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON"); c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
q = lambda s,*a: c.execute(s,a).fetchall()

print("=== G. symbol shape census, daily_bar_cache DISTINCT symbols ===")
sql_g = """SELECT CASE WHEN symbol GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]' THEN 'bare6'
                       WHEN symbol GLOB '[A-Z][A-Z][0-9]*' THEN 'XX+digits'
                       ELSE 'other' END shape, COUNT(*) n
           FROM (SELECT DISTINCT symbol FROM daily_bar_cache) GROUP BY 1 ORDER BY 2 DESC"""
print(sql_g)
for r in q(sql_g): print("  ", r)

print("\n=== H. symbol shape census, mh.instruments ===")
sql_h = """SELECT CASE WHEN symbol GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]' THEN 'bare6'
                       WHEN symbol GLOB '[A-Z][A-Z][0-9]*' THEN 'XX+digits'
                       ELSE 'other' END shape, exchange, COUNT(*) n
           FROM mh.instruments GROUP BY 1,2 ORDER BY 3 DESC"""
print(sql_h)
for r in q(sql_h): print("  ", r)

print("\n=== I. the 6 dbc symbols NOT in instruments ===")
sql_i = """SELECT d.symbol, COUNT(*) rows_, MIN(b.trade_date), MAX(b.trade_date)
           FROM (SELECT DISTINCT symbol FROM daily_bar_cache) d
           LEFT JOIN mh.instruments i ON i.symbol=d.symbol
           JOIN daily_bar_cache b ON b.symbol=d.symbol
           WHERE i.symbol IS NULL GROUP BY 1"""
print(sql_i)
for r in q(sql_i): print("  ", r)

print("\n=== J. DOUBLE-REPRESENTATION test: does dbc hold BOTH '920000' and 'BJ920000'? ===")
sql_j = """SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM daily_bar_cache) a
           JOIN (SELECT DISTINCT symbol FROM daily_bar_cache) b
             ON b.symbol = substr(a.symbol,3)
           WHERE a.symbol GLOB '[A-Z][A-Z][0-9]*'"""
print(sql_j); print("   prefixed symbols whose bare form ALSO exists:", q(sql_j)[0][0])

print("\n=== K. the ERROR trade_date row ===")
sql_k = "SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status, created_at FROM daily_bar_cache WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"
print(sql_k)
for r in q(sql_k): print("  ", r)

print("\n=== L. dbc symbols whose bars exist but are NOT bare6 (prefixed) - do they carry sessions? ===")
sql_l = """SELECT COUNT(DISTINCT symbol), COUNT(*), MIN(trade_date), MAX(trade_date)
           FROM daily_bar_cache WHERE symbol NOT GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'"""
print(sql_l); print("  ", q(sql_l)[0])
