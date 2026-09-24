# -*- coding: utf-8 -*-
import sqlite3, pathlib, sys, collections, statistics, datetime
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
OP=r"D:\codex-A股交易\trading_local.sqlite3"; MH=r"D:\codex-A股交易\market_history.sqlite3"
W0,W1="2023-09-04","2026-09-04"
def ro(p): return "file:"+pathlib.Path(p).as_posix()+"?mode=ro"
op=sqlite3.connect(ro(OP),uri=True); mh=sqlite3.connect(ro(MH),uri=True)
def Q(c,s,p=()): return list(c.execute(s,p))
STK=[r[0] for r in Q(mh,"SELECT symbol FROM instruments WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ')")]
cur=op.cursor(); cur.execute("CREATE TEMP TABLE u(symbol TEXT PRIMARY KEY)")
cur.executemany("INSERT INTO u VALUES(?)",[(s,) for s in STK])
spine=sorted(r[0] for r in Q(op,"SELECT DISTINCT d.trade_date FROM daily_bar_cache d JOIN u ON u.symbol=d.symbol WHERE d.trade_date>=? AND d.trade_date<=?",(W0,W1)))
FIRST,LAST=spine[0],spine[-1]
meta=dict((r[0],(r[1],r[2])) for r in Q(mh,"SELECT symbol,list_date,delist_date FROM instruments"))
def norm(x):
    x=str(x)[:10] if x else None
    return x if x and len(x)==10 and x[4]=='-' else None
obs=dict(Q(op,"""SELECT d.symbol,COUNT(DISTINCT d.trade_date) FROM daily_bar_cache d JOIN u ON u.symbol=d.symbol
  WHERE d.trade_date>=? AND d.trade_date<=? AND d.open IS NOT NULL AND d.high IS NOT NULL AND d.low IS NOT NULL
  AND d.close IS NOT NULL AND d.close>0 GROUP BY 1""",(W0,W1)))

print("="*100); print("Q1 -- WHICH sessions does a MODAL (536-bar) stock actually miss?"); print("="*100)
modal=[s for s in STK if obs.get(s)==536]
print("  modal stocks n=%d ; sampling 3"%len(modal))
for s in modal[:3]:
    have={r[0] for r in Q(op,"SELECT DISTINCT trade_date FROM daily_bar_cache WHERE symbol=? AND trade_date>=? AND trade_date<=? AND close>0 AND open IS NOT NULL",(s,W0,W1))}
    miss=[d for d in spine if d not in have]
    print("   %s list_date=%s missing=%d  first_missing=%s last_missing=%s"%(s,meta[s][0],len(miss),miss[0],miss[-1]))
    print("      all missing dates <= 2024-06-21 ? %s   (count in ramp window: %d)"%(all(d<='2024-06-21' for d in miss),sum(1 for d in miss if d<='2024-06-21')))
print("  spine sessions on/before 2024-06-21 =",sum(1 for d in spine if d<='2024-06-21'))

print("\n"+"="*100); print("Q2 -- the 247 stocks at ratio>=0.99 (list/delist-aware denominator): who are they?"); print("="*100)
hi=[]
for s in STK:
    o=obs.get(s,0)
    if o==0: continue
    ld=norm(meta[s][0]); dd=norm(meta[s][1])
    lo=max(FIRST,ld) if ld else FIRST; h=min(LAST,dd) if dd else LAST
    e=sum(1 for d in spine if lo<=d<=h)
    if e>0 and o/e>=0.99: hi.append((s,o,e,ld))
print("  count=%d"%len(hi))
print("  list_date >= 2024-06-24 :",sum(1 for _,_,_,l in hi if l and l>='2024-06-24'))
print("  list_date <  2024-06-24 :",sum(1 for _,_,_,l in hi if l and l< '2024-06-24'))
print("  eligible-session distribution:",collections.Counter(e for _,_,e,_ in hi).most_common(5))
print("  median eligible sessions for these 'well covered' names =",statistics.median(e for _,_,e,_ in hi))
print("  samples:",hi[:5])

print("\n"+"="*100); print("Q3 -- THE REAL DENOMINATOR: what fraction of the 3-YEAR WINDOW has ANY data at all?"); print("="*100)
for lbl,c,tbl in (("trading_local.daily_bar_cache",op,"daily_bar_cache"),("market_history.daily_bars",mh,"daily_bars")):
    r=Q(c,"SELECT COUNT(*),COUNT(DISTINCT trade_date) FROM %s WHERE trade_date>=? AND trade_date<?"%tbl,("2023-09-04","2024-04-09"))[0]
    print("  [SQL] SELECT COUNT(*),COUNT(DISTINCT trade_date) FROM %s WHERE trade_date>='2023-09-04' AND trade_date<'2024-04-09'"%tbl)
    print("        -> rows=%d sessions=%d"%r)
d0=datetime.date.fromisoformat(W0); fs=datetime.date.fromisoformat(FIRST); d1=datetime.date.fromisoformat(W1)
wd_pre=sum(1 for i in range((fs-d0).days) if (d0+datetime.timedelta(days=i)).weekday()<5)
wd_all=sum(1 for i in range((d1-d0).days+1) if (d0+datetime.timedelta(days=i)).weekday()<5)
print("  window 2023-09-04..2026-09-04 spans %d calendar days / %d weekdays"%((d1-d0).days+1,wd_all))
print("  2023-09-04..2024-04-08 spans %d weekdays -> 0 sessions, 0 rows, 0 symbols in BOTH stores"%wd_pre)
print("  observed span 2024-04-09..2026-09-04 = %d sessions (%.1f%% of the window's calendar length)"%(len(spine),100*((d1-fs).days+1)/((d1-d0).days+1)))
print("  broad-market span 2024-06-24..2026-09-04 = %d sessions"%sum(1 for d in spine if d>='2024-06-24'))

print("\n"+"="*100); print("Q4 -- coverage restated against the broad-market span only (most generous honest denom)"); print("="*100)
bm=[d for d in spine if d>='2024-06-24']
v=sorted(min(obs.get(s,0),len(bm))/len(bm) for s in STK if obs.get(s,0)>0)
print("  denom=%d sessions (2024-06-24..%s).  median=%.4f  >=0.95: %d  >=0.99: %d"%(
    len(bm),LAST,statistics.median(v),sum(1 for x in v if x>=.95),sum(1 for x in v if x>=.99)))
