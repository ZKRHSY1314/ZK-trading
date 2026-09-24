# -*- coding: utf-8 -*-
"""Part 3: fold-count semantics vs the service, and the sector vintage-key collapse."""
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro", uri=True)
c.row_factory = sqlite3.Row


def show(t, sql, params=()):
    print(f"\n----- {t}")
    rows = c.execute(sql, params).fetchall()
    if not rows:
        print("  (0 rows)")
        return
    print("  " + " | ".join(rows[0].keys()))
    for r in rows[:40]:
        print("  " + " | ".join("NULL" if v is None else str(v) for v in tuple(r)))
    if len(rows) > 40:
        print(f"  ... {len(rows)-40} more")


show("J1 sector: do the 25 timestamp-vintages collapse to far fewer TRADING DAYS? "
     "(if so the canonical policy dedups nothing for sector)", """
SELECT substr(data_version,1,10) AS vintage_calendar_day,
       COUNT(DISTINCT data_version) AS distinct_vintage_keys,
       COUNT(DISTINCT decision_id) AS snapshots,
       COUNT(*) AS rows_
FROM forecast_decisions WHERE scope='sector'
GROUP BY 1 ORDER BY 1""")

show("J2 sector: same 24 canonical snapshots would be how many folds if keyed by DAY?", """
SELECT COUNT(DISTINCT substr(data_version,1,10)) AS calendar_days,
       COUNT(DISTINCT data_version) AS timestamp_vintages,
       COUNT(DISTINCT decision_id) AS snapshots
FROM forecast_decisions WHERE scope='sector'""")

show("J3 stock: vintages and snapshots per vintage (dedup DOES work here)", """
SELECT data_version, COUNT(DISTINCT decision_id) AS snapshots, COUNT(*) AS rows_,
       COUNT(DISTINCT subject) AS distinct_subjects_across_snapshots
FROM forecast_decisions WHERE scope='stock' GROUP BY data_version ORDER BY data_version""")

show("J4 outcome-writer staleness: newest outcome vs newest decision", """
SELECT (SELECT MAX(observed_at) FROM forecast_outcomes) AS newest_outcome,
       (SELECT MAX(decision_cutoff) FROM forecast_decisions) AS newest_decision,
       (SELECT MAX(decision_cutoff) FROM forecast_decisions
         WHERE decision_id IN (SELECT DISTINCT decision_id FROM forecast_outcomes))
         AS newest_decision_with_any_outcome""")

show("J5 the 5 canonical stock vintages: are THEY matured? (contrast with 2026-09-03)", """
SELECT d.data_version, COUNT(*) AS rows_,
       SUM(CASE WHEN o.id IS NULL THEN 0 ELSE 1 END) AS matured_rows
FROM forecast_decisions d
LEFT JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope
                             AND o.subject=d.subject AND o.horizon_days=d.horizon_days
WHERE d.scope='stock' GROUP BY d.data_version ORDER BY d.data_version""")

show("J6 forecast_evaluations: are the 746 legacy rows tagged with a policy version?", """
SELECT COUNT(*) AS total,
       SUM(canonical_policy_version IS NULL) AS null_policy_version,
       COUNT(DISTINCT canonical_policy_version) AS distinct_versions
FROM forecast_evaluations""")
