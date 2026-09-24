import sqlite3, json, statistics
from collections import defaultdict
OP=r"D:/codex-A股交易/trading_local.sqlite3"; MH=r"D:/codex-A股交易/market_history.sqlite3"
c=sqlite3.connect(f"file:{OP}?mode=ro",uri=True); m=sqlite3.connect(f"file:{MH}?mode=ro",uri=True)

print("### A) is market_history an INDEPENDENT reference? provider mix around the cutover", flush=True)
for r in m.execute("""SELECT provider, COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date)
 FROM daily_bars GROUP BY 1 ORDER BY 2 DESC"""): print("  ",r, flush=True)
print("  mh rows on the cutover dates by provider:", flush=True)
for r in m.execute("""SELECT trade_date, provider, COUNT(*) FROM daily_bars
 WHERE trade_date IN ('2024-08-12','2024-08-13') GROUP BY 1,2"""): print("   ",r, flush=True)

print("\n### B) concrete walk-through: SZ002582 across the 2024-08-13 boundary", flush=True)
ca={d:(o,h,l,cl,src) for d,o,h,l,cl,src in c.execute(
 """SELECT trade_date,open,high,low,close,source FROM daily_bar_cache
    WHERE symbol='SZ002582' AND trade_date BETWEEN '2024-08-05' AND '2024-08-21' ORDER BY trade_date""")}
mm={d:cl for d,cl in m.execute(
 """SELECT trade_date,close FROM daily_bars WHERE symbol='SZ002582' AND adjustment_mode='qfq'
    AND trade_date BETWEEN '2024-08-05' AND '2024-08-21'""")}
print(f"  {'date':12s} {'cache_close':>11s} {'mh_qfq':>9s} {'ratio':>7s}  source", flush=True)
for d in sorted(ca):
    r=ca[d][3]/mm[d] if d in mm and mm[d] else float('nan')
    print(f"  {d:12s} {ca[d][3]:11.4f} {mm.get(d,float('nan')):9.4f} {r:7.4f}  {ca[d][4]}", flush=True)

print("\n### C) same for SH603093 (opposite-sign shift)", flush=True)
ca={d:(cl,src) for d,cl,src in c.execute(
 """SELECT trade_date,close,source FROM daily_bar_cache WHERE symbol='SH603093'
    AND trade_date BETWEEN '2024-08-07' AND '2024-08-19' ORDER BY trade_date""")}
mm={d:cl for d,cl in m.execute(
 """SELECT trade_date,close FROM daily_bars WHERE symbol='SH603093' AND adjustment_mode='qfq'
    AND trade_date BETWEEN '2024-08-07' AND '2024-08-19'""")}
for d in sorted(ca):
    r=ca[d][0]/mm[d] if d in mm and mm[d] else float('nan')
    print(f"  {d:12s} cache={ca[d][0]:9.4f}  mh={mm.get(d,float('nan')):9.4f}  ratio={r:7.4f}  {ca[d][1]}", flush=True)

print("\n### D) CORRECTED counts: distinct SYMBOLS with a genuine artifactual level break", flush=True)
B=json.load(open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjrefute_boundaries.json"))["boundaries"]
bs=defaultdict(list)
for sym,dp,d,ret,s0,s1 in B: bs[sym].append((dp,d))
K=10
def mhser(sym,d0,d1):
    return {td:cl for td,cl in m.execute(
      "SELECT trade_date,close FROM daily_bars WHERE symbol=? AND adjustment_mode='qfq' AND trade_date BETWEEN ? AND ?",(sym,d0,d1)) if cl}
cur=c.execute("""SELECT symbol,trade_date,close,source FROM daily_bar_cache
 WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
 AND trade_date BETWEEN '2023-09-04' AND '2026-09-04' ORDER BY symbol,trade_date""")
shift_by_sym=defaultdict(float); shift_bnd=[]; untest=set()
cs=None; buf=[]
def proc(sym,rows):
    if sym not in bs: return
    dates=[r[0] for r in rows]; cl=[r[1] for r in rows]; idx={d:i for i,d in enumerate(dates)}
    mh=mhser(sym,dates[0],dates[-1])
    if not mh: untest.add(sym); return
    tested=False
    for dp,d in bs[sym]:
        i=idx.get(d)
        if i is None or i<1: continue
        rb=[cl[j]/mh[dates[j]] for j in range(max(0,i-K),i) if dates[j] in mh and cl[j] and mh[dates[j]]]
        ra=[cl[j]/mh[dates[j]] for j in range(i,min(len(dates),i+K)) if dates[j] in mh and cl[j] and mh[dates[j]]]
        if len(rb)>=3 and len(ra)>=3:
            mb,ma=statistics.median(rb),statistics.median(ra)
            if mb>0:
                s=abs(ma/mb-1.0); tested=True
                shift_bnd.append((s,sym,dp,d))
                shift_by_sym[sym]=max(shift_by_sym[sym],s)
    if not tested: untest.add(sym)
for sym,td,close,src in cur:
    if sym!=cs:
        if cs is not None: proc(cs,buf)
        cs=sym; buf=[]
    buf.append((td,close,src))
proc(cs,buf)
tot_syms=5566
print(f"  boundary symbols: {len(bs)};  testable: {len(shift_by_sym)};  untestable (no mh overlap): {len(untest)}", flush=True)
for thr in (0.005,0.01,0.02,0.05,0.10):
    ns=sum(1 for v in shift_by_sym.values() if v>thr); nb=sum(1 for x in shift_bnd if x[0]>thr)
    print(f"    level shift > {thr*100:4g}% :  {nb:5d} boundaries   {ns:5d} distinct symbols "
          f"({ns/tot_syms*100:4.1f}% of {tot_syms} in-window symbols)", flush=True)
json.dump(sorted(shift_bnd,reverse=True)[:500], open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjrefute_worst.json","w"))
