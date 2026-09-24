import sqlite3
db = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
def q(label, sql, p=()):
    print("\n### " + label)
    print("SQL: " + " ".join(sql.split()))
    rows = con.execute(sql, p).fetchall()
    for r in rows[:40]:
        print("   ", dict(r))
    if len(rows) > 40: print(f"    ... {len(rows)} rows total")
    return rows

# ---- A. ledger shape, my own counts (do not trust the brief) ----
q("A1 ledger totals by scope", """
SELECT scope, COUNT(*) AS rows_, COUNT(DISTINCT decision_id) AS decision_ids,
       COUNT(DISTINCT data_version) AS vintages,
       COUNT(DISTINCT subject) AS subjects,
       MIN(decision_cutoff) AS min_cut, MAX(decision_cutoff) AS max_cut
FROM forecast_decisions GROUP BY scope""")

q("A2 global distinct (scope,data_version) vintage pairs and decision_ids", """
SELECT COUNT(*) AS rows_, COUNT(DISTINCT decision_id) AS decision_ids,
       COUNT(DISTINCT scope||'/'||data_version) AS scope_vintages
FROM forecast_decisions""")

# ---- B. the worst vintage claim ----
q("B1 top vintages by snapshot count", """
SELECT scope, data_version,
       COUNT(DISTINCT decision_id) AS snapshots, COUNT(*) AS rows_,
       COUNT(DISTINCT subject) AS distinct_subjects,
       COUNT(DISTINCT horizon_days) AS horizons,
       MIN(decision_cutoff) AS first_cut, MAX(decision_cutoff) AS last_cut,
       ROUND((julianday(MAX(decision_cutoff))-julianday(MIN(decision_cutoff)))*24.0,2) AS span_hours
FROM forecast_decisions GROUP BY scope, data_version
ORDER BY snapshots DESC LIMIT 8""")

# ---- C. are the re-recordings actually the SAME content? independent dup test ----
q("C1 stock/2026-07-15 : distinct subject-sets across its snapshots", """
WITH s AS (SELECT decision_id, GROUP_CONCAT(subject) AS subj_sig
           FROM (SELECT decision_id, subject FROM forecast_decisions
                 WHERE scope='stock' AND data_version='2026-07-15' AND horizon_days=1
                 ORDER BY decision_id, subject)
           GROUP BY decision_id)
SELECT COUNT(*) AS snapshots, COUNT(DISTINCT subj_sig) AS distinct_subject_sets FROM s""")

q("C2 stock/2026-07-15 : distinct (subject,rank,score) signatures across snapshots", """
WITH s AS (SELECT decision_id, GROUP_CONCAT(sig) AS full_sig FROM (
    SELECT decision_id, subject||':'||COALESCE(rank,-1)||':'||COALESCE(ROUND(score,6),-999) AS sig
    FROM forecast_decisions WHERE scope='stock' AND data_version='2026-07-15' AND horizon_days=1
    ORDER BY decision_id, subject) GROUP BY decision_id)
SELECT COUNT(*) AS snapshots, COUNT(DISTINCT full_sig) AS distinct_rank_score_sets FROM s""")

# ---- D. the target evaluation row, as stored ----
q("D1 stored evaluation stock h=1 at 2026-09-04T04:43:08Z", """
SELECT evaluation_id, as_of, scope, horizon_days, status, sample_count, fold_count, coverage
FROM forecast_evaluations
WHERE scope='stock' AND horizon_days=1 AND as_of='2026-09-04T04:43:08Z'""")

q("D2 max stored sample/fold per scope+horizon (any status)", """
SELECT scope, horizon_days, MAX(sample_count) AS max_sample, MAX(fold_count) AS max_fold,
       COUNT(*) AS n_rows FROM forecast_evaluations GROUP BY scope, horizon_days""")

# ---- E. INDEPENDENT reproduction of legacy math, pure SQL, no canonical CTE ----
# legacy: fold = distinct decision_id having >=1 matured row; sample = matured rows.
q("E1 my independent legacy recompute, stock h=1 @ 2026-09-04T04:43:08Z", """
SELECT COUNT(*) AS my_sample_count, COUNT(DISTINCT d.decision_id) AS my_fold_count,
       COUNT(DISTINCT d.data_version) AS distinct_vintages_behind_them,
       COUNT(DISTINCT d.subject) AS distinct_subjects
FROM forecast_decisions d
JOIN forecast_outcomes o
  ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject
 AND o.horizon_days=d.horizon_days AND o.observed_at <= '2026-09-04T04:43:08Z'
WHERE d.scope='stock' AND d.review_only=1 AND d.horizon_days=1
  AND d.decision_cutoff <= '2026-09-04T04:43:08Z'
  AND d.available_at   <= '2026-09-04T04:43:08Z'""")

# ---- F. DEDUP baseline that does NOT depend on the new canonical policy ----
q("F1 same window, deduplicated to distinct (vintage,subject) observations", """
SELECT COUNT(*) AS distinct_vintage_subject_obs FROM (
 SELECT DISTINCT d.data_version, d.subject
 FROM forecast_decisions d
 JOIN forecast_outcomes o
   ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject
  AND o.horizon_days=d.horizon_days AND o.observed_at <= '2026-09-04T04:43:08Z'
 WHERE d.scope='stock' AND d.review_only=1 AND d.horizon_days=1
   AND d.decision_cutoff <= '2026-09-04T04:43:08Z'
   AND d.available_at   <= '2026-09-04T04:43:08Z')""")

q("F2 per-vintage breakdown inside that same window", """
SELECT d.data_version, COUNT(DISTINCT d.decision_id) AS snapshots_with_matured,
       COUNT(*) AS matured_rows, COUNT(DISTINCT d.subject) AS distinct_subjects
FROM forecast_decisions d
JOIN forecast_outcomes o
  ON o.decision_id=d.decision_id AND o.scope=d.scope AND o.subject=d.subject
 AND o.horizon_days=d.horizon_days AND o.observed_at <= '2026-09-04T04:43:08Z'
WHERE d.scope='stock' AND d.review_only=1 AND d.horizon_days=1
  AND d.decision_cutoff <= '2026-09-04T04:43:08Z'
  AND d.available_at   <= '2026-09-04T04:43:08Z'
GROUP BY d.data_version ORDER BY d.data_version""")
con.close()
