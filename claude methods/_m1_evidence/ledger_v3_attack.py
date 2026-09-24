import sqlite3, sys
sys.path.insert(0, r"D:/codex-A股交易/backend")
from app.forecasting.canonical import canonical_snapshot_cte

P = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{P}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
c = con.cursor()

# --- Build a read-only TEMP shadow that mirrors the pending migration ---
c.execute("""CREATE TEMP TABLE fdd_shadow AS
             SELECT scope,data_version,decision_id,claimed_at,candidate_count,
                    recorded_count,'legacy_unknown' AS run_kind
             FROM main.forecast_decision_days""")
# Point the CTE at the shadow by textual substitution of the table name only.
CTE = canonical_snapshot_cte().replace("FROM forecast_decision_days",
                                       "FROM temp.fdd_shadow") \
                              .replace("JOIN forecast_decision_days c",
                                       "JOIN temp.fdd_shadow c")

def show(label, sql, args=()):
    print("\n### " + label)
    for r in c.execute(sql, args).fetchall()[:40]:
        print("   ", dict(r))

print("=== CROSS-CHECK: real CTE vs my Python (expect 24 sector/inferred + 5 stock/inferred) ===")
show("CTE canonical tally", f"""WITH {CTE}
   SELECT scope, selection_kind, COUNT(*) AS n FROM canonical
   GROUP BY scope, selection_kind ORDER BY scope, selection_kind""")

print("\n=== ATTACK 1: index contamination in 'stock' subjects ===")
show("stock subjects, distinct, sample",
     """SELECT COUNT(DISTINCT subject) AS distinct_subjects,
               SUM(CASE WHEN subject LIKE '00%' OR subject LIKE '30%' OR subject LIKE '60%'
                        OR subject LIKE '68%' OR subject LIKE '8%' OR subject LIKE '4%'
                   THEN 1 ELSE 0 END) AS looks_like_stock_code,
               COUNT(*) AS rows FROM forecast_decisions WHERE scope='stock'""")
show("first 12 distinct stock subjects",
     "SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock' ORDER BY subject LIMIT 12")
show("first 12 distinct sector subjects",
     "SELECT DISTINCT subject FROM forecast_decisions WHERE scope='sector' ORDER BY subject LIMIT 12")

print("\n=== ATTACK 2: fold inflation SURVIVING the policy (sector data_version is a timestamp) ===")
show("sector: canonical folds vs distinct TRADING DAYS",
     f"""WITH {CTE}
     SELECT COUNT(DISTINCT d.decision_id) AS canonical_folds,
            COUNT(DISTINCT substr(d.decision_cutoff,1,10)) AS distinct_cutoff_days,
            MIN(substr(d.decision_cutoff,1,10)) AS first_day,
            MAX(substr(d.decision_cutoff,1,10)) AS last_day
     FROM forecast_decisions d JOIN canonical cs
       ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
     WHERE d.scope='sector'""")
show("sector canonical folds per cutoff day",
     f"""WITH {CTE}
     SELECT substr(d.decision_cutoff,1,10) AS day, COUNT(DISTINCT d.decision_id) AS folds
     FROM forecast_decisions d JOIN canonical cs
       ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
     WHERE d.scope='sector' GROUP BY day ORDER BY day""")
show("stock canonical folds per cutoff day",
     f"""WITH {CTE}
     SELECT substr(d.decision_cutoff,1,10) AS day, COUNT(DISTINCT d.decision_id) AS folds
     FROM forecast_decisions d JOIN canonical cs
       ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
     WHERE d.scope='stock' GROUP BY day ORDER BY day""")

print("\n=== ATTACK 3: do production filters (review_only/decision_cutoff/available_at/observed_at) change anything? ===")
show("filter sensitivity at as_of=2026-09-05T00:00:00Z (confirmed+inferred, stock h=5)",
     f"""WITH {CTE}
     SELECT COUNT(*) AS rows_no_filter,
            SUM(CASE WHEN d.review_only=1 THEN 1 ELSE 0 END) AS pass_review_only,
            SUM(CASE WHEN d.decision_cutoff<='2026-09-05T00:00:00Z' THEN 1 ELSE 0 END) AS pass_cutoff,
            SUM(CASE WHEN d.available_at<='2026-09-05T00:00:00Z' THEN 1 ELSE 0 END) AS pass_available,
            SUM(CASE WHEN o.id IS NOT NULL THEN 1 ELSE 0 END) AS matured_any,
            SUM(CASE WHEN o.observed_at<='2026-09-05T00:00:00Z' THEN 1 ELSE 0 END) AS matured_observed_in_time
     FROM forecast_decisions d JOIN canonical cs
       ON cs.decision_id=d.decision_id AND cs.scope=d.scope AND cs.data_version=d.data_version
     LEFT JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope
       AND o.subject=d.subject AND o.horizon_days=d.horizon_days
     WHERE d.scope='stock' AND d.horizon_days=5""")

print("\n=== ATTACK 4: available_at vs decision_cutoff sanity (lookahead) ===")
show("rows where available_at < decision_cutoff",
     """SELECT scope, COUNT(*) AS n FROM forecast_decisions
        WHERE available_at < decision_cutoff GROUP BY scope""")

print("\n=== ATTACK 5: the 746 legacy evaluations ===")
show("evaluations by scope/status and policy version col presence",
     """SELECT scope, status, COUNT(*) AS n, MIN(created_at) AS mn, MAX(created_at) AS mx,
               MAX(fold_count) AS max_folds, MAX(sample_count) AS max_samples
        FROM forecast_evaluations GROUP BY scope,status ORDER BY scope,status""")
print("   columns:", [r[1] for r in c.execute("PRAGMA table_info(forecast_evaluations)")])
con.close()
