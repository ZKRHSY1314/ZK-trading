import sqlite3, sys, statistics
sys.path.insert(0, r"D:/codex-A股交易/backend")
from app.forecasting.canonical import canonical_snapshot_cte
OP = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{OP}?mode=ro", uri=True); con.row_factory = sqlite3.Row
cur = con.cursor()
def q(s,a=()): return cur.execute(s,a).fetchall()
CTE = canonical_snapshot_cte().replace("      AND c.run_kind = 'scheduled'\n","")
assert "run_kind" not in CTE

print("### 0. scope-vintages with NO canonical snapshot")
for r in q(f"""WITH {CTE}
 SELECT d.scope, d.data_version, COUNT(DISTINCT d.decision_id) snaps, COUNT(*) rows
 FROM forecast_decisions d
 LEFT JOIN canonical c ON c.scope=d.scope AND c.data_version=d.data_version
 WHERE c.scope IS NULL GROUP BY d.scope,d.data_version"""):
    print(dict(r))

print()
print("### 1. Inflation for EVERY status='ready' evaluation (113 rows), my own recomputation")
sql = f"""
WITH {CTE},
legacy AS (
  SELECT d.scope, d.horizon_days, e.as_of,
         COUNT(DISTINCT CASE WHEN o.id IS NOT NULL THEN d.decision_id END) AS legacy_folds,
         SUM(CASE WHEN o.id IS NOT NULL THEN 1 ELSE 0 END) AS legacy_samples
  FROM forecast_evaluations e
  JOIN forecast_decisions d
    ON d.scope=e.scope AND d.horizon_days=e.horizon_days
   AND d.review_only=1 AND d.decision_cutoff<=e.as_of AND d.available_at<=e.as_of
  LEFT JOIN forecast_outcomes o
    ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject
   AND o.horizon_days=d.horizon_days AND o.observed_at<=e.as_of
  WHERE e.status='ready'
  GROUP BY d.scope, d.horizon_days, e.as_of
),
canon AS (
  SELECT d.scope, d.horizon_days, e.as_of,
         COUNT(DISTINCT CASE WHEN o.id IS NOT NULL THEN d.decision_id END) AS canon_folds,
         SUM(CASE WHEN o.id IS NOT NULL THEN 1 ELSE 0 END) AS canon_samples,
         COUNT(DISTINCT CASE WHEN o.id IS NOT NULL AND cs.selection_kind='confirmed'
                             THEN d.decision_id END) AS confirmed_folds,
         SUM(CASE WHEN o.id IS NOT NULL AND cs.selection_kind='confirmed' THEN 1 ELSE 0 END)
             AS confirmed_samples
  FROM forecast_evaluations e
  JOIN forecast_decisions d
    ON d.scope=e.scope AND d.horizon_days=e.horizon_days
   AND d.review_only=1 AND d.decision_cutoff<=e.as_of AND d.available_at<=e.as_of
  JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
  LEFT JOIN forecast_outcomes o
    ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject
   AND o.horizon_days=d.horizon_days AND o.observed_at<=e.as_of
  WHERE e.status='ready'
  GROUP BY d.scope, d.horizon_days, e.as_of
)
SELECT e.evaluation_id, e.as_of, e.scope, e.horizon_days, e.status,
       e.sample_count AS stored_sample, e.fold_count AS stored_fold,
       l.legacy_samples, l.legacy_folds,
       c.canon_samples, c.canon_folds, c.confirmed_samples, c.confirmed_folds
FROM forecast_evaluations e
LEFT JOIN legacy l ON l.scope=e.scope AND l.horizon_days=e.horizon_days AND l.as_of=e.as_of
LEFT JOIN canon  c ON c.scope=e.scope AND c.horizon_days=e.horizon_days AND c.as_of=e.as_of
WHERE e.status='ready'
ORDER BY e.scope, e.horizon_days, e.as_of
"""
rows = q(sql)
print("ready rows measured:", len(rows))
exact_legacy = sum(1 for r in rows if r["stored_sample"]==r["legacy_samples"] and r["stored_fold"]==r["legacy_folds"])
print("rows where STORED == my un-deduplicated (legacy) recomputation, both fields:", exact_legacy, "/", len(rows))
mis = [dict(r) for r in rows if not (r["stored_sample"]==r["legacy_samples"] and r["stored_fold"]==r["legacy_folds"])]
print("mismatches:", len(mis))
for m in mis[:10]: print("   ", m)

fold_infl, samp_infl = [], []
zero_conf = 0
for r in rows:
    if r["canon_folds"]: fold_infl.append(r["stored_fold"]/r["canon_folds"])
    if r["canon_samples"]: samp_infl.append(r["stored_sample"]/r["canon_samples"])
    if not r["confirmed_samples"]: zero_conf += 1
print()
print("fold inflation  (stored_fold / canonical_folds_with_matured): min=%.2f median=%.2f max=%.2f  n=%d"
      % (min(fold_infl), statistics.median(fold_infl), max(fold_infl), len(fold_infl)))
print("sample inflation(stored_sample/ canonical_samples_matured)  : min=%.2f median=%.2f max=%.2f  n=%d"
      % (min(samp_infl), statistics.median(samp_infl), max(samp_infl), len(samp_infl)))
print("ready rows with ZERO confirmed matured samples:", zero_conf, "/", len(rows))

print()
print("### 2. the extreme rows")
worst = sorted(rows, key=lambda r: -(r["stored_fold"]/r["canon_folds"] if r["canon_folds"] else 0))[:6]
for r in worst:
    print("  %-6s h=%-3d as_of=%s stored %d/%d  canonical %s/%s  confirmed %s/%s  x%.2f"
          % (r["scope"], r["horizon_days"], r["as_of"], r["stored_sample"], r["stored_fold"],
             r["canon_samples"], r["canon_folds"], r["confirmed_samples"], r["confirmed_folds"],
             r["stored_fold"]/r["canon_folds"]))
print()
print("### 3. sector 'ready' rows in detail")
for r in rows:
    if r["scope"]=="sector":
        print("  h=%-3d as_of=%s stored %d/%d canonical %s/%s confirmed %s/%s"
              % (r["horizon_days"], r["as_of"], r["stored_sample"], r["stored_fold"],
                 r["canon_samples"], r["canon_folds"], r["confirmed_samples"], r["confirmed_folds"]))

print()
print("### 4. worst vintage timing check (stock/2026-07-15)")
r = q("""SELECT COUNT(DISTINCT decision_id) snaps, COUNT(*) rows,
                COUNT(DISTINCT subject) distinct_subjects,
                MIN(decision_cutoff) a, MAX(decision_cutoff) b,
                (julianday(MAX(decision_cutoff))-julianday(MIN(decision_cutoff)))*24.0 hours
         FROM forecast_decisions WHERE scope='stock' AND data_version='2026-07-15'""")[0]
print(dict(r))
print()
print("### 5. framing check: snapshots-per-vintage is NOT uniform")
for r in q("""SELECT scope, COUNT(DISTINCT decision_id)*1.0/COUNT(DISTINCT data_version) snaps_per_vintage,
                     COUNT(DISTINCT decision_id) dids, COUNT(DISTINCT data_version) vintages
              FROM forecast_decisions GROUP BY scope"""):
    print(dict(r))
con.close()
