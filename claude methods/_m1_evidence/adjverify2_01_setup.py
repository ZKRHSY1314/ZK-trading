import sqlite3
LOCAL = r"D:/codex-A股交易/trading_local.sqlite3"
MH    = r"D:/codex-A股交易/market_history.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"
print("sqlite lib version:", sqlite3.sqlite_version)
c = sqlite3.connect(f"file:{LOCAL}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS mh", (f"file:{MH}?mode=ro",))
def q(l,s,p=()):
    print("="*95); print(l); print("SQL:", " ".join(s.split()))
    for r in c.execute(s,p).fetchall()[:40]: print("   ",r)

q("B1 the 6 symbols with no instrument row + how SH000001/SH000300 classify",
  """SELECT d.symbol, i.exchange, i.asset_type, i.status
     FROM (SELECT DISTINCT symbol FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?) d
     LEFT JOIN mh.instruments i ON i.symbol=d.symbol
     WHERE i.symbol IS NULL OR d.symbol IN ('SH000001','SH000300')""",(W0,W1))

q("B2 exchange values present in mh.instruments overall",
  "SELECT exchange, asset_type, COUNT(*) FROM mh.instruments GROUP BY 1,2 ORDER BY 3 DESC")

q("B3 EARLIEST rows in window - does cache even cover 2023-09-04..2024-04?",
  """SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bar_cache
     WHERE trade_date BETWEEN ? AND ?""",(W0,W1))

q("B4 rows per year-month at the start of the window",
  """SELECT substr(trade_date,1,7) ym, COUNT(*) n, COUNT(DISTINCT symbol) s
     FROM daily_bar_cache WHERE trade_date BETWEEN ? AND '2024-09-30'
     GROUP BY 1 ORDER BY 1""",(W0,))

q("B5 indexes on daily_bar_cache",
  "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='daily_bar_cache'")
