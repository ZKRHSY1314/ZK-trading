# -*- coding: utf-8 -*-
"""Part 2: matured samples, counterfactual, and the traps the claim might have hit."""
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
DB = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
c.row_factory = sqlite3.Row


def show(t, sql, params=()):
    print(f"\n----- {t}")
    rows = c.execute(sql, params).fetchall()
    if not rows:
        print("  (0 rows)")
        return rows
    print("  " + " | ".join(rows[0].keys()))
    for r in rows[:80]:
        print("  " + " | ".join("NULL" if v is None else str(v) for v in tuple(r)))
    if len(rows) > 80:
        print(f"  ... {len(rows)-80} more")
    return rows


c.execute("""CREATE TEMP TABLE shadow_days AS
             SELECT scope, data_version, decision_id, claimed_at,
                    candidate_count, recorded_count, 'legacy_unknown' AS run_kind
             FROM forecast_decision_days""")

REQ_LIST, REQ_N = "1, 3, 5, 10, 20", 5


def policy(rk):
    return f"""
shape AS (SELECT scope, data_version, decision_id, MIN(decision_cutoff) AS snapshot_cutoff,
       COUNT(DISTINCT subject) AS subj_n, COUNT(DISTINCT horizon_days) AS hz_n,
       COUNT(DISTINCT CASE WHEN horizon_days IN ({REQ_LIST}) THEN horizon_days END) AS req_hz_n,
       COUNT(*) AS row_n FROM forecast_decisions GROUP BY scope, data_version, decision_id),
vintage AS (SELECT scope, data_version, MAX(subj_n) AS max_subj, MAX(hz_n) AS max_hz
            FROM shape GROUP BY scope, data_version),
guarded AS (SELECT scope, data_version FROM shadow_days),
conf AS (SELECT s.scope, s.data_version, s.decision_id, s.snapshot_cutoff, 'confirmed' AS selection_kind
    FROM shape s JOIN shadow_days g ON g.scope=s.scope AND g.data_version=s.data_version
                                   AND g.decision_id=s.decision_id
    WHERE g.recorded_count>0 AND {rk} AND s.subj_n=g.candidate_count AND s.row_n=g.recorded_count
      AND s.row_n=s.subj_n*s.hz_n AND (s.scope<>'stock' OR s.req_hz_n={REQ_N})),
inf AS (SELECT s.scope, s.data_version, s.decision_id, s.snapshot_cutoff, 'inferred' AS selection_kind
    FROM shape s JOIN vintage v ON v.scope=s.scope AND v.data_version=s.data_version
    LEFT JOIN guarded g ON g.scope=s.scope AND g.data_version=s.data_version
    WHERE g.scope IS NULL AND s.subj_n=v.max_subj AND s.hz_n=v.max_hz AND s.row_n=s.subj_n*s.hz_n),
elig AS (SELECT * FROM conf UNION ALL SELECT * FROM inf),
ranked AS (SELECT scope, data_version, decision_id, selection_kind,
       ROW_NUMBER() OVER (PARTITION BY scope, data_version
                          ORDER BY snapshot_cutoff ASC, decision_id ASC) AS rk FROM elig),
canon AS (SELECT scope, data_version, decision_id, selection_kind FROM ranked WHERE rk=1)"""


AS_IS = policy("g.run_kind='scheduled'")
COUNTER = policy("1=1")

print("=" * 78)
print("F. TRAP CHECKS before trusting any matured-sample number")

show("F1 is (decision_id,scope,subject,horizon_days) UNIQUE in forecast_outcomes? "
     "(if not, the LEFT JOIN fans out and inflates 'matured')", """
SELECT COUNT(*) AS dup_keys, COALESCE(SUM(n),0) AS rows_in_dup_keys, COALESCE(MAX(n),0) AS worst_fanout
FROM (SELECT decision_id, scope, subject, horizon_days, COUNT(*) AS n
      FROM forecast_outcomes GROUP BY 1,2,3,4 HAVING COUNT(*)>1)""")

show("F2 outcomes denominator: 18682 total, split by scope / labelled-ness", """
SELECT scope, COUNT(*) AS outcome_rows,
       COUNT(DISTINCT decision_id) AS decision_ids,
       COUNT(DISTINCT subject) AS subjects,
       SUM(continuous_return IS NOT NULL) AS has_continuous_return,
       SUM(benchmark_neutral_return IS NOT NULL) AS has_bench_neutral,
       MIN(observed_at) AS min_observed, MAX(observed_at) AS max_observed
FROM forecast_outcomes GROUP BY scope""")

show("F3 do ANY outcomes exist for the guarded vintage stock/2026-09-03?", """
SELECT COUNT(*) AS outcome_rows_for_that_vintage
FROM forecast_outcomes o
WHERE o.decision_id IN (SELECT DISTINCT decision_id FROM forecast_decisions
                        WHERE scope='stock' AND data_version='2026-09-03')""")

show("F4 latest observed_at vs the vintage cutoff (are 2026-09-03 forecasts even mature yet?)", """
SELECT (SELECT MAX(observed_at) FROM forecast_outcomes) AS max_outcome_observed_at,
       (SELECT MAX(decision_cutoff) FROM forecast_decisions
        WHERE scope='stock' AND data_version='2026-09-03') AS vintage_cutoff""")

show("F5 index-vs-stock: any stock-scope subject that is an index code?", """
SELECT SUM(subject LIKE 'sh000%' OR subject LIKE 'sz399%' OR subject LIKE '000300%'
           OR subject LIKE '399%' OR upper(subject) LIKE '%INDEX%') AS index_like_rows,
       COUNT(DISTINCT subject) AS distinct_subjects
FROM forecast_decisions WHERE scope='stock'""")

show("F6 sample of stock subjects", """
SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock' ORDER BY subject LIMIT 12""")

show("F7 sector data_version key shape (is the 'vintage' a date or a wall-clock timestamp?)", """
SELECT scope, length(data_version) AS dv_len, COUNT(*) AS rows_,
       COUNT(DISTINCT data_version) AS distinct_vintages,
       COUNT(DISTINCT decision_id) AS distinct_decisions,
       MIN(data_version) AS example
FROM forecast_decisions GROUP BY scope, length(data_version)""")

print("\n" + "=" * 78)
print("G. AS-MIGRATED: admissible evidence under selection_kind='confirmed'")
print("   (service semantics: review_only=1, cutoff/available_at <= as_of,")
print("    observed_at <= as_of; fold = decision with >=1 matured row)")
AS_OF = "2026-09-05T00:00:00Z"

EVID = """
SELECT d.scope, d.horizon_days,
       COUNT(DISTINCT d.decision_id) AS snapshots,
       COUNT(*) AS decision_rows,
       COUNT(DISTINCT d.subject) AS distinct_subjects,
       SUM(CASE WHEN o.id IS NULL THEN 0 ELSE 1 END) AS matured_rows,
       COUNT(DISTINCT CASE WHEN o.id IS NOT NULL THEN d.decision_id END) AS folds_with_matured,
       SUM(CASE WHEN o.continuous_return IS NOT NULL THEN 1 ELSE 0 END) AS labelled_rows
FROM forecast_decisions d
JOIN canon cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope
             AND cs.data_version=d.data_version
LEFT JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope
                             AND o.subject=d.subject AND o.horizon_days=d.horizon_days
                             AND o.observed_at <= ?
WHERE cs.selection_kind='confirmed'
  AND d.review_only=1 AND d.decision_cutoff <= ? AND d.available_at <= ?
GROUP BY d.scope, d.horizon_days ORDER BY d.scope, d.horizon_days"""

EVID_ANY = EVID.replace("WHERE cs.selection_kind='confirmed'", "WHERE 1=1")
show("G1 CONFIRMED evidence, as migrated", f"WITH {AS_IS} {EVID}", (AS_OF, AS_OF, AS_OF))
show("G2 same, with NO confirmed filter (include_inferred=True) - the exploratory pool",
     f"WITH {AS_IS} {EVID_ANY}", (AS_OF, AS_OF, AS_OF))

print("\n" + "=" * 78)
print("H. COUNTERFACTUAL: the one claim had been recorded run_kind='scheduled'")
show("H1 canonical totals in the counterfactual",
     f"WITH {COUNTER} SELECT COUNT(*) AS canonical, SUM(selection_kind='confirmed') AS confirmed, "
     "SUM(selection_kind='inferred') AS inferred FROM canon")
show("H2 which snapshot wins the guarded vintage in the counterfactual",
     f"WITH {COUNTER} SELECT * FROM canon WHERE scope='stock' AND data_version='2026-09-03'")
show("H3 CONFIRMED evidence in the counterfactual", f"WITH {COUNTER} {EVID}", (AS_OF, AS_OF, AS_OF))
show("H4 counterfactual gate arithmetic vs evaluate() defaults (min_samples=20, min_folds=3)",
     f"""WITH {COUNTER},
ev AS ({EVID})
SELECT scope, horizon_days, folds_with_matured AS fold_count, matured_rows AS sample_count,
       CASE WHEN matured_rows < 20 THEN 'sample_count_below_20' ELSE 'ok' END AS gate_samples,
       CASE WHEN folds_with_matured < 3 THEN 'fold_count_below_3' ELSE 'ok' END AS gate_folds
FROM ev""", (AS_OF, AS_OF, AS_OF))

print("\n" + "=" * 78)
print("I. SANITY: how much matured evidence exists ANYWHERE, ignoring canonical entirely")
show("I1 all decision rows joined to outcomes, no canonical filter", """
SELECT d.scope, COUNT(*) AS decision_rows,
       SUM(CASE WHEN o.id IS NULL THEN 0 ELSE 1 END) AS matured_rows,
       COUNT(DISTINCT CASE WHEN o.id IS NOT NULL THEN d.decision_id END) AS decisions_with_matured
FROM forecast_decisions d
LEFT JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope
                             AND o.subject=d.subject AND o.horizon_days=d.horizon_days
GROUP BY d.scope""")
