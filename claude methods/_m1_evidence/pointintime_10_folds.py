import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
SQL=("SELECT trade_date FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "
     "AND trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND quality_status='ready' "
     "GROUP BY trade_date HAVING COUNT(*)>=3000 ORDER BY trade_date")
d=[r[0] for r in c.execute(SQL)]; c.close()
N=len(d); print("dense days:",N, d[0],"..",d[-1])
WARM=120; H=20; EMB=20
print(f"\nWARM-UP (features only, never a labelled sample): d[0..{WARM-1}] = {d[0]} .. {d[WARM-1]}")
print(f"SAMPLE-ELIGIBLE decision dates: d[{WARM}..{N-1-H}] = {d[WARM]} .. {d[N-1-H]}  ({N-H-WARM} days)")
print(f"  (last {H} days {d[N-H]} .. {d[-1]} cannot carry a 20d label -> UNLABELLED TAIL)")
TEST=50
print(f"\n=== Anchored walk-forward: 4 folds, test={TEST}d, purge={H}d, embargo={EMB}d ===")
last_sample = N-1-H
folds=[]
for k in range(4,0,-1):
    te = last_sample - (4-k)*(TEST+EMB)
    ts = te-TEST+1
    ve = ts-1-H
    vs = ve-40+1
    tre = vs-1-H
    trs = WARM
    folds.append((k,trs,tre,vs,ve,ts,te))
for k,trs,tre,vs,ve,ts,te in sorted(folds):
    if tre-trs+1 < 60:
        print(f"fold{k}: TRAIN TOO SHORT ({tre-trs+1}d) -> not viable"); continue
    print(f"fold{k}: TRAIN {d[trs]}..{d[tre]} ({tre-trs+1}d) |purge {H}| VAL {d[vs]}..{d[ve]} ({ve-vs+1}d) "
          f"|purge {H}| TEST {d[ts]}..{d[te]} ({te-ts+1}d)  [test labels resolve by {d[min(te+H,N-1)]}]")
print("\n=== Alternative: 3 folds, test=70d (more test power) ===")
TEST=70
for k in range(3,0,-1):
    te = last_sample - (3-k)*(TEST+EMB); ts=te-TEST+1
    ve=ts-1-H; vs=ve-40+1; tre=vs-1-H; trs=WARM
    tag = "OK" if tre-trs+1>=60 else "TRAIN TOO SHORT"
    print(f"fold{k} [{tag}]: TRAIN {d[trs]}..{d[tre]} ({tre-trs+1}d) | VAL {d[vs]}..{d[ve]} | TEST {d[ts]}..{d[te]}  labels resolve by {d[min(te+H,N-1)]}")
