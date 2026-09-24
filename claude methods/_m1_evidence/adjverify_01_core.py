import sqlite3, statistics as st
OP = "D:/codex-A股交易/trading_local.sqlite3"
MH = "D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op, mh = ro(OP), ro(MH)

D0, D1 = '2024-08-12', '2024-08-13'

print("### 1. daily_bar_cache: source distribution on each side of the alleged boundary")
for d in (D0, D1):
    rows = op.execute("""SELECT source, COUNT(DISTINCT symbol) FROM daily_bar_cache
                         WHERE trade_date=? GROUP BY 1 ORDER BY 2 DESC""",(d,)).fetchall()
    print(f"  {d}: {rows}")

print()
print("### 2. Per-symbol source transition D0->D1 (DISTINCT symbols, indices excluded)")
cur = op.execute("""
SELECT a.symbol, a.source AS s0, b.source AS s1, a.close AS c0, b.close AS c1
FROM daily_bar_cache a JOIN daily_bar_cache b ON a.symbol=b.symbol
WHERE a.trade_date=? AND b.trade_date=?
  AND a.quality_status='ready' AND b.quality_status='ready'
  AND a.close IS NOT NULL AND b.close IS NOT NULL AND a.close>0
  AND a.source NOT LIKE '%index%' AND b.source NOT LIKE '%index%'
""",(D0,D1))
cache = {}
trans = {}
for sym,s0,s1,c0,c1 in cur:
    cache[sym] = (s0,s1,c0,c1)
    trans[(s0,s1)] = trans.get((s0,s1),0)+1
for k,v in sorted(trans.items(), key=lambda x:-x[1])[:12]:
    print(f"  {v:6d}  {k[0]}  ->  {k[1]}")
spliced = {s:v for s,v in cache.items() if v[0]!=v[1]}
same    = {s:v for s,v in cache.items() if v[0]==v[1]}
print(f"  DISTINCT symbols paired both days: {len(cache)}   spliced: {len(spliced)}   same-source: {len(same)}")

def summ(name, vals):
    vals=sorted(vals)
    if not vals: print(f"  {name}: EMPTY"); return
    n=len(vals)
    print(f"  {name:34s} n={n:5d} mean={statistics_mean(vals):+.4f}% med={vals[n//2]:+.4f}% "
          f"p10={vals[int(.10*n)]:+.3f}% p90={vals[int(.90*n)]:+.3f}% up%={100*sum(1 for v in vals if v>0)/n:.1f}")
def statistics_mean(v): return sum(v)/len(v)

print()
print("### 3. CACHE return on 2024-08-13 (close_D1/close_D0-1), by splice status")
summ("cache spliced", [100*(v[3]/v[2]-1) for v in spliced.values()])
summ("cache same-source", [100*(v[3]/v[2]-1) for v in same.values()])

print()
print("### 4. INDEPENDENT SERIES: market_history.daily_bars, same two dates")
cur = mh.execute("""
SELECT a.symbol, a.provider, b.provider, a.close, b.close
FROM daily_bars a JOIN daily_bars b
  ON a.symbol=b.symbol AND a.adjustment_mode=b.adjustment_mode
WHERE a.trade_date=? AND b.trade_date=? AND a.adjustment_mode='qfq'
  AND a.close>0 AND b.close>0
""",(D0,D1))
hist={}
hprov={}
for sym,p0,p1,c0,c1 in cur:
    hist[sym]=(p0,p1,c0,c1)
    hprov[(p0,p1)]=hprov.get((p0,p1),0)+1
print("  mh provider transition D0->D1:", sorted(hprov.items(), key=lambda x:-x[1]))
mh_nosplice = {s:v for s,v in hist.items() if v[0]==v[1]}
print(f"  mh symbols paired: {len(hist)}  with IDENTICAL provider both days: {len(mh_nosplice)}")

print()
print("### 5. KEY TEST: return on 2024-08-13 measured in the UNSPLICED market_history series,")
print("###           split by whether the CACHE spliced that symbol")
A = [100*(hist[s][3]/hist[s][2]-1) for s in spliced if s in mh_nosplice]
B = [100*(hist[s][3]/hist[s][2]-1) for s in same    if s in mh_nosplice]
summ("mh ret | cache-SPLICED symbols", A)
summ("mh ret | cache-SAME-source syms", B)

print()
print("### 6. Cache-vs-history ratio per symbol on each date (level-shift detector)")
print("###    if the splice injects a level shift, ratio(D1)/ratio(D0) != 1 for spliced only")
def ratios(group,label):
    r0=[];r1=[];rr=[]
    for s,v in group.items():
        h=hist.get(s)
        if not h: continue
        r0.append(v[2]/h[2]); r1.append(v[3]/h[3]); rr.append((v[3]/h[3])/(v[2]/h[2]))
    if not rr: print(f"  {label}: EMPTY"); return
    rr.sort(); n=len(rr)
    print(f"  {label:24s} n={n:5d} median ratio-of-ratios={rr[n//2]:.6f}  "
          f"p10={rr[int(.1*n)]:.5f} p90={rr[int(.9*n)]:.5f}  "
          f"frac |dev|>0.5%={100*sum(1 for x in rr if abs(x-1)>0.005)/n:.1f}%")
ratios(spliced,"SPLICED in cache")
ratios(same,"SAME-source in cache")

print()
print("### 7. PLACEBO: same 'jump' statistic for the SAME spliced symbol set on neighbouring dates")
for pd0,pd1 in [('2024-08-08','2024-08-09'),('2024-08-09','2024-08-12'),
                ('2024-08-13','2024-08-14'),('2024-08-14','2024-08-15')]:
    rows = op.execute("""SELECT a.symbol,a.close,b.close FROM daily_bar_cache a
        JOIN daily_bar_cache b ON a.symbol=b.symbol
        WHERE a.trade_date=? AND b.trade_date=? AND a.quality_status='ready'
          AND b.quality_status='ready' AND a.close>0 AND b.close>0""",(pd0,pd1)).fetchall()
    v=[100*(c1/c0-1) for s,c0,c1 in rows if s in spliced]
    if v:
        v.sort(); n=len(v)
        print(f"  cache {pd0}->{pd1}: n={n} med={v[n//2]:+.3f}% med|.|={sorted(abs(x) for x in v)[n//2]:.3f}%")
