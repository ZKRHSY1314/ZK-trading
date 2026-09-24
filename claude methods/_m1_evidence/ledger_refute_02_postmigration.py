import os, sqlite3, sys
# Point every possible config at a throwaway path so nothing can touch production.
SCRATCH = r"C:/Users/Administrator/AppData/Local/Temp/claude/never_created.sqlite3"
os.environ["DATABASE_PATH"] = SCRATCH
os.environ["ENABLE_LIVE_TRADING"] = "false"
sys.path.insert(0, r"D:/codex-A股交易/backend")
from app.forecasting.canonical import canonical_snapshot_cte, CANONICAL_POLICY_VERSION
from app.forecasting.ledger import FORECAST_HORIZONS
print("FORECAST_HORIZONS =", sorted(FORECAST_HORIZONS), " policy =", CANONICAL_POLICY_VERSION)
assert not os.path.exists(SCRATCH), "scratch db must not exist"

SRC = r"D:/codex-A股交易/trading_local.sqlite3"
src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)

mem = sqlite3.connect(":memory:")
mem.row_factory = sqlite3.Row
mem.execute("""CREATE TABLE forecast_decisions(
    id INTEGER, decision_id TEXT, scope TEXT, subject TEXT, decision_cutoff TEXT,
    available_at TEXT, horizon_days INTEGER, rank INTEGER, score REAL,
    probability REAL, data_version TEXT, review_only INTEGER)""")
rows = src.execute("""SELECT id, decision_id, scope, subject, decision_cutoff, available_at,
                             horizon_days, rank, score, probability, data_version, review_only
                      FROM forecast_decisions""").fetchall()
mem.executemany("INSERT INTO forecast_decisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", rows)
print(f"copied forecast_decisions: {len(rows):,}")

dd = src.execute("SELECT scope, data_version, decision_id, claimed_at, candidate_count, recorded_count "
                 "FROM forecast_decision_days").fetchall()
src.close()

def build_dd(run_kind_value):
    mem.execute("DROP TABLE IF EXISTS forecast_decision_days")
    mem.execute("""CREATE TABLE forecast_decision_days(
        scope TEXT, data_version TEXT, decision_id TEXT, claimed_at TEXT,
        candidate_count INTEGER, recorded_count INTEGER, run_kind TEXT)""")
    mem.executemany("INSERT INTO forecast_decision_days VALUES(?,?,?,?,?,?,?)",
                    [tuple(r) + (run_kind_value,) for r in dd])

CTE = canonical_snapshot_cte()
Q = (f"WITH {CTE} SELECT scope, data_version, decision_id, selection_kind "
     "FROM canonical ORDER BY scope, data_version")

for label, rk in (("AFTER real migration (run_kind='legacy_unknown', what init() writes)", "legacy_unknown"),
                  ("COUNTERFACTUAL (run_kind='scheduled')", "scheduled")):
    build_dd(rk)
    out = mem.execute(Q).fetchall()
    print("\n" + "="*78)
    print(label)
    print(f"  canonical snapshots selected: {len(out)}")
    kinds = {}
    for r in out:
        kinds[r["selection_kind"]] = kinds.get(r["selection_kind"], 0) + 1
    print(f"  by selection_kind: {kinds}")
    guarded = [r for r in out if (r["scope"], r["data_version"]) == ("stock", "2026-09-03")]
    print(f"  guarded vintage (stock,2026-09-03) present in canonical? {bool(guarded)}"
          + (f" -> {dict(guarded[0])}" if guarded else ""))
    # how many decision rows survive the canonical join
    n = mem.execute(f"WITH {CTE} SELECT COUNT(*) FROM forecast_decisions d "
                    "JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope "
                    "AND cs.data_version=d.data_version").fetchone()[0]
    nconf = mem.execute(f"WITH {CTE} SELECT COUNT(*) FROM forecast_decisions d "
                        "JOIN canonical cs ON cs.decision_id=d.decision_id AND cs.scope=d.scope "
                        "AND cs.data_version=d.data_version WHERE cs.selection_kind='confirmed'").fetchone()[0]
    print(f"  forecast_decisions rows surviving canonical join: {n:,} (confirmed-only: {nconf:,}) of {len(rows):,}")

# baseline context
build_dd("legacy_unknown")
tot_v = mem.execute("SELECT COUNT(*) FROM (SELECT DISTINCT scope,data_version FROM forecast_decisions)").fetchone()[0]
tot_d = mem.execute("SELECT COUNT(DISTINCT decision_id) FROM forecast_decisions").fetchone()[0]
print("\n" + "="*78)
print(f"universe: distinct (scope,data_version) vintages = {tot_v}; distinct decision_id = {tot_d}")
for r in mem.execute("SELECT scope, COUNT(DISTINCT data_version) v, COUNT(DISTINCT decision_id) d, COUNT(*) n "
                     "FROM forecast_decisions GROUP BY scope"):
    print(f"  scope={r['scope']}: vintages={r['v']} decision_ids={r['d']} rows={r['n']:,}")
# the guarded vintage's own rows
for r in mem.execute("SELECT decision_id, COUNT(DISTINCT subject) subs, COUNT(DISTINCT horizon_days) hz, COUNT(*) n "
                     "FROM forecast_decisions WHERE scope='stock' AND data_version='2026-09-03' "
                     "GROUP BY decision_id ORDER BY decision_id"):
    print(f"  [stock/2026-09-03] {r['decision_id']} subjects={r['subs']} horizons={r['hz']} rows={r['n']}")
