import sqlite3, json
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for name, path in (("market_history", MH), ("trading_local", TL)):
    c = ro(path)
    print("="*70)
    print(name)
    print("="*70)
    rows = c.execute("SELECT type,name,sql FROM sqlite_master WHERE type IN ('table','view')").fetchall()
    for t, n, sql in rows:
        low = n.lower()
        if any(k in low for k in ("universe","instrument","symbol","member","listing","delist","security","stock","calendar","board","sector","index")):
            print(f"--- [{t}] {n}")
            print(sql)
            print()
    print("ALL TABLE NAMES:", sorted(n for t,n,s in rows if t=='table'))
    c.close()
