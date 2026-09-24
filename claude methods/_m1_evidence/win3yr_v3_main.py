# -*- coding: utf-8 -*-
import sqlite3, pathlib, sys, datetime, collections, statistics
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
OP=r"D:\codex-A股交易\trading_local.sqlite3"; MH=r"D:\codex-A股交易\market_history.sqlite3"
W0,W1="2023-09-04","2026-09-04"
def ro(p): return "file:"+pathlib.Path(p).as_posix()+"?mode=ro"
op=sqlite3.connect(ro(OP),uri=True); mh=sqlite3.connect(ro(MH),uri=True)
def Q(c,s,p=()): return list(c.execute(s,p))

# ---- spine: distinct sessions in window, restricted to instrument-classified A-share stocks
STK=[r[0] for r in Q(mh,"SELECT symbol FROM instruments WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ')")]
stk=set(STK)
cur=op.cursor()
cur.execute("CREATE TEMP TABLE u(symbol TEXT PRIMARY KEY)")   # TEMP only -> in-memory, never touches the file
cur.executemany("INSERT INTO u VALUES(?)",[(s,) for s in STK])
SPINE_SQL="""SELECT DISTINCT d.trade_date FROM daily_bar_cache d JOIN u ON u.symbol=d.symbol
             WHERE d.trade_date>=? AND d.trade_date<=? AND length(d.trade_date)=10"""
spine=sorted(r[0] for r in Q(op,SPINE_SQL,(W0,W1)))
print("[SPINE] "+" ".join(SPINE_SQL.split()))
print("  sessions=%d  first=%s  last=%s"%(len(spine),spine[0],spine[-1]))
sidx={d:i for i,d in enumerate(spine)}

# ---- breadth per session (verifies the 'ramp')
BR_SQL="""SELECT d.trade_date, COUNT(DISTINCT d.symbol) FROM daily_bar_cache d JOIN u ON u.symbol=d.symbol
          WHERE d.trade_date>=? AND d.trade_date<=? GROUP BY 1 ORDER BY 1"""
br=Q(op,BR_SQL,(W0,W1))
print("\n[BREADTH] "+" ".join(BR_SQL.split()))
first_full=next(i for i,(d,n) in enumerate(br) if n>=4000)
print("  first session with >=4000 stocks: index=%d date=%s"%(first_full,br[first_full][0]))
print("  sessions BEFORE that (the ramp) = %d"%first_full)
print("  ramp head:", [(d,n) for d,n in br[:6]])
print("  ramp tail:", [(d,n) for d,n in br[first_full-3:first_full+3]])
med_after=statistics.median(n for d,n in br[first_full:])
print("  median breadth after ramp = %d"%med_after)

# ---- per-symbol observed (valid OHLC), one grouped pass -- NOT their correlated subquery
OBS_SQL="""SELECT d.symbol, COUNT(DISTINCT d.trade_date) FROM daily_bar_cache d JOIN u ON u.symbol=d.symbol
           WHERE d.trade_date>=? AND d.trade_date<=? AND length(d.trade_date)=10
             AND d.open IS NOT NULL AND d.high IS NOT NULL AND d.low IS NOT NULL
             AND d.close IS NOT NULL AND d.close>0
           GROUP BY d.symbol"""
obs=dict(Q(op,OBS_SQL,(W0,W1)))
print("\n[OBSERVED] "+" ".join(OBS_SQL.split()))
print("  symbols with >=1 valid bar = %d   (of %d stocks)"%(len(obs),len(stk)))
print("  sum of observed distinct-date counts = %d"%sum(obs.values()))

# ---- listing metadata
meta=dict((r[0],(r[1],r[2],r[3])) for r in Q(mh,"SELECT symbol,list_date,delist_date,status FROM instruments"))
FIRST=spine[0]; LAST=spine[-1]
def norm(x):
    if not x: return None
    x=str(x)[:10]
    return x if len(x)==10 and x[4]=='-' else None

pre=[s for s in stk if (norm(meta[s][0]) or "0000-00-00") < FIRST]
print("\n  stocks whose list_date < first data session (%s) = %d"%(FIRST,len(pre)))
print("  stocks with NULL/unparseable list_date = %d"%sum(1 for s in stk if norm(meta[s][0]) is None))

# ================= DENOMINATOR A: their denominator (observed spine, 587) =================
# ================= DENOMINATOR B: eligible spine sessions given list/delist =================
# ================= DENOMINATOR C: THE ACTUAL 3-YEAR WINDOW =================
d0=datetime.date.fromisoformat(W0); d1=datetime.date.fromisoformat(W1)
wd_all=sum(1 for i in range((d1-d0).days+1) if (d0+datetime.timedelta(days=i)).weekday()<5)
fs=datetime.date.fromisoformat(FIRST)
wd_before=sum(1 for i in range((fs-d0).days) if (d0+datetime.timedelta(days=i)).weekday()<5)
wd_obs_span=sum(1 for i in range((d1-fs).days+1) if (fs+datetime.timedelta(days=i)).weekday()<5)
dens=len(spine)/wd_obs_span
print("\n  window weekdays total            = %d"%wd_all)
print("  weekdays BEFORE first session    = %d   (observed sessions there: 0)"%wd_before)
print("  weekdays in observed span        = %d   observed sessions %d  density=%.4f"%(wd_obs_span,len(spine),dens))
print("  ESTIMATE (not a measurement) of true 3yr sessions = %.0f"%(wd_all*dens))

ratA={}; ratB={}; ratC={}
EST_TRUE=round(wd_all*dens)
for s in stk:
    o=obs.get(s,0)
    ratA[s]=o/len(spine)
    ld=norm(meta[s][0]); dd=norm(meta[s][1])
    lo=max(FIRST, ld) if ld else FIRST
    hi=min(LAST, dd) if dd else LAST
    elig=sum(1 for d in spine if lo<=d<=hi)
    ratB[s]=(o/elig) if elig>0 else None
    ratC[s]=o/EST_TRUE

def dist(name,r,keys):
    v=sorted(r[k] for k in keys if r.get(k) is not None)
    q=lambda p: v[min(len(v)-1,int(p*len(v)))]
    print("\n  %s  n=%d"%(name,len(v)))
    print("    D10=%.6f D25=%.6f D50=%.6f D75=%.6f D90=%.6f mean=%.6f"%(q(.10),q(.25),q(.50),q(.75),q(.90),sum(v)/len(v)))
    for th in (0.99,0.95,0.90,0.75,0.50):
        print("    >= %.2f : %5d (%.1f%%)"%(th,sum(1 for x in v if x>=th),100*sum(1 for x in v if x>=th)/len(v)))

comp=[s for s in stk if obs.get(s,0)>0]
print("\n"+"="*100); print("DISTRIBUTIONS over %d stocks with >=1 valid bar"%len(comp)); print("="*100)
dist("A: observed / 587 observed-spine sessions  (THEIR ratio)",ratA,comp)
dist("B: observed / eligible-spine sessions (list/delist aware)",ratB,comp)
dist("C: observed / est. TRUE 3-year sessions (%d)"%EST_TRUE,ratC,comp)

print("\n"+"="*100); print("HISTOGRAM of raw observed counts (top 12)"); print("="*100)
h=collections.Counter(obs.get(s,0) for s in stk)
for k,n in h.most_common(12): print("  observed=%4d  symbols=%5d  ratio_vs_587=%.6f"%(k,n,k/len(spine)))
top2=[k for k,_ in h.most_common(2)]
print("  top-2 modes cover %d symbols"%sum(h[k] for k in top2))

print("\n"+"="*100); print("PRE-EXISTING STOCKS (list_date < %s): do ANY reach 0.95?"%FIRST); print("="*100)
for label,r,dn in (("A vs 587",ratA,len(spine)),("B vs eligible",ratB,None),("C vs %d true"%EST_TRUE,ratC,EST_TRUE)):
    vals=[r[s] for s in pre if r.get(s) is not None]
    print("  %-18s n=%d  max=%.6f  >=0.95: %d  >=0.90: %d  median=%.6f"%(
        label,len(vals),max(vals),sum(1 for x in vals if x>=0.95),sum(1 for x in vals if x>=0.90),statistics.median(vals)))

print("\n"+"="*100); print("WHO IS ABOVE 0.99 vs 587? (their claim: mostly post-2024-06-24 IPOs)"); print("="*100)
hi=[s for s in comp if ratA[s]>=0.99]
print("  count =",len(hi))
lds=[norm(meta[s][0]) for s in hi]
print("  with list_date >= 2024-06-24 :",sum(1 for x in lds if x and x>='2024-06-24'))
print("  with list_date <  2024-06-24 :",sum(1 for x in lds if x and x< '2024-06-24'))
print("  null list_date               :",sum(1 for x in lds if x is None))
print("  their observed-count histogram:",collections.Counter(obs[s] for s in hi).most_common(6))
