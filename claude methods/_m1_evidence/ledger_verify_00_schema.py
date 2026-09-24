import sqlite3, json
OP = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()
for t in ("forecast_decisions","forecast_outcomes","forecast_evaluations","forecast_decision_days"):
    print("="*100)
    print("TABLE", t)
    r = cur.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()
    print(r["sql"] if r else "MISSING")
    print("-- indexes:")
    for i in cur.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND tbl_name=?", (t,)):
        print("   ", i["name"], "|", i["sql"])
    n = cur.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
    print("-- rows:", n)
con.close()
