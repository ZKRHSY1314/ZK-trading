import sqlite3, statistics
con=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True);cur=con.cursor()
rows=cur.execute("""
select d.rank, o.horizon_days, o.continuous_return, o.benchmark_neutral_return
from forecast_outcomes o join forecast_decisions d
  on d.decision_id=o.decision_id and d.subject=o.subject and d.horizon_days=o.horizon_days
where o.scope='stock' and o.benchmark_neutral_return is not null
""").fetchall()
print("joined stock outcomes:", len(rows))
from collections import defaultdict
b=defaultdict(list)
for rank,h,cr,bn in rows:
    bucket = "top5" if rank<=5 else ("6-10" if rank<=10 else ("11-20" if rank<=20 else "21+"))
    b[(h,bucket)].append(bn)
for k in sorted(b):
    v=b[k]
    print(k, "n=%d"%len(v), "mean_excess=%.4f%%"%(100*statistics.fmean(v)), "hit>0=%.1f%%"%(100*sum(1 for x in v if x>0)/len(v)))
allv=[bn for _,_,_,bn in rows]
print("ALL n=%d mean_excess=%.4f%% hit=%.1f%%"%(len(allv),100*statistics.fmean(allv),100*sum(1 for x in allv if x>0)/len(allv)))
