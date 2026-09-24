import sqlite3
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")

def q(sql, label):
    print("\n### " + label); print("SQL:", " ".join(sql.split()))
    for r in c.execute(sql): print("   ", r)

q("SELECT asset_type, exchange, status, COUNT(*) FROM mh.instruments GROUP BY 1,2,3 ORDER BY 4 DESC", "instruments census")
q("SELECT length(symbol) AS L, COUNT(*) FROM mh.instruments GROUP BY 1", "instrument symbol lengths")
q("SELECT symbol FROM mh.instruments LIMIT 8", "sample instrument symbols")
q("SELECT length(symbol) AS L, COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1", "cache symbol lengths")
q("SELECT DISTINCT symbol FROM daily_bar_cache LIMIT 8", "sample cache symbols")
q("SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache", "cache distinct symbols total")
q("""SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM daily_bar_cache) d
     JOIN mh.instruments i ON i.symbol=d.symbol""", "cache symbols joinable to instruments")
q("""SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM daily_bar_cache) d
     LEFT JOIN mh.instruments i ON i.symbol=d.symbol WHERE i.symbol IS NULL""", "cache symbols NOT in instruments")
q("SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bar_cache", "cache full date range")
q("SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'", "cache distinct dates in window")
q("SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM mh.daily_bars", "market_history date range/spine")
q("SELECT COUNT(DISTINCT trade_date) FROM mh.daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'", "MH distinct dates in window")
q("SELECT trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AS ok, COUNT(*) FROM daily_bar_cache GROUP BY 1", "cache date format sanity")
q("SELECT source, COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC LIMIT 10", "cache sources")
c.close()
