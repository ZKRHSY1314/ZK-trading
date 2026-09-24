"""READ-ONLY audit of forecast_decisions / forecast_outcomes / forecast_evaluations.

Opens production strictly read-only. No writes, no migrations, no service
constructors.
"""
import sqlite3
import sys
import json

DB = r"D:\codex-A股交易\trading_local.sqlite3"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row


def q(sql, params=()):
    return con.execute(sql, params).fetchall()


def show(title, sql, params=(), limit=None):
    print("\n" + "#" * 100)
    print("## " + title)
    print("SQL: " + " ".join(sql.split()))
    rows = q(sql, params)
    if limit:
        rows = rows[:limit]
    if not rows:
        print("   (no rows)")
        return rows
    keys = rows[0].keys()
    print("   " + " | ".join(str(k) for k in keys))
    for r in rows:
        print("   " + " | ".join(str(r[k]) for k in keys))
    return rows


print("READ-ONLY probe:")
try:
    con.execute("CREATE TABLE _probe_should_fail(x)")
    print("   !!! WRITE SUCCEEDED - NOT READ ONLY !!!")
except sqlite3.OperationalError as e:
    print("   confirmed read-only: " + str(e))

show(
    "D1 forecast_decisions totals",
    "SELECT COUNT(*) AS rows, COUNT(DISTINCT decision_id) AS decision_ids, "
    "COUNT(DISTINCT data_version) AS data_versions, "
    "COUNT(DISTINCT scope || '~' || data_version) AS scope_vintages, "
    "COUNT(DISTINCT subject) AS subjects, MIN(decision_cutoff) AS min_cutoff, "
    "MAX(decision_cutoff) AS max_cutoff, MIN(available_at) AS min_avail, "
    "MAX(available_at) AS max_avail, MIN(created_at) AS min_created, "
    "MAX(created_at) AS max_created FROM forecast_decisions",
)

show(
    "D2 forecast_decisions by scope",
    "SELECT scope, COUNT(*) AS rows, COUNT(DISTINCT decision_id) AS decision_ids, "
    "COUNT(DISTINCT data_version) AS data_versions, COUNT(DISTINCT subject) AS subjects, "
    "MIN(decision_cutoff) AS min_cutoff, MAX(decision_cutoff) AS max_cutoff "
    "FROM forecast_decisions GROUP BY scope ORDER BY scope",
)

show(
    "D3 forecast_decisions by horizon",
    "SELECT horizon_days, COUNT(*) AS rows, COUNT(DISTINCT decision_id) AS decision_ids "
    "FROM forecast_decisions GROUP BY horizon_days ORDER BY horizon_days",
)

show(
    "D4 forecast_decisions by scope x horizon",
    "SELECT scope, horizon_days, COUNT(*) AS rows, COUNT(DISTINCT decision_id) AS decision_ids "
    "FROM forecast_decisions GROUP BY scope, horizon_days ORDER BY scope, horizon_days",
)

show(
    "D5 status / model_version / prompt_version distribution",
    "SELECT status, model_version, prompt_version, COUNT(*) AS rows, "
    "COUNT(DISTINCT decision_id) AS ids FROM forecast_decisions "
    "GROUP BY status, model_version, prompt_version ORDER BY rows DESC",
)

show(
    "D6 distinct decision_cutoff dates and instants",
    "SELECT COUNT(DISTINCT substr(decision_cutoff,1,10)) AS distinct_cutoff_dates, "
    "COUNT(DISTINCT decision_cutoff) AS distinct_cutoff_instants FROM forecast_decisions",
)

show(
    "D6b distinct decision_cutoff dates by scope",
    "SELECT scope, COUNT(DISTINCT substr(decision_cutoff,1,10)) AS distinct_cutoff_dates, "
    "COUNT(DISTINCT decision_cutoff) AS distinct_cutoff_instants, "
    "COUNT(DISTINCT data_version) AS data_versions "
    "FROM forecast_decisions GROUP BY scope",
)

show(
    "D7 duplication per (scope,data_version): worst 30 vintages",
    "SELECT scope, data_version, COUNT(DISTINCT decision_id) AS snapshots, COUNT(*) AS rows, "
    "COUNT(DISTINCT subject) AS subjects, COUNT(DISTINCT horizon_days) AS horizons, "
    "MIN(decision_cutoff) AS first_cutoff, MAX(decision_cutoff) AS last_cutoff "
    "FROM forecast_decisions GROUP BY scope, data_version "
    "ORDER BY snapshots DESC, rows DESC LIMIT 30",
)

show(
    "D8 vintage duplication summary",
    "SELECT scope, COUNT(*) AS vintages, SUM(snapshots) AS total_snapshots, "
    "SUM(rows) AS total_rows, MAX(snapshots) AS max_snapshots_one_vintage, "
    "MIN(snapshots) AS min_snapshots_one_vintage, "
    "ROUND(AVG(snapshots),2) AS avg_snapshots_per_vintage FROM "
    "(SELECT scope, data_version, COUNT(DISTINCT decision_id) AS snapshots, COUNT(*) AS rows "
    "FROM forecast_decisions GROUP BY scope, data_version) GROUP BY scope",
)

show(
    "D9 subjects-per-snapshot distribution (snapshot shape)",
    "SELECT scope, subject_count, horizon_count, COUNT(*) AS snapshot_count, "
    "SUM(row_count) AS rows FROM (SELECT scope, decision_id, "
    "COUNT(DISTINCT subject) AS subject_count, COUNT(DISTINCT horizon_days) AS horizon_count, "
    "COUNT(*) AS row_count FROM forecast_decisions GROUP BY scope, decision_id) "
    "GROUP BY scope, subject_count, horizon_count ORDER BY scope, subject_count DESC",
)

show(
    "D10 non-rectangular snapshots (row_count != subjects*horizons)",
    "SELECT scope, COUNT(*) AS snapshots FROM (SELECT scope, decision_id, "
    "COUNT(DISTINCT subject) AS s, COUNT(DISTINCT horizon_days) AS h, COUNT(*) AS r "
    "FROM forecast_decisions GROUP BY scope, decision_id) WHERE r <> s*h GROUP BY scope",
)

show("D11 the guard records in forecast_decision_days", "SELECT * FROM forecast_decision_days")

show(
    "D12 does the guarded vintage line up with forecast_decisions",
    "SELECT c.scope, c.data_version, c.decision_id AS claimed_id, c.candidate_count, "
    "c.recorded_count, "
    "(SELECT COUNT(*) FROM forecast_decisions d WHERE d.scope=c.scope AND d.data_version=c.data_version) AS vintage_rows, "
    "(SELECT COUNT(DISTINCT decision_id) FROM forecast_decisions d WHERE d.scope=c.scope AND d.data_version=c.data_version) AS vintage_snapshots, "
    "(SELECT COUNT(*) FROM forecast_decisions d WHERE d.decision_id=c.decision_id) AS claimed_snapshot_rows, "
    "(SELECT COUNT(DISTINCT subject) FROM forecast_decisions d WHERE d.decision_id=c.decision_id) AS claimed_snapshot_subjects, "
    "(SELECT COUNT(DISTINCT horizon_days) FROM forecast_decisions d WHERE d.decision_id=c.decision_id) AS claimed_snapshot_horizons "
    "FROM forecast_decision_days c",
)

show(
    "O1 forecast_outcomes totals",
    "SELECT COUNT(*) AS rows, COUNT(DISTINCT decision_id) AS decision_ids, "
    "COUNT(DISTINCT subject) AS subjects, COUNT(DISTINCT data_version) AS data_versions, "
    "MIN(observed_at) AS min_observed, MAX(observed_at) AS max_observed, "
    "MIN(created_at) AS min_created, MAX(created_at) AS max_created FROM forecast_outcomes",
)

show("O2 forecast_outcomes by status", "SELECT status, COUNT(*) AS rows FROM forecast_outcomes GROUP BY status")

show(
    "O3 forecast_outcomes by scope",
    "SELECT scope, COUNT(*) AS rows, COUNT(DISTINCT decision_id) AS decision_ids, "
    "COUNT(DISTINCT subject) AS subjects FROM forecast_outcomes GROUP BY scope",
)

show(
    "O4 forecast_outcomes by scope x horizon",
    "SELECT scope, horizon_days, COUNT(*) AS rows, COUNT(DISTINCT decision_id) AS decision_ids "
    "FROM forecast_outcomes GROUP BY scope, horizon_days ORDER BY scope, horizon_days",
)

show(
    "O5 labelled coverage: decision rows with vs without an outcome",
    "SELECT d.scope, COUNT(*) AS decision_rows, "
    "SUM(CASE WHEN o.id IS NULL THEN 0 ELSE 1 END) AS labelled_rows, "
    "SUM(CASE WHEN o.id IS NULL THEN 1 ELSE 0 END) AS unlabelled_rows "
    "FROM forecast_decisions d LEFT JOIN forecast_outcomes o "
    "ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject "
    "AND o.horizon_days=d.horizon_days GROUP BY d.scope",
)

show(
    "O6 outcome snapshots per vintage (duplication carried into labels)",
    "SELECT scope, COUNT(*) AS vintages, SUM(snapshots) AS snapshots, SUM(rows) AS rows, "
    "MAX(snapshots) AS worst FROM (SELECT d.scope AS scope, d.data_version AS data_version, "
    "COUNT(DISTINCT o.decision_id) AS snapshots, COUNT(*) AS rows FROM forecast_outcomes o "
    "JOIN forecast_decisions d ON d.decision_id=o.decision_id AND d.scope=o.scope "
    "AND d.subject=o.subject AND d.horizon_days=o.horizon_days "
    "GROUP BY d.scope, d.data_version) GROUP BY scope",
)

show(
    "O7 outcome data_version differing from decision data_version",
    "SELECT COUNT(*) AS rows_with_differing_data_version FROM forecast_outcomes o "
    "JOIN forecast_decisions d ON d.decision_id=o.decision_id AND d.scope=o.scope "
    "AND d.subject=o.subject AND d.horizon_days=o.horizon_days "
    "WHERE o.data_version <> d.data_version",
)

show(
    "O8 observed_at date span by scope",
    "SELECT scope, MIN(substr(observed_at,1,10)) AS first_observed_date, "
    "MAX(substr(observed_at,1,10)) AS last_observed_date, "
    "COUNT(DISTINCT substr(observed_at,1,10)) AS distinct_observed_dates FROM forecast_outcomes GROUP BY scope",
)

show(
    "E1 forecast_evaluations totals",
    "SELECT COUNT(*) AS rows, COUNT(DISTINCT evaluation_id) AS ids, "
    "COUNT(DISTINCT as_of) AS distinct_as_of, MIN(as_of) AS min_as_of, MAX(as_of) AS max_as_of, "
    "MIN(created_at) AS min_created, MAX(created_at) AS max_created FROM forecast_evaluations",
)

show(
    "E2 evaluations by scope x horizon x status",
    "SELECT scope, horizon_days, status, COUNT(*) AS rows, MIN(sample_count) AS min_sample, "
    "MAX(sample_count) AS max_sample, MIN(fold_count) AS min_fold, MAX(fold_count) AS max_fold "
    "FROM forecast_evaluations GROUP BY scope, horizon_days, status ORDER BY scope, horizon_days, status",
)

show(
    "E3 evaluations by status only",
    "SELECT status, COUNT(*) AS rows, COUNT(DISTINCT as_of) AS as_of_instants "
    "FROM forecast_evaluations GROUP BY status",
)

show(
    "E4 evaluations by as_of date",
    "SELECT substr(as_of,1,10) AS as_of_date, COUNT(*) AS rows, COUNT(DISTINCT as_of) AS instants, "
    "MAX(fold_count) AS max_fold, MAX(sample_count) AS max_sample FROM forecast_evaluations "
    "GROUP BY as_of_date ORDER BY as_of_date",
)

show(
    "E5 fold_count distribution",
    "SELECT fold_count, COUNT(*) AS rows, MIN(sample_count) AS min_sample, "
    "MAX(sample_count) AS max_sample FROM forecast_evaluations GROUP BY fold_count ORDER BY fold_count",
)

show(
    "E6 every evaluation row whose status is not insufficient_data",
    "SELECT evaluation_id, as_of, scope, horizon_days, status, sample_count, fold_count, "
    "coverage, precision_at_k, spearman_rank_ic, brier_score FROM forecast_evaluations "
    "WHERE status <> 'insufficient_data' ORDER BY as_of, scope, horizon_days",
)

show(
    "E7 top-25 evaluations by fold_count",
    "SELECT as_of, scope, horizon_days, status, sample_count, fold_count, coverage, spearman_rank_ic "
    "FROM forecast_evaluations ORDER BY fold_count DESC, sample_count DESC LIMIT 25",
)

show(
    "E7b sample_count distribution buckets",
    "SELECT scope, MIN(sample_count) AS min_s, MAX(sample_count) AS max_s, "
    "SUM(sample_count) AS sum_s, MIN(fold_count) AS min_f, MAX(fold_count) AS max_f, "
    "COUNT(*) AS rows FROM forecast_evaluations GROUP BY scope",
)

cols = [r["name"] for r in q("PRAGMA table_info(forecast_evaluations)")]
print("\n" + "#" * 100)
print("## E8 canonical_policy_version column in production forecast_evaluations?")
print("SQL: PRAGMA table_info(forecast_evaluations)")
print("   columns: " + str(cols))
print("   canonical_policy_version present: " + str("canonical_policy_version" in cols))
try:
    r = q("SELECT COUNT(*) AS n, COUNT(canonical_policy_version) AS non_null FROM forecast_evaluations")
    print("   " + str(dict(r[0])))
except sqlite3.OperationalError as e:
    print("   SELECT canonical_policy_version -> OperationalError: " + str(e))

dcols = [r["name"] for r in q("PRAGMA table_info(forecast_decision_days)")]
print("\n## E9 run_kind column in production forecast_decision_days?")
print("SQL: PRAGMA table_info(forecast_decision_days)")
print("   columns: " + str(dcols))
print("   run_kind present: " + str("run_kind" in dcols))

print("\n## E10 metrics_json key inventory over all forecast_evaluations rows")
print("SQL: SELECT metrics_json FROM forecast_evaluations")
keys = {}
evq = {}
polv = {}
aggr = {}
for r in q("SELECT metrics_json FROM forecast_evaluations"):
    try:
        m = json.loads(r["metrics_json"])
    except Exception:
        continue
    for k in m:
        keys[k] = keys.get(k, 0) + 1
    evq[m.get("evidence_quality")] = evq.get(m.get("evidence_quality"), 0) + 1
    polv[m.get("canonical_policy_version")] = polv.get(m.get("canonical_policy_version"), 0) + 1
    aggr[m.get("aggregation")] = aggr.get(m.get("aggregation"), 0) + 1
print("   keys: " + json.dumps(keys, ensure_ascii=False, sort_keys=True))
print("   metrics_json.evidence_quality distribution: " + str(evq))
print("   metrics_json.canonical_policy_version distribution: " + str(polv))
print("   metrics_json.aggregation distribution: " + str(aggr))

print("\n## E10b one full metrics_json sample (highest fold_count)")
row = q(
    "SELECT evaluation_id, as_of, scope, horizon_days, status, sample_count, fold_count, metrics_json "
    "FROM forecast_evaluations ORDER BY fold_count DESC LIMIT 1"
)[0]
print("   " + row["evaluation_id"] + " as_of=" + row["as_of"] + " scope=" + row["scope"])
print(json.dumps(json.loads(row["metrics_json"]), ensure_ascii=False, indent=2, sort_keys=True))

con.close()
