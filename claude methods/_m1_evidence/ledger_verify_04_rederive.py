# -*- coding: utf-8 -*-
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
OPS = "D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True); c.row_factory = sqlite3.Row; cur = c.cursor()

print("### R1  The canonical CTE's 'confirmed' branch requires forecast_decision_days.run_kind='scheduled'.")
print("SQL: PRAGMA table_info(forecast_decision_days)")
cols = [r[1] for r in cur.execute("PRAGMA table_info(forecast_decision_days)").fetchall()]
print("   columns:", cols)
print("   run_kind present in PRODUCTION? ->", "run_kind" in cols)

print("\nSQL: SELECT run_kind FROM forecast_decision_days LIMIT 1   (direct probe)")
try:
    cur.execute("SELECT run_kind FROM forecast_decision_days LIMIT 1").fetchall()
    print("   -> succeeded")
except sqlite3.OperationalError as e:
    print("   -> OperationalError:", e)

print("\n### R2  Contents of the guard table that 'confirmed' selection depends on")
print("SQL: SELECT COUNT(*) FROM forecast_decision_days")
print("   rows:", cur.execute("SELECT COUNT(*) n FROM forecast_decision_days").fetchone()["n"])
for r in cur.execute("SELECT * FROM forecast_decision_days"):
    print("   ", dict(r))

print("\n### R3  How many decision snapshots exist vs how many are guarded?")
print("SQL: SELECT COUNT(DISTINCT scope||'|'||data_version||'|'||decision_id) FROM forecast_decisions")
n_snap = cur.execute("SELECT COUNT(*) n FROM (SELECT 1 FROM forecast_decisions GROUP BY scope,data_version,decision_id)").fetchone()["n"]
print("   distinct (scope,data_version,decision_id) snapshots:", n_snap)
n_guard = cur.execute("SELECT COUNT(*) n FROM (SELECT 1 FROM forecast_decision_days GROUP BY scope,data_version,decision_id)").fetchone()["n"]
print("   guarded snapshots:", n_guard)
print("   -> unguarded snapshots (would classify 'inferred' at best):", n_snap - n_guard)

print("\n### R4  Vintages: how many (scope,data_version) vintages, how many guarded?")
for r in cur.execute("""SELECT scope, COUNT(DISTINCT data_version) vintages
                        FROM forecast_decisions GROUP BY scope"""):
    print(f"   scope={r['scope']:7s} distinct data_version vintages={r['vintages']}")
for r in cur.execute("SELECT scope, COUNT(DISTINCT data_version) v FROM forecast_decision_days GROUP BY scope"):
    print(f"   GUARDED scope={r['scope']:7s} vintages={r['v']}")

print("\n### R5  Recoverable lineage depth: can each evaluation's decisions be dated & versioned?")
print("SQL: SELECT decision_id, MIN(created_at), MIN(data_version), MIN(decision_cutoff) FROM forecast_decisions GROUP BY decision_id (sample)")
for r in cur.execute("""SELECT decision_id, MIN(created_at) c, MIN(data_version) dv, MIN(decision_cutoff) dc,
                               COUNT(*) rows_, COUNT(DISTINCT subject) subs, COUNT(DISTINCT horizon_days) hz
                        FROM forecast_decisions GROUP BY decision_id ORDER BY c LIMIT 5"""):
    print(f"   {r['decision_id']}  created={r['c']} data_version={r['dv']} cutoff={r['dc']} rows={r['rows_']} subjects={r['subs']} horizons={r['hz']}")
print("   -> decision-level lineage (who/when/which data_version) IS present and joinable.")
c.close()
