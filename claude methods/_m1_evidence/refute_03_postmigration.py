import sqlite3, sys, os
sys.path.insert(0, r"D:\codex-A股交易\backend")
from app.forecasting.canonical import canonical_snapshot_cte
CTE = canonical_snapshot_cte()

SRC = r"D:\codex-A股交易\trading_local.sqlite3"
TMP = r"D:\codex-A股交易\claude methods\_m1_evidence\refute_replica.sqlite3"
if os.path.exists(TMP): os.remove(TMP)

src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True); src.row_factory = sqlite3.Row
rep = sqlite3.connect(TMP)

# copy schema+data for only the forecast tables (scratch replica, prod untouched)
for t in ("forecast_decisions", "forecast_decision_days", "forecast_outcomes"):
    ddl = src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone()[0]
    rep.execute(ddl)
    rows = src.execute(f"SELECT * FROM {t}").fetchall()
    if rows:
        cols = rows[0].keys()
        rep.executemany(
            f"INSERT INTO {t}({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
            [tuple(r[c] for c in cols) for r in rows])
rep.commit()
rep.row_factory = sqlite3.Row

def canon(tag):
    try:
        rows = rep.execute(f"WITH {CTE} SELECT scope,data_version,decision_id,selection_kind FROM canonical ORDER BY scope,data_version").fetchall()
        kinds = {}
        for r in rows: kinds[r["selection_kind"]] = kinds.get(r["selection_kind"],0)+1
        print(f"{tag}: {len(rows)} canonical snapshots  {kinds}")
        return rows
    except sqlite3.Error as e:
        print(f"{tag}: FAIL {e}")
        return None

print("--- A. replica as-is (pre-migration, mirrors prod) ---")
canon("pre-migration")

print("\n--- B. apply _migrate_decision_day_run_kind verbatim (legacy_unknown) ---")
rep.execute("""CREATE TABLE fdd__m (scope TEXT NOT NULL, data_version TEXT NOT NULL,
 decision_id TEXT NOT NULL, claimed_at TEXT NOT NULL, candidate_count INTEGER NOT NULL,
 recorded_count INTEGER NOT NULL, run_kind TEXT NOT NULL
 CHECK(run_kind IN ('scheduled','manual','replay','challenger','legacy_unknown')),
 PRIMARY KEY(scope,data_version))""")
rep.execute("""INSERT INTO fdd__m SELECT scope,data_version,decision_id,claimed_at,
 candidate_count,recorded_count,'legacy_unknown' FROM forecast_decision_days""")
rep.execute("DROP TABLE forecast_decision_days")
rep.execute("ALTER TABLE fdd__m RENAME TO forecast_decision_days")
rep.commit()
post = canon("post-migration")

print("\n--- C. counterfactual: if that row were run_kind='scheduled' ---")
rep.execute("UPDATE forecast_decision_days SET run_kind='scheduled'")
sched = canon("if-scheduled")

print("\n--- D. which vintage differs between B and C ---")
pb = {(r["scope"],r["data_version"]) for r in post}
pc = {(r["scope"],r["data_version"]) for r in sched}
print("lost under legacy_unknown:", sorted(pc-pb))

print("\n--- E. the guarded vintage's shape vs its claim ---")
for r in rep.execute("""
 SELECT d.scope,d.data_version,d.decision_id,
   COUNT(DISTINCT d.subject) subj, COUNT(DISTINCT d.horizon_days) hz, COUNT(*) rows
 FROM forecast_decisions d WHERE d.scope='stock' AND d.data_version='2026-09-03'
 GROUP BY d.scope,d.data_version,d.decision_id ORDER BY d.decision_id"""):
    print(" ", dict(r))
print("  claim:", dict(rep.execute("SELECT * FROM forecast_decision_days").fetchone()))

print("\n--- F. how much labelled data sits under the guarded vintage ---")
for r in rep.execute("""
 SELECT COUNT(*) decisions, COUNT(DISTINCT d.decision_id) snapshots
 FROM forecast_decisions d WHERE d.scope='stock' AND d.data_version='2026-09-03'"""):
    print("  ", dict(r))
for r in rep.execute("""
 SELECT COUNT(*) matured_outcomes FROM forecast_decisions d
 JOIN forecast_outcomes o ON o.decision_id=d.decision_id AND o.scope=d.scope
   AND o.subject=d.subject AND o.horizon_days=d.horizon_days
 WHERE d.scope='stock' AND d.data_version='2026-09-03'"""):
    print("  ", dict(r))

print("\n--- G. total distinct vintages present in forecast_decisions ---")
print("  ", dict(rep.execute("SELECT COUNT(*) vintages FROM (SELECT DISTINCT scope,data_version FROM forecast_decisions)").fetchone()))
rep.close(); src.close()
