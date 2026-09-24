import sqlite3, sys
sys.path.insert(0, r"D:\codex-A股交易\backend")
from app.forecasting.canonical import canonical_snapshot_cte
CTE = canonical_snapshot_cte()
rep = sqlite3.connect(r"D:\codex-A股交易\claude methods\_m1_evidence\refute_replica.sqlite3")
rep.row_factory = sqlite3.Row
# replica currently has run_kind='scheduled' from step C; reset to legacy_unknown (true post-migration state)
rep.execute("UPDATE forecast_decision_days SET run_kind='legacy_unknown'"); rep.commit()

canon = {(r["scope"],r["data_version"]) for r in rep.execute(
    f"WITH {CTE} SELECT scope,data_version FROM canonical")}
allv = {(r["scope"],r["data_version"]) for r in rep.execute(
    "SELECT DISTINCT scope,data_version FROM forecast_decisions")}
print("total vintages:", len(allv), " canonical post-migration:", len(canon))
print("vintages with NO canonical snapshot:", sorted(allv-canon))
guarded = {(r["scope"],r["data_version"]) for r in rep.execute("SELECT scope,data_version FROM forecast_decision_days")}
print("guarded vintages:", sorted(guarded))
for v in sorted(allv-canon):
    print(f"\n  vintage {v}  guarded={v in guarded}")
    for r in rep.execute("""SELECT decision_id, COUNT(DISTINCT subject) subj,
      COUNT(DISTINCT horizon_days) hz, COUNT(*) rows FROM forecast_decisions
      WHERE scope=? AND data_version=? GROUP BY decision_id ORDER BY decision_id LIMIT 12""", v):
        print("    ", dict(r))

# how many of the 746 legacy evaluations could be attributed post-migration
src = sqlite3.connect(r"file:D:\codex-A股交易\trading_local.sqlite3?mode=ro", uri=True)
print("\nforecast_evaluations rows:", src.execute("SELECT COUNT(*) FROM forecast_evaluations").fetchone()[0],
      "-> all would carry canonical_policy_version=NULL (column does not exist yet)")
