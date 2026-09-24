import os, sqlite3, sys
os.environ["DATABASE_PATH"] = r"C:/Users/Administrator/AppData/Local/Temp/claude/never_created.sqlite3"
sys.path.insert(0, r"D:/codex-A股交易/backend")
from app.forecasting.canonical import canonical_snapshot_cte
CTE = canonical_snapshot_cte()

src = sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro", uri=True)
mem = sqlite3.connect(":memory:"); mem.row_factory = sqlite3.Row
mem.execute("""CREATE TABLE forecast_decisions(id INTEGER, decision_id TEXT, scope TEXT, subject TEXT,
 decision_cutoff TEXT, available_at TEXT, horizon_days INTEGER, rank INTEGER, score REAL,
 probability REAL, data_version TEXT, review_only INTEGER)""")
mem.executemany("INSERT INTO forecast_decisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
  src.execute("""SELECT id,decision_id,scope,subject,decision_cutoff,available_at,horizon_days,rank,
                        score,probability,data_version,review_only FROM forecast_decisions""").fetchall())
dd = src.execute("SELECT scope,data_version,decision_id,claimed_at,candidate_count,recorded_count "
                 "FROM forecast_decision_days").fetchall()
src.close()
mem.execute("""CREATE TABLE forecast_decision_days(scope TEXT,data_version TEXT,decision_id TEXT,
 claimed_at TEXT,candidate_count INTEGER,recorded_count INTEGER,run_kind TEXT)""")
# exactly what _migrate_decision_day_run_kind writes for pre-existing rows
mem.executemany("INSERT INTO forecast_decision_days VALUES(?,?,?,?,?,?,'legacy_unknown')",
                [tuple(r) for r in dd])

print("POST-init() state -- the default read-path filter (cs.selection_kind='confirmed' OR ?=1)")
for scope in ("stock", "sector"):
    for flag, label in ((0, "include_inferred=False  <-- DEFAULT everywhere"), (1, "include_inferred=True")):
        n = mem.execute(f"""WITH {CTE} SELECT COUNT(*) FROM forecast_decisions d
            JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope
             AND cs.data_version=d.data_version
            WHERE d.scope=? AND d.review_only=1 AND (cs.selection_kind='confirmed' OR ?=1)""",
            (scope, flag)).fetchone()[0]
        tot = mem.execute("SELECT COUNT(*) FROM forecast_decisions WHERE scope=? AND review_only=1",
                          (scope,)).fetchone()[0]
        print(f"  scope={scope:6s} {label:38s} -> {n:6,} rows of {tot:,} review_only rows")
