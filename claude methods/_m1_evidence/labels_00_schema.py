import sqlite3, json, sys
DB = r"D:\codex-A股交易\trading_local.sqlite3"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()
for t in ("forecast_decisions","forecast_outcomes","forecast_evaluations","forecast_decision_days"):
    print("="*80)
    print("TABLE", t)
    r = cur.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()
    print(r["sql"] if r else "MISSING")
    print("-- columns --")
    for c in cur.execute(f"PRAGMA table_info({t})").fetchall():
        print(f"  {c['cid']:>2} {c['name']:<30} {c['type']:<10} notnull={c['notnull']} dflt={c['dflt_value']!r} pk={c['pk']}")
    print("-- indexes --")
    for i in cur.execute(f"PRAGMA index_list({t})").fetchall():
        cols = [x["name"] for x in cur.execute(f"PRAGMA index_info({i['name']})").fetchall()]
        print(f"  {i['name']} unique={i['unique']} origin={i['origin']} cols={cols}")
    print("-- count --", cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
con.close()
