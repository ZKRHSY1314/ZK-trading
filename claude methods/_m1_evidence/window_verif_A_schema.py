import sqlite3, os
TL = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
con = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
con.execute("PRAGMA query_only=ON")
con.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
c = con.cursor()

print("=== daily_bar_cache DDL ===")
print(c.execute("SELECT sql FROM sqlite_master WHERE name='daily_bar_cache'").fetchone()[0])
print()
print("=== indexes on daily_bar_cache ===")
for r in c.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND tbl_name='daily_bar_cache'"):
    print(r)
print()
print("=== mh.instruments DDL ===")
print(c.execute("SELECT sql FROM mh.sqlite_master WHERE name='instruments'").fetchone()[0])
print()
print("=== sample symbols daily_bar_cache ===")
for r in c.execute("SELECT symbol, trade_date, source FROM daily_bar_cache LIMIT 8"):
    print(r)
print()
print("=== sample symbols mh.instruments ===")
for r in c.execute("SELECT symbol, asset_type, exchange, board, status, list_date, delist_date FROM mh.instruments LIMIT 8"):
    print(r)
print()
print("=== instruments asset_type x exchange census ===")
for r in c.execute("SELECT asset_type, exchange, COUNT(*) FROM mh.instruments GROUP BY 1,2 ORDER BY 3 DESC"):
    print(r)
print()
print("=== GLOBAL trade_date range in daily_bar_cache (no window) ===")
print(c.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT symbol) FROM daily_bar_cache").fetchone())
print()
print("=== distinct trade_date length / format anomalies ===")
for r in c.execute("SELECT LENGTH(trade_date) L, typeof(trade_date) T, COUNT(*) FROM daily_bar_cache GROUP BY 1,2"):
    print(r)
print()
print("=== symbol length census in daily_bar_cache ===")
for r in c.execute("SELECT LENGTH(symbol) L, COUNT(DISTINCT symbol) nsym, COUNT(*) nrow FROM daily_bar_cache GROUP BY 1 ORDER BY 1"):
    print(r)
con.close()
