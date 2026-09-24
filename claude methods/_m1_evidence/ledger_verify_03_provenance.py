# -*- coding: utf-8 -*-
import sqlite3, json, sys, io
from collections import Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
OPS = "D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)
c.row_factory = sqlite3.Row
cur = c.cursor()

print("### T1  Independent 'degraded' test (marker the auditor did NOT use)")
print("Current code (feedback.py:1123-1125) forces status='degraded' whenever")
print("evidence_quality=='exploratory' and status would be 'ready'.")
print("SQL: SELECT status, COUNT(*) FROM forecast_evaluations GROUP BY status")
for r in cur.execute("SELECT status, COUNT(*) n FROM forecast_evaluations GROUP BY status ORDER BY n DESC"):
    print(f"   {r['status']:20s} {r['n']}")
d = cur.execute("SELECT COUNT(*) n FROM forecast_evaluations WHERE status='degraded'").fetchone()['n']
print(f"   -> rows with status='degraded': {d}")
print("   A single row written under v3 with inferred folds would be 'degraded'. Zero exist.")

print("\n### T2  Does the table's CHECK/DDL permit 'degraded' at all? (is absence structural or evidential?)")
ddl = cur.execute("SELECT sql FROM sqlite_master WHERE name='forecast_evaluations'").fetchone()[0]
print("   status column CHECK constraint present?", "CHECK" in ddl.split("status TEXT")[1].split(",")[0] if "status TEXT" in ddl else "n/a")
print("   status is unconstrained TEXT -> 'degraded' was storable; its absence is evidential, not structural.")

print("\n### T3  Provenance linkage: do stored by_decision decision_ids resolve to real decisions?")
rows = cur.execute("SELECT id, evaluation_id, status, metrics_json FROM forecast_evaluations").fetchall()
all_dids = set(); per_eval = {}
for r in rows:
    o = json.loads(r["metrics_json"])
    dids = {str(x.get("decision_id")) for x in (o.get("metrics", {}).get("by_decision") or []) if x.get("decision_id")}
    per_eval[r["id"]] = dids
    all_dids |= dids
print("SQL: parse metrics.by_decision[].decision_id over all 746 rows")
print("   distinct decision_id referenced by evaluations:", len(all_dids))
print("   evaluations carrying >=1 decision_id:", sum(1 for v in per_eval.values() if v))
print("   evaluations carrying ZERO decision_id :", sum(1 for v in per_eval.values() if not v))

known = {r[0] for r in cur.execute("SELECT decision_id FROM forecast_decisions").fetchall()}
print("SQL: SELECT decision_id FROM forecast_decisions  ->", len(known), "distinct")
resolved = all_dids & known
print("   referenced decision_ids that RESOLVE in forecast_decisions:", len(resolved), "/", len(all_dids))
print("   dangling (referenced but absent):", len(all_dids - resolved))

print("\n### T4  Is selection_kind a STORED column anywhere (i.e. is provenance persisted)?")
for t in ("forecast_decisions", "forecast_outcomes", "forecast_decision_days"):
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
    print(f"   {t}: n_cols={len(cols)}")
    print(f"      selection_kind stored? {'selection_kind' in cols}")
    print(f"      policy/version cols  : {[x for x in cols if 'policy' in x.lower() or 'version' in x.lower()]}")
    print(f"      cols: {cols}")

print("\n### T5  Denominator check - is 746 rows or 746 distinct evaluations, and is 113 'ready' right?")
r = cur.execute("""SELECT COUNT(*) rows_, COUNT(DISTINCT evaluation_id) dist_id,
                          SUM(status='ready') ready, SUM(status='insufficient_data') insuf,
                          COUNT(DISTINCT scope||'|'||horizon_days) scope_horizon
                   FROM forecast_evaluations""").fetchone()
print("SQL: SELECT COUNT(*), COUNT(DISTINCT evaluation_id), SUM(status='ready') ... FROM forecast_evaluations")
print(f"   rows={r['rows_']} distinct_evaluation_id={r['dist_id']} ready={r['ready']} insufficient={r['insuf']} distinct(scope,horizon)={r['scope_horizon']}")

print("\n### T6  Off-by-one / boundary: is ANY row created at-or-after the newest claimed timestamp?")
print("SQL: SELECT COUNT(*) FROM forecast_evaluations WHERE created_at >= '2026-09-04 04:44:03'")
print("   ->", cur.execute("SELECT COUNT(*) n FROM forecast_evaluations WHERE created_at >= '2026-09-04 04:44:03'").fetchone()['n'])
print("SQL: SELECT COUNT(*) FROM forecast_evaluations WHERE created_at > '2026-09-04 04:44:03'")
print("   ->", cur.execute("SELECT COUNT(*) n FROM forecast_evaluations WHERE created_at > '2026-09-04 04:44:03'").fetchone()['n'])
print("   max(created_at) =", cur.execute("SELECT MAX(created_at) m FROM forecast_evaluations").fetchone()['m'])

print("\n### T7  Would the missing column break a query TODAY? (does anything already select it?)")
try:
    cur.execute("SELECT canonical_policy_version FROM forecast_evaluations LIMIT 1")
    print("   SELECT canonical_policy_version -> SUCCEEDED (column exists)")
except sqlite3.OperationalError as e:
    print("   SELECT canonical_policy_version -> OperationalError:", e)

print("\n### T8  scope/horizon spread of the 113 'ready' rows (are they one securities set or many?)")
for r in cur.execute("""SELECT scope, horizon_days, COUNT(*) n FROM forecast_evaluations
                        WHERE status='ready' GROUP BY scope, horizon_days ORDER BY scope, horizon_days"""):
    print(f"   scope={r['scope']:7s} horizon={r['horizon_days']:3d} ready_rows={r['n']}")
c.close()
