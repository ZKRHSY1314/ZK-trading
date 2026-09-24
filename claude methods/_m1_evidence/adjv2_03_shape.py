# -*- coding: utf-8 -*-
import json, collections
E=json.load(open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjv2_events.json"))
print("total raw over-own-limit:", len(E))
BINS=[(0.0,0.002),(0.002,0.005),(0.005,0.01),(0.01,0.02),(0.02,0.05),(0.05,0.10),(0.10,1e9)]
by=collections.defaultdict(collections.Counter)
for e in E:
    ex = abs(e['ret'])-e['lim']          # excess over the board limit
    for lo,hi in BINS:
        if lo<=ex<hi: by[e['board']][(lo,hi)]+=1; break
print("\nexcess-over-limit distribution by board (how far past the limit):")
hdr="board       " + "".join(f"{lo:.3f}-{hi:.3f} ".rjust(14) if hi<1e8 else "   >0.10     " for lo,hi in BINS)
print(hdr)
for b in ['sh_main','sz_main','chi_next','star','beijing']:
    print(f"{b:12s}" + "".join(f"{by[b][k]:>13d} " for k in BINS))
print("\n=> everything in the first bins is limit-price 2dp rounding noise, not a violation.")
tot=collections.Counter()
for e in E:
    ex=abs(e['ret'])-e['lim']
    tot['excess>0.01']+= ex>0.01
    tot['excess>0.005']+= ex>0.005
    tot['abs_ret>0.11 (their prefilter)'] += abs(e['ret'])>0.11
print("\n", dict(tot))
print("\n main-board events with |ret|>0.11:", sum(1 for e in E if e['board'] in('sh_main','sz_main') and abs(e['ret'])>0.11))
