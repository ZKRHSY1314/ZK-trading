import sqlite3
OP="D:/codex-A股交易/trading_local.sqlite3"; MH="D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op,mh=ro(OP),ro(MH)
def med(v):
    v=sorted(v); return v[len(v)//2] if v else float('nan')

# spliced set (tencent->akshare on 2024-08-13)
spl=[r[0] for r in op.execute("""
SELECT a.symbol FROM daily_bar_cache a JOIN daily_bar_cache b ON a.symbol=b.symbol
WHERE a.trade_date='2024-08-12' AND b.trade_date='2024-08-13'
  AND a.quality_status='ready' AND b.quality_status='ready'
  AND a.close>0 AND b.close>0 AND a.source<>b.source AND a.source NOT LIKE '%index%'""")]
spl=set(spl)
print(f"spliced symbols = {len(spl)}")

print("\n### A. Is market_history itself unspliced there? (vintage check for these symbols)")
for d in ('2024-08-12','2024-08-13'):
    r=mh.execute("""SELECT provider, substr(available_at,1,10), substr(fetched_at,1,10), COUNT(*)
        FROM daily_bars WHERE trade_date=? AND adjustment_mode='qfq' GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 6""",(d,)).fetchall()
    print(f"  {d}: {r}")

print("\n### B. STEP FUNCTION: median(cache_close / history_close) per trade_date, spliced symbols only")
q="""SELECT symbol, trade_date, close FROM daily_bar_cache
     WHERE trade_date BETWEEN '2024-07-15' AND '2024-09-10' AND quality_status='ready' AND close>0"""
c={}
for s,d,v in op.execute(q):
    if s in spl: c[(s,d)]=v
h={}
for s,d,v in mh.execute("""SELECT symbol,trade_date,close FROM daily_bars
     WHERE trade_date BETWEEN '2024-07-15' AND '2024-09-10' AND adjustment_mode='qfq' AND close>0"""):
    if s in spl: h[(s,d)]=v
dates=sorted({d for (_,d) in c})
print("   date        n     median(cache/hist)   pct>1.001   pct<0.999")
for d in dates:
    r=[c[(s,d)]/h[(s,d)] for s in spl if (s,d) in c and (s,d) in h]
    if not r: continue
    hi=100*sum(1 for x in r if x>1.001)/len(r); lo=100*sum(1 for x in r if x<0.999)/len(r)
    mark="  <== BOUNDARY" if d=='2024-08-13' else ""
    print(f"  {d} {len(r):5d}   {med(r):.6f}          {hi:5.1f}%     {lo:5.1f}%{mark}")

print("\n### C. Splice-attributable excess return on 2024-08-13 (paired, per symbol)")
rows=op.execute("""SELECT a.symbol,a.close,b.close FROM daily_bar_cache a JOIN daily_bar_cache b
  ON a.symbol=b.symbol WHERE a.trade_date='2024-08-12' AND b.trade_date='2024-08-13'
  AND a.quality_status='ready' AND b.quality_status='ready' AND a.close>0 AND b.close>0""").fetchall()
rc={s:100*(c1/c0-1) for s,c0,c1 in rows}
rh={}
for s,c0,c1 in mh.execute("""SELECT a.symbol,a.close,b.close FROM daily_bars a JOIN daily_bars b
  ON a.symbol=b.symbol AND a.adjustment_mode=b.adjustment_mode
  WHERE a.trade_date='2024-08-12' AND b.trade_date='2024-08-13' AND a.adjustment_mode='qfq'
  AND a.close>0 AND b.close>0""").fetchall():
    rh[s]=100*(c1/c0-1)
ex=[rc[s]-rh[s] for s in spl if s in rc and s in rh]
ex.sort(); n=len(ex)
print(f"  n={n}  mean excess={sum(ex)/n:+.4f}pp  median={ex[n//2]:+.4f}pp  p75={ex[int(.75*n)]:+.3f}  p90={ex[int(.90*n)]:+.3f}  p99={ex[int(.99*n)]:+.3f}")
for t in (0.5,1,2,5,10):
    print(f"    |excess| > {t}pp : {100*sum(1 for x in ex if abs(x)>t)/n:5.1f}%   (signed > +{t}pp: {100*sum(1 for x in ex if x>t)/n:5.1f}%)")
# control
exc=[rc[s]-rh[s] for s in rc if s not in spl and s in rh]
exc.sort(); m=len(exc)
print(f"  CONTROL (non-spliced) n={m} mean={sum(exc)/m:+.4f}pp median={exc[m//2]:+.4f}pp  |excess|>0.5pp={100*sum(1 for x in exc if abs(x)>0.5)/m:.1f}%")

print("\n### D. Raw-return stats they quoted, recomputed, vs splice-attributable")
rr=sorted(rc[s] for s in spl if s in rc); N=len(rr)
print(f"  raw |ret| median = {med([abs(x) for x in rr]):.4f}%   raw signed median = {rr[N//2]:+.4f}%")
print(f"  raw |ret|>2% = {100*sum(1 for x in rr if abs(x)>2)/N:.1f}%   raw |ret|>10% = {100*sum(1 for x in rr if abs(x)>10)/N:.1f}%")

print("\n### E. adjustment_mode recorded on each side (spliced symbols)")
for d in ('2024-08-12','2024-08-13'):
    r=op.execute("""SELECT source, adjustment_mode, volume_unit, COUNT(*) FROM daily_bar_cache
      WHERE trade_date=? AND quality_status='ready' GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 6""",(d,)).fetchall()
    print(f"  {d}: {r}")
