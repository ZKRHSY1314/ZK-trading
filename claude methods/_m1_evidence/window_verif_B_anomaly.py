import sqlite3
TL = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
con = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
con.execute("PRAGMA query_only=ON")
con.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
c = con.cursor()

print("=== the 4 length-6 symbols ===")
for r in c.execute("SELECT symbol, COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE LENGTH(symbol)=6 GROUP BY 1"):
    print(r)
print()
print("=== the LENGTH=5 trade_date row(s) ===")
for r in c.execute("SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status, created_at FROM daily_bar_cache WHERE LENGTH(trade_date)<>10"):
    print(r)
print()
print("=== TRUE max valid trade_date ===")
print(c.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'").fetchone())
print()
print("=== length-8 symbols NOT in mh.instruments ===")
for r in c.execute("""SELECT d.symbol, COUNT(*) FROM daily_bar_cache d
  LEFT JOIN mh.instruments i ON i.symbol=d.symbol
  WHERE i.symbol IS NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 20"""):
    print(r)
print()
print("=== symbols in daily_bar_cache: prefix census ===")
for r in c.execute("SELECT SUBSTR(symbol,1,2) p, COUNT(DISTINCT symbol) nsym, COUNT(*) nrow FROM daily_bar_cache GROUP BY 1 ORDER BY 3 DESC"):
    print(r)
print()
print("=== window session count, 3 denominators ===")
q = """SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache
       WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'
         AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"""
print("sessions in window (all symbols):", c.execute(q).fetchone()[0])
print("sessions in window (stock-joined):", c.execute("""
  SELECT COUNT(DISTINCT d.trade_date) FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
  WHERE d.trade_date BETWEEN '2023-09-04' AND '2026-09-04'
    AND d.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'""").fetchone()[0])
print("sessions ALL TIME valid-format:", c.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'").fetchone()[0])
print("any rows outside window at all?", c.execute("""SELECT COUNT(*) FROM daily_bar_cache
  WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
    AND (trade_date < '2023-09-04' OR trade_date > '2026-09-04')""").fetchone()[0])
con.close()
