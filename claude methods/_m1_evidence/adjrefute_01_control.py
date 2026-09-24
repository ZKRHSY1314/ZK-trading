# READ-ONLY adversarial verification of the "vendor splice" claim.
import sqlite3, statistics, random, sys, json
from collections import defaultdict

OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
W0, W1 = '2023-09-04', '2026-09-04'
DATE_GLOB = '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'

def q(x): return statistics.quantiles(x, n=100, method='inclusive') if len(x) > 1 else None
def pct(v, p):
    if not v: return float('nan')
    s = sorted(v); i = min(len(s)-1, int(round(p/100*(len(s)-1))))
    return s[i]

print("### STEP 1: classify symbols (stock vs index) from market_history.instruments", flush=True)
m = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
inst = {}
for sym, exch, atype, board, status in m.execute(
    "SELECT symbol, exchange, asset_type, board, status FROM instruments"):
    inst[sym] = (exch, atype, board, status)
print(f"instruments loaded: {len(inst)}", flush=True)
exch_counts = defaultdict(int)
for v in inst.values(): exch_counts[(v[0], v[1])] += 1
for k, v in sorted(exch_counts.items(), key=lambda x: -x[1]): print("   ", k, v, flush=True)

def is_index(sym):
    e = inst.get(sym, (None,)*4)[0]
    if e == 'INDEX': return True
    # fall back to code shape for symbols absent from instruments
    core = sym.split('.')[0] if '.' in sym else sym
    core = ''.join(ch for ch in core if ch.isdigit())
    if len(core) == 6 and (core.startswith('000') and sym.upper().startswith('SH')): return True
    return False

print("\n### STEP 2: stream daily_bar_cache in window, build consecutive-pair table", flush=True)
c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON")
cur = c.execute(f"""
SELECT symbol, trade_date, close, source, quality_status
FROM daily_bar_cache
WHERE trade_date GLOB '{DATE_GLOB}'
  AND trade_date BETWEEN ? AND ?
ORDER BY symbol, trade_date
""", (W0, W1))

# accumulators
boundary_pairs = []      # (sym, d_prev, d, ret, src_prev, src)
nonb_sample   = []       # reservoir of non-boundary pairs
NONB_TARGET   = 400000
absret_by_date = defaultdict(list)
n_rows = 0
syms_all = set(); syms_ready = set()
n_pairs = 0; n_bpairs = 0
src_change_dates = defaultdict(int)
sym_has_boundary = set()
sym_multisource = defaultdict(set)
rng = random.Random(20260905)
nonb_seen = 0

prev = None  # (sym, date, close, source)
def flush_sym(): pass

for sym, td, close, src, qs in cur:
    n_rows += 1
    syms_all.add(sym)
    if qs == 'ready': syms_ready.add(sym)
    sym_multisource[sym].add(src)
    if prev is not None and prev[0] == sym:
        pc = prev[2]
        if pc is not None and close is not None and pc > 0 and close > 0:
            ret = close/pc - 1.0
            absret_by_date[td].append(abs(ret))
            n_pairs += 1
            if src != prev[3]:
                n_bpairs += 1
                sym_has_boundary.add(sym)
                src_change_dates[td] += 1
                boundary_pairs.append((sym, prev[1], td, ret, prev[3], src))
            else:
                nonb_seen += 1
                if len(nonb_sample) < NONB_TARGET:
                    nonb_sample.append((sym, prev[1], td, ret, src))
                else:
                    j = rng.randrange(nonb_seen)
                    if j < NONB_TARGET: nonb_sample[j] = (sym, prev[1], td, ret, src)
    prev = (sym, td, close, src)
    if n_rows % 500000 == 0: print(f"   ...{n_rows} rows", flush=True)

print(f"rows in window (valid date shape): {n_rows}", flush=True)
print(f"distinct symbols in window: {len(syms_all)}   (with any ready row: {len(syms_ready)})", flush=True)
print(f"consecutive pairs with usable closes: {n_pairs}", flush=True)
print(f"source-change boundaries (pairs): {n_bpairs}  over {len(sym_has_boundary)} symbols", flush=True)
print(f"symbols served by >1 source in window: {sum(1 for s,v in sym_multisource.items() if len(v)>1)}", flush=True)

idx_syms = {s for s in syms_all if is_index(s)}
print(f"symbols classified INDEX: {len(idx_syms)}", flush=True)
print(f"  boundaries on INDEX symbols: {sum(1 for b in boundary_pairs if b[0] in idx_syms)}", flush=True)
print(f"  symbols with boundary that are INDEX: {len(sym_has_boundary & idx_syms)}", flush=True)
notin = {s for s in syms_all if s not in inst}
print(f"symbols in cache but ABSENT from instruments: {len(notin)}  sample={sorted(notin)[:15]}", flush=True)

print("\n### STEP 3: THE CONTROL — |return| at boundaries vs |return| everywhere else", flush=True)
b_abs = [abs(b[3]) for b in boundary_pairs]
n_abs = [abs(x[3]) for x in nonb_sample]
b_abs_stk = [abs(b[3]) for b in boundary_pairs if b[0] not in idx_syms]
n_abs_stk = [abs(x[3]) for x in nonb_sample if x[0] not in idx_syms]
def rep(name, v):
    print(f"  {name:34s} n={len(v):8d}  p50={pct(v,50)*100:6.2f}%  p90={pct(v,90)*100:6.2f}%  "
          f"p99={pct(v,99)*100:7.2f}%  max={max(v)*100 if v else 0:8.2f}%  "
          f">2%={sum(1 for x in v if x>0.02)/max(1,len(v))*100:5.1f}%  "
          f">5%={sum(1 for x in v if x>0.05)/max(1,len(v))*100:5.1f}%  "
          f">10%={sum(1 for x in v if x>0.10)/max(1,len(v))*100:5.1f}%", flush=True)
rep("BOUNDARY pairs (all)", b_abs)
rep("NON-boundary pairs (all, sampled)", n_abs)
rep("BOUNDARY pairs (stocks only)", b_abs_stk)
rep("NON-boundary pairs (stocks only)", n_abs_stk)

print("\n### STEP 4: DATE-MATCHED control (same trading day, cross-sectional)", flush=True)
day_med = {d: pct(v,50) for d,v in absret_by_date.items() if len(v) >= 50}
day_p90 = {d: pct(v,90) for d,v in absret_by_date.items() if len(v) >= 50}
ratios_b = []; excess_b = 0; tot_b = 0
for sym,dp,d,ret,s0,s1 in boundary_pairs:
    if d in day_med and day_med[d] > 1e-9:
        ratios_b.append(abs(ret)/day_med[d]); tot_b += 1
        if abs(ret) > day_p90[d]: excess_b += 1
ratios_n = []; excess_n = 0; tot_n = 0
for sym,dp,d,ret,s1 in nonb_sample:
    if d in day_med and day_med[d] > 1e-9:
        ratios_n.append(abs(ret)/day_med[d]); tot_n += 1
        if abs(ret) > day_p90[d]: excess_n += 1
print(f"  boundary   : median(|ret| / same-day median|ret|) = {pct(ratios_b,50):.3f}   share above same-day p90 = {excess_b/max(1,tot_b)*100:.1f}%  (n={tot_b})", flush=True)
print(f"  non-boundary: median(|ret| / same-day median|ret|) = {pct(ratios_n,50):.3f}   share above same-day p90 = {excess_n/max(1,tot_n)*100:.1f}%  (n={tot_n})", flush=True)
print(f"  NULL expectation for 'share above same-day p90' = 10.0%", flush=True)

print("\n### STEP 5: when do source flips happen? (are they a calendar sweep?)", flush=True)
top = sorted(src_change_dates.items(), key=lambda x:-x[1])[:20]
for d,n in top: print(f"   {d}  {n} boundaries", flush=True)
print(f"   dates carrying >=1 boundary: {len(src_change_dates)}", flush=True)
pairsrc = defaultdict(int)
for b in boundary_pairs: pairsrc[(b[4],b[5])] += 1
print("   source transitions:", flush=True)
for k,v in sorted(pairsrc.items(), key=lambda x:-x[1]): print(f"      {k[0]} -> {k[1]}: {v}", flush=True)

json.dump({"boundaries":[list(b) for b in boundary_pairs]},
          open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjrefute_boundaries.json","w"))
json.dump({"nonb":[list(x) for x in nonb_sample[:60000]]},
          open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjrefute_nonb.json","w"))
print("\nsaved boundary + non-boundary control sets", flush=True)
