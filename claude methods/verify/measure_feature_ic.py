import sqlite3, json, statistics
from collections import defaultdict
con=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True);cur=con.cursor()
rows=cur.execute("""
select d.rank,d.score,d.features_json,o.benchmark_neutral_return
from forecast_outcomes o join forecast_decisions d
 on d.decision_id=o.decision_id and d.subject=o.subject and d.horizon_days=o.horizon_days
where o.scope='stock' and o.horizon_days=1 and o.benchmark_neutral_return is not null limit 4000
""").fetchall()
keys=set()
for r in rows[:50]:
    try: keys|=set(json.loads(r[2] or "{}").keys())
    except: pass
print("feature keys:", sorted(keys))
# correlation of each numeric feature with excess return
data=defaultdict(list)
for rank,score,fj,bn in rows:
    try: f=json.loads(fj or "{}")
    except: continue
    for k,v in f.items():
        if isinstance(v,(int,float)) and not isinstance(v,bool): data[k].append((v,bn))
def spearman(pairs):
    n=len(pairs)
    if n<30: return None
    xs=sorted(range(n), key=lambda i:pairs[i][0]); ys=sorted(range(n), key=lambda i:pairs[i][1])
    rx=[0]*n; ry=[0]*n
    for r,i in enumerate(xs): rx[i]=r
    for r,i in enumerate(ys): ry[i]=r
    mx=statistics.fmean(rx); my=statistics.fmean(ry)
    num=sum((rx[i]-mx)*(ry[i]-my) for i in range(n))
    den=(sum((rx[i]-mx)**2 for i in range(n))*sum((ry[i]-my)**2 for i in range(n)))**.5
    return num/den if den else None
out=[]
for k,pairs in data.items():
    s=spearman(pairs)
    if s is not None: out.append((abs(s),s,k,len(pairs)))
out.sort(reverse=True)
print("\ntop feature IC vs next-day excess return (pooled, n rows):")
for a,s,k,n in out[:15]: print(f"  {k:38s} IC={s:+.3f} n={n}")
print("\nscore IC:", spearman([(s,b) for _,s,_,b in [(0,r[1],0,r[3]) for r in rows] if s is not None]))
