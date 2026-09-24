import sqlite3, statistics as st
OP=r"D:/codex-A股交易/trading_local.sqlite3"; MH=r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c=ro(OP); m=ro(MH)
DATES=['2024-08-05','2024-08-07','2024-08-09','2024-08-12','2024-08-13','2024-08-14','2024-08-16','2024-08-23','2024-09-20','2025-03-14']
ph=",".join("?"*len(DATES))
cc={}
for s,d,src,cl in c.execute(f"SELECT symbol,trade_date,source,close FROM daily_bar_cache WHERE trade_date IN ({ph}) AND adjustment_mode='qfq' AND quality_status='ready'",DATES):
    cc.setdefault(s,{})[d]=(src,cl)
mm={}
for s,d,cl in m.execute(f"SELECT symbol,trade_date,close FROM daily_bars WHERE trade_date IN ({ph}) AND adjustment_mode='qfq'",DATES):
    mm.setdefault(s,{})[d]=cl
sp=[s for s,v in cc.items() if '2024-08-12' in v and '2024-08-13' in v
    and v['2024-08-12'][0]!=v['2024-08-13'][0] and s in mm]
def med(v): v=sorted(v); return v[len(v)//2] if v else float('nan')
print("=== [K] PERSISTENCE: median(cache_close / MH_close - 1) by date, spliced symbols (n=%d) ==="%len(sp))
for d in DATES:
    v=[100*(cc[s][d][1]/mm[s][d]-1) for s in sp if d in cc[s] and d in mm[s] and mm[s][d] and cc[s][d][1]]
    src=[cc[s][d][0] for s in sp if d in cc[s]]
    dom=max(set(src),key=src.count) if src else "-"
    print(f"   {d}  n={len(v):5d}  median_ratio={med(v):+.4f}%   dominant cache source={dom}")

print("\n=== [L] OFF-BY-ONE test: does cache 08-13 close match MH 08-13, or a neighbouring day? ===")
for tgt in ['2024-08-12','2024-08-13','2024-08-14']:
    v=[abs(100*(cc[s]['2024-08-13'][1]/mm[s][tgt]-1)) for s in sp if tgt in mm[s] and mm[s][tgt]]
    exact=sum(1 for x in v if x<0.01)
    print(f"   cache(08-13) vs MH({tgt}): n={len(v)} median|diff|={med(v):.4f}%  exact-match(<0.01%)={100*exact/len(v):.1f}%")
print("   control: cache(08-12) vs MH(08-12):", end=" ")
v=[abs(100*(cc[s]['2024-08-12'][1]/mm[s]['2024-08-12'][0 if False else 0]-1)) if False else abs(100*(cc[s]['2024-08-12'][1]/mm[s]['2024-08-12']-1)) for s in sp if '2024-08-12' in mm[s]]
print(f"median|diff|={med(v):.4f}%  exact-match={100*sum(1 for x in v if x<0.01)/len(v):.1f}%")

print("\n=== [M] equal-weighted market impact on 2024-08-13 (all qfq stocks with both bars) ===")
uni=[s for s,v in cc.items() if '2024-08-12' in v and '2024-08-13' in v and v['2024-08-12'][1] and v['2024-08-13'][1]]
rc=[100*(cc[s]['2024-08-13'][1]/cc[s]['2024-08-12'][1]-1) for s in uni]
uni2=[s for s in uni if s in mm and '2024-08-12' in mm[s] and '2024-08-13' in mm[s] and mm[s]['2024-08-12']]
rm=[100*(mm[s]['2024-08-13']/mm[s]['2024-08-12']-1) for s in uni2]
rc2=[100*(cc[s]['2024-08-13'][1]/cc[s]['2024-08-12'][1]-1) for s in uni2]
print(f"   cache EW return  n={len(rc)}  mean={st.mean(rc):+.4f}%")
print(f"   matched subset:  n={len(uni2)}  cache mean={st.mean(rc2):+.4f}%   MH mean={st.mean(rm):+.4f}%   INFLATION={st.mean(rc2)-st.mean(rm):+.4f}pp")
