import sqlite3, collections, statistics
MH = r"D:\codex-A股交易\market_history.sqlite3"
OP = r"D:\codex-A股交易\trading_local.sqlite3"
def ro(p): return sqlite3.connect("file:"+p.replace("\\","/")+"?mode=ro", uri=True)

mh=ro(MH); op=ro(OP)
mh.execute("PRAGMA query_only=ON"); op.execute("PRAGMA query_only=ON")

# classify symbols
inst={}
for sym,ex,at,st in mh.execute("SELECT symbol,exchange,asset_type,status FROM instruments"):
    inst[sym]=(ex,at,st)
print("instruments loaded:", len(inst))
print("exchange counts:", collections.Counter(v[0] for v in inst.values()))
print("asset_type counts:", collections.Counter(v[1] for v in inst.values()))

# cache-side profile first
print("\n--- trading_local.daily_bar_cache profile")
print("SQL: SELECT adjustment_mode, COUNT(*), COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1")
for r in op.execute("SELECT adjustment_mode, COUNT(*), COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1"): print("   ",r)
print("SQL: SELECT source, COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC")
for r in op.execute("SELECT source, COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC LIMIT 15"): print("   ",r)
print("SQL: SELECT substr(updated_at,1,10) d, COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC LIMIT 15")
for r in op.execute("SELECT substr(updated_at,1,10) d, COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC LIMIT 15"): print("   ",r)
print("SQL: SELECT provider, COUNT(*) FROM daily_bars GROUP BY 1 ORDER BY 2 DESC")
for r in mh.execute("SELECT provider, COUNT(*) FROM daily_bars GROUP BY 1 ORDER BY 2 DESC LIMIT 15"): print("   ",r)

# ---- streaming merge join on (symbol, trade_date)
A = mh.execute("SELECT symbol,trade_date,close,provider,substr(fetched_at,1,10) FROM daily_bars WHERE adjustment_mode='qfq' ORDER BY symbol,trade_date")
B = op.execute("SELECT symbol,trade_date,close,source,adjustment_mode,substr(updated_at,1,10) FROM daily_bar_cache ORDER BY symbol,trade_date")

def nxt(it):
    try: return next(it)
    except StopIteration: return None
a=nxt(A); b=nxt(B)
overlap=0; samesrc=0
gt1=0; gt5=0; gt1_syms=set(); samesrc_syms=set()
gt1_nonidx=0; samesrc_nonidx=0; gt1_syms_nonidx=set(); samesrc_syms_nonidx=set()
cohort=collections.Counter(); cohort_gt1=collections.Counter()
ratios_by_sym=collections.defaultdict(list)
signs=collections.Counter()
badclose=0
while a is not None and b is not None:
    ka=(a[0],a[1]); kb=(b[0],b[1])
    if ka<kb: a=nxt(A); continue
    if kb<ka: b=nxt(B); continue
    overlap+=1
    sym=a[0]; mclose=a[2]; prov=a[3]; fday=a[4]
    cclose=b[2]; src=b[3]; cadj=b[4]
    if cadj=='qfq' and src==prov:
        samesrc+=1; samesrc_syms.add(sym)
        cohort[fday]+=1
        ex=inst.get(sym,(None,None,None))[0]
        isidx = (ex=='INDEX')
        if not isidx:
            samesrc_nonidx+=1; samesrc_syms_nonidx.add(sym)
        if cclose is not None and cclose>0 and mclose is not None:
            r=mclose/cclose-1.0
            if abs(r)>0.01:
                gt1+=1; gt1_syms.add(sym); cohort_gt1[fday]+=1
                signs['up' if r>0 else 'down']+=1
                ratios_by_sym[sym].append(mclose/cclose)
                if not isidx:
                    gt1_nonidx+=1; gt1_syms_nonidx.add(sym)
            if abs(r)>0.05: gt5+=1
        else:
            badclose+=1
    a=nxt(A); b=nxt(B)

print("\n=== RESTATEMENT (my own streaming merge join, no SQL JOIN) ===")
print(f"overlapping (symbol,trade_date) keys present in BOTH stores: {overlap}")
print(f"  of which cache.adjustment_mode='qfq' AND cache.source = history.provider: {samesrc}  ({len(samesrc_syms)} distinct symbols)")
print(f"  same-provider keys with |mh.close/cache.close - 1| > 1%: {gt1}  = {gt1/max(samesrc,1):.4%}  across {len(gt1_syms)} distinct symbols")
print(f"  same-provider keys with |ratio-1| > 5%: {gt5}  = {gt5/max(samesrc,1):.4%}")
print(f"  keys with unusable close (null/<=0): {badclose}")
print(f"  EXCLUDING INDEX instruments: denom={samesrc_nonidx} ({len(samesrc_syms_nonidx)} symbols), >1% moves={gt1_nonidx} = {gt1_nonidx/max(samesrc_nonidx,1):.4%} across {len(gt1_syms_nonidx)} symbols")
print(f"  direction of >1% moves: {dict(signs)}")
print("\n  by market_history fetched_at cohort:")
for d in sorted(cohort): print(f"     {d}: denom={cohort[d]:>8}  >1%={cohort_gt1[d]:>7}  = {cohort_gt1[d]/max(cohort[d],1):.4%}")

# is the move a clean per-symbol scale factor (real corporate action) or noise?
print("\n  per-symbol coefficient of variation of the close ratio, for symbols with >=20 restated bars:")
clean=0; noisy=0; ex=[]
for s,rs in ratios_by_sym.items():
    if len(rs)<20: continue
    m=statistics.mean(rs); sd=statistics.pstdev(rs)
    cv=sd/m if m else 9
    if cv<0.005: clean+=1
    else: noisy+=1
    if len(ex)<10: ex.append((s,len(rs),round(m,5),round(cv,5)))
print(f"     symbols with >=20 restated bars: {clean+noisy}   near-constant ratio (CV<0.5%) = {clean}   variable ratio = {noisy}")
for e in ex: print("      sample:",e)
mh.close(); op.close()
