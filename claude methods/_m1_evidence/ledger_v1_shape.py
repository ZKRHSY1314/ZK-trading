import sqlite3
p = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
c = con.cursor()
def q(label, sql, args=()):
    print("\n### " + label)
    print("SQL: " + " ".join(sql.split()))
    rows = c.execute(sql, args).fetchall()
    for r in rows[:60]:
        print("   ", dict(r))
    if len(rows) > 60: print(f"    ... {len(rows)} rows total")

q("A. distinct decision_id / (scope,decision_id) / (scope,data_version) vintages",
  """SELECT COUNT(*) AS rows_total,
            COUNT(DISTINCT decision_id) AS distinct_decision_id,
            COUNT(DISTINCT scope||'|'||decision_id) AS distinct_scope_decision,
            COUNT(DISTINCT scope||'|'||data_version) AS distinct_vintages,
            COUNT(DISTINCT data_version) AS distinct_data_version
     FROM forecast_decisions""")

q("B. rows and vintages by scope",
  """SELECT scope, COUNT(*) AS rows, COUNT(DISTINCT decision_id) AS dids,
            COUNT(DISTINCT data_version) AS vintages,
            MIN(decision_cutoff) AS min_cut, MAX(decision_cutoff) AS max_cut
     FROM forecast_decisions GROUP BY scope""")

q("C. data_version value shapes (non 10-char / non-date)",
  """SELECT length(data_version) AS len, COUNT(*) AS n,
            MIN(data_version) AS mn, MAX(data_version) AS mx
     FROM forecast_decisions GROUP BY length(data_version)""")

q("D. does any decision_id span >1 scope or >1 data_version?",
  """SELECT COUNT(*) FROM (
        SELECT decision_id FROM forecast_decisions
        GROUP BY decision_id HAVING COUNT(DISTINCT scope)>1 OR COUNT(DISTINCT data_version)>1)""")

q("E. outcomes: totals, join integrity to decisions",
  """SELECT (SELECT COUNT(*) FROM forecast_outcomes) AS outcomes_rows,
            (SELECT COUNT(DISTINCT decision_id) FROM forecast_outcomes) AS outcome_dids,
            (SELECT COUNT(*) FROM forecast_outcomes o
               WHERE NOT EXISTS (SELECT 1 FROM forecast_decisions d
                 WHERE d.decision_id=o.decision_id AND d.scope=o.scope
                   AND d.subject=o.subject AND d.horizon_days=o.horizon_days)) AS orphan_outcomes""")

q("F. outcomes by scope",
  """SELECT scope, COUNT(*) AS n, MIN(observed_at) AS mn, MAX(observed_at) AS mx,
            COUNT(DISTINCT decision_id) AS dids FROM forecast_outcomes GROUP BY scope""")

q("G. the guarded vintage stock/2026-09-03: all snapshots and outcome coverage",
  """SELECT d.decision_id, MIN(d.decision_cutoff) AS cut, COUNT(*) AS rows,
            COUNT(DISTINCT d.subject) AS subs, COUNT(DISTINCT d.horizon_days) AS hz,
            SUM(CASE WHEN o.id IS NULL THEN 0 ELSE 1 END) AS matured
     FROM forecast_decisions d
     LEFT JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope
       AND o.subject=d.subject AND o.horizon_days=d.horizon_days
     WHERE d.scope='stock' AND d.data_version='2026-09-03'
     GROUP BY d.decision_id ORDER BY cut""")
con.close()
