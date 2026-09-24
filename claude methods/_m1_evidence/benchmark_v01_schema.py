import sqlite3, json, os
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p.replace(chr(92),'/')}?mode=ro", uri=True)

for label, p in (("trading_local", OP), ("market_history", MH)):
    c = ro(p)
    print("="*80)
    print(label)
    print("="*80)
    rows = c.execute("SELECT type,name,sql FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
    for t,n,s in rows:
        low = n.lower()
        if any(k in low for k in ("backtest","trade","equity","fill","simul","order","position","bench","index","result","run")):
            try:
                cnt = c.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
            except Exception as e:
                cnt = f"ERR {e}"
            print(f"\n--- {t} {n}  rows={cnt}")
            print(s)
    print("\n[ALL table names in %s]" % label)
    allt = [r[1] for r in rows if r[0]=='table']
    print(", ".join(allt))
    c.close()
