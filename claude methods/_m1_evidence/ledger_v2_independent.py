"""Independent reimplementation of the canonical policy in pure Python.
Read-only. Does NOT reuse canonical_snapshot_cte(); rebuilt from the documented
rules in backend/app/forecasting/canonical.py docstring so a SQL bug in the CTE
would show up as a disagreement."""
import sqlite3
from collections import defaultdict

P = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{P}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
c = con.cursor()

REQUIRED_STOCK_HORIZONS = {1, 3, 5, 10, 20}   # FORECAST_HORIZONS

# ---- load raw ----
SQL_SHAPE = """
SELECT scope, data_version, decision_id,
       MIN(decision_cutoff) AS snapshot_cutoff,
       COUNT(DISTINCT subject) AS subject_count,
       COUNT(DISTINCT horizon_days) AS horizon_count,
       COUNT(DISTINCT CASE WHEN horizon_days IN (1,3,5,10,20) THEN horizon_days END)
           AS required_horizon_count,
       COUNT(*) AS row_count
FROM forecast_decisions
GROUP BY scope, data_version, decision_id
"""
shapes = [dict(r) for r in c.execute(SQL_SHAPE)]
guards = {(r["scope"], r["data_version"]): dict(r)
          for r in c.execute("SELECT * FROM forecast_decision_days")}

print(f"snapshots(scope,data_version,decision_id) = {len(shapes)}")
print(f"guard records                            = {len(guards)}")

def select_canonical(guard_run_kind):
    """guard_run_kind: what run_kind the migration/counterfactual assigns."""
    by_vintage = defaultdict(list)
    for s in shapes:
        by_vintage[(s["scope"], s["data_version"])].append(s)

    chosen = {}
    for vintage, snaps in by_vintage.items():
        eligible = []
        g = guards.get(vintage)
        if g is not None:
            # Rule 1/2: guarded vintage is decided SOLELY by the guard.
            if g["recorded_count"] > 0 and guard_run_kind == "scheduled":
                for s in snaps:
                    if (s["decision_id"] == g["decision_id"]
                            and s["subject_count"] == g["candidate_count"]
                            and s["row_count"] == g["recorded_count"]
                            and s["row_count"] == s["subject_count"] * s["horizon_count"]
                            and (s["scope"] != "stock"
                                 or s["required_horizon_count"] == len(REQUIRED_STOCK_HORIZONS))):
                        eligible.append((s, "confirmed"))
            # recorded_count==0 or non-scheduled -> nothing, and NO shape fallback.
        else:
            # Rule 3: unguarded -> infer by shape.
            max_sub = max(s["subject_count"] for s in snaps)
            max_hz = max(s["horizon_count"] for s in snaps)
            for s in snaps:
                if (s["subject_count"] == max_sub and s["horizon_count"] == max_hz
                        and s["row_count"] == s["subject_count"] * s["horizon_count"]):
                    eligible.append((s, "inferred"))
        if eligible:
            eligible.sort(key=lambda t: (t[0]["snapshot_cutoff"], t[0]["decision_id"]))
            s, kind = eligible[0]
            chosen[vintage] = (s["decision_id"], kind)
    return chosen

for run_kind in ("legacy_unknown", "scheduled"):
    chosen = select_canonical(run_kind)
    tally = defaultdict(int)
    for (scope, dv), (did, kind) in chosen.items():
        tally[(scope, kind)] += 1
    print(f"\n=== guard run_kind = {run_kind!r} ===")
    print(f"  canonical snapshots total = {len(chosen)}")
    for key in sorted(tally):
        print(f"    {key[0]:6s} / {key[1]:14s} = {tally[key]}")

    # ---- matured-sample accounting, MY OWN join via EXISTS (not LEFT JOIN) ----
    for kind_filter, label in ((("confirmed",), "confirmed ONLY (official)"),
                               (("confirmed", "inferred"), "confirmed+inferred (exploratory)")):
        keep = {did for (did, k) in chosen.values() if k in kind_filter}
        if not keep:
            print(f"  [{label}] -> NO canonical decision_ids at all")
            continue
        marks = ",".join("?" * len(keep))
        rows = c.execute(f"""
            SELECT d.scope, d.horizon_days,
                   COUNT(DISTINCT d.decision_id) AS folds,
                   COUNT(*) AS decision_rows,
                   COUNT(DISTINCT d.subject) AS distinct_subjects,
                   SUM(CASE WHEN EXISTS (
                         SELECT 1 FROM forecast_outcomes o
                          WHERE o.decision_id = d.decision_id AND o.scope = d.scope
                            AND o.subject = d.subject AND o.horizon_days = d.horizon_days
                       ) THEN 1 ELSE 0 END) AS matured_samples,
                   SUM(CASE WHEN d.review_only=1 THEN 1 ELSE 0 END) AS review_only_rows
            FROM forecast_decisions d
            WHERE d.decision_id IN ({marks})
            GROUP BY d.scope, d.horizon_days
            ORDER BY d.scope, d.horizon_days
        """, tuple(keep)).fetchall()
        print(f"  [{label}] decision_ids kept = {len(keep)}")
        for r in rows:
            print("     ", dict(r))
con.close()
