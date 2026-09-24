# -*- coding: utf-8 -*-
import sqlite3, sys, io, bisect
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OPS = r"D:\codex-A股交易\trading_local.sqlite3"; RES = r"D:\codex-A股交易\market_history.sqlite3"
THS = "tonghuasun.local.quotes.candle"; W0,W1 = "2023-09-04","2026-09-04"
def ro(p): return sqlite3.connect("file:"+p.replace("\\","/")+"?mode=ro", uri=True)
c = ro(OPS); c.execute("ATTACH DATABASE ? AS mh", ["file:"+RES.replace("\\","/")+"?mode=ro"])
def show(t,q,rows):
    print("\n"+"="*78); print("["+t+"]"); print("SQL: "+" ".join(q.split()))
    for r in rows: print("   ",r)

q="""SELECT mn, mx, COUNT(*) symbols FROM (
       SELECT symbol, COUNT(DISTINCT trade_date) n, MIN(trade_date) mn, MAX(trade_date) mx
       FROM daily_bar_cache WHERE source=? GROUP BY symbol HAVING n=500)
     GROUP BY mn,mx ORDER BY symbols DESC LIMIT 8"""
show("E modal (min,max) among the 232 exactly-500 symbols", q, c.execute(q,[THS]).fetchall())

q="""SELECT symbol, n, mn, mx FROM (
       SELECT symbol, COUNT(DISTINCT trade_date) n, MIN(trade_date) mn, MAX(trade_date) mx
       FROM daily_bar_cache WHERE source=? GROUP BY symbol) WHERE n>500 ORDER BY symbol"""
show("F symbols with >500 THS sessions: did the FLOOR move or only the ROOF?", q, c.execute(q,[THS]).fetchall())

# ---- calendar from the RESEARCH store, which is the deeper of the two ----
q="""SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM mh.daily_bars"""
show("G research-store date span", q, c.execute(q).fetchall())
cal=[r[0] for r in c.execute("""SELECT trade_date FROM mh.daily_bars GROUP BY trade_date
                                HAVING COUNT(DISTINCT symbol)>=200 ORDER BY trade_date""").fetchall()]
print("\n[G2] research-store sessions with >=200 symbols:",len(cal),cal[0],"..",cal[-1])

# union calendar across BOTH stores = best available trading calendar
cal2=[r[0] for r in c.execute("""SELECT trade_date FROM (
        SELECT trade_date, COUNT(DISTINCT symbol) n FROM mh.daily_bars GROUP BY trade_date
        UNION ALL
        SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bar_cache GROUP BY trade_date)
      GROUP BY trade_date HAVING MAX(n)>=200 ORDER BY trade_date""").fetchall()]
print("[G3] UNION calendar (>=200 symbols in either store):",len(cal2),cal2[0],"..",cal2[-1])
i0=bisect.bisect_left(cal2,W0); i1=bisect.bisect_right(cal2,W1)-1
print("     sessions inside research window %s..%s = %d"%(W0,W1,i1-i0+1))
print("     tail-500 reach from %s -> %s"%(cal2[i1], cal2[max(0,i1-499)]))
# sessions between the observed THS floor and the big sweep date
a=bisect.bisect_left(cal2,"2024-07-30"); b=bisect.bisect_right(cal2,"2026-09-03")-1
print("     sessions 2024-07-30..2026-09-03 on the union calendar = %d (cap is 500)"%(b-a+1))
a=bisect.bisect_left(cal2,"2024-07-30"); b=bisect.bisect_right(cal2,"2026-09-04")-1
print("     sessions 2024-07-30..2026-09-04 on the union calendar = %d"%(b-a+1))
c.close()
