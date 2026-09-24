import sqlite3, sys, statistics
sys.path.insert(0, r"D:/codex-A股交易/backend")
from app.forecasting.canonical import canonical_snapshot_cte
con = sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro", uri=True); con.row_factory=sqlite3.Row
cur=con.cursor()
def q(s,a=()): return cur.execute(s,a).fetchall()
CTE = canonical_snapshot_cte().replace("      AND c.run_kind = 'scheduled'\n","")

print("### subjects: any index masquerading as a stock?")
for r in q("SELECT scope, COUNT(DISTINCT subject) n FROM forecast_decisions GROUP BY scope"): print(dict(r))
print("sample stock subjects:", [r["subject"] for r in q("SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock' ORDER BY subject LIMIT 8")])
print("stock subjects NOT 6-digit:", [r["subject"] for r in q("SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock' AND subject NOT GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'")])

sql=f"""WITH {CTE},
canon AS (SELECT d.scope,d.horizon_days,e.as_of,
   COUNT(DISTINCT CASE WHEN o.id IS NOT NULL THEN d.decision_id END) cf,
   SUM(CASE WHEN o.id IS NOT NULL THEN 1 ELSE 0 END) cs
 FROM forecast_evaluations e
 JOIN forecast_decisions d ON d.scope=e.scope AND d.horizon_days=e.horizon_days AND d.review_only=1
   AND d.decision_cutoff<=e.as_of AND d.available_at<=e.as_of
 JOIN canonical k ON k.decision_id=d.decision_id AND k.scope=d.scope AND k.data_version=d.data_version
 LEFT JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject
   AND o.horizon_days=d.horizon_days AND o.observed_at<=e.as_of
 WHERE e.status='ready' GROUP BY d.scope,d.horizon_days,e.as_of)
SELECT e.scope,e.horizon_days,e.as_of,e.sample_count sc,e.fold_count fc,c.cs,c.cf
FROM forecast_evaluations e JOIN canon c ON c.scope=e.scope AND c.horizon_days=e.horizon_days AND c.as_of=e.as_of
WHERE e.status='ready'"""
rows=q(sql)
for scope in ("stock","sector"):
    sub=[r for r in rows if r["scope"]==scope]
    fi=[r["fc"]/r["cf"] for r in sub if r["cf"]]
    si=[r["sc"]/r["cs"] for r in sub if r["cs"]]
    print(f"\n{scope}: n={len(sub)}")
    print("  fold  inflation min=%.2f median=%.2f max=%.2f"%(min(fi),statistics.median(fi),max(fi)))
    print("  sample inflation min=%.2f median=%.2f max=%.2f"%(min(si),statistics.median(si),max(si)))
    print("  rows with fold inflation >= 2x:", sum(1 for x in fi if x>=2), "| >=10x:", sum(1 for x in fi if x>=10))
con.close()
