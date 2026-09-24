# -*- coding: utf-8 -*-
import sqlite3, sys, io, bisect
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OPS=r"D:\codex-A股交易\trading_local.sqlite3"; RES=r"D:\codex-A股交易\market_history.sqlite3"
THS="tonghuasun.local.quotes.candle"; W0,W1="2023-09-04","2026-09-04"; REACH="2024-08-13"
def ro(p): return sqlite3.connect("file:"+p.replace("\\","/")+"?mode=ro", uri=True)
c=ro(OPS); c.execute("ATTACH DATABASE ? AS mh",["file:"+RES.replace("\\","/")+"?mode=ro"])
def show(t,q,rows):
    print("\n"+"="*78); print("["+t+"]"); print("SQL: "+" ".join(q.split()))
    for r in rows: print("   ",r)

cal=[r[0] for r in c.execute("""SELECT trade_date FROM (
        SELECT trade_date, COUNT(DISTINCT symbol) n FROM mh.daily_bars GROUP BY trade_date
        UNION ALL SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bar_cache GROUP BY trade_date)
      GROUP BY trade_date HAVING MAX(n)>=200 ORDER BY trade_date""").fetchall()]
idx={d:i for i,d in enumerate(cal)}
def pos(d,lo=True): return bisect.bisect_left(cal,d) if lo else bisect.bisect_right(cal,d)-1
print("[cal] %d sessions %s..%s ; REACH(500 back from %s)=%s @idx %d"
      %(len(cal),cal[0],cal[-1],cal[-1],cal[-500],len(cal)-500))
REACH=cal[-500]
print("[cal] arithmetic check: sessions 2024-08-13..2026-09-03 =",
      pos("2026-09-03",False)-pos("2024-08-13")+1, "(expect exactly 500 = the cap)")
print("[cal] sessions 2024-07-30..2026-09-03 =", pos("2026-09-03",False)-pos("2024-07-30")+1,
      "-> the 500-row symbols with a 2024-07-30 floor missed that many sessions (suspensions)")

# ---- 1. cross-DB overlap on RAW symbols (my earlier substr cut was wrong) ----
q="""SELECT (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE source=?) cache_syms,
            (SELECT COUNT(DISTINCT symbol) FROM mh.daily_bars WHERE provider=?) res_syms,
            (SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM mh.daily_bars WHERE provider=?
               INTERSECT SELECT DISTINCT symbol FROM daily_bar_cache WHERE source=?)) overlap"""
show("1 THS symbol overlap between the two DBs (raw symbol, no substr)", q,
     c.execute(q,[THS,THS,THS,THS]).fetchall())

# ---- 2. is the THS footprint really broad market, or one board? ----
q="""SELECT i.exchange, i.board, COUNT(DISTINCT d.symbol) syms, COUNT(*) rows
     FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
     WHERE d.source=? GROUP BY i.exchange,i.board ORDER BY syms DESC"""
show("2 THS cache footprint by board (clean 1:1 join)", q, c.execute(q,[THS]).fetchall())

# ---- 3. THE REAL TEST: can THS reach the window start for NEW listings? ----
q="""SELECT COUNT(*) FROM mh.instruments WHERE asset_type='stock'
     AND list_date IS NOT NULL AND list_date<=? AND (delist_date IS NULL OR delist_date>=?)"""
show("3a stock universe alive during the window", q, c.execute(q,[W1,W0]).fetchall())
q="""SELECT CASE WHEN list_date>=? THEN 'listed ON/AFTER the tail-500 floor -> THS CAN cover its whole life'
                 ELSE 'listed BEFORE the floor -> THS structurally cannot reach its early history' END k,
            COUNT(*) symbols
     FROM mh.instruments WHERE asset_type='stock' AND list_date IS NOT NULL
       AND list_date<=? AND (delist_date IS NULL OR delist_date>=?) GROUP BY k"""
show("3b does the 500-candle cap bite for EVERY stock, or only older ones?", q,
     c.execute(q,[REACH,W1,W0]).fetchall())

# ---- 4. head-gap reachability: missing cells before vs after the floor ----
first={}
for s,d in c.execute("""SELECT symbol, MIN(trade_date) FROM (
        SELECT symbol,trade_date FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-*'
        UNION ALL SELECT symbol,trade_date FROM mh.daily_bars) GROUP BY symbol"""):
    first[s]=d
inst=c.execute("""SELECT symbol,list_date,delist_date FROM mh.instruments
                  WHERE asset_type='stock' AND list_date IS NOT NULL
                    AND list_date<=? AND (delist_date IS NULL OR delist_date>=?)""",[W1,W0]).fetchall()
below=above=0; nodata_syms=0; covered=0
iR=idx[REACH]
for sym,ld,dd in inst:
    start=max(W0,ld); i0=pos(start)
    end=min(W1,dd) if dd else W1; i1=pos(end,False)
    if i1<i0: continue
    f=first.get(sym)
    fi=pos(f) if f else i1+1          # no data at all -> entire span is head gap
    if not f: nodata_syms+=1
    fi=min(fi,i1+1)
    if fi<=i0: covered+=1; continue
    below+=max(0,min(fi,iR)-i0)       # cells before the THS floor  -> unreachable
    above+=max(0,fi-max(i0,iR))       # cells on/after the floor    -> THS COULD serve
print("\n"+"="*78)
print("[4] HEAD-GAP REACHABILITY (my own count, union calendar %s..%s)"%(cal[0],cal[-1]))
print("SQL: per-symbol MIN(trade_date) over UNION(daily_bar_cache, mh.daily_bars),")
print("     joined to mh.instruments WHERE asset_type='stock' AND alive in window;")
print("     head-gap cells = calendar sessions in [max(window_start,list_date), first_observed)")
print("    stocks alive in window        :",len(inst))
print("    with NO bar in either DB      :",nodata_syms)
print("    with no head gap at all       :",covered)
print("    head-gap cells BEFORE %s (THS structurally cannot serve) : %d"%(REACH,below))
print("    head-gap cells ON/AFTER %s  (THS could serve today)      : %d"%(REACH,above))
print("    NOTE: calendar starts %s, so every window session before it is UNCOUNTED here."%cal[0])
print("          True head gap is strictly larger; this is a floor, not the total.")
c.close()
