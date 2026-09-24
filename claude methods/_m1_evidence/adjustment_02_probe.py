# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def q(path, sql, params=()):
    con=sqlite3.connect(f"file:{path}?mode=ro",uri=True)
    try: return con.execute(sql,params).fetchall()
    finally: con.close()
def show(t,sql,path=TL):
    print("\n### "+t); print("SQL: "+" ".join(sql.split()))
    for r in q(path,sql): print("   ",r)

show("symbol format sample", "SELECT symbol, COUNT(*) FROM daily_bar_cache GROUP BY symbol ORDER BY RANDOM() LIMIT 15")
show("symbol length distribution", "SELECT length(symbol), COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1")
show("symbol prefix(1) distribution", "SELECT substr(symbol,1,1), COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC")
show("symbol prefix(3) top", "SELECT substr(symbol,1,3), COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC LIMIT 30")
show("mh instruments symbol format", "SELECT symbol, exchange, asset_type, board FROM instruments ORDER BY RANDOM() LIMIT 15", MH)
show("mh instruments exchange x asset_type", "SELECT exchange, asset_type, board, COUNT(*) FROM instruments GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 40", MH)
show("bad trade_date rows in cache", "SELECT symbol,trade_date,close,source,adjustment_mode,quality_status FROM daily_bar_cache WHERE length(trade_date)<>10 OR trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")
show("the 'none' mode rows in cache", "SELECT symbol, source, quality_status, COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE adjustment_mode='none' GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 60")
show("the volume_unit='unknown' rows", "SELECT symbol, source, adjustment_mode, COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE volume_unit='unknown' GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 20")
