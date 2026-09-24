import sqlite3, json
db = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
for t in ("forecast_evaluations","forecast_decisions","forecast_outcomes","forecast_decision_days"):
    r = con.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()
    print("="*90); print(t); print(r["sql"] if r else "MISSING")
print("="*90)
print("indexes:")
for r in con.execute("SELECT name,tbl_name,sql FROM sqlite_master WHERE type='index' AND tbl_name LIKE 'forecast%'"):
    print(" ", r["tbl_name"], r["name"], r["sql"])
con.close()
