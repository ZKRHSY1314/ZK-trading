import sqlite3, json, sys, io
sys.stdout.reconfigure(encoding='utf-8')

OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for label, path in (("trading_local", OP), ("market_history", MH)):
    c = ro(path)
    print("="*100)
    print("DB:", label, path)
    rows = c.execute("SELECT type,name,sql FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
    names = [r[1] for r in rows]
    print("OBJECT COUNT:", len(names))
    interest = [n for n in names if any(k in n.lower() for k in
        ("bench","index","global","backtest","fundamental","profile","instrument","calendar","session","trading_day","universe"))]
    print("INTERESTING:", interest)
    for t, n, s in rows:
        if n in interest:
            try:
                cnt = c.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
            except Exception as e:
                cnt = f"ERR {e}"
            print("-"*90)
            print(f"[{label}.{n}]  type={t}  rows={cnt}")
            print(s)
    c.close()
