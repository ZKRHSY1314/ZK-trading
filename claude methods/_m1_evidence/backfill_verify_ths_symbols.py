# -*- coding: utf-8 -*-
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OPS = r"D:\codex-A股交易\trading_local.sqlite3"
RES = r"D:\codex-A股交易\market_history.sqlite3"
THS = "tonghuasun.local.quotes.candle"
def ro(p): return sqlite3.connect("file:"+p.replace("\\","/")+"?mode=ro", uri=True)
c = ro(OPS); c.execute("ATTACH DATABASE ? AS mh", ["file:"+RES.replace("\\","/")+"?mode=ro"])
def show(t,q,rows):
    print("\n"+"="*78); print("["+t+"]"); print("SQL: "+" ".join(q.split()))
    for r in rows: print("   ",r)

q="SELECT symbol, COUNT(*) FROM daily_bar_cache GROUP BY symbol ORDER BY symbol LIMIT 8"
show("A cache symbol format sample", q, c.execute(q).fetchall())
q="SELECT symbol, exchange, asset_type, board, list_date, delist_date, status FROM mh.instruments LIMIT 8"
show("B instruments symbol format sample", q, c.execute(q).fetchall())
q="SELECT symbol,COUNT(*) FROM mh.daily_bars GROUP BY symbol ORDER BY symbol LIMIT 6"
show("C research-store symbol format sample", q, c.execute(q).fetchall())

# the 3 bare-code THS symbols: index or stock?
q="""SELECT d.symbol, COUNT(*) n, MIN(d.trade_date), MAX(d.trade_date)
     FROM daily_bar_cache d WHERE d.source=? AND d.symbol GLOB '[0-9]*' GROUP BY d.symbol"""
show("D the 3 bare-code THS symbols (index-contamination check)", q, c.execute(q,[THS]).fetchall())
for s in ("000001","600000","920000","920002"):
    r=c.execute("SELECT symbol,exchange,asset_type,board,list_date,status FROM mh.instruments WHERE symbol LIKE ?",
                ["%"+s+"%"]).fetchall()
    print("    instruments match for",s,":",r[:4])

# do 500-session symbols agree on a common span? (proves the true calendar)
q="""SELECT MIN(trade_date) mn, MAX(trade_date) mx, COUNT(*) symbols FROM (
       SELECT symbol, COUNT(DISTINCT trade_date) n, MIN(trade_date) trade_date_mn,
              MIN(trade_date) mn, MAX(trade_date) mx
       FROM daily_bar_cache WHERE source=? GROUP BY symbol HAVING n=500)
     GROUP BY mn, mx ORDER BY symbols DESC LIMIT 10"""
show("E span shared by the symbols that returned exactly 500 candles", q, c.execute(q,[THS]).fetchall())

q="""SELECT mn, mx, COUNT(*) symbols FROM (
       SELECT symbol, COUNT(DISTINCT trade_date) n, MIN(trade_date) mn, MAX(trade_date) mx
       FROM daily_bar_cache WHERE source=? GROUP BY symbol HAVING n=500)
     GROUP BY mn,mx ORDER BY symbols DESC LIMIT 8"""
show("E2 modal (min,max) among exactly-500 symbols", q, c.execute(q,[THS]).fetchall())

# the 16 symbols that exceed 500 -- forward accumulation or real backfill?
q="""SELECT symbol, n, mn, mx FROM (
       SELECT symbol, COUNT(DISTINCT trade_date) n, MIN(trade_date) mn, MAX(trade_date) mx
       FROM daily_bar_cache WHERE source=? GROUP BY symbol) WHERE n>500 ORDER BY n DESC"""
show("F the 16 symbols with >500 THS sessions: did the FLOOR move or the ROOF?", q,
     c.execute(q,[THS]).fetchall())
c.close()
