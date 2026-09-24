# READ-ONLY. Direct test: does the PRICE LEVEL shift at a source boundary?
# Plus a date-matched control for the cache-vs-market_history agreement test.
import sqlite3, json, random, statistics
from collections import defaultdict

OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
W0, W1 = '2023-09-04', '2026-09-04'
K = 10  # trading days each side

def pctl(v,p):
    if not v: return float('nan')
    s=sorted(v); return s[min(len(s)-1,int(round(p/100*(len(s)-1))))]

B = json.load(open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjrefute_boundaries.json"))["boundaries"]
bnd_by_sym = defaultdict(list)
for sym,dp,d,ret,s0,s1 in B: bnd_by_sym[sym].append((dp,d,ret,s0,s1))
print(f"boundaries loaded: {len(B)} over {len(bnd_by_sym)} symbols", flush=True)

c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
m = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)

print("\n### symbol-format join sanity: cache symbol vs market_history symbol", flush=True)
mh_syms = {r[0] for r in m.execute("SELECT DISTINCT symbol FROM daily_bars WHERE trade_date BETWEEN ? AND ?", (W0,W1))}
print(f"  mh symbols in window: {len(mh_syms)}  sample={sorted(mh_syms)[:5]}", flush=True)
print(f"  boundary symbols found in mh: {len(set(bnd_by_sym) & mh_syms)} / {len(bnd_by_sym)}", flush=True)

cur = c.execute(f"""
SELECT symbol, trade_date, close, source FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND trade_date BETWEEN ? AND ? ORDER BY symbol, trade_date""", (W0,W1))

# ---- results ----
level_shift = []          # per boundary: ratio_after/ratio_before  (ratio = cache/mh)
ratio_disp_before = []
bnd_agree = []            # per boundary >2%: |cache_ret - mh_ret| in pp
ctl_agree  = []           # date-matched control pairs, same dates, same magnitude band
unverif = 0
n_checked = 0
rng = random.Random(7)

# control pool: for each boundary date pair, we will pick other symbols with same dates & no boundary
bnd_datepairs = defaultdict(int)
for sym,dp,d,ret,s0,s1 in B: bnd_datepairs[(dp,d)] += 1
ctl_candidates = defaultdict(list)   # (dp,d) -> list of (sym, ret)

cur_sym=None; buf=[]
def mh_series(sym, d0, d1):
    return {td: cl for td, cl in m.execute(
        "SELECT trade_date, close FROM daily_bars WHERE symbol=? AND adjustment_mode='qfq' AND trade_date BETWEEN ? AND ?",
        (sym, d0, d1)) if cl}

def process(sym, rows):
    global unverif, n_checked
    if not rows: return
    dates=[r[0] for r in rows]; closes=[r[1] for r in rows]
    idx={d:i for i,d in enumerate(dates)}
    bl = bnd_by_sym.get(sym)
    # collect control candidates: consecutive pairs on boundary dates where THIS symbol had no source change
    bset = {(x[0],x[1]) for x in bl} if bl else set()
    for i in range(1,len(rows)):
        dp,d = dates[i-1], dates[i]
        if (dp,d) in bnd_datepairs and (dp,d) not in bset and rows[i][2]==rows[i-1][2]:
            if closes[i-1] and closes[i] and closes[i-1]>0:
                ctl_candidates[(dp,d)].append((sym, closes[i]/closes[i-1]-1.0))
    if not bl: return
    mh = mh_series(sym, dates[0], dates[-1])
    if not mh: 
        unverif += len(bl); return
    for dp,d,ret,s0,s1 in bl:
        i = idx.get(d)
        if i is None or i<1: continue
        # ---- LEVEL SHIFT TEST: cache/mh price ratio before vs after boundary ----
        rb=[]; ra=[]
        for j in range(max(0,i-K), i):
            if dates[j] in mh and closes[j]: rb.append(closes[j]/mh[dates[j]])
        for j in range(i, min(len(dates), i+K)):
            if dates[j] in mh and closes[j]: ra.append(closes[j]/mh[dates[j]])
        if len(rb)>=3 and len(ra)>=3:
            mb, ma = statistics.median(rb), statistics.median(ra)
            if mb>0:
                level_shift.append((abs(ma/mb-1.0), sym, dp, d, mb, ma))
                ratio_disp_before.append(max(rb)/min(rb)-1.0 if min(rb)>0 else 0)
            n_checked+=1
        # ---- return agreement test (only for the >2% subset the auditor used) ----
        if abs(ret)>0.02:
            if dp in mh and d in mh and mh[dp]>0:
                mret = mh[d]/mh[dp]-1.0
                bnd_agree.append((abs(ret-mret), sym, dp, d, ret, mret))
            else:
                unverif+=1

for sym,td,close,src in cur:
    if sym!=cur_sym:
        if cur_sym is not None: process(cur_sym, buf)
        cur_sym=sym; buf=[]
    buf.append((td, close, src))
process(cur_sym, buf)

print(f"\n### LEVEL-SHIFT TEST  (median cache/mh price ratio, {K}d before vs {K}d after boundary)", flush=True)
ls=[x[0] for x in level_shift]
print(f"  boundaries testable: {len(ls)}", flush=True)
print(f"  |ratio_after/ratio_before - 1|:  p50={pctl(ls,50)*100:.4f}%  p90={pctl(ls,90)*100:.4f}%  "
      f"p99={pctl(ls,99)*100:.4f}%  max={max(ls)*100:.3f}%", flush=True)
for thr in (0.001,0.005,0.01,0.02,0.05):
    print(f"    boundaries with level shift > {thr*100:g}% : {sum(1 for x in ls if x>thr)} "
          f"({sum(1 for x in ls if x>thr)/len(ls)*100:.2f}%)", flush=True)
print("  worst 10 level shifts:", flush=True)
for x in sorted(level_shift, reverse=True)[:10]:
    print(f"    {x[1]}  {x[2]}->{x[3]}  ratio_before={x[4]:.6f} ratio_after={x[5]:.6f}  shift={x[0]*100:.3f}%", flush=True)

print(f"\n### RETURN-AGREEMENT: boundaries with |cache ret|>2%, cache vs mh qfq return", flush=True)
ba=[x[0] for x in bnd_agree]
print(f"  n={len(ba)}   unverifiable(no mh on one/both dates)={unverif}", flush=True)
for thr in (0.005,0.01,0.02):
    print(f"    |cache_ret - mh_ret| > {thr*100:g}pp : {sum(1 for x in ba if x>thr)} ({sum(1 for x in ba if x>thr)/len(ba)*100:.1f}%)", flush=True)

print(f"\n### DATE-MATCHED CONTROL: same dates, other symbols, NO source change, |ret|>2%", flush=True)
ctl=[]
for (dp,d),n in bnd_datepairs.items():
    pool=[x for x in ctl_candidates.get((dp,d),[]) if abs(x[1])>0.02]
    rng.shuffle(pool)
    for sym,ret in pool[:max(1,n)]:
        ctl.append((sym,dp,d,ret))
print(f"  control pairs assembled: {len(ctl)}", flush=True)
ca=[]; cun=0
byc=defaultdict(list)
for sym,dp,d,ret in ctl: byc[sym].append((dp,d,ret))
for sym,items in byc.items():
    ds=[x[0] for x in items]+[x[1] for x in items]
    mh=mh_series(sym, min(ds), max(ds))
    for dp,d,ret in items:
        if dp in mh and d in mh and mh[dp]>0: ca.append(abs(ret-(mh[d]/mh[dp]-1.0)))
        else: cun+=1
print(f"  n={len(ca)}  unverifiable={cun}", flush=True)
for thr in (0.005,0.01,0.02):
    print(f"    |cache_ret - mh_ret| > {thr*100:g}pp : {sum(1 for x in ca if x>thr)} ({sum(1 for x in ca if x>thr)/max(1,len(ca))*100:.1f}%)", flush=True)
print("\n  >>> If the two disagreement rates match, the boundary is NOT the cause.", flush=True)
