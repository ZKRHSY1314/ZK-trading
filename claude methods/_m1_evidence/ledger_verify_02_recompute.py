import sqlite3, sys
sys.path.insert(0, r"D:/codex-A股交易/backend")
OP = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()
def q(sql, args=()):
    return cur.execute(sql, args).fetchall()

AS_OF = '2026-09-04T04:43:08.314189Z'

print("### 1. Does the SHIPPED canonical_snapshot_cte() run against this DB?")
from app.forecasting.canonical import canonical_snapshot_cte, CANONICAL_POLICY_VERSION
CTE = canonical_snapshot_cte()
print("policy:", CANONICAL_POLICY_VERSION, "| references run_kind:", "run_kind" in CTE)
try:
    rows = q(f"WITH {CTE} SELECT scope, data_version, decision_id, selection_kind FROM canonical ORDER BY scope, data_version")
    print("RAN OK ->", len(rows), "canonical snapshots")
    for r in rows: print("   ", dict(r))
except sqlite3.Error as e:
    print("!! SQLITE ERROR:", type(e).__name__, e)

print()
print("### 2. Same CTE with run_kind clause REMOVED (schema has no run_kind)")
CTE2 = CTE.replace("AND c.run_kind = 'scheduled'\n", "").replace("AND c.run_kind = 'scheduled'", "")
print("still references run_kind:", "run_kind" in CTE2)
rows2 = q(f"WITH {CTE2} SELECT scope, data_version, decision_id, selection_kind FROM canonical ORDER BY scope, data_version")
print("canonical snapshots:", len(rows2))
kinds = {}
for r in rows2:
    kinds[r["selection_kind"]] = kinds.get(r["selection_kind"], 0) + 1
print("by kind:", kinds)
for r in rows2:
    if r["scope"] == "stock": print("   STOCK:", dict(r))

print()
print("### 3. LEGACY (no canonical join) reproduction of stored numbers, stock h=1, as_of=%s" % AS_OF)
legacy = """
SELECT COUNT(DISTINCT d.decision_id) AS folds_all_dids,
       COUNT(DISTINCT CASE WHEN o.id IS NOT NULL THEN d.decision_id END) AS folds_with_matured,
       COUNT(*) AS forecast_rows,
       SUM(CASE WHEN o.id IS NOT NULL THEN 1 ELSE 0 END) AS matured_rows
FROM forecast_decisions d
LEFT JOIN forecast_outcomes o
  ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject
 AND o.horizon_days=d.horizon_days AND o.observed_at <= ?
WHERE d.scope='stock' AND d.review_only=1 AND d.horizon_days=1
  AND d.decision_cutoff <= ? AND d.available_at <= ?
"""
print(dict(q(legacy, (AS_OF, AS_OF, AS_OF))[0]))
print("STORED in DB:", dict(q("SELECT sample_count, fold_count, coverage, status FROM forecast_evaluations WHERE evaluation_id='forecast-eval-3cdfb653978f1c8b8901afdd'")[0]))

print()
print("### 4. CANONICAL baseline (run_kind-stripped CTE), stock, per horizon, same as_of")
canon = f"""
WITH {CTE2}
SELECT d.horizon_days,
       COUNT(DISTINCT d.decision_id) AS canonical_folds,
       COUNT(DISTINCT CASE WHEN o.id IS NOT NULL THEN d.decision_id END) AS folds_with_matured,
       COUNT(*) AS forecast_rows,
       SUM(CASE WHEN o.id IS NOT NULL THEN 1 ELSE 0 END) AS matured_rows,
       GROUP_CONCAT(DISTINCT cs.selection_kind) AS kinds
FROM forecast_decisions d
JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
LEFT JOIN forecast_outcomes o
  ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject
 AND o.horizon_days=d.horizon_days AND o.observed_at <= ?
WHERE d.scope='stock' AND d.review_only=1 AND d.decision_cutoff <= ?
  AND d.available_at <= ?
GROUP BY d.horizon_days ORDER BY d.horizon_days
"""
for r in q(canon, (AS_OF, AS_OF, AS_OF)): print(dict(r))

print()
print("### 5. CONFIRMED-only canonical baseline, stock")
canon_c = canon.replace("WHERE d.scope='stock'", "WHERE cs.selection_kind='confirmed' AND d.scope='stock'")
res = q(canon_c, (AS_OF, AS_OF, AS_OF))
print("rows:", len(res))
for r in res: print(dict(r))

print()
print("### 6. Is the guard row's snapshot shape-eligible? (why confirmed may be 0)")
for r in q("""
SELECT s.scope, s.data_version, s.decision_id, s.subject_count, s.horizon_count,
       s.row_count, c.candidate_count, c.recorded_count,
       (s.subject_count = c.candidate_count) AS subj_ok,
       (s.row_count = c.recorded_count) AS rows_ok,
       (s.row_count = s.subject_count*s.horizon_count) AS rect_ok
FROM (SELECT scope,data_version,decision_id,COUNT(DISTINCT subject) subject_count,
             COUNT(DISTINCT horizon_days) horizon_count, COUNT(*) row_count
      FROM forecast_decisions GROUP BY scope,data_version,decision_id) s
JOIN forecast_decision_days c ON c.scope=s.scope AND c.data_version=s.data_version
ORDER BY s.decision_id"""):
    print(dict(r))
con.close()
