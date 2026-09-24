# -*- coding: utf-8 -*-
"""INDEPENDENT re-derivation of the canonical-snapshot claim. READ-ONLY."""
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
DB = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
c.row_factory = sqlite3.Row


def show(t, sql, params=()):
    print(f"\n----- {t}\nSQL: {' '.join(sql.split())}")
    rows = c.execute(sql, params).fetchall()
    if not rows:
        print("  (0 rows)")
        return rows
    print("  " + " | ".join(rows[0].keys()))
    for r in rows[:60]:
        print("  " + " | ".join("NULL" if v is None else str(v) for v in tuple(r)))
    if len(rows) > 60:
        print(f"  ... {len(rows)-60} more")
    return rows


print("=" * 78)
print("A. CROSS-DB CHECK: do forecast tables exist in market_history?")
m = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
print("  market_history forecast tables:",
      [r[0] for r in m.execute(
          "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%forecast%'")])
m.close()

print("\n" + "=" * 78)
print("B. LEDGER SHAPE - rows vs distinct decisions vs distinct subjects")
show("B1 totals", """
SELECT COUNT(*) AS rows_total,
       COUNT(DISTINCT decision_id) AS distinct_decision_ids,
       COUNT(DISTINCT scope || '|' || data_version) AS distinct_vintages,
       COUNT(DISTINCT subject) AS distinct_subjects,
       MIN(decision_cutoff) AS min_cutoff, MAX(decision_cutoff) AS max_cutoff
FROM forecast_decisions""")

show("B2 by scope", """
SELECT scope, COUNT(*) AS rows_total,
       COUNT(DISTINCT decision_id) AS decision_ids,
       COUNT(DISTINCT data_version) AS vintages,
       COUNT(DISTINCT subject) AS distinct_subjects,
       SUM(review_only) AS review_only_rows,
       MIN(decision_cutoff) AS min_cutoff, MAX(decision_cutoff) AS max_cutoff
FROM forecast_decisions GROUP BY scope""")

show("B3 decision_ids spanning >1 scope or >1 data_version (join integrity)", """
SELECT COUNT(*) AS decision_ids_spanning_multiple
FROM (SELECT decision_id FROM forecast_decisions
      GROUP BY decision_id
      HAVING COUNT(DISTINCT scope) > 1 OR COUNT(DISTINCT data_version) > 1)""")

show("B4 research-window containment on data_version", """
SELECT SUM(CASE WHEN data_version BETWEEN '2023-09-04' AND '2026-09-04' THEN 1 ELSE 0 END) AS inside,
       SUM(CASE WHEN data_version < '2023-09-04' THEN 1 ELSE 0 END) AS before_window,
       SUM(CASE WHEN data_version > '2026-09-04' THEN 1 ELSE 0 END) AS after_window,
       SUM(CASE WHEN length(data_version) <> 10 THEN 1 ELSE 0 END) AS non_iso_date_len
FROM forecast_decisions""")

print("\n" + "=" * 78)
print("C. BUILD THE MIGRATED SHADOW (TEMP table; main db opened mode=ro)")
c.execute("""CREATE TEMP TABLE shadow_days AS
             SELECT scope, data_version, decision_id, claimed_at,
                    candidate_count, recorded_count, 'legacy_unknown' AS run_kind
             FROM forecast_decision_days""")
show("C1 shadow contents", "SELECT * FROM shadow_days")
print("  (main db is mode=ro; TEMP db is separate - production untouched)")

REQ = (1, 3, 5, 10, 20)   # FORECAST_HORIZONS, backend/app/forecasting/ledger.py:13
REQ_LIST = ", ".join(map(str, REQ))
REQ_N = len(REQ)


def policy(run_kind_sql: str) -> str:
    return f"""
shape AS (
    SELECT scope, data_version, decision_id,
           MIN(decision_cutoff) AS snapshot_cutoff,
           COUNT(DISTINCT subject)      AS subj_n,
           COUNT(DISTINCT horizon_days) AS hz_n,
           COUNT(DISTINCT CASE WHEN horizon_days IN ({REQ_LIST}) THEN horizon_days END) AS req_hz_n,
           COUNT(*) AS row_n
    FROM forecast_decisions GROUP BY scope, data_version, decision_id
),
vintage AS (
    SELECT scope, data_version, MAX(subj_n) AS max_subj, MAX(hz_n) AS max_hz
    FROM shape GROUP BY scope, data_version
),
guarded AS (SELECT scope, data_version FROM shadow_days),
conf AS (
    SELECT s.scope, s.data_version, s.decision_id, s.snapshot_cutoff, 'confirmed' AS selection_kind
    FROM shape s JOIN shadow_days g
      ON g.scope = s.scope AND g.data_version = s.data_version AND g.decision_id = s.decision_id
    WHERE g.recorded_count > 0
      AND {run_kind_sql}
      AND s.subj_n = g.candidate_count
      AND s.row_n  = g.recorded_count
      AND s.row_n  = s.subj_n * s.hz_n
      AND (s.scope <> 'stock' OR s.req_hz_n = {REQ_N})
),
inf AS (
    SELECT s.scope, s.data_version, s.decision_id, s.snapshot_cutoff, 'inferred' AS selection_kind
    FROM shape s JOIN vintage v ON v.scope = s.scope AND v.data_version = s.data_version
    LEFT JOIN guarded g ON g.scope = s.scope AND g.data_version = s.data_version
    WHERE g.scope IS NULL
      AND s.subj_n = v.max_subj AND s.hz_n = v.max_hz
      AND s.row_n = s.subj_n * s.hz_n
),
elig AS (SELECT * FROM conf UNION ALL SELECT * FROM inf),
ranked AS (
    SELECT scope, data_version, decision_id, selection_kind,
           ROW_NUMBER() OVER (PARTITION BY scope, data_version
                              ORDER BY snapshot_cutoff ASC, decision_id ASC) AS rk
    FROM elig
),
canon AS (SELECT scope, data_version, decision_id, selection_kind FROM ranked WHERE rk = 1)
"""


AS_IS = policy("g.run_kind = 'scheduled'")
COUNTER = policy("'scheduled' = 'scheduled'")

print("\n" + "=" * 78)
print("D. AS-MIGRATED: canonical selection (my own hand-written policy SQL)")
show("D1 canonical by scope x selection_kind",
     f"WITH {AS_IS} SELECT scope, selection_kind, COUNT(*) AS snapshots, "
     "COUNT(DISTINCT data_version) AS vintages FROM canon "
     "GROUP BY scope, selection_kind ORDER BY scope, selection_kind")
show("D2 canonical grand total",
     f"WITH {AS_IS} SELECT COUNT(*) AS canonical_snapshots, "
     "SUM(selection_kind = 'confirmed') AS confirmed, "
     "SUM(selection_kind = 'inferred') AS inferred FROM canon")
show("D3 vintages with NO canonical snapshot at all",
     f"WITH {AS_IS} SELECT d.scope, d.data_version, "
     "COUNT(DISTINCT d.decision_id) AS snapshots_on_disk, COUNT(*) AS rows_on_disk "
     "FROM forecast_decisions d LEFT JOIN canon k "
     "ON k.scope = d.scope AND k.data_version = d.data_version "
     "WHERE k.scope IS NULL GROUP BY d.scope, d.data_version")

print("\n" + "=" * 78)
print("E. GUARD RECORD: test each canonical condition SEPARATELY")
show("E1 per-condition pass/fail for the claimed decision_id", f"""
WITH shape AS (
    SELECT scope, data_version, decision_id,
           COUNT(DISTINCT subject) AS subj_n, COUNT(DISTINCT horizon_days) AS hz_n,
           COUNT(DISTINCT CASE WHEN horizon_days IN ({REQ_LIST}) THEN horizon_days END) AS req_hz_n,
           COUNT(*) AS row_n
    FROM forecast_decisions GROUP BY scope, data_version, decision_id)
SELECT g.decision_id, g.candidate_count, g.recorded_count, g.run_kind,
       s.subj_n, s.hz_n, s.req_hz_n, s.row_n,
       (g.recorded_count > 0)         AS t1_finalized,
       (g.run_kind = 'scheduled')     AS t2_run_kind,
       (s.subj_n = g.candidate_count) AS t3_subjects,
       (s.row_n = g.recorded_count)   AS t4_rowcount,
       (s.row_n = s.subj_n * s.hz_n)  AS t5_rectangular,
       (s.req_hz_n = {REQ_N})         AS t6_full_grid
FROM shadow_days g JOIN shape s
  ON s.scope = g.scope AND s.data_version = g.data_version AND s.decision_id = g.decision_id""")

show("E2 the claimed vintage: every snapshot on it", """
SELECT decision_id, COUNT(*) AS rows_, COUNT(DISTINCT subject) AS subjects,
       COUNT(DISTINCT horizon_days) AS horizons, MIN(decision_cutoff) AS cutoff,
       MIN(review_only) AS min_review_only, MAX(review_only) AS max_review_only,
       MIN(available_at) AS min_available_at
FROM forecast_decisions WHERE scope = 'stock' AND data_version = '2026-09-03'
GROUP BY decision_id ORDER BY cutoff""")

show("E3 total rows on the claimed vintage", """
SELECT COUNT(*) AS rows_total, COUNT(DISTINCT decision_id) AS snapshots,
       COUNT(DISTINCT subject) AS distinct_subjects
FROM forecast_decisions WHERE scope = 'stock' AND data_version = '2026-09-03'""")
