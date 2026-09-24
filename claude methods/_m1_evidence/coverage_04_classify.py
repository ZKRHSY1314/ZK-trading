import sqlite3, pathlib, sys
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
def rouri(p): return "file:" + pathlib.Path(p).as_posix() + "?mode=ro"
c = sqlite3.connect(rouri(OP), uri=True)
c.execute("ATTACH DATABASE ? AS mh", (rouri(MH),))
def show(label, sql, params=()):
    print("### " + label); print("SQL:", " ".join(sql.split()))
    rows = list(c.execute(sql, params))
    for r in rows[:60]: print("   ", r)
    if len(rows) > 60: print(f"    ... ({len(rows)} rows total)")
    print(flush=True)

show("cache symbols NOT present in mh.instruments (unclassifiable)",
 """SELECT d.symbol, COUNT(*) n, MIN(d.trade_date), MAX(d.trade_date), MIN(d.source)
    FROM daily_bar_cache d LEFT JOIN mh.instruments i ON i.symbol = d.symbol
    WHERE i.symbol IS NULL GROUP BY d.symbol ORDER BY n DESC""")
show("count of unclassifiable cache symbols + their rows",
 """SELECT COUNT(DISTINCT d.symbol), COUNT(*) FROM daily_bar_cache d
    LEFT JOIN mh.instruments i ON i.symbol=d.symbol WHERE i.symbol IS NULL""")
show("cache symbols by source=index",
 """SELECT symbol, COUNT(*) FROM daily_bar_cache WHERE source='akshare.stock_zh_index_daily' GROUP BY 1 ORDER BY 2 DESC""")
show("mh.daily_bars symbols NOT in instruments",
 """SELECT COUNT(DISTINCT b.symbol) FROM mh.daily_bars b LEFT JOIN mh.instruments i ON i.symbol=b.symbol WHERE i.symbol IS NULL""")
show("instruments with NO bars in cache",
 """SELECT COUNT(*) FROM mh.instruments i WHERE NOT EXISTS (SELECT 1 FROM daily_bar_cache d WHERE d.symbol=i.symbol)""")
show("instruments with NO bars in mh.daily_bars",
 """SELECT COUNT(*) FROM mh.instruments i WHERE NOT EXISTS (SELECT 1 FROM mh.daily_bars b WHERE b.symbol=i.symbol)""")
show("list them (instruments missing from mh.daily_bars)",
 """SELECT i.symbol, i.name, i.exchange, i.board, i.list_date, i.status FROM mh.instruments i
    WHERE NOT EXISTS (SELECT 1 FROM mh.daily_bars b WHERE b.symbol=i.symbol) ORDER BY i.symbol""")
show("distinct STOCK symbols in cache window (classified via instruments)",
 """SELECT COUNT(DISTINCT d.symbol) FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
    WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
      AND d.trade_date BETWEEN '2023-09-04' AND '2026-09-04'
      AND d.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'""")
show("distinct STOCK symbols in mh window",
 """SELECT COUNT(DISTINCT b.symbol) FROM mh.daily_bars b JOIN mh.instruments i ON i.symbol=b.symbol
    WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
      AND b.trade_date BETWEEN '2023-09-04' AND '2026-09-04'""")
show("VALID stock rows in cache window",
 """SELECT COUNT(*) FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
    WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
      AND d.trade_date BETWEEN '2023-09-04' AND '2026-09-04'
      AND d.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
      AND d.open IS NOT NULL AND d.high IS NOT NULL AND d.low IS NOT NULL AND d.close IS NOT NULL AND d.close>0""")
show("VALID stock rows in mh window",
 """SELECT COUNT(*) FROM mh.daily_bars b JOIN mh.instruments i ON i.symbol=b.symbol
    WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
      AND b.trade_date BETWEEN '2023-09-04' AND '2026-09-04'
      AND b.close > 0""")
show("cache in-window OHLC violation rows detail",
 """SELECT symbol, trade_date, open, high, low, close, source FROM daily_bar_cache
    WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'
      AND open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
      AND (high<low OR high<open OR high<close OR low>open OR low>close)""")
