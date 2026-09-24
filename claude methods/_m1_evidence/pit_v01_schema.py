import sqlite3, json
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for name, path in (("OPERATIONAL", OP), ("MARKET_HISTORY", MH)):
    c = ro(path)
    print("="*90)
    print(name, path)
    rows = c.execute("SELECT type,name FROM sqlite_master WHERE type IN ('table','view') ORDER BY type,name").fetchall()
    print("objects:", len(rows))
    for t,n in rows:
        print(f"  {t:5s} {n}")
    c.close()
