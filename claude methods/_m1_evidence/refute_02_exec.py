import sqlite3, sys, traceback
sys.path.insert(0, r"D:\codex-A股交易\backend")
from app.forecasting.canonical import canonical_snapshot_cte  # pure string builder

DB = r"D:\codex-A股交易\trading_local.sqlite3"
def ro():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c

CTE = canonical_snapshot_cte()
print("CTE mentions c.run_kind:", "c.run_kind" in CTE)

def attempt(name, sql, params=()):
    c = ro()
    try:
        rows = c.execute(sql, params).fetchall()
        print(f"[OK]   {name}: {len(rows)} rows")
        return rows
    except sqlite3.Error as e:
        print(f"[FAIL] {name}: {type(e).__name__}: {e}")
        return None
    finally:
        c.close()

print("\n--- 1. canonical.py:215 canonical_snapshots() ---")
attempt("canonical_snapshots",
  f"WITH {CTE} SELECT scope, data_version, decision_id, selection_kind FROM canonical ORDER BY scope, data_version")

print("\n--- 2. ledger.py:373 list_matured(deduplicate=True) ---")
attempt("ledger.list_matured dedup", f"""
WITH {CTE}
SELECT d.decision_id, cs.selection_kind AS canonical_selection_kind
FROM forecast_decisions d
JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject AND o.horizon_days=d.horizon_days
WHERE d.review_only = 1 AND (cs.selection_kind='confirmed' OR ?=1)
""", (0,))

print("\n--- 2b. ledger.list_matured(deduplicate=False) [no CTE] ---")
attempt("ledger.list_matured raw", """
SELECT d.decision_id, NULL AS canonical_selection_kind
FROM forecast_decisions d
JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject AND o.horizon_days=d.horizon_days
WHERE d.review_only = 1
""")

print("\n--- 3. feedback.py:270 label_due count ---")
attempt("feedback.label_due count", f"""
WITH {CTE} SELECT COUNT(*) AS count
FROM forecast_decisions d
JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
LEFT JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject AND o.horizon_days=d.horizon_days
WHERE d.scope=? AND d.review_only=1 AND o.id IS NULL AND d.decision_cutoff<=? AND d.available_at<=? AND (cs.selection_kind='confirmed' OR ?=1)
""", ("stock", "2026-09-04T00:00:00Z", "2026-09-04T00:00:00Z", 0))

print("\n--- 4. feedback.py:964 evaluate ---")
attempt("feedback.evaluate", f"""
WITH {CTE}
SELECT d.decision_id, d.subject, cs.selection_kind, o.id AS outcome_id
FROM forecast_decisions d
JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
LEFT JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject AND o.horizon_days=d.horizon_days AND o.observed_at<=?
WHERE d.scope=? AND d.review_only=1 AND d.horizon_days=? AND d.decision_cutoff<=? AND d.available_at<=? AND (cs.selection_kind='confirmed' OR ?=1)
""", ("2026-09-04T00:00:00Z", "stock", 1, "2026-09-04T00:00:00Z", "2026-09-04T00:00:00Z", 0))

print("\n--- 5. calibration.py:125 INSERT column list (EXPLAIN only, read-only conn) ---")
attempt("calibration INSERT compile", """
EXPLAIN INSERT OR IGNORE INTO forecast_evaluations(
  evaluation_id, as_of, scope, horizon_days, status, sample_count, fold_count,
  coverage, precision_at_k, spearman_rank_ic, brier_score, metrics_json,
  canonical_policy_version, review_only
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)
""", ("x","x","x",1,"x",0,0,0.0,None,None,None,"{}",None))

print("\n--- 6. Isolate WHICH column breaks it: strip run_kind only ---")
attempt("CTE minus run_kind filter",
  f"WITH {CTE.replace(chr(10)+'      AND c.run_kind = ' + chr(39) + 'scheduled' + chr(39), '')} "
  "SELECT scope, data_version, decision_id, selection_kind FROM canonical ORDER BY scope, data_version")
