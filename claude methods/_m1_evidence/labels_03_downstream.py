"""READ-ONLY: how far the 746 legacy evaluations have already propagated, and
what the canonical policy does NOT fix (sector vintage keying)."""
import sqlite3
import sys
import json

sys.path.insert(0, r"D:\codex-A股交易\backend")
from app.forecasting.canonical import canonical_snapshot_cte  # noqa: E402

DB = r"D:\codex-A股交易\trading_local.sqlite3"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
CTE = canonical_snapshot_cte()

# Production's forecast_decision_days has no run_kind column, so the canonical
# CTE cannot run against it. This TEMP shadow reproduces exactly what
# _migrate_decision_day_run_kind would produce (existing claims -> legacy_unknown).
# TEMP tables live in this connection's private temp db; production stays read-only.
con.execute(
    """
    CREATE TEMP TABLE forecast_decision_days AS
    SELECT scope, data_version, decision_id, claimed_at, candidate_count, recorded_count,
           'legacy_unknown' AS run_kind
    FROM main.forecast_decision_days
    """
)


def show(title, sql, params=()):
    print("\n" + "#" * 100)
    print("## " + title)
    print("SQL: " + " ".join(sql.split()))
    rows = con.execute(sql, params).fetchall()
    if not rows:
        print("   (no rows)")
        return rows
    print("   " + " | ".join(str(k) for k in rows[0].keys()))
    for r in rows:
        print("   " + " | ".join(str(r[k]) for k in r.keys()))
    return rows


show(
    "P1 agent_calibration_proposals by type and status",
    "SELECT proposal_type, status, COUNT(*) AS rows, MIN(created_at) AS first, MAX(created_at) AS last "
    "FROM agent_calibration_proposals GROUP BY proposal_type, status ORDER BY rows DESC",
)

show(
    "P2 forecast_calibration proposals in full",
    "SELECT id, proposal_type, target, status, created_by, created_at, updated_at "
    "FROM agent_calibration_proposals WHERE proposal_type='forecast_calibration' ORDER BY id",
)

print("\n" + "#" * 100)
print("## P3 which forecast_evaluations row each forecast_calibration proposal cites")
print("SQL: SELECT id, target, status, evidence_json FROM agent_calibration_proposals "
      "WHERE proposal_type='forecast_calibration'")
for r in con.execute(
    "SELECT id, target, status, evidence_json FROM agent_calibration_proposals "
    "WHERE proposal_type='forecast_calibration' ORDER BY id"
):
    try:
        ev = json.loads(r["evidence_json"])
    except Exception:
        ev = {}
    eid = ev.get("evaluation_id")
    hit = con.execute(
        "SELECT as_of, scope, horizon_days, status, sample_count, fold_count "
        "FROM forecast_evaluations WHERE evaluation_id = ?",
        (eid,),
    ).fetchone()
    print(f"   proposal id={r['id']} target={r['target']} status={r['status']}")
    print(f"      cites evaluation_id={eid}")
    print(f"      that row in forecast_evaluations: {dict(hit) if hit else 'NOT FOUND'}")
    m = ev.get("metrics") or {}
    print(f"      evidence metrics: sample_count={m.get('sample_count')} fold_count={m.get('fold_count')} "
          f"status={m.get('status')} evidence_quality={m.get('evidence_quality')!r} "
          f"canonical_policy_version={m.get('canonical_policy_version')!r}")

show(
    "P4 sandbox / paper-simulation consumers of those proposals",
    "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
    "('agent_sandbox_experiments','agent_paper_simulations','agent_experiment_runs')",
)
for t in ("agent_sandbox_experiments", "agent_paper_simulations", "agent_experiment_runs"):
    try:
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"   SELECT COUNT(*) FROM {t}  ->  {n}")
    except sqlite3.OperationalError as e:
        print(f"   {t}: {e}")

print("\n" + "#" * 100)
print("## S1 sector vintage keying: data_version IS the decision instant, so the")
print("##    canonical one-per-vintage rule removes nothing for sector")
print("SQL: SELECT COUNT(DISTINCT data_version), COUNT(DISTINCT decision_id), "
      "COUNT(DISTINCT substr(decision_cutoff,1,10)) FROM forecast_decisions WHERE scope='sector'")
r = con.execute(
    "SELECT COUNT(DISTINCT data_version) AS vintages, COUNT(DISTINCT decision_id) AS snapshots, "
    "COUNT(DISTINCT substr(decision_cutoff,1,10)) AS trading_dates, "
    "SUM(CASE WHEN data_version = decision_cutoff THEN 0 ELSE 1 END) AS rows_where_dv_ne_cutoff, "
    "COUNT(*) AS rows FROM forecast_decisions WHERE scope='sector'"
).fetchone()
print("   " + str(dict(r)))
print("   sample sector rows:")
for x in con.execute(
    "SELECT decision_id, data_version, decision_cutoff FROM forecast_decisions "
    "WHERE scope='sector' ORDER BY decision_cutoff LIMIT 4"
):
    print("     ", dict(x))

show(
    "S2 canonical sector snapshots per TRADING DATE (fold inflation surviving the policy)",
    f"WITH {CTE} SELECT substr(d.decision_cutoff,1,10) AS trading_date, "
    "COUNT(DISTINCT d.decision_id) AS canonical_snapshots, COUNT(*) AS decision_rows "
    "FROM forecast_decisions d JOIN canonical cs ON cs.decision_id=d.decision_id "
    "AND cs.scope=d.scope AND cs.data_version=d.data_version WHERE d.scope='sector' "
    "GROUP BY trading_date ORDER BY trading_date",
)

show(
    "S3 canonical stock snapshots per TRADING DATE (policy working as intended)",
    f"WITH {CTE} SELECT d.data_version AS bar_vintage, substr(d.decision_cutoff,1,10) AS recorded_date, "
    "COUNT(DISTINCT d.decision_id) AS canonical_snapshots, COUNT(*) AS decision_rows "
    "FROM forecast_decisions d JOIN canonical cs ON cs.decision_id=d.decision_id "
    "AND cs.scope=d.scope AND cs.data_version=d.data_version WHERE d.scope='stock' "
    "GROUP BY bar_vintage, recorded_date ORDER BY bar_vintage",
)

show(
    "S4 stock: rows removed by the canonical policy",
    f"WITH {CTE} SELECT d.scope, COUNT(*) AS total_rows, "
    "SUM(CASE WHEN cs.decision_id IS NULL THEN 1 ELSE 0 END) AS excluded_rows, "
    "SUM(CASE WHEN cs.decision_id IS NULL THEN 0 ELSE 1 END) AS kept_rows "
    "FROM forecast_decisions d LEFT JOIN canonical cs ON cs.decision_id=d.decision_id "
    "AND cs.scope=d.scope AND cs.data_version=d.data_version GROUP BY d.scope",
)

print("\n" + "#" * 100)
print("## G1 the gates a confirmed-only evaluation would face today")
print("##    ForecastFeedbackService.evaluate defaults: min_samples=20, min_folds=3, k=5")
print("##    include_inferred=False by default -> only 'confirmed' snapshots are read")
print("SQL: (confirmed-only aggregate, see labels_02 STEP 6)")
r = con.execute(
    f"""
    WITH {CTE}
    SELECT COUNT(*) AS confirmed_snapshots FROM canonical WHERE selection_kind='confirmed'
    """
).fetchall()
print("   confirmed canonical snapshots against production-as-it-stands: query cannot run (run_kind missing)")
print("   -> measured in labels_02 under the post-migration TEMP shadow: 0 confirmed / 29 inferred")

show(
    "G2 unlabelled decision rows in the one guarded vintage (stock 2026-09-03)",
    "SELECT d.decision_id, COUNT(*) AS rows, SUM(CASE WHEN o.id IS NULL THEN 1 ELSE 0 END) AS unlabelled "
    "FROM forecast_decisions d LEFT JOIN forecast_outcomes o ON o.decision_id=d.decision_id "
    "AND o.scope=d.scope AND o.subject=d.subject AND o.horizon_days=d.horizon_days "
    "WHERE d.scope='stock' AND d.data_version='2026-09-03' GROUP BY d.decision_id ORDER BY d.decision_id",
)

show(
    "G3 how many forecast_evaluations rows were written after the canonical module landed",
    "SELECT COUNT(*) AS rows, MAX(created_at) AS newest FROM forecast_evaluations",
)

show(
    "E11 duplicate metric payloads: identical (scope,horizon,sample,fold,rank_ic) repeated",
    "SELECT scope, horizon_days, sample_count, fold_count, spearman_rank_ic, COUNT(*) AS identical_rows "
    "FROM forecast_evaluations WHERE status='ready' GROUP BY scope, horizon_days, sample_count, "
    "fold_count, spearman_rank_ic HAVING COUNT(*) > 1 ORDER BY identical_rows DESC LIMIT 20",
)

con.close()
print("\nDONE - read-only.")
