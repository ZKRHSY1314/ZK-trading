import sqlite3, json
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for label, path in (("market_history", MH), ("trading_local", TL)):
    c = ro(path)
    print("="*70)
    print(label)
    print("="*70)
    rows = c.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
    for n,t in rows:
        print(f"  {t:5s} {n}")
    print()
    # any table whose name hints at universe/instrument/listing/delist/symbol
    hints = [n for n,t in rows if any(k in n.lower() for k in ("instrument","universe","symbol","listing","delist","candidate","stock","security","member","pool","snapshot","calendar"))]
    for n in hints:
        try:
            ddl = c.execute("SELECT sql FROM sqlite_master WHERE name=?", (n,)).fetchone()[0]
            cnt = c.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
            print(f"--- {label}.{n}  rows={cnt}")
            print(ddl)
            print()
        except Exception as e:
            print(f"--- {label}.{n} ERR {e}")
    c.close()
