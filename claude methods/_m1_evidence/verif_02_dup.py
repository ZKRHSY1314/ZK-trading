import sqlite3
db = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True); con.row_factory = sqlite3.Row
def q(label, sql, p=()):
    print("\n### " + label); print("SQL: " + " ".join(sql.split()))
    rows = con.execute(sql, p).fetchall()
    for r in rows[:30]: print("   ", dict(r))
    if len(rows) > 30: print(f"    ... {len(rows)} rows total")
    return rows

q("G0 does their quoted as_of exist at all?", """
SELECT COUNT(*) AS n FROM forecast_evaluations WHERE as_of='2026-09-04T04:43:08Z'""")
q("G1 the real max as_of rows, stock", """
SELECT as_of, horizon_days, status, sample_count, fold_count FROM forecast_evaluations
WHERE scope='stock' ORDER BY as_of DESC LIMIT 12""")

# DECISIVE: are the many outcome rows measuring the SAME return for the same subject+vintage?
q("H1 stock/2026-07-15 h=1: distinct returns per subject across its 44 snapshots", """
SELECT COUNT(*) AS subject_vintage_cells,
       SUM(n_outcome_rows) AS total_outcome_rows,
       SUM(distinct_returns) AS total_distinct_returns,
       MAX(distinct_returns) AS worst_case_distinct_per_cell
FROM (
  SELECT d.subject, COUNT(*) AS n_outcome_rows,
         COUNT(DISTINCT ROUND(o.continuous_return,10)) AS distinct_returns
  FROM forecast_decisions d
  JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope
       AND o.subject=d.subject AND o.horizon_days=d.horizon_days
  WHERE d.scope='stock' AND d.data_version='2026-07-15' AND d.horizon_days=1
  GROUP BY d.subject)""")

q("H2 same test across ALL stock vintages, h=1", """
SELECT SUM(n_outcome_rows) AS total_outcome_rows,
       COUNT(*) AS distinct_subject_vintage_cells,
       SUM(distinct_returns) AS sum_distinct_returns,
       MAX(distinct_returns) AS max_distinct_per_cell
FROM (
  SELECT d.data_version, d.subject, COUNT(*) AS n_outcome_rows,
         COUNT(DISTINCT ROUND(o.continuous_return,10)) AS distinct_returns
  FROM forecast_decisions d
  JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope
       AND o.subject=d.subject AND o.horizon_days=d.horizon_days
  WHERE d.scope='stock' AND d.horizon_days=1
  GROUP BY d.data_version, d.subject)""")

# INDEPENDENT dedup: earliest snapshot per vintage (my own rule, not their CTE)
q("I1 my own dedup: earliest decision_id per stock vintage, matured h=1 count", """
WITH firstsnap AS (
  SELECT data_version, decision_id FROM (
    SELECT data_version, decision_id, MIN(decision_cutoff) AS c,
           ROW_NUMBER() OVER (PARTITION BY data_version ORDER BY MIN(decision_cutoff), decision_id) AS rn
    FROM forecast_decisions WHERE scope='stock' GROUP BY data_version, decision_id)
  WHERE rn=1)
SELECT COUNT(*) AS dedup_sample_count, COUNT(DISTINCT d.decision_id) AS dedup_fold_count
FROM forecast_decisions d
JOIN firstsnap f ON f.decision_id=d.decision_id AND f.data_version=d.data_version
JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope
     AND o.subject=d.subject AND o.horizon_days=d.horizon_days
     AND o.observed_at <= '2026-09-04T04:43:08Z'
WHERE d.scope='stock' AND d.review_only=1 AND d.horizon_days=1
  AND d.decision_cutoff <= '2026-09-04T04:43:08Z' AND d.available_at <= '2026-09-04T04:43:08Z'""")

# ready-row census
q("J1 ready rows by scope", """
SELECT status, scope, COUNT(*) AS n FROM forecast_evaluations GROUP BY status, scope ORDER BY status, scope""")
q("J2 the 3630/121 and 1074/36 repeat counts", """
SELECT scope, horizon_days, sample_count, fold_count, COUNT(*) AS n_rows,
       COUNT(DISTINCT status) AS statuses, MIN(status) AS a_status
FROM forecast_evaluations
WHERE (sample_count=3630 AND fold_count=121) OR (sample_count=1074 AND fold_count=36)
GROUP BY scope, horizon_days, sample_count, fold_count ORDER BY sample_count DESC, horizon_days""")

q("K1 forecast_decision_days full contents", "SELECT * FROM forecast_decision_days")
q("K2 sector data_version cardinality (dedup headroom)", """
SELECT COUNT(DISTINCT data_version) AS vintages, COUNT(DISTINCT decision_id) AS decision_ids,
       MAX(LENGTH(data_version)) AS max_dv_len, MIN(data_version) AS sample_dv
FROM forecast_decisions WHERE scope='sector'""")
q("K3 stock data_version cardinality", """
SELECT COUNT(DISTINCT data_version) AS vintages, COUNT(DISTINCT decision_id) AS decision_ids,
       MAX(LENGTH(data_version)) AS max_dv_len FROM forecast_decisions WHERE scope='stock'""")
q("L1 are index symbols present in stock scope?", """
SELECT COUNT(DISTINCT subject) AS distinct_subjects,
  SUM(CASE WHEN subject LIKE 'SH000%' OR subject LIKE 'SZ399%' OR subject LIKE '000%'
        OR subject LIKE '399%' OR UPPER(subject) LIKE '%INDEX%' THEN 1 ELSE 0 END) AS indexish_rows
FROM forecast_decisions WHERE scope='stock'""")
q("L2 sample of stock subjects", """
SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock' ORDER BY subject LIMIT 15""")
con.close()
