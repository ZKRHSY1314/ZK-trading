# -*- coding: utf-8 -*-
import sqlite3, pathlib, sys, datetime, collections
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
OP=r"D:\codex-A股交易\trading_local.sqlite3"; MH=r"D:\codex-A股交易\market_history.sqlite3"
W0,W1="2023-09-04","2026-09-04"
def ro(p): return "file:"+pathlib.Path(p).as_posix()+"?mode=ro"
op=sqlite3.connect(ro(OP),uri=True); mh=sqlite3.connect(ro(MH),uri=True)
def Q(c,s,p=()): return list(c.execute(s,p))

print("="*100); print("STEP 3 -- IS THERE ANY TRADING-CALENDAR TABLE ANYWHERE?"); print("="*100)
for nm,c in (("trading_local",op),("market_history",mh)):
    t=[r[0] for r in Q(c,"SELECT name FROM sqlite_master WHERE type='table'")]
    cal=[x for x in t if any(k in x.lower() for k in ("calendar","session","trade_day","tradingday","holiday"))]
    print(nm,"tables=",len(t)," calendar-ish:",cal)

print(); print("="*100); print("STEP 4 -- SYMBOL JOIN INTEGRITY (do cache symbols match instruments symbols?)"); print("="*100)
cache=set(r[0] for r in Q(op,"SELECT DISTINCT symbol FROM daily_bar_cache"))
inst=dict((r[0],r[1:]) for r in Q(mh,"SELECT symbol,asset_type,exchange,list_date,delist_date,status FROM instruments"))
stock=set(s for s,v in inst.items() if v[0]=='stock' and v[1] in ('SH','SZ','BJ'))
print("distinct cache symbols          =",len(cache))
print("instruments rows                =",len(inst))
print("instruments stock SH/SZ/BJ      =",len(stock))
print("cache ∩ stock                   =",len(cache&stock))
print("cache symbols NOT in instruments=",len(cache-set(inst)), sorted(cache-set(inst))[:20])
print("stock symbols with NO cache rows=",len(stock-cache), sorted(stock-cache)[:20])
print("cache symbols in instruments but NOT stock:",len(cache&set(inst)-stock), sorted((cache&set(inst))-stock)[:20])

print(); print("="*100); print("STEP 5 -- WHAT DOES THE WINDOW ACTUALLY CONTAIN? row/date census by month"); print("="*100)
sql="""SELECT substr(trade_date,1,7) ym, COUNT(*) rows, COUNT(DISTINCT trade_date) sess, COUNT(DISTINCT symbol) syms
       FROM daily_bar_cache WHERE trade_date>=? AND trade_date<=? GROUP BY 1 ORDER BY 1"""
print("[SQL-I] "+" ".join(sql.split()))
rows=Q(op,sql,(W0,W1))
for r in rows: print("   %s rows=%9d sessions=%3d symbols=%5d" % r)

print(); print("[SQL-J] earliest/latest trade_date in the ENTIRE cache (no window filter)")
print("   ",Q(op,"SELECT MIN(trade_date),MAX(trade_date),COUNT(*) FROM daily_bar_cache WHERE length(trade_date)=10")[0])
print("[SQL-K] rows in window-prefix 2023-09-04..2024-04-08 (the first 7 months of the research window)")
print("   ",Q(op,"SELECT COUNT(*),COUNT(DISTINCT symbol),COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date>=? AND trade_date<?",("2023-09-04","2024-04-09"))[0])
print("[SQL-L] same for market_history.daily_bars")
print("   ",Q(mh,"SELECT COUNT(*),COUNT(DISTINCT symbol),COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date>=? AND trade_date<?",("2023-09-04","2024-04-09"))[0])
print("[SQL-M] market_history.daily_bars global min/max")
print("   ",Q(mh,"SELECT MIN(trade_date),MAX(trade_date),COUNT(*) FROM daily_bars")[0])
