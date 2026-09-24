import sqlite3, json
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for name, path in (("market_history", MH), ("trading_local", TL)):
    c = ro(path)
    print("="*90)
    print("DB:", name)
    rows = c.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
    print("tables/views:", len(rows))
    # any table whose name or columns hint at delist/instrument/listing
    for n,t in rows:
        cols = [r[1] for r in c.execute(f"PRAGMA table_info('{n}')").fetchall()]
        hit_name = any(k in n.lower() for k in ("instrument","symbol","listing","delist","security","stock","universe","catalog"))
        hit_col  = any(any(k in col.lower() for k in ("delist","list_date","listed","status","ipo")) for col in cols)
        if hit_name or hit_col:
            print(f"  [{t}] {n}  cols={cols}")
    c.close()
