import sqlite3, sys
sys.path.insert(0, r"D:/codex-A股交易/backend")
db = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True); con.row_factory = sqlite3.Row
def q(label, sql, p=()):
    print("\n### " + label); print("SQL: " + " ".join(sql.split()))
    try:
        rows = con.execute(sql, p).fetchall()
    except Exception as e:
        print("   !! SQL ERROR:", e); return []
    for r in rows[:30]: print("   ", dict(r))
    if len(rows) > 30: print(f"    ... {len(rows)} rows total")
    return rows

print("### M0 forecast_decision_days columns actually on disk")
print("   ", [r["name"] for r in con.execute("PRAGMA table_info(forecast_decision_days)")])

# Can their canonical CTE run against the live DB at all?
from app.forecasting.canonical import canonical_snapshot_cte
q("M1 canonical CTE executed read-only against the live DB",
  f"WITH {canonical_snapshot_cte()} SELECT scope, data_version, decision_id, selection_kind FROM canonical ORDER BY scope, data_version")

# Would the single guard row qualify as CONFIRMED, ignoring run_kind?
q("M2 guard row vs its snapshot shape (run_kind ignored)", """
SELECT c.scope, c.data_version, c.decision_id, c.candidate_count, c.recorded_count,
       s.subject_count, s.horizon_count, s.row_count,
       CASE WHEN s.subject_count=c.candidate_count AND s.row_count=c.recorded_count
             AND s.row_count=s.subject_count*s.horizon_count THEN 'shape_matches' ELSE 'MISMATCH' END AS verdict
FROM forecast_decision_days c
JOIN (SELECT scope,data_version,decision_id,COUNT(DISTINCT subject) subject_count,
             COUNT(DISTINCT horizon_days) horizon_count, COUNT(*) row_count
      FROM forecast_decisions GROUP BY scope,data_version,decision_id) s
  ON s.scope=c.scope AND s.data_version=c.data_version AND s.decision_id=c.decision_id""")

# SECTOR: is there any re-recording inflation at all?
q("N1 sector snapshots per vintage", """
SELECT COUNT(*) AS vintages, MAX(snaps) AS max_snapshots_per_vintage, SUM(snaps) AS total_snaps
FROM (SELECT data_version, COUNT(DISTINCT decision_id) AS snaps
      FROM forecast_decisions WHERE scope='sector' GROUP BY data_version)""")

# Inflation factor for EVERY ready row, my own dedup rule (earliest snapshot per vintage)
print("\n### O1 inflation factor for all 113 'ready' rows (my own earliest-per-vintage dedup)")
SQL_ONE = """
WITH firstsnap AS (
  SELECT scope, data_version, decision_id FROM (
    SELECT scope, data_version, decision_id,
           ROW_NUMBER() OVER (PARTITION BY scope, data_version
                              ORDER BY MIN(decision_cutoff), decision_id) AS rn
    FROM forecast_decisions GROUP BY scope, data_version, decision_id) WHERE rn=1)
SELECT COUNT(*) AS dedup_sample, COUNT(DISTINCT d.decision_id) AS dedup_fold
FROM forecast_decisions d
JOIN firstsnap f ON f.scope=d.scope AND f.data_version=d.data_version AND f.decision_id=d.decision_id
JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope
     AND o.subject=d.subject AND o.horizon_days=d.horizon_days AND o.observed_at <= ?
WHERE d.scope=? AND d.review_only=1 AND d.horizon_days=?
  AND d.decision_cutoff <= ? AND d.available_at <= ?
"""
rows = con.execute("""SELECT evaluation_id, as_of, scope, horizon_days, sample_count, fold_count
                      FROM forecast_evaluations WHERE status='ready'
                      ORDER BY scope, horizon_days, as_of""").fetchall()
print("   (per-row SQL:", " ".join(SQL_ONE.split()), ")")
worst_f = worst_s = 0.0; worst_row = None; agg = {}
for r in rows:
    d = con.execute(SQL_ONE, (r["as_of"], r["scope"], r["horizon_days"], r["as_of"], r["as_of"])).fetchone()
    ds, df = d["dedup_sample"], d["dedup_fold"]
    fs = r["sample_count"]/ds if ds else float('inf')
    ff = r["fold_count"]/df if df else float('inf')
    key = (r["scope"], r["horizon_days"], r["sample_count"], r["fold_count"], ds, df)
    agg[key] = agg.get(key, 0) + 1
    if ff > worst_f: worst_f, worst_s, worst_row = ff, fs, (r["scope"], r["horizon_days"], r["as_of"], r["sample_count"], r["fold_count"], ds, df)
for k, n in sorted(agg.items()):
    sc, h, ss, sf, ds, df = k
    print(f"   {sc:6s} h={h:<3d} stored {ss:>5d}/{sf:<4d}  dedup {ds:>4d}/{df:<3d}  "
          f"x{ss/ds if ds else 0:.2f} sample  x{sf/df if df else 0:.2f} fold   ({n} rows)")
print("   WORST fold inflation:", worst_row, f"-> fold x{worst_f:.2f}, sample x{worst_s:.2f}")

# min_folds / min_samples thresholds
con.close()
