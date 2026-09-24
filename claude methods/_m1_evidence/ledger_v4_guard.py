import sqlite3
P = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{P}?mode=ro", uri=True); con.row_factory = sqlite3.Row
c = con.cursor()
print("### Guard predicates, evaluated one by one")
for r in c.execute("""
SELECT g.decision_id, g.candidate_count, g.recorded_count,
       s.subject_count, s.row_count, s.horizon_count, s.required_horizon_count,
       (g.recorded_count > 0)                                AS p1_finalized,
       (s.subject_count = g.candidate_count)                 AS p2_subjects,
       (s.row_count = g.recorded_count)                      AS p3_rows,
       (s.row_count = s.subject_count * s.horizon_count)     AS p4_rectangular,
       (s.required_horizon_count = 5)                        AS p5_full_grid
FROM forecast_decision_days g
JOIN (SELECT scope,data_version,decision_id,COUNT(DISTINCT subject) subject_count,
             COUNT(DISTINCT horizon_days) horizon_count,
             COUNT(DISTINCT CASE WHEN horizon_days IN (1,3,5,10,20) THEN horizon_days END)
                 required_horizon_count, COUNT(*) row_count
      FROM forecast_decisions GROUP BY scope,data_version,decision_id) s
  ON s.scope=g.scope AND s.data_version=g.data_version AND s.decision_id=g.decision_id"""):
    print("   ", dict(r))
print("\n### Rows in guarded vintage stock/2026-09-03, and their maturity")
for r in c.execute("""
SELECT COUNT(*) AS rows_in_vintage,
       COUNT(DISTINCT d.decision_id) AS snapshots,
       SUM(CASE WHEN EXISTS(SELECT 1 FROM forecast_outcomes o WHERE o.decision_id=d.decision_id
             AND o.scope=d.scope AND o.subject=d.subject AND o.horizon_days=d.horizon_days)
           THEN 1 ELSE 0 END) AS matured
FROM forecast_decisions d WHERE d.scope='stock' AND d.data_version='2026-09-03'"""):
    print("   ", dict(r))
print("\n### Sector data_version is a per-run timestamp -> vintage grouping is a no-op")
for r in c.execute("""
SELECT scope, COUNT(DISTINCT data_version) AS vintages,
       COUNT(DISTINCT decision_id) AS snapshots,
       COUNT(DISTINCT substr(decision_cutoff,1,10)) AS cutoff_days
FROM forecast_decisions GROUP BY scope"""):
    print("   ", dict(r))
con.close()
