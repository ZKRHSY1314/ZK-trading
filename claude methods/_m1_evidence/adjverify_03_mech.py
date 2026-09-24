import sqlite3
OP="D:/codex-A股交易/trading_local.sqlite3"; MH="D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op,mh=ro(OP),ro(MH)
def med(v):
    v=sorted(v); return v[len(v)//2] if v else float('nan')

print("### F. market_history coverage bounds (can it referee the 2026 dates?)")
print("  mh daily_bars:", mh.execute("SELECT MIN(trade_date),MAX(trade_date),COUNT(*) FROM daily_bars").fetchone())
print("  cache        :", op.execute("SELECT MIN(trade_date),MAX(trade_date),COUNT(*) FROM daily_bar_cache").fetchone())

print("\n### G. Their mechanism claim: timestamps for 2024-08 rows")
for r in op.execute("""SELECT source, substr(created_at,1,10) cday, substr(updated_at,1,10) uday, COUNT(*)
  FROM daily_bar_cache WHERE trade_date BETWEEN '2024-08-01' AND '2024-08-31'
  GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 8"""):
    print("  ",r)

print("\n### H. Direction test: which SIDE moved? cache vs the 2026-07-15 tencent vintage in mh")
for d in ('2024-08-09','2024-08-12','2024-08-13','2024-08-14'):
    r=[]
    ch={s:c for s,c in op.execute("SELECT symbol,close FROM daily_bar_cache WHERE trade_date=? AND quality_status='ready' AND close>0",(d,))}
    for s,c in mh.execute("SELECT symbol,close FROM daily_bars WHERE trade_date=? AND adjustment_mode='qfq' AND close>0",(d,)):
        if s in ch: r.append(ch[s]/c)
    print(f"  {d}: n={len(r)} median cache/tencent-vintage = {med(r):.6f}")

print("\n### I. ALL mass-splice dates in the research window (>=100 distinct symbols changing source)")
prev={}; out=[]
rows=op.execute("""SELECT trade_date, symbol, source, close FROM daily_bar_cache
  WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND quality_status='ready'
    AND close>0 AND source NOT LIKE '%index%' ORDER BY symbol, trade_date""")
lastsym=None; lastsrc=None; lastclose=None
from collections import defaultdict
bydate=defaultdict(list)
for d,s,src,cl in rows:
    if s==lastsym and lastsrc is not None and src!=lastsrc and lastclose:
        bydate[d].append((s,100*(cl/lastclose-1)))
    lastsym,lastsrc,lastclose=s,src,cl
tot=sum(len(v) for v in bydate.values())
print(f"  total source boundaries in window = {tot} across {len(bydate)} dates")
print("  date         nsym   median signed raw ret")
for d,v in sorted(bydate.items(), key=lambda x:-len(x[1]))[:10]:
    print(f"  {d}  {len(v):5d}   {med([x[1] for x in v]):+.3f}%")

print("\n### J. Referee the 2026 splice dates using market_history where it reaches")
mx=mh.execute("SELECT MAX(trade_date) FROM daily_bars").fetchone()[0]
for d0,d1 in [('2026-07-23','2026-07-24'),('2026-07-24','2026-07-27'),('2026-09-03','2026-09-04')]:
    if d1>mx:
        print(f"  {d1}: BEYOND market_history max ({mx}) -> no independent referee")
        continue
    ch0={s:c for s,c in op.execute("SELECT symbol,close FROM daily_bar_cache WHERE trade_date=? AND quality_status='ready' AND close>0",(d0,))}
    ch1={s:(c,src) for s,c,src in op.execute("SELECT symbol,close,source FROM daily_bar_cache WHERE trade_date=? AND quality_status='ready' AND close>0",(d1,))}
    src0={s:x for s,x in op.execute("SELECT symbol,source FROM daily_bar_cache WHERE trade_date=? AND quality_status='ready'",(d0,))}
    h0={s:c for s,c in mh.execute("SELECT symbol,close FROM daily_bars WHERE trade_date=? AND adjustment_mode='qfq' AND close>0",(d0,))}
    h1={s:c for s,c in mh.execute("SELECT symbol,close FROM daily_bars WHERE trade_date=? AND adjustment_mode='qfq' AND close>0",(d1,))}
    ex=[]
    for s in ch1:
        if s in ch0 and s in h0 and s in h1 and src0.get(s) and src0[s]!=ch1[s][1]:
            ex.append(100*(ch1[s][0]/ch0[s]-1) - 100*(h1[s]/h0[s]-1))
    if ex: print(f"  {d0}->{d1}: spliced n={len(ex)} mean excess={sum(ex)/len(ex):+.3f}pp median={med(ex):+.3f}pp")
    else:  print(f"  {d0}->{d1}: no overlapping referee rows")
