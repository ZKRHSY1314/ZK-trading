"""Apply app.forecasting.canonical's policy to PRODUCTION, strictly read-only.

canonical.py is a pure SQL-string module: importing it touches no database.
The production connection is opened with mode=ro. The only writable objects are
SQLite TEMP tables, which live in this connection's private temp database and
are discarded on close - the production file is never written.
"""
import sqlite3
import sys
import json

sys.path.insert(0, r"D:\codex-A股交易\backend")
from app.forecasting.canonical import (  # noqa: E402
    CANONICAL_POLICY_VERSION,
    canonical_snapshot_cte,
    required_stock_horizons,
)

DB = r"D:\codex-A股交易\trading_local.sqlite3"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

CTE = canonical_snapshot_cte()
print("CANONICAL_POLICY_VERSION =", CANONICAL_POLICY_VERSION)
print("required_stock_horizons() =", required_stock_horizons())
with open("labels_02_canonical_cte.sql", "w", encoding="utf-8") as fh:
    fh.write("WITH " + CTE + "\nSELECT scope, data_version, decision_id, selection_kind FROM canonical\n")
print("CTE written to labels_02_canonical_cte.sql")

print("\n" + "=" * 100)
print("STEP 1 - run the canonical CTE against production EXACTLY as the code would")
print("=" * 100)
sql = f"WITH {CTE} SELECT scope, data_version, decision_id, selection_kind FROM canonical ORDER BY scope, data_version"
try:
    rows = con.execute(sql).fetchall()
    print("   SUCCEEDED, rows =", len(rows))
    for r in rows:
        print("   ", dict(r))
except sqlite3.OperationalError as e:
    print("   FAILED with sqlite3.OperationalError:", e)
    print("   -> every read path that composes canonical_snapshot_cte() raises on this database.")

print("\n" + "=" * 100)
print("STEP 2 - reproduce the post-migration schema in TEMP tables (production untouched)")
print("   _migrate_decision_day_run_kind backfills existing claims to run_kind='legacy_unknown'")
print("=" * 100)
con.execute(
    """
    CREATE TEMP TABLE forecast_decision_days AS
    SELECT scope, data_version, decision_id, claimed_at, candidate_count, recorded_count,
           'legacy_unknown' AS run_kind
    FROM main.forecast_decision_days
    """
)
print("   TEMP forecast_decision_days rows:",
      con.execute("SELECT COUNT(*) FROM temp.forecast_decision_days").fetchone()[0])
print("   contents:", [dict(r) for r in con.execute("SELECT * FROM temp.forecast_decision_days")])


def canonical_report(label):
    print("\n--- " + label + " ---")
    rows = con.execute(
        f"WITH {CTE} SELECT scope, data_version, decision_id, selection_kind FROM canonical "
        "ORDER BY scope, data_version"
    ).fetchall()
    print("   total canonical snapshots:", len(rows))
    agg = {}
    for r in rows:
        agg[(r["scope"], r["selection_kind"])] = agg.get((r["scope"], r["selection_kind"]), 0) + 1
    for k in sorted(agg):
        print(f"   scope={k[0]:<7} selection_kind={k[1]:<10} count={agg[k]}")
    for r in rows:
        print("     ", r["scope"], "|", r["data_version"], "|", r["decision_id"], "|", r["selection_kind"])
    return rows


rows_legacy = canonical_report("STEP 2 result: run_kind='legacy_unknown' (what the migration will produce)")

print("\n" + "=" * 100)
print("STEP 3 - counterfactual: what if that one claim had been recorded as run_kind='scheduled'")
print("=" * 100)
con.execute("UPDATE temp.forecast_decision_days SET run_kind = 'scheduled'")
rows_sched = canonical_report("STEP 3 result: run_kind='scheduled' counterfactual")
con.execute("UPDATE temp.forecast_decision_days SET run_kind = 'legacy_unknown'")

print("\n" + "=" * 100)
print("STEP 4 - why each vintage did or did not get a canonical snapshot")
print("=" * 100)
diag = con.execute(
    f"""
    WITH {CTE},
    guarded AS (SELECT scope, data_version, decision_id AS claim_id, candidate_count,
                       recorded_count, run_kind FROM forecast_decision_days)
    SELECT s.scope, s.data_version,
           COUNT(*) AS snapshots_in_vintage,
           MAX(s.subject_count) AS max_subjects,
           MAX(s.horizon_count) AS max_horizons,
           SUM(CASE WHEN s.row_count = s.subject_count*s.horizon_count THEN 1 ELSE 0 END) AS rectangular_snapshots,
           (SELECT COUNT(*) FROM guarded g WHERE g.scope=s.scope AND g.data_version=s.data_version) AS is_guarded,
           (SELECT g.run_kind FROM guarded g WHERE g.scope=s.scope AND g.data_version=s.data_version) AS run_kind,
           (SELECT COUNT(*) FROM canonical c WHERE c.scope=s.scope AND c.data_version=s.data_version) AS canonical_rows,
           (SELECT c.selection_kind FROM canonical c WHERE c.scope=s.scope AND c.data_version=s.data_version) AS selection_kind
    FROM canonical_snapshot_shape s
    GROUP BY s.scope, s.data_version
    ORDER BY s.scope, s.data_version
    """
).fetchall()
print("   scope | data_version | snapshots | max_subj | max_hz | rect | guarded | run_kind | canonical | kind")
for r in diag:
    print("   " + " | ".join(str(r[k]) for k in r.keys()))
uncovered = [r for r in diag if r["canonical_rows"] == 0]
print("\n   vintages with NO canonical snapshot:", len(uncovered))
for r in uncovered:
    print("     ", r["scope"], r["data_version"], "guarded=", r["is_guarded"],
          "rect=", r["rectangular_snapshots"], "of", r["snapshots_in_vintage"])

print("\n" + "=" * 100)
print("STEP 5 - decision rows / outcome rows that survive the canonical filter")
print("=" * 100)
r = con.execute(
    f"""
    WITH {CTE}
    SELECT d.scope, cs.selection_kind,
           COUNT(*) AS decision_rows,
           COUNT(DISTINCT d.decision_id) AS snapshots,
           COUNT(DISTINCT d.subject) AS subjects
    FROM forecast_decisions d
    JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
    GROUP BY d.scope, cs.selection_kind
    """
).fetchall()
print("   decision rows inside canonical snapshots:")
for x in r:
    print("     ", dict(x))
print("   total decision rows =",
      con.execute("SELECT COUNT(*) FROM forecast_decisions").fetchone()[0])

r = con.execute(
    f"""
    WITH {CTE}
    SELECT o.scope, cs.selection_kind, COUNT(*) AS outcome_rows,
           COUNT(DISTINCT o.decision_id) AS snapshots
    FROM forecast_outcomes o
    JOIN forecast_decisions d ON d.decision_id=o.decision_id AND d.scope=o.scope
                             AND d.subject=o.subject AND d.horizon_days=o.horizon_days
    JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
    GROUP BY o.scope, cs.selection_kind
    """
).fetchall()
print("   outcome rows inside canonical snapshots:")
for x in r:
    print("     ", dict(x))
print("   total outcome rows =",
      con.execute("SELECT COUNT(*) FROM forecast_outcomes").fetchone()[0])

print("\n   outcome rows attached to NON-canonical snapshots (excluded on read):")
r = con.execute(
    f"""
    WITH {CTE}
    SELECT o.scope, COUNT(*) AS outcome_rows, COUNT(DISTINCT o.decision_id) AS snapshots
    FROM forecast_outcomes o
    JOIN forecast_decisions d ON d.decision_id=o.decision_id AND d.scope=o.scope
                             AND d.subject=o.subject AND d.horizon_days=o.horizon_days
    LEFT JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
    WHERE cs.decision_id IS NULL
    GROUP BY o.scope
    """
).fetchall()
for x in r:
    print("     ", dict(x))

print("\n" + "=" * 100)
print("STEP 6 - CONFIRMED-canonical + official-provenance evidence that would remain")
print("=" * 100)
for label, kinds in (("confirmed only", ("confirmed",)), ("confirmed+inferred", ("confirmed", "inferred"))):
    r = con.execute(
        f"""
        WITH {CTE}
        SELECT d.scope, d.horizon_days,
               COUNT(DISTINCT d.decision_id) AS folds,
               COUNT(*) AS decision_rows,
               SUM(CASE WHEN o.id IS NULL THEN 0 ELSE 1 END) AS matured_samples
        FROM forecast_decisions d
        JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
        LEFT JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope
                                     AND o.subject=d.subject AND o.horizon_days=d.horizon_days
        WHERE cs.selection_kind IN ({",".join("'" + k + "'" for k in kinds)})
        GROUP BY d.scope, d.horizon_days
        ORDER BY d.scope, d.horizon_days
        """
    ).fetchall()
    print(f"\n   [{label}] scope | horizon | folds | decision_rows | matured_samples")
    if not r:
        print("      (no rows - ZERO admissible evidence)")
    for x in r:
        print("      " + " | ".join(str(x[k]) for k in x.keys()))

print("\n" + "=" * 100)
print("STEP 7 - metrics_json nested-payload inventory (746 rows)")
print("=" * 100)
inner_keys = {}
evq = {}
polv = {}
conf_fold = {}
for row in con.execute("SELECT metrics_json FROM forecast_evaluations"):
    payload = json.loads(row["metrics_json"])
    m = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    for k in m:
        inner_keys[k] = inner_keys.get(k, 0) + 1
    evq[m.get("evidence_quality")] = evq.get(m.get("evidence_quality"), 0) + 1
    polv[m.get("canonical_policy_version")] = polv.get(m.get("canonical_policy_version"), 0) + 1
    conf_fold[m.get("confirmed_fold_count")] = conf_fold.get(m.get("confirmed_fold_count"), 0) + 1
print("   metrics_json['metrics'] keys:", json.dumps(inner_keys, sort_keys=True))
print("   nested evidence_quality:", evq)
print("   nested canonical_policy_version:", polv)
print("   nested confirmed_fold_count:", conf_fold)

print("\n" + "=" * 100)
print("STEP 8 - fold inflation: stored fold_count vs distinct decision DATES available at as_of")
print("=" * 100)
r = con.execute(
    """
    SELECT e.as_of, e.scope, e.horizon_days, e.status, e.sample_count, e.fold_count,
      (SELECT COUNT(DISTINCT d.decision_id) FROM forecast_decisions d
        WHERE d.scope=e.scope AND d.horizon_days=e.horizon_days AND d.decision_cutoff<=e.as_of) AS snapshots_at_as_of,
      (SELECT COUNT(DISTINCT d.data_version) FROM forecast_decisions d
        WHERE d.scope=e.scope AND d.horizon_days=e.horizon_days AND d.decision_cutoff<=e.as_of) AS vintages_at_as_of,
      (SELECT COUNT(DISTINCT substr(d.decision_cutoff,1,10)) FROM forecast_decisions d
        WHERE d.scope=e.scope AND d.horizon_days=e.horizon_days AND d.decision_cutoff<=e.as_of) AS cutoff_dates_at_as_of
    FROM forecast_evaluations e
    WHERE e.status='ready'
    ORDER BY e.fold_count DESC, e.as_of
    LIMIT 15
    """
).fetchall()
print("   as_of | scope | hz | status | sample | fold | snapshots<=as_of | vintages<=as_of | cutoff_dates<=as_of")
for x in r:
    print("   " + " | ".join(str(x[k]) for k in x.keys()))

print("\n   Ratio summary over ALL 'ready' evaluations:")
r = con.execute(
    """
    SELECT scope, COUNT(*) AS ready_rows, MAX(fold_count) AS max_fold, MAX(sample_count) AS max_sample,
      MAX((SELECT COUNT(DISTINCT d.data_version) FROM forecast_decisions d
           WHERE d.scope=e.scope AND d.horizon_days=e.horizon_days AND d.decision_cutoff<=e.as_of)) AS max_vintages
    FROM forecast_evaluations e WHERE status='ready' GROUP BY scope
    """
).fetchall()
for x in r:
    print("   ", dict(x))

con.close()
print("\nDONE - production database was opened read-only and never written.")
