import sqlite3
from collections import defaultdict
OP="D:/codex-A股交易/trading_local.sqlite3"; MH="D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op,mh=ro(OP),ro(MH)
def med(v):
    v=sorted(v); return v[len(v)//2] if v else float('nan')

# build per-symbol ordered series once
cache=defaultdict(list)
for d,s,src,cl in op.execute("""SELECT trade_date,symbol,source,close FROM daily_bar_cache
  WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND quality_status='ready' AND close>0
    AND source NOT LIKE '%index%' ORDER BY symbol, trade_date"""):
    cache[s].append((d,src,cl))
hist={}
for s,d,c in mh.execute("SELECT symbol,trade_date,close FROM daily_bars WHERE adjustment_mode='qfq' AND close>0"):
    hist[(s,d)]=c
MXH=mh.execute("SELECT MAX(trade_date) FROM daily_bars").fetchone()[0]

bnd=defaultdict(list)
for s,ser in cache.items():
    for i in range(1,len(ser)):
        if ser[i][1]!=ser[i-1][1]:
            d0,_,c0=ser[i-1]; d1,_,c1=ser[i]
            rc=100*(c1/c0-1)
            h0=hist.get((s,d0)); h1=hist.get((s,d1))
            ex = rc-100*(h1/h0-1) if (h0 and h1) else None
            bnd[d1].append((rc,ex))

print("### K. Every boundary date >=30 symbols: RAW return vs SPLICE-ATTRIBUTABLE excess")
print("  date         nsym  raw_med    refereed  mean_excess  med_excess  |ex|>1pp   verdict")
tot=0
for d,v in sorted(bnd.items(), key=lambda x:-len(x[1])):
    tot+=len(v)
    if len(v)<30: continue
    raw=med([x[0] for x in v])
    ex=[x[1] for x in v if x[1] is not None]
    if not ex:
        print(f"  {d}  {len(v):5d}  {raw:+7.3f}%   0        --           --          --        NO REFEREE (>{MXH})")
        continue
    m=sum(ex)/len(ex); mm=med(ex); big=100*sum(1 for x in ex if abs(x)>1)/len(ex)
    verdict = "DISTORTING" if abs(m)>0.05 or big>5 else "benign (basis unchanged)"
    print(f"  {d}  {len(v):5d}  {raw:+7.3f}%   {len(ex):5d}    {m:+8.4f}pp   {mm:+8.4f}pp   {big:5.1f}%    {verdict}")
print(f"  TOTAL boundaries in window = {tot} across {len(bnd)} dates")

print("\n### L. Final magnitude of the 2024-08-13 event")
v=[x[1] for x in bnd['2024-08-13'] if x[1] is not None]
v.sort(); n=len(v)
av=sorted(abs(x) for x in v)
print(f"  refereed n={n}  mean excess={sum(v)/n:+.4f}pp  median excess={v[n//2]:+.4f}pp  median |excess|={av[n//2]:.4f}pp")
print(f"  raw (uncontrolled) median signed={med([x[0] for x in bnd['2024-08-13']]):+.4f}%  <- what the claim quotes as the jump")
allsym=len(set(s for s in cache if any(d=='2024-08-13' for d,_,_ in cache[s][-4000:]) ))
n813=op.execute("""SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date='2024-08-13'
   AND quality_status='ready' AND close>0 AND source NOT LIKE '%index%'""").fetchone()[0]
print(f"  distinct non-index securities trading 2024-08-13 = {n813}; boundaries = {len(bnd['2024-08-13'])} ({100*len(bnd['2024-08-13'])/n813:.1f}% of the market)")
