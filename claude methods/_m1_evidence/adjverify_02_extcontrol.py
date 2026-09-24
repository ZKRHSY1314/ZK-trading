import sqlite3, statistics as st
OP=r"D:/codex-A股交易/trading_local.sqlite3"
MH=r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c=ro(OP); m=ro(MH)

print("=== [C] market_history provider/vintage for 2024-08-12/13 ===")
for r in m.execute("""SELECT trade_date, provider, adjustment_mode, substr(fetched_at,1,10) f,
       COUNT(*) n, COUNT(DISTINCT symbol) nsym
       FROM daily_bars WHERE trade_date IN ('2024-08-12','2024-08-13')
       GROUP BY 1,2,3,4 ORDER BY 1,5 DESC"""): print(r)

# cache returns
Q_CACHE="""
WITH d AS (SELECT symbol,trade_date,source,close FROM daily_bar_cache
           WHERE trade_date IN ('2024-08-12','2024-08-13') AND adjustment_mode='qfq'
             AND quality_status='ready'),
 p AS (SELECT symbol,
        MAX(CASE WHEN trade_date='2024-08-12' THEN source END) s12,
        MAX(CASE WHEN trade_date='2024-08-13' THEN source END) s13,
        MAX(CASE WHEN trade_date='2024-08-12' THEN close  END) c12,
        MAX(CASE WHEN trade_date='2024-08-13' THEN close  END) c13
      FROM d GROUP BY symbol)
SELECT symbol,s12,s13,c12,c13 FROM p WHERE c12 IS NOT NULL AND c13 IS NOT NULL AND c12>0"""
cache={}
for sym,s12,s13,c12,c13 in c.execute(Q_CACHE):
    cache[sym]=(s12,s13,(c13/c12-1)*100.0)

Q_MH="""
WITH d AS (SELECT symbol,trade_date,close FROM daily_bars
           WHERE trade_date IN ('2024-08-12','2024-08-13') AND adjustment_mode='qfq'),
 p AS (SELECT symbol,
        MAX(CASE WHEN trade_date='2024-08-12' THEN close END) c12,
        MAX(CASE WHEN trade_date='2024-08-13' THEN close END) c13
      FROM d GROUP BY symbol)
SELECT symbol,c12,c13 FROM p WHERE c12 IS NOT NULL AND c13 IS NOT NULL AND c12>0"""
mh={s:(c13/c12-1)*100.0 for s,c12,c13 in m.execute(Q_MH)}

# stock-only universe from instruments
stocks={r[0] for r in m.execute("SELECT symbol FROM instruments WHERE asset_type='stock'")}
print(f"\ncache ret symbols={len(cache)}  mh ret symbols={len(mh)}  instruments stocks={len(stocks)}")

def desc(name,v):
    v=sorted(v)
    if not v: print(f"{name}: EMPTY"); return
    n=len(v)
    print(f"{name}: n={n} mean={st.mean(v):+.4f}% median={v[n//2]:+.4f}% "
          f"p10={v[int(n*.10)]:+.3f} p90={v[int(n*.90)]:+.3f} up%={100*sum(1 for x in v if x>0)/n:.1f}")

spliced=[s for s,(a,b,_) in cache.items() if a and b and a!=b]
same   =[s for s,(a,b,_) in cache.items() if a and b and a==b]
print(f"\n=== [D] cache-only comparison (their claim), stocks-only filter applied ===")
sp_s=[s for s in spliced if s in stocks]; sm_s=[s for s in same if s in stocks]
desc("  spliced   (cache ret)", [cache[s][2] for s in sp_s])
desc("  NOTspliced(cache ret)", [cache[s][2] for s in sm_s])

print(f"\n=== [E] EXTERNAL control: same symbols, return from market_history.daily_bars qfq ===")
sp_b=[s for s in sp_s if s in mh]; sm_b=[s for s in sm_s if s in mh]
print(f"  overlap: spliced {len(sp_b)}/{len(sp_s)}   nonspliced {len(sm_b)}/{len(sm_s)}")
desc("  spliced   (MH ret)   ", [mh[s] for s in sp_b])
desc("  NOTspliced(MH ret)   ", [mh[s] for s in sm_b])

print(f"\n=== [F] PER-SYMBOL error: cache_ret - MH_ret (pp) ===")
d_sp=sorted(cache[s][2]-mh[s] for s in sp_b)
d_sm=sorted(cache[s][2]-mh[s] for s in sm_b)
desc("  spliced   err", d_sp)
desc("  NOTspliced err", d_sm)
print(f"  |err|>0.5pp  spliced: {100*sum(1 for x in d_sp if abs(x)>0.5)/max(1,len(d_sp)):.1f}%  "
      f"nonspliced: {100*sum(1 for x in d_sm if abs(x)>0.5)/max(1,len(d_sm)):.1f}%")
print(f"  |err|>2.0pp  spliced: {100*sum(1 for x in d_sp if abs(x)>2.0)/max(1,len(d_sp)):.1f}%  "
      f"nonspliced: {100*sum(1 for x in d_sm if abs(x)>2.0)/max(1,len(d_sm)):.1f}%")
