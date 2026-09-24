import sqlite3, json
OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIST = r"D:/codex-A股交易/market_history.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for label, path in (("HIST", HIST), ("OPS", OPS)):
    c = ro(path)
    print("="*80)
    print(label, path)
    print("="*80)
    rows = c.execute(
        "SELECT type,name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
    ).fetchall()
    names = [r[1] for r in rows]
    # anything universe / instrument / listing / delist / calendar related
    hits = [n for n in names if any(k in n.lower() for k in
            ("univ","instr","list","delist","symbol","member","secur","calend","ticker","stock","snapshot"))]
    print("candidate tables:", hits)
    print("total tables:", len(names))
    for n in hits:
        print("-"*70)
        ddl = c.execute("SELECT sql FROM sqlite_master WHERE name=?", (n,)).fetchone()[0]
        print(ddl)
        try:
            cnt = c.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
            print("rows:", cnt)
        except Exception as e:
            print("count err", e)
    c.close()
