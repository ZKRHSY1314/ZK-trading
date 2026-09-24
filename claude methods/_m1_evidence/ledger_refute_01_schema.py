import sqlite3, os
ROOT = r"D:/codex-A股交易/trading_local.sqlite3"
BACKEND = r"D:/codex-A股交易/backend/trading_local.sqlite3"

def cols(con, t):
    return [r[1] for r in con.execute(f"PRAGMA table_info({t})")]

for label, path in (("ROOT(production per config.py)", ROOT), ("backend/ (stale leftover)", BACKEND)):
    print("="*78)
    print(f"{label}\n  {path}  size={os.path.getsize(path):,} bytes")
    for sidecar in ("-wal", "-shm"):
        p = path + sidecar
        print(f"  sidecar {sidecar}: {'EXISTS size='+str(os.path.getsize(p)) if os.path.exists(p) else 'absent'}")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    for t in ("forecast_decision_days", "forecast_evaluations", "forecast_decisions"):
        c = cols(con, t)
        if not c:
            print(f"  {t}: TABLE ABSENT"); continue
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: rows={n:,} cols={c}")
    # my own independent probe -- NOT their CTE, just the single predicate
    for probe in ("SELECT COUNT(*) FROM forecast_decision_days c WHERE c.run_kind='scheduled'",
                  "SELECT COUNT(*) FROM forecast_evaluations WHERE canonical_policy_version IS NOT NULL"):
        try:
            print(f"  PROBE OK  {probe} -> {con.execute(probe).fetchone()[0]}")
        except sqlite3.OperationalError as e:
            print(f"  PROBE ERR {probe} -> OperationalError: {e}")
    # what the one decision-day row actually is
    if cols(con, "forecast_decision_days"):
        for r in con.execute("SELECT * FROM forecast_decision_days"):
            print("  decision_day row:", dict(r))
    con.close()

# schema-as-declared for a FRESH db (does CREATE TABLE already carry run_kind?)
import re, sys
sys.path.insert(0, r"D:/codex-A股交易/backend")
src = open(r"D:/codex-A股交易/backend/app/storage/sqlite_store.py", encoding="utf-8").read()
m = re.search(r"CREATE TABLE IF NOT EXISTS forecast_decision_days\((.*?)\);", src, re.S)
print("="*78)
print("SCHEMA constant, forecast_decision_days CREATE body:")
print(m.group(1) if m else "NOT FOUND")
