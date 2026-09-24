import sqlite3, json
p = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
c = con.cursor()
for t in ("forecast_decisions","forecast_outcomes","forecast_evaluations","forecast_decision_days"):
    r = c.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()
    print("="*80)
    print(r["sql"] if r else f"{t}: MISSING")
print("="*80)
print("INDEXES:")
for r in c.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND tbl_name LIKE 'forecast%'"):
    print(" ", r["tbl_name"], r["name"], r["sql"])
print("="*80)
print("forecast_decision_days FULL DUMP:")
for r in c.execute("SELECT * FROM forecast_decision_days"):
    print(json.dumps(dict(r), ensure_ascii=False, default=str))
con.close()
