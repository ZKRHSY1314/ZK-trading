import sqlite3, os, json
ROOT = r"D:\codex-A股交易"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

mh = ro(os.path.join(ROOT,"market_history.sqlite3")); mh.row_factory = sqlite3.Row
tl = ro(os.path.join(ROOT,"trading_local.sqlite3")); tl.row_factory = sqlite3.Row

print("### market_history.ingest_runs DDL")
print(mh.execute("SELECT sql FROM sqlite_master WHERE name='ingest_runs'").fetchone()[0])
rows = mh.execute("SELECT * FROM ingest_runs ORDER BY rowid").fetchall()
print(f"rows={len(rows)}")
print("cols:", rows[0].keys() if rows else None)
with open("backfill_ingest_runs_dump.json","w",encoding="utf-8") as f:
    json.dump([dict(r) for r in rows], f, ensure_ascii=False, indent=1, default=str)
for r in rows[:6]:
    d = dict(r)
    print(json.dumps({k:(str(v)[:220]) for k,v in d.items()}, ensure_ascii=False))
print("... last 3 ...")
for r in rows[-3:]:
    d = dict(r)
    print(json.dumps({k:(str(v)[:220]) for k,v in d.items()}, ensure_ascii=False))

for tbl, db in [("capital_flow_ingestion_runs", tl), ("full_market_feature_runs", tl), ("import_runs", tl)]:
    print("\n### trading_local." + tbl + " DDL")
    ddl = db.execute("SELECT sql FROM sqlite_master WHERE name=?", (tbl,)).fetchone()
    print(ddl[0] if ddl else "MISSING")
    rs = db.execute(f"SELECT * FROM {tbl} ORDER BY rowid").fetchall()
    print(f"rows={len(rs)}")
    with open(f"backfill_{tbl}_dump.json","w",encoding="utf-8") as f:
        json.dump([dict(r) for r in rs], f, ensure_ascii=False, indent=1, default=str)
    for r in rs[:4]:
        print(json.dumps({k:str(v)[:200] for k,v in dict(r).items()}, ensure_ascii=False))
    if len(rs) > 4:
        print("...")
        for r in rs[-2:]:
            print(json.dumps({k:str(v)[:200] for k,v in dict(r).items()}, ensure_ascii=False))
