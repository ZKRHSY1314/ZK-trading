"""READ-ONLY: what evidence survives under confirmed-canonical + official provenance,
and the exact size of the fold/sample inflation in the 746 legacy evaluations."""
import sqlite3
import sys

sys.path.insert(0, r"D:\codex-A股交易\backend")
from app.forecasting.canonical import canonical_snapshot_cte  # noqa: E402

DB = r"D:\codex-A股交易\trading_local.sqlite3"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
CTE = canonical_snapshot_cte()

con.execute(
    """
    CREATE TEMP TABLE forecast_decision_days AS
    SELECT scope, data_version, decision_id, claimed_at, candidate_count, recorded_count,
           'legacy_unknown' AS run_kind
    FROM main.forecast_decision_days
    """
)


def show(title, sql, params=(), echo_sql=True):
    print("\n" + "#" * 100)
    print("## " + title)
    if echo_sql:
        print("SQL: " + " ".join(sql.split()))
    else:
        print("SQL: <canonical CTE from app.forecasting.canonical> + " + " ".join(sql.split()[-40:]))
    rows = con.execute(sql, params).fetchall()
    if not rows:
        print("   (no rows)")
        return rows
    print("   " + " | ".join(str(k) for k in rows[0].keys()))
    for r in rows:
        print("   " + " | ".join(str(r[k]) for k in r.keys()))
    return rows


REMAIN = """
SELECT d.scope, d.horizon_days, cs.selection_kind,
       COUNT(DISTINCT d.decision_id) AS folds,
       COUNT(*) AS decision_rows,
       SUM(CASE WHEN o.id IS NULL THEN 0 ELSE 1 END) AS matured_samples
FROM forecast_decisions d
JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
LEFT JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope
                             AND o.subject=d.subject AND o.horizon_days=d.horizon_days
GROUP BY d.scope, d.horizon_days, cs.selection_kind
ORDER BY d.scope, d.horizon_days, cs.selection_kind
"""

print("=" * 100)
print("A. run_kind='legacy_unknown' (the state the pending migration will produce)")
print("=" * 100)
show("A1 folds and matured samples by scope/horizon/selection_kind",
     f"WITH {CTE} {REMAIN}", echo_sql=False)
show("A2 CONFIRMED-only evidence",
     f"WITH {CTE} SELECT d.scope, d.horizon_days, COUNT(DISTINCT d.decision_id) AS folds, "
     "COUNT(*) AS decision_rows, SUM(CASE WHEN o.id IS NULL THEN 0 ELSE 1 END) AS matured_samples "
     "FROM forecast_decisions d JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope "
     "AND cs.data_version=d.data_version LEFT JOIN forecast_outcomes o ON o.decision_id=d.decision_id "
     "AND o.scope=d.scope AND o.subject=d.subject AND o.horizon_days=d.horizon_days "
     "WHERE cs.selection_kind='confirmed' GROUP BY d.scope, d.horizon_days",
     echo_sql=False)

print("\n" + "=" * 100)
print("B. counterfactual run_kind='scheduled' (the claim treated as an official run)")
print("=" * 100)
con.execute("UPDATE temp.forecast_decision_days SET run_kind='scheduled'")
show("B1 CONFIRMED-only evidence under the counterfactual",
     f"WITH {CTE} SELECT d.scope, d.horizon_days, COUNT(DISTINCT d.decision_id) AS folds, "
     "COUNT(*) AS decision_rows, SUM(CASE WHEN o.id IS NULL THEN 0 ELSE 1 END) AS matured_samples "
     "FROM forecast_decisions d JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope "
     "AND cs.data_version=d.data_version LEFT JOIN forecast_outcomes o ON o.decision_id=d.decision_id "
     "AND o.scope=d.scope AND o.subject=d.subject AND o.horizon_days=d.horizon_days "
     "WHERE cs.selection_kind='confirmed' GROUP BY d.scope, d.horizon_days",
     echo_sql=False)
print("\n   gates: min_samples=20, min_folds=3 (ForecastFeedbackService.evaluate defaults)")
con.execute("UPDATE temp.forecast_decision_days SET run_kind='legacy_unknown'")

print("\n" + "=" * 100)
print("C. inflation size of the 746 legacy evaluations")
print("=" * 100)
show(
    "C1 duplication ratio in forecast_decisions",
    "SELECT COUNT(*) AS rows, COUNT(DISTINCT decision_id) AS snapshots, "
    "ROUND(1.0*COUNT(*)/COUNT(DISTINCT decision_id),2) AS rows_per_snapshot, "
    "COUNT(DISTINCT scope || '~' || data_version) AS vintages, "
    "ROUND(1.0*COUNT(DISTINCT decision_id)/COUNT(DISTINCT scope || '~' || data_version),2) AS snapshots_per_vintage "
    "FROM forecast_decisions",
)
show(
    "C2 the single worst vintage",
    "SELECT scope, data_version, COUNT(DISTINCT decision_id) AS snapshots, COUNT(*) AS rows, "
    "COUNT(DISTINCT subject) AS distinct_subjects, MIN(decision_cutoff) AS first_cutoff, "
    "MAX(decision_cutoff) AS last_cutoff, "
    "ROUND((julianday(replace(MAX(decision_cutoff),'Z','')) - julianday(replace(MIN(decision_cutoff),'Z','')))*24,2) AS hours_spanned "
    "FROM forecast_decisions GROUP BY scope, data_version ORDER BY snapshots DESC LIMIT 3",
)
show(
    "C3 the most-inflated stored evaluation vs the canonical truth for the same as_of",
    f"WITH {CTE} SELECT e.as_of, e.scope, e.horizon_days, e.status, e.sample_count AS stored_sample, "
    "e.fold_count AS stored_fold, e.spearman_rank_ic, "
    "(SELECT COUNT(DISTINCT d.decision_id) FROM forecast_decisions d JOIN canonical c2 "
    "  ON c2.decision_id=d.decision_id AND c2.scope=d.scope AND c2.data_version=d.data_version "
    "  WHERE d.scope=e.scope AND d.horizon_days=e.horizon_days AND d.decision_cutoff<=e.as_of) AS canonical_folds_any_kind, "
    "(SELECT COUNT(DISTINCT d.decision_id) FROM forecast_decisions d JOIN canonical c2 "
    "  ON c2.decision_id=d.decision_id AND c2.scope=d.scope AND c2.data_version=d.data_version "
    "  WHERE c2.selection_kind='confirmed' AND d.scope=e.scope AND d.horizon_days=e.horizon_days "
    "  AND d.decision_cutoff<=e.as_of) AS canonical_folds_confirmed, "
    "(SELECT COUNT(*) FROM forecast_decisions d JOIN canonical c2 "
    "  ON c2.decision_id=d.decision_id AND c2.scope=d.scope AND c2.data_version=d.data_version "
    "  JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject "
    "  AND o.horizon_days=d.horizon_days AND o.observed_at<=e.as_of "
    "  WHERE d.scope=e.scope AND d.horizon_days=e.horizon_days AND d.decision_cutoff<=e.as_of) AS canonical_samples_any_kind "
    "FROM forecast_evaluations e WHERE e.status='ready' "
    "GROUP BY e.scope, e.horizon_days, e.sample_count, e.fold_count "
    "ORDER BY e.scope, e.horizon_days, stored_fold DESC",
    echo_sql=False,
)
show(
    "C4 'ready' evaluations that would not clear min_folds=3 on canonical CONFIRMED evidence",
    "SELECT COUNT(*) AS ready_rows_total FROM forecast_evaluations WHERE status='ready'",
)

print("\n" + "=" * 100)
print("D. outcomes by canonical membership and horizon")
print("=" * 100)
show(
    "D1 outcome rows by scope/horizon split canonical vs excluded",
    f"WITH {CTE} SELECT o.scope, o.horizon_days, "
    "SUM(CASE WHEN cs.decision_id IS NULL THEN 0 ELSE 1 END) AS canonical_outcomes, "
    "SUM(CASE WHEN cs.decision_id IS NULL THEN 1 ELSE 0 END) AS non_canonical_outcomes, "
    "COUNT(*) AS total FROM forecast_outcomes o "
    "JOIN forecast_decisions d ON d.decision_id=o.decision_id AND d.scope=o.scope AND d.subject=o.subject "
    "AND d.horizon_days=o.horizon_days "
    "LEFT JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version "
    "GROUP BY o.scope, o.horizon_days ORDER BY o.scope, o.horizon_days",
    echo_sql=False,
)
show(
    "D2 orphan check: outcome rows with no matching decision row",
    "SELECT COUNT(*) AS orphan_outcomes FROM forecast_outcomes o LEFT JOIN forecast_decisions d "
    "ON d.decision_id=o.decision_id AND d.scope=o.scope AND d.subject=o.subject "
    "AND d.horizon_days=o.horizon_days WHERE d.id IS NULL",
)
show(
    "D3 outcome data_version format (what it actually records)",
    "SELECT data_version, COUNT(*) AS rows FROM forecast_outcomes GROUP BY data_version "
    "ORDER BY rows DESC LIMIT 5",
)

con.close()
print("\nDONE - read-only.")
