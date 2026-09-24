# -*- coding: utf-8 -*-
import json, collections
K=json.load(open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjv2_unexplained.json"))
print(f"my UNEXPLAINED total: {len(K)}")

print("\n=== excess-over-limit magnitude of my 2307 unexplained, by mh verdict ===")
B=[(0,0.002),(0.002,0.005),(0.005,0.01),(0.01,0.05),(0.05,9)]
t=collections.defaultdict(collections.Counter)
for e in K:
    ex=abs(e['ret'])-e['lim']
    for lo,hi in B:
        if lo<=ex<hi: t[e['mh']][(lo,hi)]+=1; break
print("verdict        " + "".join(f"{lo}-{hi}".rjust(12) for lo,hi in B))
for v in ['confirmed','absent','cache_only','differs']:
    print(f"{v:14s}" + "".join(f"{t[v][k]:>12d}" for k in B))

print("\n=== SOURCE-SPLICE test: does the bar's source differ from the previous bar's? ===")
sp=collections.Counter()
for e in K: sp[(e['src']!=e['psrc'], e['mh'])]+=1
for k,v in sorted(sp.items()): print("  src_changed=%-5s mh=%-11s %d"%(k[0],k[1],v))
allsp=sum(v for k,v in sp.items() if k[0]); print(f"  -> {allsp}/{len(K)} = {allsp/len(K)*100:.1f}% sit on a source change")

print("\n############ RECONCILIATION TO THEIR CLAIM (their |ret|>0.11 prefilter) ############")
H=[e for e in K if abs(e['ret'])>0.11]
print(f"my unexplained AND |ret|>0.11 : {len(H)} events / {len(set(e['symbol'] for e in H))} symbols")
print("  by board:", dict(collections.Counter(e['board'] for e in H)))
print("  by mh verdict:", dict(collections.Counter(e['mh'] for e in H)))
print("  consecutive-session:", sum(1 for e in H if e['sessions_gap']==1), "/", len(H))
un=[e for e in H if e['mh']=='absent']
print(f"  UNVERIFIABLE: {len(un)} = {len(un)/len(H)*100:.1f}%  by board:", dict(collections.Counter(e['board'] for e in un)))
bj=[e for e in H if e['board']=='beijing']
print(f"  BJ events: {len(bj)}, sources:", dict(collections.Counter(e['src'] for e in bj)))
print("  cache_only:", sum(1 for e in H if e['mh']=='cache_only'), " differs:", sum(1 for e in H if e['mh']=='differs'),
      " confirmed:", sum(1 for e in H if e['mh']=='confirmed'))

print("\n=== how many of THEIR 430 would my IPO filter have removed? ===")
# recompute the same |ret|>0.11 set WITHOUT the IPO/gap exclusions
import sqlite3
E=json.load(open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjv2_events.json"))
allh=[e for e in E if abs(e['ret'])>0.11 and abs(e['ret'])>e['lim']]
print(f"  no-exclusion analogue of their 430: {len(allh)} events / {len(set(e['symbol'] for e in allh))} symbols")
print("  by board:", dict(collections.Counter(e['board'] for e in allh)))
print(f"  removed by IPO-no-limit window: {len(allh)-len(H)} events")
