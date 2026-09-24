# -*- coding: utf-8 -*-
import sqlite3,sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
mh=sqlite3.connect("file:D:/codex-A股交易/market_history.sqlite3?mode=ro",uri=True)
tl=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
print("CONFIRMED HALF  (market_history):")
print("  instruments non-stock          =", mh.execute("SELECT COUNT(*) FROM instruments WHERE asset_type IS NULL OR asset_type<>'stock'").fetchone()[0], "of 5561")
print("  bar symbols in index code range=", mh.execute("""SELECT COUNT(DISTINCT symbol) FROM daily_bars WHERE (substr(symbol,1,2)='SH' AND substr(symbol,3,1) IN ('0','9')) OR (substr(symbol,1,2)='SZ' AND substr(symbol,3,2)='39') OR (substr(symbol,1,2)='BJ' AND substr(symbol,3,2) IN ('89','95'))""").fetchone()[0], "of", mh.execute("SELECT COUNT(DISTINCT symbol) FROM daily_bars").fetchone()[0])
print("REFUTED HALF   (trading_local = the store backtest/engine.py actually reads):")
print("  true index series:", tl.execute("SELECT symbol,COUNT(*),MIN(trade_date),MAX(trade_date) FROM daily_bar_cache WHERE source='akshare.stock_zh_index_daily' GROUP BY symbol").fetchall())
print("  window days covered by SH000300:", tl.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE symbol='SH000300' AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'").fetchone()[0], "of", tl.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'").fetchone()[0])
print("  forecast_outcomes w/ benchmark_return:", tl.execute("SELECT COUNT(*) FROM forecast_outcomes WHERE benchmark_return IS NOT NULL").fetchone()[0], "of", tl.execute("SELECT COUNT(*) FROM forecast_outcomes").fetchone()[0], "| distinct values:", tl.execute("SELECT COUNT(DISTINCT benchmark_return) FROM forecast_outcomes").fetchone()[0])
