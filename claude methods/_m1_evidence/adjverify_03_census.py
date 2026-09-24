import sqlite3, statistics as st
OP=r"D:/codex-A股交易/trading_local.sqlite3"
MH=r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c=ro(OP); m=ro(MH)

print("=== [G] LEVEL decomposition: cache close vs market_history close, spliced symbols ===")
Q="""
WITH d AS (SELECT symbol,trade_date,source,close FROM daily_bar_cache
           WHERE trade_date IN ('2024-08-12','2024-08-13') AND adjustment_mode='qfq' AND quality_status='ready'),
 p AS (SELECT symbol,
        MAX(CASE WHEN trade_date='2024-08-12' THEN source END) s12,
        MAX(CASE WHEN trade_date='2024-08-13' THEN source END) s13,
        MAX(CASE WHEN trade_date='2024-08-12' THEN close END) c12,
        MAX(CASE WHEN trade_date='2024-08-13' THEN close END) c13
      FROM d GROUP BY symbol)
SELECT symbol,s12,s13,c12,c13 FROM p WHERE c12>0 AND c13>0"""
cache={s:(a,b,x,y) for s,a,b,x,y in c.execute(Q)}
QM="""WITH d AS (SELECT symbol,trade_date,close FROM daily_bars
       WHERE trade_date IN ('2024-08-12','2024-08-13') AND adjustment_mode='qfq')
 SELECT symbol, MAX(CASE WHEN trade_date='2024-08-12' THEN close END),
        MAX(CASE WHEN trade_date='2024-08-13' THEN close END) FROM d GROUP BY symbol"""
mh={s:(a,b) for s,a,b in m.execute(QM) if a and b and a>0 and b>0}
sp=[s for s,(a,b,_,_) in cache.items() if a and b and a!=b and s in mh]
sm=[s for s,(a,b,_,_) in cache.items() if a and b and a==b and s in mh]
def med(v): v=sorted(v); return v[len(v)//2]
for nm,grp in (("spliced",sp),("non-spliced",sm)):
    r12=[100*(cache[s][2]/mh[s][0]-1) for s in grp]
    r13=[100*(cache[s][3]/mh[s][1]-1) for s in grp]
    print(f"  {nm:12s} n={len(grp):5d}  median(cache_close/MH_close-1): 08-12={med(r12):+.4f}%  08-13={med(r13):+.4f}%")

print("\n=== [H] jump magnitude at 2024-08-13 splice (my own numbers) ===")
j=sorted(100*(cache[s][3]/cache[s][2]-1) - 100*(mh[s][1]/mh[s][0]-1) for s in sp)
raw=sorted(abs(100*(cache[s][3]/cache[s][2]-1)) for s in sp)
n=len(sp)
print(f"  n={n}  median|cache ret|={med(raw):.4f}%  frac |ret|>2%={100*sum(1 for x in raw if x>2)/n:.1f}%  >10%={100*sum(1 for x in raw if x>10)/n:.1f}%")
print(f"  ARTIFACT (cache_ret - MH_ret): median={med(j):+.4f}pp mean={st.mean(j):+.4f}pp  frac>2pp={100*sum(1 for x in j if x>2)/n:.1f}%  frac>10pp={100*sum(1 for x in j if x>10)/n:.1f}%")

print("\n=== [I] boundary census: distinct symbols whose source changes vs prev available bar ===")
QB="""
WITH b AS (SELECT symbol,trade_date,source,
             LAG(source) OVER (PARTITION BY symbol ORDER BY trade_date) ps
           FROM daily_bar_cache WHERE adjustment_mode='qfq' AND quality_status='ready')
SELECT trade_date, COUNT(DISTINCT symbol) FROM b
 WHERE ps IS NOT NULL AND ps<>source AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'
 GROUP BY 1 ORDER BY 2 DESC LIMIT 15"""
tot=0
for r in c.execute(QB): print("   ",r)
QT="""WITH b AS (SELECT symbol,trade_date,source,
             LAG(source) OVER (PARTITION BY symbol ORDER BY trade_date) ps
           FROM daily_bar_cache WHERE adjustment_mode='qfq' AND quality_status='ready')
SELECT COUNT(*) , COUNT(DISTINCT symbol) FROM b WHERE ps IS NOT NULL AND ps<>source
 AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'"""
print("   TOTAL boundaries (rows, distinct symbols) in window:", list(c.execute(QT))[0])
QP="""WITH b AS (SELECT symbol,trade_date,source,
             LAG(source) OVER (PARTITION BY symbol ORDER BY trade_date) ps
           FROM daily_bar_cache WHERE adjustment_mode='qfq' AND quality_status='ready')
SELECT ps||' -> '||source, COUNT(*) FROM b WHERE ps IS NOT NULL AND ps<>source
 AND trade_date BETWEEN '2023-09-04' AND '2026-09-04' GROUP BY 1 ORDER BY 2 DESC LIMIT 8"""
print("   top transitions:")
for r in c.execute(QP): print("     ",r)

print("\n=== [J] created_at/updated_at vintage by source, Aug-2024 (rows) ===")
for r in c.execute("""SELECT source, substr(created_at,1,10), substr(updated_at,1,10), COUNT(*)
   FROM daily_bar_cache WHERE trade_date BETWEEN '2024-08-01' AND '2024-08-31'
   GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 8"""): print("   ",r)
